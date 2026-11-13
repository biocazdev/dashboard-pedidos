"""
db.py
-----
Camada de acesso a dados. Le o .env para decidir entre:
  - DEMO_MODE=True  -> dados ficticios (mock_data.py)
  - DEMO_MODE=False -> consulta real no SQL Server do Protheus (tabelas do
                        dicionario de dados SC5/SC6/SD2/SF2/SA1/SB1/SA3)

As duas rotas devolvem os MESMOS nomes de coluna, para que kpis.py e app.py
funcionem identicamente nos dois modos. Ver queries.sql para o detalhe/
comentario de cada consulta usada aqui.
"""

from __future__ import annotations

import datetime as dt
import os

import pandas as pd
from dotenv import load_dotenv

import mock_data

load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "sim", "yes", "y", "s")


DEMO_MODE = _env_bool("DEMO_MODE", True)
TABLE_SUFFIX = os.getenv("PROTHEUS_TABLE_SUFFIX", "010").strip()
FILIAL = os.getenv("FILIAL", "01").strip()


def _tbl(prefix: str) -> str:
    """Monta o nome fisico da tabela do dicionario Protheus, ex: SC5 -> SC5010."""
    return f"{prefix}{TABLE_SUFFIX}"


def is_demo_mode() -> bool:
    return DEMO_MODE


def connection_summary() -> dict:
    """Resumo (sem senha) da configuracao atual, para exibir na sidebar."""
    return {
        "modo": "DEMO (dados ficticios)" if DEMO_MODE else "PRODUCAO",
        "servidor": os.getenv("DB_SERVER", "-"),
        "banco": os.getenv("DB_DATABASE", "-"),
        "sufixo_tabelas": TABLE_SUFFIX,
        "filial": FILIAL,
    }


