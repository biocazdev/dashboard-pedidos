"""
mock_data.py
------------
Gerador de dados FICTICIOS com a mesma "forma" (nomes de coluna) que o
db.py devolve ao consultar o Protheus de verdade. Usado quando DEMO_MODE=True
no .env, para permitir testar o dashboard sem precisar de conexao com o banco.

As colunas geradas aqui casam 1:1 com as colunas produzidas pelas consultas
reais em db.py (ver queries.sql), entao kpis.py funciona igual nos dois modos.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

_SEED = 42
_HISTORICO_MESES = 15  # quantos meses de historico sintetico gerar

_GRUPOS_PRODUTO = ["Eletronicos", "Ferragens", "Embalagens", "Quimicos", "Alimentos", "Servicos"]

_NOMES_CLIENTE_BASE = [
    "Comercial Alfa", "Industria Beta", "Distribuidora Gama", "Mercado Delta",
    "Atacado Epsilon", "Metalurgica Zeta", "Papelaria Eta", "Auto Pecas Theta",
    "Farma Iota", "Construtora Kappa", "Transportes Lambda", "Grafica Mu",
    "Supermercado Nu", "Eletrica Xi", "Moveis Omicron", "Textil Pi",
    "Quimica Rho", "Alimentos Sigma", "Plasticos Tau", "Ferramentas Upsilon",
    "Cosmeticos Phi", "Bebidas Chi", "Embalagens Psi", "Papelaria Omega",
    "Comercial Aurora", "Distribuidora Boreal", "Industria Cedro", "Mercado Dahlia",
    "Atacado Estrela", "Metalurgica Fenix", "Grupo Girassol", "Grupo Horizonte",
    "Rede Ipe", "Rede Jade", "Comercial Kiwi", "Distribuidora Lotus",
    "Industria Marfim", "Mercado Nectar", "Atacado Opala", "Grupo Prisma",
]

_NOMES_VENDEDOR = [
    "Ana Souza", "Bruno Lima", "Carla Nunes", "Diego Alves",
    "Elaine Costa", "Fabio Rocha", "Giovana Melo", "Hugo Pereira",
]

# Regiao (CC2_XREGIA) / Regional (CC2_XREGIO) - espelha a estrutura real
# encontrada no municipio (CC2) deste cliente: uma Regiao geografica ampla
# contendo varias Regionais (areas/equipes comerciais menores).
_REGIOES_REGIONAIS = [
    ("Sudeste", "SP Capital"),
    ("Sudeste", "SP Interior"),
    ("Sudeste", "MG/ES"),
    ("Sul", "PR/SC"),
    ("Sul", "RS"),
    ("Nordeste", "BA/SE"),
    ("Nordeste", "PE/PB/RN"),
    ("Centro-Oeste", "GO/DF/MT"),
    ("Norte", "TO/PA"),
]


def _rng() -> np.random.Generator:
    return np.random.default_rng(_SEED)


def _gerar_cadastros():
    rng = _rng()

    n_clientes = len(_NOMES_CLIENTE_BASE)
    regiao_idx = rng.integers(0, len(_REGIOES_REGIONAIS), size=n_clientes)
    clientes = pd.DataFrame({
        "cod_cliente": [f"{i:06d}" for i in range(1, n_clientes + 1)],
        "loja_cliente": ["01"] * n_clientes,
        "cliente": _NOMES_CLIENTE_BASE,
        "regiao": [_REGIOES_REGIONAIS[i][0] for i in regiao_idx],
        "regional": [_REGIOES_REGIONAIS[i][1] for i in regiao_idx],
    })

    vendedores = pd.DataFrame({
        "cod_vendedor": [f"{i:03d}" for i in range(1, len(_NOMES_VENDEDOR) + 1)],
        "vendedor": _NOMES_VENDEDOR,
    })

    n_produtos = 36
    grupos = rng.choice(_GRUPOS_PRODUTO, size=n_produtos)
    precos_base = rng.uniform(15, 1800, size=n_produtos).round(2)
    produtos = pd.DataFrame({
        "cod_produto": [f"P{i:05d}" for i in range(1, n_produtos + 1)],
        "produto": [f"Produto {i:03d} - {g}" for i, g in zip(range(1, n_produtos + 1), grupos)],
        "grupo_produto": grupos,
        "preco_base": precos_base,
    })

    return clientes, vendedores, produtos


def _gerar_pedidos_e_itens(clientes, vendedores, produtos, hoje: dt.date):
    rng = _rng()

    inicio_historico = (pd.Timestamp(hoje) - pd.DateOffset(months=_HISTORICO_MESES)).date()
    dias_historico = (hoje - inicio_historico).days

    # ~9 pedidos por dia util em media, com variacao
    n_pedidos = int(dias_historico * 0.9 * rng.uniform(0.85, 1.15))
    n_pedidos = max(n_pedidos, 150)

    pedido_ids = [f"{i:06d}" for i in range(1, n_pedidos + 1)]

    offsets = rng.integers(0, dias_historico + 1, size=n_pedidos)
    datas_pedido = [inicio_historico + dt.timedelta(days=int(o)) for o in offsets]

    cli_idx = rng.integers(0, len(clientes), size=n_pedidos)
    vend_idx = rng.integers(0, len(vendedores), size=n_pedidos)

    pedidos = pd.DataFrame({
        "pedido": pedido_ids,
        "emissao_pedido": pd.to_datetime(datas_pedido),
        "cod_cliente": clientes["cod_cliente"].values[cli_idx],
        "loja_cliente": clientes["loja_cliente"].values[cli_idx],
        "cliente": clientes["cliente"].values[cli_idx],
        "regiao": clientes["regiao"].values[cli_idx],
        "regional": clientes["regional"].values[cli_idx],
        "cod_vendedor": vendedores["cod_vendedor"].values[vend_idx],
        "vendedor": vendedores["vendedor"].values[vend_idx],
    })

    # ---- Itens do pedido (SC6) ----
    itens_rows = []
    for _, ped in pedidos.iterrows():
        n_itens = rng.integers(1, 5)
        prod_idx = rng.choice(len(produtos), size=n_itens, replace=False)
        idade_pedido_dias = (hoje - ped["emissao_pedido"].date()).days

        for it, pidx in enumerate(prod_idx, start=1):
            prod = produtos.iloc[pidx]
            qtd_pedida = int(rng.integers(1, 60))
            preco_unit = round(float(prod["preco_base"]) * rng.uniform(0.9, 1.1), 2)

            # Quanto mais antigo o pedido, maior a chance de ja ter sido
            # totalmente entregue/faturado. Pedidos recentes ficam com saldo em aberto.
            prob_completo = min(0.97, 0.15 + idade_pedido_dias / 45)
            if rng.random() < prob_completo:
                qtd_entregue = qtd_pedida
            elif rng.random() < 0.6:
                qtd_entregue = int(qtd_pedida * rng.uniform(0.2, 0.85))
            else:
                qtd_entregue = 0

            # pequena fatia de itens bloqueados (credito, estoque etc.)
            bloqueio = ""
            if rng.random() < 0.04:
                bloqueio = rng.choice(["CR", "ES"])  # credito / estoque

            itens_rows.append({
                "pedido": ped["pedido"],
                "item": f"{it:02d}",
                "cod_produto": prod["cod_produto"],
                "produto": prod["produto"],
                "grupo_produto": prod["grupo_produto"],
                "qtd_pedida": qtd_pedida,
                "qtd_entregue": qtd_entregue,
                "preco_unit": preco_unit,
                "valor_item": round(qtd_pedida * preco_unit, 2),
                "bloqueio": bloqueio,
            })

    itens_pedido = pd.DataFrame(itens_rows)
    return pedidos, itens_pedido


def _gerar_notas_fiscais(pedidos, itens_pedido, hoje: dt.date):
    rng = _rng()

    notas_rows = []
    nota_num = 1
    for pedido_id, grupo in itens_pedido.groupby("pedido"):
        ped = pedidos.loc[pedidos["pedido"] == pedido_id].iloc[0]
        entregues = grupo[grupo["qtd_entregue"] > 0]
        if entregues.empty:
            continue

        # Prazo de faturamento: normalmente poucos dias apos o pedido,
        # com uma cauda mais longa em alguns casos.
        atraso_dias = int(max(0, rng.normal(loc=6, scale=4)))
        emissao_nf = ped["emissao_pedido"] + pd.Timedelta(days=atraso_dias)
        if emissao_nf.date() > hoje:
            continue

        nota_id = f"{nota_num:06d}"
        serie = "1"
        nota_num += 1

        valor_mercadoria = float((entregues["qtd_entregue"] * entregues["preco_unit"]).sum())
        # cabecalho da NF inclui impostos (ICMS/IPI simplificado) sobre a mercadoria
        valor_faturado = round(valor_mercadoria * rng.uniform(1.05, 1.18), 2)

        for _, item in entregues.iterrows():
            valor_item_nf = round(item["qtd_entregue"] * item["preco_unit"], 2)
            notas_rows.append({
                "nota": nota_id,
                "serie": serie,
                "emissao_nf": emissao_nf,
                "cod_cliente": ped["cod_cliente"],
                "loja_cliente": ped["loja_cliente"],
                "cliente": ped["cliente"],
                "regiao": ped["regiao"],
                "regional": ped["regional"],
                "cod_vendedor": ped["cod_vendedor"],
                "vendedor": ped["vendedor"],
                "valor_faturado": valor_faturado,
                "valor_mercadoria": round(valor_mercadoria, 2),
                "pedido": pedido_id,
                "item_pedido": item["item"],
                "cod_produto": item["cod_produto"],
                "produto": item["produto"],
                "grupo_produto": item["grupo_produto"],
                "quantidade": item["qtd_entregue"],
                "valor_item": valor_item_nf,
            })

    notas = pd.DataFrame(notas_rows)
    if not notas.empty:
        notas["emissao_nf"] = pd.to_datetime(notas["emissao_nf"])
    return notas


def _generate_full(hoje: dt.date):
    clientes, vendedores, produtos = _gerar_cadastros()
    pedidos, itens_pedido = _gerar_pedidos_e_itens(clientes, vendedores, produtos, hoje)
    notas = _gerar_notas_fiscais(pedidos, itens_pedido, hoje)
    return pedidos, itens_pedido, notas


def get_filtered_dataset(date_start: dt.date, date_end: dt.date) -> dict:
    """Gera o dataset ficticio completo e filtra pelo periodo pedido,
    imitando o comportamento das consultas reais em db.py."""
    hoje = dt.date.today()
    pedidos, itens_pedido, notas = _generate_full(hoje)

    mask_pedidos = (pedidos["emissao_pedido"].dt.date >= date_start) & (
        pedidos["emissao_pedido"].dt.date <= date_end
    )
    pedidos_f = pedidos.loc[mask_pedidos].reset_index(drop=True)
    itens_pedido_f = itens_pedido[itens_pedido["pedido"].isin(pedidos_f["pedido"])].reset_index(drop=True)

    if not notas.empty:
        mask_notas = (notas["emissao_nf"].dt.date >= date_start) & (notas["emissao_nf"].dt.date <= date_end)
        notas_f = notas.loc[mask_notas].reset_index(drop=True)
    else:
        notas_f = notas

    # notas ligadas aos pedidos do periodo, independente da data de emissao da NF
    # (usado para calcular taxa de conversao e prazo medio de faturamento)
    notas_dos_pedidos_periodo = notas[notas["pedido"].isin(pedidos_f["pedido"])].reset_index(drop=True) if not notas.empty else notas

    return {
        "pedidos": pedidos_f,
        "itens_pedido": itens_pedido_f,
        "notas": notas_f,
        "notas_dos_pedidos_periodo": notas_dos_pedidos_periodo,
    }


def get_metas() -> pd.DataFrame:
    """Meta de vendas MENSAL ficticia por vendedor, so para demonstrar a
    secao de metas no modo demo. Em producao isso vem do Protheus assim que
    a tabela/campo real de meta for confirmado."""
    rng = _rng()
    metas = (rng.uniform(90_000, 260_000, size=len(_NOMES_VENDEDOR))).round(-3)
    return pd.DataFrame({"vendedor": _NOMES_VENDEDOR, "meta_mensal": metas})
