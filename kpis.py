"""
kpis.py
-------
Funcoes puras de calculo dos indicadores do dashboard, a partir dos
DataFrames devolvidos por db.fetch_dataset(). Nao depende de Streamlit nem
de banco de dados: recebe DataFrames, devolve numeros/DataFrames prontos
para exibir ou plotar.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

BLOQUEIOS_VAZIOS = ("", " ", None, np.nan)


def _sem_bloqueio(serie: pd.Series) -> pd.Series:
    return serie.fillna("").astype(str).str.strip() == ""


# ---------------------------------------------------------------------------
# KPIs "cabecalho" (cards)
# ---------------------------------------------------------------------------

def faturamento_total(notas: pd.DataFrame) -> float:
    """Soma do valor dos ITENS de NF (D2_TOTAL) - evita duplicar o valor do
    cabecalho quando uma NF tem varios itens."""
    if notas.empty:
        return 0.0
    return float(notas["valor_item"].sum())


def faturamento_bruto_cabecalho(notas: pd.DataFrame) -> float:
    """Soma do valor de CABECALHO da NF (F2_VALFAT, com impostos), contado
    uma unica vez por nota (evita duplicar por causa dos itens)."""
    if notas.empty:
        return 0.0
    return float(notas.drop_duplicates(subset=["nota", "serie"])["valor_faturado"].sum())


def total_notas(notas: pd.DataFrame) -> int:
    if notas.empty:
        return 0
    return int(notas.drop_duplicates(subset=["nota", "serie"]).shape[0])


def total_pedidos(pedidos: pd.DataFrame) -> int:
    if pedidos.empty:
        return 0
    return int(pedidos["pedido"].nunique())


def valor_total_pedidos(itens_pedido: pd.DataFrame) -> float:
    if itens_pedido.empty:
        return 0.0
    return float(itens_pedido["valor_item"].sum())


def ticket_medio_nf(notas: pd.DataFrame) -> float:
    n = total_notas(notas)
    return faturamento_total(notas) / n if n else 0.0


def ticket_medio_pedido(itens_pedido: pd.DataFrame, pedidos: pd.DataFrame) -> float:
    n = total_pedidos(pedidos)
    return valor_total_pedidos(itens_pedido) / n if n else 0.0


def backlog(itens_pedido: pd.DataFrame) -> dict:
    """Saldo a faturar (pedidos ainda nao totalmente entregues/faturados)."""
    if itens_pedido.empty:
        return {"valor": 0.0, "qtd_itens": 0, "qtd_pedidos": 0}

    df = itens_pedido.copy()
    df["saldo_qtd"] = (df["qtd_pedida"] - df["qtd_entregue"]).clip(lower=0)
    df_aberto = df[df["saldo_qtd"] > 0]
    valor = float((df_aberto["saldo_qtd"] * df_aberto["preco_unit"]).sum())
    return {
        "valor": valor,
        "qtd_itens": int(df_aberto.shape[0]),
        "qtd_pedidos": int(df_aberto["pedido"].nunique()),
    }


def taxa_conversao(itens_pedido: pd.DataFrame, notas_dos_pedidos_periodo: pd.DataFrame) -> float:
    """% do valor pedido no periodo que ja foi faturado (em qualquer data)."""
    total_pedido = valor_total_pedidos(itens_pedido)
    if not total_pedido:
        return 0.0
    faturado = faturamento_total(notas_dos_pedidos_periodo)
    return min(faturado / total_pedido * 100, 100.0)


def prazo_medio_faturamento(pedidos: pd.DataFrame, notas_dos_pedidos_periodo: pd.DataFrame) -> dict:
    """Dias entre emissao do pedido e emissao da NF correspondente."""
    if pedidos.empty or notas_dos_pedidos_periodo.empty:
        return {"media": None, "mediana": None}

    merged = notas_dos_pedidos_periodo.drop_duplicates(subset=["nota", "serie", "pedido"]).merge(
        pedidos[["pedido", "emissao_pedido"]].drop_duplicates(subset=["pedido"]),
        on="pedido",
        how="inner",
    )
    if merged.empty:
        return {"media": None, "mediana": None}

    prazos = (merged["emissao_nf"] - merged["emissao_pedido"]).dt.days
    prazos = prazos[prazos >= 0]
    if prazos.empty:
        return {"media": None, "mediana": None}

    return {"media": float(prazos.mean()), "mediana": float(prazos.median())}


def pedidos_bloqueados(itens_pedido: pd.DataFrame) -> dict:
    if itens_pedido.empty:
        return {"valor": 0.0, "qtd_itens": 0, "qtd_pedidos": 0}

    df_bloq = itens_pedido[~_sem_bloqueio(itens_pedido["bloqueio"])]
    return {
        "valor": float(df_bloq["valor_item"].sum()),
        "qtd_itens": int(df_bloq.shape[0]),
        "qtd_pedidos": int(df_bloq["pedido"].nunique()) if not df_bloq.empty else 0,
    }


# ---------------------------------------------------------------------------
# Series/tabelas para graficos
# ---------------------------------------------------------------------------

def evolucao_mensal(notas: pd.DataFrame) -> pd.DataFrame:
    if notas.empty:
        return pd.DataFrame(columns=["mes", "faturamento"])
    df = notas.copy()
    df["mes"] = df["emissao_nf"].dt.to_period("M").dt.to_timestamp()
    out = df.groupby("mes", as_index=False)["valor_item"].sum().rename(columns={"valor_item": "faturamento"})
    return out.sort_values("mes")


def faturamento_por_vendedor(notas: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    if notas.empty:
        return pd.DataFrame(columns=["vendedor", "faturamento"])
    df = notas.copy()
    df["vendedor"] = df["vendedor"].fillna("Sem vendedor").replace("", "Sem vendedor")
    out = df.groupby("vendedor", as_index=False)["valor_item"].sum().rename(columns={"valor_item": "faturamento"})
    return out.sort_values("faturamento", ascending=False).head(top_n)


def faturamento_por_cliente(notas: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    if notas.empty:
        return pd.DataFrame(columns=["cliente", "faturamento"])
    out = notas.groupby("cliente", as_index=False)["valor_item"].sum().rename(columns={"valor_item": "faturamento"})
    return out.sort_values("faturamento", ascending=False).head(top_n)


def faturamento_por_produto(notas: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    if notas.empty:
        return pd.DataFrame(columns=["produto", "faturamento"])
    out = notas.groupby("produto", as_index=False)["valor_item"].sum().rename(columns={"valor_item": "faturamento"})
    return out.sort_values("faturamento", ascending=False).head(top_n)


def faturamento_por_grupo(notas: pd.DataFrame) -> pd.DataFrame:
    if notas.empty:
        return pd.DataFrame(columns=["grupo_produto", "faturamento"])
    out = notas.groupby("grupo_produto", as_index=False)["valor_item"].sum().rename(columns={"valor_item": "faturamento"})
    return out.sort_values("faturamento", ascending=False)


def faturamento_por_regiao(notas: pd.DataFrame) -> pd.DataFrame:
    """Faturamento agrupado pela Regiao do cliente (campo customizado
    CC2_XREGIA do municipio - ex: Sudeste, Sul, Nordeste)."""
    if notas.empty or "regiao" not in notas.columns:
        return pd.DataFrame(columns=["regiao", "faturamento"])
    df = notas.copy()
    df["regiao"] = df["regiao"].fillna("Sem região").replace("", "Sem região")
    out = df.groupby("regiao", as_index=False)["valor_item"].sum().rename(columns={"valor_item": "faturamento"})
    return out.sort_values("faturamento", ascending=False)


def faturamento_por_regional(notas: pd.DataFrame) -> pd.DataFrame:
    """Faturamento agrupado pela Regional do cliente (campo customizado
    CC2_XREGIO do municipio - area/equipe comercial dentro da regiao)."""
    if notas.empty or "regional" not in notas.columns:
        return pd.DataFrame(columns=["regional", "faturamento"])
    df = notas.copy()
    df["regional"] = df["regional"].fillna("Sem regional").replace("", "Sem regional")
    out = df.groupby("regional", as_index=False)["valor_item"].sum().rename(columns={"valor_item": "faturamento"})
    return out.sort_values("faturamento", ascending=False)


def curva_abc_clientes(notas: pd.DataFrame) -> pd.DataFrame:
    """Classificacao ABC de clientes por faturamento (A ate 80% acumulado,
    B ate 95%, C o restante)."""
    if notas.empty:
        return pd.DataFrame(columns=["cliente", "faturamento", "pct_acumulado", "classe"])

    out = notas.groupby("cliente", as_index=False)["valor_item"].sum().rename(columns={"valor_item": "faturamento"})
    out = out.sort_values("faturamento", ascending=False).reset_index(drop=True)
    total = out["faturamento"].sum()
    out["pct_acumulado"] = out["faturamento"].cumsum() / total * 100 if total else 0

    def classifica(pct):
        if pct <= 80:
            return "A"
        if pct <= 95:
            return "B"
        return "C"

    out["classe"] = out["pct_acumulado"].apply(classifica)
    return out


def saldo_a_faturar_por_cliente(itens_pedido: pd.DataFrame, pedidos: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    if itens_pedido.empty or pedidos.empty:
        return pd.DataFrame(columns=["cliente", "saldo"])

    df = itens_pedido.copy()
    df["saldo_qtd"] = (df["qtd_pedida"] - df["qtd_entregue"]).clip(lower=0)
    df = df[df["saldo_qtd"] > 0]
    df["saldo_valor"] = df["saldo_qtd"] * df["preco_unit"]

    merged = df.merge(pedidos[["pedido", "cliente"]].drop_duplicates(subset=["pedido"]), on="pedido", how="left")
    out = merged.groupby("cliente", as_index=False)["saldo_valor"].sum().rename(columns={"saldo_valor": "saldo"})
    return out.sort_values("saldo", ascending=False).head(top_n)


def faturamento_por_produto_filtrado(
    notas: pd.DataFrame,
    vendedor: str | None = None,
    cliente: str | None = None,
    top_n: int = 10,
) -> pd.DataFrame:
    """Mix de produtos, com recorte opcional por vendedor e/ou cliente -
    usado no drill-down comercial (quem vende/compra o que)."""
    if notas.empty:
        return pd.DataFrame(columns=["produto", "faturamento"])

    df = notas
    if vendedor and vendedor != "Todos":
        df = df[df["vendedor"] == vendedor]
    if cliente and cliente != "Todos":
        df = df[df["cliente"] == cliente]

    return faturamento_por_produto(df, top_n=top_n)


# ---------------------------------------------------------------------------
# Comparativo com periodo anterior / alertas comerciais
# ---------------------------------------------------------------------------

def periodo_anterior(date_start: dt.date, date_end: dt.date) -> tuple[dt.date, dt.date]:
    """Devolve o periodo imediatamente anterior, com a MESMA duracao em dias
    do periodo selecionado - base de comparacao para o "vs periodo anterior"."""
    dias = (date_end - date_start).days + 1
    anterior_fim = date_start - dt.timedelta(days=1)
    anterior_inicio = anterior_fim - dt.timedelta(days=dias - 1)
    return anterior_inicio, anterior_fim


def variacao_pct(atual: float, anterior: float) -> float | None:
    """% de variacao de 'atual' em relacao a 'anterior'. None quando nao da
    para calcular (sem base de comparacao)."""
    if not anterior:
        return None
    return (atual - anterior) / anterior * 100


def clientes_inativos_ou_queda(
    notas_atual: pd.DataFrame,
    notas_anterior: pd.DataFrame,
    limiar_queda_pct: float = -30.0,
) -> pd.DataFrame:
    """Clientes que compravam no periodo anterior e pararam de comprar
    (Inativo) ou tiveram queda forte de faturamento (Em queda) no periodo
    atual - lista de atencao para a equipe comercial, ordenada pelo maior
    valor de faturamento em risco."""
    cols = ["cliente", "faturamento_atual", "faturamento_anterior", "variacao_pct", "status"]
    if notas_anterior.empty:
        return pd.DataFrame(columns=cols)

    fat_atual = notas_atual.groupby("cliente")["valor_item"].sum() if not notas_atual.empty else pd.Series(dtype=float)
    fat_anterior = notas_anterior.groupby("cliente")["valor_item"].sum()

    df = pd.concat(
        [fat_anterior.rename("faturamento_anterior"), fat_atual.rename("faturamento_atual")],
        axis=1,
    ).fillna(0.0).reset_index().rename(columns={"index": "cliente"})

    df = df[df["faturamento_anterior"] > 0].copy()
    if df.empty:
        return pd.DataFrame(columns=cols)

    df["variacao_pct"] = (df["faturamento_atual"] - df["faturamento_anterior"]) / df["faturamento_anterior"] * 100
    df["valor_em_risco"] = (df["faturamento_anterior"] - df["faturamento_atual"]).clip(lower=0)

    def classifica(row):
        if row["faturamento_atual"] == 0:
            return "Inativo"
        if row["variacao_pct"] <= limiar_queda_pct:
            return "Em queda"
        return None

    df["status"] = df.apply(classifica, axis=1)
    df = df[df["status"].notna()]
    return df.sort_values("valor_em_risco", ascending=False)[
        ["cliente", "faturamento_anterior", "faturamento_atual", "variacao_pct", "status"]
    ]


def aplicar_filtros(
    pedidos: pd.DataFrame,
    itens_pedido: pd.DataFrame,
    notas: pd.DataFrame,
    notas_dos_pedidos_periodo: pd.DataFrame,
    vendedores: list[str] | None = None,
    clientes: list[str] | None = None,
    grupos_produto: list[str] | None = None,
    regioes: list[str] | None = None,
    regionais: list[str] | None = None,
) -> dict:
    """Aplica os filtros dinamicos da sidebar (vendedor/cliente/grupo de
    produto/regiao/regional) de forma consistente nos 4 dataframes do
    dataset. itens_pedido nao tem vendedor/cliente/regiao/regional
    diretamente, por isso e recortado pela lista de pedidos que sobrou apos
    esses filtros."""
    pedidos_f, itens_f, notas_f, notas_per_f = pedidos, itens_pedido, notas, notas_dos_pedidos_periodo
    recorta_itens = False

    if vendedores:
        recorta_itens = True
        if not pedidos_f.empty:
            pedidos_f = pedidos_f[pedidos_f["vendedor"].isin(vendedores)]
        if not notas_f.empty:
            notas_f = notas_f[notas_f["vendedor"].isin(vendedores)]
        if not notas_per_f.empty:
            notas_per_f = notas_per_f[notas_per_f["vendedor"].isin(vendedores)]

    if clientes:
        recorta_itens = True
        if not pedidos_f.empty:
            pedidos_f = pedidos_f[pedidos_f["cliente"].isin(clientes)]
        if not notas_f.empty:
            notas_f = notas_f[notas_f["cliente"].isin(clientes)]
        if not notas_per_f.empty:
            notas_per_f = notas_per_f[notas_per_f["cliente"].isin(clientes)]

    if regioes:
        recorta_itens = True
        if not pedidos_f.empty and "regiao" in pedidos_f.columns:
            pedidos_f = pedidos_f[pedidos_f["regiao"].isin(regioes)]
        if not notas_f.empty and "regiao" in notas_f.columns:
            notas_f = notas_f[notas_f["regiao"].isin(regioes)]
        if not notas_per_f.empty and "regiao" in notas_per_f.columns:
            notas_per_f = notas_per_f[notas_per_f["regiao"].isin(regioes)]

    if regionais:
        recorta_itens = True
        if not pedidos_f.empty and "regional" in pedidos_f.columns:
            pedidos_f = pedidos_f[pedidos_f["regional"].isin(regionais)]
        if not notas_f.empty and "regional" in notas_f.columns:
            notas_f = notas_f[notas_f["regional"].isin(regionais)]
        if not notas_per_f.empty and "regional" in notas_per_f.columns:
            notas_per_f = notas_per_f[notas_per_f["regional"].isin(regionais)]

    if grupos_produto:
        if not notas_f.empty:
            notas_f = notas_f[notas_f["grupo_produto"].isin(grupos_produto)]
        if not notas_per_f.empty:
            notas_per_f = notas_per_f[notas_per_f["grupo_produto"].isin(grupos_produto)]
        if not itens_f.empty:
            itens_f = itens_f[itens_f["grupo_produto"].isin(grupos_produto)]

    if recorta_itens and not itens_f.empty:
        itens_f = itens_f[itens_f["pedido"].isin(pedidos_f["pedido"])]

    return {
        "pedidos": pedidos_f,
        "itens_pedido": itens_f,
        "notas": notas_f,
        "notas_dos_pedidos_periodo": notas_per_f,
    }