def _get_connection():
    import pyodbc  # import tardio: so exige o driver instalado quando for usar de fato

    driver = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
    server = os.getenv("DB_SERVER", "localhost")
    port = os.getenv("DB_PORT", "1433")
    database = os.getenv("DB_DATABASE", "")
    user = os.getenv("DB_USER", "")
    password = os.getenv("DB_PASSWORD", "")

    conn_str = (
        f"DRIVER={{{driver}}};SERVER={server},{port};DATABASE={database};"
        f"UID={user};PWD={password};TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str, timeout=15)


def _query(sql: str, params: list) -> pd.DataFrame:
    conn = _get_connection()
    try:
        return pd.read_sql(sql, conn, params=params)
    finally:
        conn.close()


def _yyyymmdd(d: dt.date) -> str:
    # Campos de data no Protheus (ex: C5_EMISSAO) sao gravados como CHAR(8) "AAAAMMDD"
    return d.strftime("%Y%m%d")


def _fetch_pedidos(date_start: dt.date, date_end: dt.date) -> pd.DataFrame:
    sql = f"""
        SELECT
            C5.C5_NUM        AS pedido,
            C5.C5_EMISSAO    AS emissao_pedido,
            C5.C5_CLIENTE    AS cod_cliente,
            C5.C5_LOJACLI    AS loja_cliente,
            A1.A1_NOME       AS cliente,
            CC2.CC2_XREGIA   AS regiao,
            CC2.CC2_XREGIO   AS regional,
            C5.C5_VEND1      AS cod_vendedor,
            A3.A3_NOME       AS vendedor
        FROM {_tbl('SC5')} C5
        LEFT JOIN {_tbl('SA1')} A1
               ON A1.A1_COD = C5.C5_CLIENTE
              AND A1.A1_LOJA = C5.C5_LOJACLI
              AND A1.D_E_L_E_T_ = ''
        LEFT JOIN {_tbl('CC2')} CC2
               ON UPPER(RTRIM(CC2.CC2_MUN)) = UPPER(RTRIM(A1.A1_MUN))
              AND UPPER(RTRIM(CC2.CC2_EST)) = UPPER(RTRIM(A1.A1_EST))
              AND CC2.D_E_L_E_T_ = ''
        LEFT JOIN {_tbl('SA3')} A3
               ON A3.A3_COD = C5.C5_VEND1
              AND A3.D_E_L_E_T_ = ''
        WHERE C5.D_E_L_E_T_ = ''
          AND C5.C5_FILIAL = ?
          AND C5.C5_EMISSAO BETWEEN ? AND ?
    """
    df = _query(sql, [FILIAL, _yyyymmdd(date_start), _yyyymmdd(date_end)])
    if not df.empty:
        df["emissao_pedido"] = pd.to_datetime(df["emissao_pedido"], format="%Y%m%d", errors="coerce")
    return df


def _fetch_itens_pedido(date_start: dt.date, date_end: dt.date) -> pd.DataFrame:
    sql = f"""
        SELECT
            C6.C6_NUM     AS pedido,
            C6.C6_ITEM    AS item,
            C6.C6_PRODUTO AS cod_produto,
            B1.B1_DESC    AS produto,
            CASE
                WHEN NULLIF(LTRIM(RTRIM(BM.BM_DESC)), '') IS NOT NULL
                    THEN LTRIM(RTRIM(B1.B1_GRUPO)) + ' - ' + LTRIM(RTRIM(BM.BM_DESC))
                ELSE LTRIM(RTRIM(B1.B1_GRUPO))
            END AS grupo_produto,
            C6.C6_QTDVEN  AS qtd_pedida,
            C6.C6_QTDENT  AS qtd_entregue,
            C6.C6_PRCVEN  AS preco_unit,
            C6.C6_VALOR   AS valor_item,
            C6.C6_BLQ     AS bloqueio
        FROM {_tbl('SC6')} C6
        INNER JOIN {_tbl('SC5')} C5
               ON C5.C5_NUM = C6.C6_NUM
              AND C5.C5_FILIAL = C6.C6_FILIAL
              AND C5.D_E_L_E_T_ = ''
        LEFT JOIN {_tbl('SB1')} B1
               ON B1.B1_COD = C6.C6_PRODUTO
              AND B1.D_E_L_E_T_ = ''
        LEFT JOIN {_tbl('SBM')} BM
               ON BM.BM_GRUPO = B1.B1_GRUPO
              AND BM.D_E_L_E_T_ = ''
        WHERE C6.D_E_L_E_T_ = ''
          AND C6.C6_FILIAL = ?
          AND C5.C5_EMISSAO BETWEEN ? AND ?
    """
    return _query(sql, [FILIAL, _yyyymmdd(date_start), _yyyymmdd(date_end)])


def _fetch_notas(date_start: dt.date, date_end: dt.date, by_pedido_date: bool = False) -> pd.DataFrame:
    """Notas fiscais de saida (faturamento). Por padrao filtra pela data de
    emissao da propria NF; com by_pedido_date=True filtra pela data de emissao
    do PEDIDO de origem (usado para taxa de conversao / prazo de faturamento).
    Sempre traz o vendedor de origem (via SC5/SA3), para permitir "faturamento
    por vendedor" mesmo quando o pedido foi feito fora do periodo filtrado."""
    filtro_data = "C5.C5_EMISSAO BETWEEN ? AND ?" if by_pedido_date else "F2.F2_EMISSAO BETWEEN ? AND ?"

    sql = f"""
        SELECT
            F2.F2_DOC      AS nota,
            F2.F2_SERIE    AS serie,
            F2.F2_EMISSAO  AS emissao_nf,
            F2.F2_CLIENTE  AS cod_cliente,
            F2.F2_LOJA     AS loja_cliente,
            A1.A1_NOME     AS cliente,
            CC2.CC2_XREGIA AS regiao,
            CC2.CC2_XREGIO AS regional,
            C5.C5_VEND1    AS cod_vendedor,
            A3.A3_NOME     AS vendedor,
            F2.F2_VALFAT   AS valor_faturado,
            F2.F2_VALMERC  AS valor_mercadoria,
            D2.D2_PEDIDO   AS pedido,
            D2.D2_ITEMPV   AS item_pedido,
            D2.D2_COD      AS cod_produto,
            B1.B1_DESC     AS produto,
            CASE
                WHEN NULLIF(LTRIM(RTRIM(BM.BM_DESC)), '') IS NOT NULL
                    THEN LTRIM(RTRIM(B1.B1_GRUPO)) + ' - ' + LTRIM(RTRIM(BM.BM_DESC))
                ELSE LTRIM(RTRIM(B1.B1_GRUPO))
            END AS grupo_produto,
            D2.D2_QUANT    AS quantidade,
            D2.D2_TOTAL    AS valor_item
        FROM {_tbl('SF2')} F2
        INNER JOIN {_tbl('SD2')} D2
               ON D2.D2_DOC = F2.F2_DOC
              AND D2.D2_SERIE = F2.F2_SERIE
              AND D2.D2_CLIENTE = F2.F2_CLIENTE
              AND D2.D2_LOJA = F2.F2_LOJA
              AND D2.D2_FILIAL = F2.F2_FILIAL
              AND D2.D_E_L_E_T_ = ''
        LEFT JOIN {_tbl('SA1')} A1
               ON A1.A1_COD = F2.F2_CLIENTE
              AND A1.A1_LOJA = F2.F2_LOJA
              AND A1.D_E_L_E_T_ = ''
        LEFT JOIN {_tbl('CC2')} CC2
               ON UPPER(RTRIM(CC2.CC2_MUN)) = UPPER(RTRIM(A1.A1_MUN))
              AND UPPER(RTRIM(CC2.CC2_EST)) = UPPER(RTRIM(A1.A1_EST))
              AND CC2.D_E_L_E_T_ = ''
        LEFT JOIN {_tbl('SB1')} B1
               ON B1.B1_COD = D2.D2_COD
              AND B1.D_E_L_E_T_ = ''
        LEFT JOIN {_tbl('SBM')} BM
               ON BM.BM_GRUPO = B1.B1_GRUPO
              AND BM.D_E_L_E_T_ = ''
        LEFT JOIN {_tbl('SC5')} C5
               ON C5.C5_NUM = D2.D2_PEDIDO
              AND C5.C5_FILIAL = D2.D2_FILIAL
              AND C5.D_E_L_E_T_ = ''
        LEFT JOIN {_tbl('SA3')} A3
               ON A3.A3_COD = C5.C5_VEND1
              AND A3.D_E_L_E_T_ = ''
        WHERE F2.D_E_L_E_T_ = ''
          AND F2.F2_FILIAL = ?
          AND {filtro_data}
    """
    df = _query(sql, [FILIAL, _yyyymmdd(date_start), _yyyymmdd(date_end)])
    if not df.empty:
        df["emissao_nf"] = pd.to_datetime(df["emissao_nf"], format="%Y%m%d", errors="coerce")
    return df


def _fetch_from_protheus(date_start: dt.date, date_end: dt.date) -> dict:
    pedidos = _fetch_pedidos(date_start, date_end)
    itens_pedido = _fetch_itens_pedido(date_start, date_end)
    notas = _fetch_notas(date_start, date_end, by_pedido_date=False)
    notas_dos_pedidos_periodo = _fetch_notas(date_start, date_end, by_pedido_date=True)
    return {
        "pedidos": pedidos,
        "itens_pedido": itens_pedido,
        "notas": notas,
        "notas_dos_pedidos_periodo": notas_dos_pedidos_periodo,
    }


def fetch_dataset(date_start: dt.date, date_end: dt.date) -> dict:
    """Ponto unico de entrada usado pelo app.py. Devolve um dict com os
    DataFrames: pedidos, itens_pedido, notas, notas_dos_pedidos_periodo."""
    if DEMO_MODE:
        return mock_data.get_filtered_dataset(date_start, date_end)
    return _fetch_from_protheus(date_start, date_end)


def fetch_metas() -> pd.DataFrame:
    """Meta de vendas mensal por vendedor. Em DEMO_MODE devolve valores
    ficticios para ilustrar a secao. Em producao devolve vazio ate a tabela/
    campo real de meta no Protheus deste cliente ser confirmado (nao ha
    convencao padrao universal no dicionario - varia por customizacao)."""
    if DEMO_MODE:
        return mock_data.get_metas()
    return pd.DataFrame(columns=["vendedor", "meta_mensal"])
