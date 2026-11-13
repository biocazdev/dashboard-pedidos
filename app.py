"""
app.py
------
Dashboard de Faturamento de Pedidos (Protheus) em Streamlit.
Identidade visual: Biocaz (logo.png + paleta oficial da marca).
Organizado em abas para a area comercial: Visao Geral, Rankings & Mix,
Metas de Vendas e Alertas Comerciais - com filtros dinamicos na lateral
(Vendedor / Cliente / Grupo de produto) e comparativo com o periodo anterior.

Rode com:  streamlit run app.py
(ou de forma mais simples, no Windows, execute run_dashboard.bat)
"""

from __future__ import annotations

import datetime as dt
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import db
import kpis

# ---------------------------------------------------------------------------
# Identidade visual Biocaz
# ---------------------------------------------------------------------------
# Cores oficiais da marca (fornecidas pelo cliente):
#   Pantone 7723 C -> #43AA8A (verde-agua / teal)
#   Pantone 2746 C -> #0C1B7D (azul-marinho)
#   Pantone Black C -> #000000 (preto)
BIOCAZ = {
    "teal": "#43AA8A",
    "teal_escuro": "#2F7A63",
    "teal_claro": "#8FD4BC",
    "navy": "#0C1B7D",
    "navy_claro": "#3A4FC9",
    "preto": "#000000",
}

# Paleta categorica derivada da marca (ordem fixa, usada em graficos com
# varias categorias — ex.: grupos de produto)
CATEGORICA = [
    BIOCAZ["navy"],
    BIOCAZ["teal"],
    BIOCAZ["teal_escuro"],
    BIOCAZ["navy_claro"],
    "#6B7280",   # cinza neutro
    BIOCAZ["preto"],
]

# Cores de "atencao" usadas em graficos de alerta (saldo em aberto, bloqueios,
# clientes em queda) - restritas as cores oficiais da marca (nunca um tom
# fora da paleta Biocaz).
STATUS = {"warning": BIOCAZ["navy_claro"], "inativo": "#8A93A8"}
ABC_CORES = {"A": BIOCAZ["teal"], "B": BIOCAZ["navy"], "C": "#8A93A8"}

INK_PRIMARIO = BIOCAZ["navy"]
INK_SECUNDARIO = "#4B5160"
INK_MUTED = "#8A93A8"
GRID = "#E3E7EF"
SURFACE = "#FFFFFF"
PAGE = "#F5F7FA"

LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")

PLOTLY_LAYOUT = dict(
    paper_bgcolor=SURFACE,
    plot_bgcolor=SURFACE,
    font=dict(family="system-ui, -apple-system, 'Segoe UI', sans-serif", color=INK_SECUNDARIO, size=13),
    margin=dict(l=10, r=10, t=30, b=10),
    hoverlabel=dict(bgcolor=SURFACE, font_color=INK_PRIMARIO, bordercolor=GRID),
)


def moeda(v: float | None) -> str:
    if v is None or pd.isna(v):
        return "-"
    return f"R$ {v:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")


def numero(v: float | None) -> str:
    if v is None or pd.isna(v):
        return "-"
    return f"{v:,.0f}".replace(",", ".")


def percentual(v: float | None) -> str:
    if v is None or pd.isna(v):
        return "-"
    return f"{v:.1f}%"


def delta_pct(v: float | None) -> str | None:
    """Formata a variacao percentual para uso no 'delta' do st.metric."""
    if v is None or pd.isna(v):
        return None
    return f"{v:+.1f}% vs período anterior"


FONTE_MONO = "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, 'Courier New', monospace"


def estiliza_eixos(fig: go.Figure):
    fig.update_xaxes(showgrid=False, showline=True, linecolor=GRID, tickfont=dict(color=INK_MUTED))
    fig.update_yaxes(
        showgrid=True, gridcolor=GRID, zeroline=False,
        tickfont=dict(color=INK_MUTED, family=FONTE_MONO),
        automargin=True,
    )
    return fig


def aplica_rotulos_esquerda(fig: go.Figure, categorias, tamanho_max: int = 26) -> go.Figure:
    """Deixa os rotulos do eixo Y (cliente, produto, vendedor etc.) todos
    comecando na mesma posicao horizontal, sem o efeito "escada" do
    alinhamento nativo do Plotly (que ancora o rotulo pela ponta DIREITA,
    coladinha no eixo - nomes curtos ficam recuados, nomes longos avancam
    pra esquerda).

    Importante: os dados da barra (y=...) continuam com o nome ORIGINAL e
    completo - isso mantem corretos o hover, o clique-pra-filtrar e o
    agrupamento de barras. So o TEXTO EXIBIDO no eixo e trocado (via
    tickvals/ticktext), por duas razoes: (1) nomes reais do Protheus
    (cliente, descricao de produto) podem ter 40, 60+ caracteres - sem
    truncar, a margem do grafico tentaria caber o nome inteiro e
    espremeria as barras numa faixa minuscula; (2) como o eixo usa fonte
    monoespacada (estiliza_eixos), completar cada nome truncado com
    espacos ate o mesmo tamanho faz o INICIO de todo mundo cair
    exatamente na mesma posicao - a fonte normal (variavel) nao garante
    isso, so a monoespacada."""
    originais = [str(c) for c in categorias]
    truncados = [
        c if len(c) <= tamanho_max else c[: tamanho_max - 1].rstrip() + "…"
        for c in originais
    ]
    maior = max((len(c) for c in truncados), default=0)
    exibidos = [c.ljust(maior) for c in truncados]
    fig.update_yaxes(tickmode="array", tickvals=originais, ticktext=exibidos)
    return fig


def opcoes_unicas(*series: pd.Series) -> list[str]:
    """Junta series de dataframes diferentes e devolve valores unicos,
    nao vazios, ordenados - usado para montar as opcoes dos filtros."""
    partes = [s for s in series if s is not None and not s.empty]
    if not partes:
        return []
    todos = pd.concat(partes, ignore_index=True).dropna()
    todos = todos[todos.astype(str).str.strip() != ""]
    return sorted(todos.unique().tolist())


def _extrai_categoria_clicada(evento, eixo: str = "y") -> str | None:
    """Le o retorno de st.plotly_chart(..., on_select='rerun') e devolve a
    categoria (eixo 'x' ou 'y') do primeiro ponto clicado, ou None se nada
    estiver selecionado."""
    if not evento:
        return None
    pontos = (evento.get("selection") or {}).get("points") or []
    if not pontos:
        return None
    valor = pontos[0].get(eixo)
    # Os rotulos do eixo Y vem com espacos extras no final (truque de
    # rotulos_eixo_esquerda para alinhar o texto a esquerda) - remove antes
    # de usar como valor de filtro, senao nao bate com as opcoes do multiselect.
    return valor.strip() if isinstance(valor, str) else valor


def grafico_clicavel(fig: go.Figure, chave: str, altura: int, eixo: str, chave_filtro: str):
    """Renderiza o grafico e faz o clique numa barra funcionar como atalho
    de filtro: clicar adiciona aquele valor ao filtro correspondente na
    lateral; clicar de novo remove. So reage quando a selecao MUDA em
    relacao ao ultimo estado conhecido, para nao reprocessar o mesmo clique
    a cada rerun (o Plotly mantem a barra "selecionada" entre reruns)."""
    evento = st.plotly_chart(
        fig, use_container_width=True, on_select="rerun", selection_mode="points", key=chave,
    )
    categoria = _extrai_categoria_clicada(evento, eixo)
    marcador = f"_ultimo_{chave}"
    if categoria == st.session_state.get(marcador):
        return
    st.session_state[marcador] = categoria
    if not categoria:
        return
    # Nao da para alterar st.session_state[chave_filtro] aqui: o widget do
    # filtro (na sidebar) ja foi instanciado mais cedo nesta mesma execucao,
    # e o Streamlit proibe isso. Em vez disso, guarda a intencao e processa
    # no INICIO da proxima execucao, antes dos widgets serem criados.
    st.session_state["_pendente_toggle_filtro"] = (chave_filtro, categoria)
    st.rerun()


# Aplica um clique pendente de algum grafico (guardado por grafico_clicavel
# acima) ANTES de qualquer widget de filtro ser criado - o Streamlit proibe
# alterar st.session_state de uma chave de widget depois que ele ja foi
# instanciado na mesma execucao, entao isso precisa acontecer bem cedo.
_pendente = st.session_state.pop("_pendente_toggle_filtro", None)
if _pendente:
    _chave_filtro_pend, _categoria_pend = _pendente
    _atual_pend = st.session_state.get(_chave_filtro_pend, [])
    if _categoria_pend in _atual_pend:
        st.session_state[_chave_filtro_pend] = [v for v in _atual_pend if v != _categoria_pend]
    else:
        st.session_state[_chave_filtro_pend] = _atual_pend + [_categoria_pend]


# ---------------------------------------------------------------------------
# Config de pagina
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Faturamento de Pedidos - Biocaz",
    page_icon=LOGO_PATH if os.path.exists(LOGO_PATH) else "📦",
    layout="wide",
)

st.markdown(
    f"""
    <style>
        .stApp {{ background-color: {PAGE}; }}

        /* Reduz o espaco em branco padrao do Streamlit no topo da pagina,
        pra o cabecalho comecar mais colado no topo. */
        .block-container {{ padding-top: 1.5rem; }}

        /* Cabecalho com identidade Biocaz */
        .biocaz-header {{
            display: flex;
            align-items: center;
            gap: 18px;
            background-color: {SURFACE};
            border-radius: 12px;
            padding: 18px 24px;
            border: 1px solid rgba(12,27,125,0.08);
            border-bottom: 4px solid {BIOCAZ['teal']};
            margin-bottom: 16px;
        }}
        .biocaz-header h1 {{
            color: {INK_PRIMARIO};
            font-size: 1.5rem;
            font-weight: 700;
            margin: 0;
        }}
        .biocaz-header p {{
            color: {INK_SECUNDARIO};
            margin: 2px 0 0 0;
            font-size: 0.92rem;
        }}

        h2, h3 {{ color: {INK_PRIMARIO} !important; }}

        div[data-testid="stMetric"] {{
            background-color: {SURFACE};
            border: 1px solid rgba(12,27,125,0.08);
            border-left: 4px solid {BIOCAZ['teal']};
            border-radius: 10px;
            padding: 14px 16px 10px 16px;
            text-align: right;
        }}
        div[data-testid="stMetricLabel"] {{
            color: {INK_SECUNDARIO};
            justify-content: flex-end;
            text-align: right;
        }}
        div[data-testid="stMetricValue"] {{
            color: {INK_PRIMARIO};
            font-size: 1.45rem;
            white-space: normal;
            overflow-wrap: break-word;
            line-height: 1.25;
            justify-content: flex-end;
            text-align: right;
        }}
        div[data-testid="stMetricDelta"] {{ justify-content: flex-end; }}

        section[data-testid="stSidebar"] {{
            background-color: {SURFACE};
            border-right: 1px solid rgba(12,27,125,0.08);
        }}

        button[data-baseweb="tab"] {{
            font-weight: 600;
        }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar - periodo
# ---------------------------------------------------------------------------
with st.sidebar:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=160)

    st.header("Período")
    hoje = dt.date.today()
    padrao_inicio = (pd.Timestamp(hoje) - pd.DateOffset(months=3)).date()

    periodo = st.date_input(
        "Emissão",
        value=(padrao_inicio, hoje),
        max_value=hoje,
        format="DD/MM/YYYY",
    )
    if isinstance(periodo, tuple) and len(periodo) == 2:
        date_start, date_end = periodo
    else:
        date_start, date_end = padrao_inicio, hoje

if date_start > date_end:
    st.error("A data inicial não pode ser depois da data final.")
    st.stop()


@st.cache_data(show_spinner="Carregando dados do Protheus...", ttl=300)
def carregar_dados(inicio: dt.date, fim: dt.date) -> dict:
    dataset = db.fetch_dataset(inicio, fim)
    return {k: v for k, v in dataset.items()}


try:
    dataset_raw = carregar_dados(date_start, date_end)
except Exception as exc:  # conexao/consulta falhou
    st.error(
        "Não foi possível consultar o Protheus. Verifique o .env "
        "(servidor, banco, usuário, senha, driver ODBC e sufixo das tabelas).\n\n"
        f"Detalhe técnico: {exc}"
    )
    if "driver" in str(exc).lower() or "data source name not found" in str(exc).lower():
        try:
            import pyodbc
            drivers_sql = [d for d in pyodbc.drivers() if "sql server" in d.lower()]
            if drivers_sql:
                st.warning(
                    "O driver configurado em DB_DRIVER no .env não foi encontrado nesta máquina. "
                    "Drivers ODBC de SQL Server instalados aqui:\n\n"
                    + "\n".join(f"- {d}" for d in drivers_sql)
                    + "\n\nCopie um desses nomes EXATAMENTE (sem aspas) para DB_DRIVER no .env e reinicie o dashboard."
                )
            else:
                st.warning(
                    "Nenhum driver ODBC de SQL Server foi encontrado nesta máquina. "
                    "Instale o 'Microsoft ODBC Driver 17 (ou 18) for SQL Server' e reinicie o dashboard."
                )
        except Exception:
            pass
    st.stop()

pedidos_raw = dataset_raw["pedidos"]
itens_pedido_raw = dataset_raw["itens_pedido"]
notas_raw = dataset_raw["notas"]
notas_periodo_raw = dataset_raw["notas_dos_pedidos_periodo"]

# Período anterior (mesma duração), para o comparativo - carregado de forma
# resiliente: se falhar, o dashboard segue funcionando sem o comparativo.
ant_inicio, ant_fim = kpis.periodo_anterior(date_start, date_end)
try:
    dataset_ant_raw = carregar_dados(ant_inicio, ant_fim)
    comparativo_disponivel = True
except Exception:
    dataset_ant_raw = {
        "pedidos": pd.DataFrame(columns=pedidos_raw.columns),
        "itens_pedido": pd.DataFrame(columns=itens_pedido_raw.columns),
        "notas": pd.DataFrame(columns=notas_raw.columns),
        "notas_dos_pedidos_periodo": pd.DataFrame(columns=notas_periodo_raw.columns),
    }
    comparativo_disponivel = False

# ---------------------------------------------------------------------------
# Sidebar - filtros dinamicos (derivados dos dados do periodo selecionado)
# ---------------------------------------------------------------------------
vendedor_opts = opcoes_unicas(pedidos_raw.get("vendedor"), notas_raw.get("vendedor"))
cliente_opts = opcoes_unicas(pedidos_raw.get("cliente"), notas_raw.get("cliente"))
grupo_opts = opcoes_unicas(notas_raw.get("grupo_produto"), itens_pedido_raw.get("grupo_produto"))
regiao_opts = opcoes_unicas(pedidos_raw.get("regiao"), notas_raw.get("regiao"))
regional_opts = opcoes_unicas(pedidos_raw.get("regional"), notas_raw.get("regional"))

# Sanitiza selecoes guardadas em sessao (ex: vindas de clique num grafico)
# contra as opcoes validas do periodo atual, para o widget nao quebrar caso
# algum valor tenha saido da lista (ex: apos trocar o periodo).
for _chave, _opts in (
    ("filtro_vendedor", vendedor_opts), ("filtro_cliente", cliente_opts),
    ("filtro_grupo", grupo_opts), ("filtro_regiao", regiao_opts), ("filtro_regional", regional_opts),
):
    st.session_state[_chave] = [v for v in st.session_state.get(_chave, []) if v in _opts]

with st.sidebar:
    st.divider()
    st.header("Filtros")
    st.caption("Dica: clicar numa barra dos gráficos também filtra (clique de novo para remover).")
    vendedor_sel = st.multiselect("Vendedor", vendedor_opts, placeholder="Todos", key="filtro_vendedor")
    cliente_sel = st.multiselect("Cliente", cliente_opts, placeholder="Todos", key="filtro_cliente")
    grupo_sel = st.multiselect("Grupo de produto", grupo_opts, placeholder="Todos", key="filtro_grupo")
    with st.expander("Mais filtros"):
        regiao_sel = st.multiselect("Região", regiao_opts, placeholder="Todos", key="filtro_regiao")
        regional_sel = st.multiselect("Regional", regional_opts, placeholder="Todos", key="filtro_regional")

    st.divider()
    if db.is_demo_mode():
        st.warning("Modo DEMO ativo — dados fictícios.")
    else:
        st.success("Conectado ao Protheus")
    with st.expander("Detalhes da conexão"):
        resumo = db.connection_summary()
        for chave, valor in resumo.items():
            st.caption(f"**{chave}:** {valor}")

    st.divider()
    # on_click roda ANTES do script recarregar os dados nesta mesma execucao
    # (mesmo o botao estando aqui embaixo, depois do carregar_dados() visual-
    # mente mais acima no codigo) - assim o cache ja sai limpo a tempo.
    st.button("🔄 Atualizar dados", use_container_width=True, on_click=st.cache_data.clear)

dataset_f = kpis.aplicar_filtros(
    pedidos_raw, itens_pedido_raw, notas_raw, notas_periodo_raw,
    vendedores=vendedor_sel, clientes=cliente_sel, grupos_produto=grupo_sel,
    regioes=regiao_sel, regionais=regional_sel,
)
pedidos = dataset_f["pedidos"]
itens_pedido = dataset_f["itens_pedido"]
notas = dataset_f["notas"]
notas_periodo = dataset_f["notas_dos_pedidos_periodo"]

dataset_ant_f = kpis.aplicar_filtros(
    dataset_ant_raw["pedidos"], dataset_ant_raw["itens_pedido"],
    dataset_ant_raw["notas"], dataset_ant_raw["notas_dos_pedidos_periodo"],
    vendedores=vendedor_sel, clientes=cliente_sel, grupos_produto=grupo_sel,
    regioes=regiao_sel, regionais=regional_sel,
)
notas_ant = dataset_ant_f["notas"]

# ---------------------------------------------------------------------------
# Cabecalho
# ---------------------------------------------------------------------------
resumo_conexao = db.connection_summary()
st.markdown(
    f"""
    <div class="biocaz-header">
        <div>
            <h1>📦 Dashboard de Faturamento de Pedidos</h1>
            <p>Período: {date_start.strftime('%d/%m/%Y')} a {date_end.strftime('%d/%m/%Y')} ·
               Filial {resumo_conexao['filial']}</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if pedidos_raw.empty and notas_raw.empty:
    st.info("Nenhum pedido ou nota fiscal encontrado para o período selecionado.")
    st.stop()

if pedidos.empty and notas.empty:
    st.warning("Nenhum resultado para os filtros selecionados. Ajuste os filtros na lateral.")
    st.stop()

aba_geral, aba_rankings, aba_metas, aba_alertas = st.tabs(
    ["📊 Visão Geral", "🏆 Rankings & Mix", "🎯 Metas de Vendas", "⚠️ Alertas Comerciais"]
)

# ===========================================================================
# ABA: Visao Geral
# ===========================================================================
with aba_geral:
    fat_total = kpis.faturamento_total(notas)
    qtd_notas = kpis.total_notas(notas)
    qtd_pedidos = kpis.total_pedidos(pedidos)
    ticket_nf = kpis.ticket_medio_nf(notas)

    if comparativo_disponivel:
        fat_total_ant = kpis.faturamento_total(notas_ant)
        qtd_notas_ant = kpis.total_notas(notas_ant)
        qtd_pedidos_ant = kpis.total_pedidos(dataset_ant_f["pedidos"])
        ticket_nf_ant = kpis.ticket_medio_nf(notas_ant)
    else:
        fat_total_ant = qtd_notas_ant = qtd_pedidos_ant = ticket_nf_ant = None

    linha1 = st.columns(4)
    linha1[0].metric(
        "Faturamento total (líquido)", moeda(fat_total),
        delta=delta_pct(kpis.variacao_pct(fat_total, fat_total_ant)) if comparativo_disponivel else None,
        help="Soma do valor dos itens das notas fiscais emitidas no período (sem impostos do cabeçalho).",
    )
    linha1[1].metric(
        "Notas fiscais emitidas", numero(qtd_notas),
        delta=delta_pct(kpis.variacao_pct(qtd_notas, qtd_notas_ant)) if comparativo_disponivel else None,
        help="Quantidade de notas fiscais de saída (faturamento) emitidas no período.",
    )
    linha1[2].metric(
        "Pedidos no período", numero(qtd_pedidos),
        delta=delta_pct(kpis.variacao_pct(qtd_pedidos, qtd_pedidos_ant)) if comparativo_disponivel else None,
        help="Quantidade de pedidos de venda com emissão dentro do período selecionado.",
    )
    linha1[3].metric(
        "Ticket médio por NF", moeda(ticket_nf),
        delta=delta_pct(kpis.variacao_pct(ticket_nf, ticket_nf_ant)) if comparativo_disponivel else None,
        help="Faturamento total dividido pela quantidade de notas fiscais emitidas no período.",
    )

    if not comparativo_disponivel:
        st.caption("Comparativo com o período anterior indisponível neste momento (falha ao carregar os dados de referência).")

    with st.expander("Ver mais indicadores"):
        fat_bruto = kpis.faturamento_bruto_cabecalho(notas)
        ticket_pedido = kpis.ticket_medio_pedido(itens_pedido, pedidos)
        conversao = kpis.taxa_conversao(itens_pedido, notas_periodo)
        prazo = kpis.prazo_medio_faturamento(pedidos, notas_periodo)

        linha2 = st.columns(4)
        linha2[0].metric(
            "Faturamento total (c/ impostos)", moeda(fat_bruto),
            help="Valor de cabeçalho das notas fiscais (inclui impostos), contado uma única vez por nota.",
        )
        linha2[1].metric(
            "Ticket médio por pedido", moeda(ticket_pedido),
            help="Valor total dos itens de pedido dividido pela quantidade de pedidos do período.",
        )
        linha2[2].metric(
            "Taxa de conversão pedido → NF", percentual(conversao),
            help="Percentual do valor pedido no período que já foi faturado (em qualquer data).",
        )
        linha2[3].metric(
            "Prazo médio de faturamento",
            f"{prazo['media']:.1f} dias" if prazo["media"] is not None else "-",
            help="Dias entre a emissão do pedido e a emissão da nota fiscal correspondente.",
        )

    st.divider()
    st.subheader("Evolução mensal do faturamento")
    evo = kpis.evolucao_mensal(notas)
    if evo.empty:
        st.caption("Sem dados de faturamento no período para exibir a evolução.")
    else:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=evo["mes"], y=evo["faturamento"],
            marker_color=BIOCAZ["teal"],
            marker_line_width=0,
            hovertemplate="%{x|%b/%Y}<br>Faturamento: R$ %{y:,.2f}<extra></extra>",
        ))
        fig.update_layout(**PLOTLY_LAYOUT, height=320, showlegend=False)
        estiliza_eixos(fig)
        fig.update_xaxes(type="date", dtick="M1", tickformat="%b/%Y")
        st.plotly_chart(fig, use_container_width=True)

# ===========================================================================
# ABA: Rankings & Mix
# ===========================================================================
with aba_rankings:
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Top 10 clientes por faturamento")
        top_cli = kpis.faturamento_por_cliente(notas, top_n=10)
        if top_cli.empty:
            st.caption("Sem dados no período.")
        else:
            top_cli = top_cli.sort_values("faturamento")
            fig = go.Figure(go.Bar(
                x=top_cli["faturamento"], y=top_cli["cliente"], orientation="h",
                marker_color=BIOCAZ["navy"], marker_line_width=0,
                hovertemplate="%{y}<br>R$ %{x:,.2f}<extra></extra>",
            ))
            fig.update_layout(**PLOTLY_LAYOUT, height=380, showlegend=False)
            estiliza_eixos(fig)
            aplica_rotulos_esquerda(fig, top_cli["cliente"])
            grafico_clicavel(fig, "chart_top_clientes", 380, "y", "filtro_cliente")

    with col_b:
        st.subheader("Top 10 produtos por faturamento")
        top_prod = kpis.faturamento_por_produto(notas, top_n=10)
        if top_prod.empty:
            st.caption("Sem dados no período.")
        else:
            top_prod = top_prod.sort_values("faturamento")
            fig = go.Figure(go.Bar(
                x=top_prod["faturamento"], y=top_prod["produto"], orientation="h",
                marker_color=BIOCAZ["teal_escuro"], marker_line_width=0,
                hovertemplate="%{y}<br>R$ %{x:,.2f}<extra></extra>",
            ))
            fig.update_layout(**PLOTLY_LAYOUT, height=380, showlegend=False)
            estiliza_eixos(fig)
            aplica_rotulos_esquerda(fig, top_prod["produto"])
            st.plotly_chart(fig, use_container_width=True)

    col_c, col_d = st.columns(2)

    with col_c:
        st.subheader("Faturamento por vendedor")
        top_vend = kpis.faturamento_por_vendedor(notas, top_n=10)
        if top_vend.empty:
            st.caption("Sem dados no período.")
        else:
            top_vend = top_vend.sort_values("faturamento")
            fig = go.Figure(go.Bar(
                x=top_vend["faturamento"], y=top_vend["vendedor"], orientation="h",
                marker_color=BIOCAZ["navy_claro"], marker_line_width=0,
                hovertemplate="%{y}<br>R$ %{x:,.2f}<extra></extra>",
            ))
            fig.update_layout(**PLOTLY_LAYOUT, height=340, showlegend=False)
            estiliza_eixos(fig)
            aplica_rotulos_esquerda(fig, top_vend["vendedor"])
            grafico_clicavel(fig, "chart_vendedor", 340, "y", "filtro_vendedor")

    with col_d:
        st.subheader("Faturamento por grupo de produto")
        grp = kpis.faturamento_por_grupo(notas)
        if grp.empty:
            st.caption("Sem dados no período.")
        else:
            cores = [CATEGORICA[i % len(CATEGORICA)] for i in range(len(grp))]
            fig = go.Figure(go.Bar(
                x=grp["grupo_produto"].astype(str), y=grp["faturamento"],
                marker_color=cores, marker_line_width=0,
                hovertemplate="%{x}<br>R$ %{y:,.2f}<extra></extra>",
            ))
            fig.update_layout(**PLOTLY_LAYOUT, height=340, showlegend=False)
            # Os codigos de grupo sao numericos (1701, 1702...) e, se nao
            # forcarmos o eixo X como categoria, o Plotly entende que e um
            # eixo numerico continuo e espalha as barras num intervalo
            # (ex: 1700 a 1800) em vez de uma barra por codigo.
            fig.update_xaxes(type="category")
            estiliza_eixos(fig)
            grafico_clicavel(fig, "chart_grupo", 340, "x", "filtro_grupo")

    col_e, col_f = st.columns(2)

    with col_e:
        st.subheader("Faturamento por região")
        reg = kpis.faturamento_por_regiao(notas)
        if reg.empty:
            st.caption("Sem dados de região no período.")
        else:
            reg = reg.sort_values("faturamento")
            fig = go.Figure(go.Bar(
                x=reg["faturamento"], y=reg["regiao"], orientation="h",
                marker_color=BIOCAZ["teal"], marker_line_width=0,
                hovertemplate="%{y}<br>R$ %{x:,.2f}<extra></extra>",
            ))
            fig.update_layout(**PLOTLY_LAYOUT, height=max(260, 40 * len(reg)), showlegend=False)
            estiliza_eixos(fig)
            aplica_rotulos_esquerda(fig, reg["regiao"])
            grafico_clicavel(fig, "chart_regiao", max(260, 40 * len(reg)), "y", "filtro_regiao")

    with col_f:
        st.subheader("Faturamento por regional")
        regl = kpis.faturamento_por_regional(notas)
        if regl.empty:
            st.caption("Sem dados de regional no período.")
        else:
            regl = regl.sort_values("faturamento")
            fig = go.Figure(go.Bar(
                x=regl["faturamento"], y=regl["regional"], orientation="h",
                marker_color=BIOCAZ["navy"], marker_line_width=0,
                hovertemplate="%{y}<br>R$ %{x:,.2f}<extra></extra>",
            ))
            fig.update_layout(**PLOTLY_LAYOUT, height=max(260, 40 * len(regl)), showlegend=False)
            estiliza_eixos(fig)
            aplica_rotulos_esquerda(fig, regl["regional"])
            grafico_clicavel(fig, "chart_regional", max(260, 40 * len(regl)), "y", "filtro_regional")

    with st.expander("Curva ABC de clientes"):
        abc = kpis.curva_abc_clientes(notas)
        if abc.empty:
            st.caption("Sem dados no período.")
        else:
            top_abc = abc.head(20).sort_values("faturamento")
            cores_abc = [ABC_CORES[c] for c in top_abc["classe"]]
            fig = go.Figure(go.Bar(
                x=top_abc["faturamento"], y=top_abc["cliente"], orientation="h",
                marker_color=cores_abc, marker_line_width=0,
                showlegend=False,
                hovertemplate="%{y}<br>R$ %{x:,.2f}<extra></extra>",
            ))
            for classe, cor in ABC_CORES.items():
                fig.add_trace(go.Bar(x=[None], y=[None], marker_color=cor, name=f"Classe {classe}"))
            fig.update_layout(**PLOTLY_LAYOUT, height=460, legend=dict(orientation="h", y=1.08, x=0))
            estiliza_eixos(fig)
            aplica_rotulos_esquerda(fig, top_abc["cliente"])
            grafico_clicavel(fig, "chart_abc", 460, "y", "filtro_cliente")

            resumo_abc = abc.groupby("classe").agg(
                clientes=("cliente", "count"), faturamento=("faturamento", "sum")
            ).reindex(["A", "B", "C"]).fillna(0)
            resumo_abc["faturamento"] = resumo_abc["faturamento"].apply(moeda)
            st.caption("Classe A = até 80% do faturamento acumulado · B = até 95% · C = restante")
            st.dataframe(resumo_abc, use_container_width=True)

    st.divider()
    st.subheader("Mix de produtos por vendedor / cliente")
    st.caption("Escolha um vendedor e/ou cliente para ver quais produtos ele mais vende/compra.")
    col_f1, col_f2 = st.columns(2)
    vendedor_mix = col_f1.selectbox("Vendedor", ["Todos"] + vendedor_opts, key="mix_vendedor")
    cliente_mix = col_f2.selectbox("Cliente", ["Todos"] + cliente_opts, key="mix_cliente")

    mix = kpis.faturamento_por_produto_filtrado(notas, vendedor=vendedor_mix, cliente=cliente_mix, top_n=10)
    if mix.empty:
        st.caption("Sem dados para essa combinação de filtros.")
    else:
        mix = mix.sort_values("faturamento")
        fig = go.Figure(go.Bar(
            x=mix["faturamento"], y=mix["produto"], orientation="h",
            marker_color=BIOCAZ["teal_claro"], marker_line_width=0,
            hovertemplate="%{y}<br>R$ %{x:,.2f}<extra></extra>",
        ))
        fig.update_layout(**PLOTLY_LAYOUT, height=380, showlegend=False)
        estiliza_eixos(fig)
        aplica_rotulos_esquerda(fig, mix["produto"])
        st.plotly_chart(fig, use_container_width=True)

# ===========================================================================
# ABA: Metas de Vendas
# ===========================================================================
with aba_metas:
    metas = db.fetch_metas()
    if metas.empty:
        st.info(
            "A meta de vendas por vendedor ainda não está configurada para este ambiente. "
            "Assim que a tabela/campo de meta no Protheus for confirmado, esta seção passa a "
            "comparar automaticamente o realizado com a meta de cada vendedor."
        )
    else:
        n_dias = (date_end - date_start).days + 1
        n_meses = max(n_dias / 30.44, 0.1)

        realizado = kpis.faturamento_por_vendedor(notas, top_n=9999)
        comparativo_metas = metas.merge(realizado, on="vendedor", how="outer").fillna(0.0)
        comparativo_metas["meta_periodo"] = comparativo_metas["meta_mensal"] * n_meses
        comparativo_metas["atingido_pct"] = comparativo_metas.apply(
            lambda r: (r["faturamento"] / r["meta_periodo"] * 100) if r["meta_periodo"] else None,
            axis=1,
        )
        comparativo_metas = comparativo_metas.sort_values("faturamento", ascending=False)

        st.caption(
            f"Meta mensal cadastrada, proporcional aos {n_dias} dia(s) do período selecionado "
            f"(fator ≈ {n_meses:.2f}x a meta mensal)."
        )

        plot_df = comparativo_metas.sort_values("faturamento")
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=plot_df["faturamento"], y=plot_df["vendedor"], orientation="h",
            name="Realizado", marker_color=BIOCAZ["teal"], marker_line_width=0,
            hovertemplate="%{y}<br>Realizado: R$ %{x:,.2f}<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            x=plot_df["meta_periodo"], y=plot_df["vendedor"], orientation="h",
            name="Meta", marker_color=BIOCAZ["navy_claro"], marker_line_width=0,
            hovertemplate="%{y}<br>Meta: R$ %{x:,.2f}<extra></extra>",
        ))
        fig.update_layout(
            **PLOTLY_LAYOUT, height=max(320, 40 * len(plot_df)), barmode="group",
            legend=dict(orientation="h", y=1.08, x=0),
        )
        estiliza_eixos(fig)
        aplica_rotulos_esquerda(fig, plot_df["vendedor"])
        st.plotly_chart(fig, use_container_width=True)

        tabela = comparativo_metas[["vendedor", "faturamento", "meta_periodo", "atingido_pct"]].copy()
        tabela.columns = ["Vendedor", "Realizado", "Meta (período)", "Atingido (%)"]
        tabela["Realizado"] = tabela["Realizado"].apply(moeda)
        tabela["Meta (período)"] = tabela["Meta (período)"].apply(moeda)
        tabela["Atingido (%)"] = tabela["Atingido (%)"].apply(percentual)
        st.dataframe(tabela, use_container_width=True, hide_index=True)

# ===========================================================================
# ABA: Alertas Comerciais
# ===========================================================================
with aba_alertas:
    st.subheader("Clientes inativos ou em queda")
    st.caption("Compradores do período anterior que deixaram de comprar (Inativo) ou tiveram queda forte de faturamento (Em queda ≤ -30%) no período atual.")

    if not comparativo_disponivel:
        st.caption("Indisponível neste momento (falha ao carregar os dados do período anterior).")
    else:
        inativos = kpis.clientes_inativos_ou_queda(notas, notas_ant)
        if inativos.empty:
            st.success("Nenhum cliente inativo ou em queda forte identificado no período.")
        else:
            tabela_inativos = inativos.copy()
            tabela_inativos["faturamento_anterior"] = tabela_inativos["faturamento_anterior"].apply(moeda)
            tabela_inativos["faturamento_atual"] = tabela_inativos["faturamento_atual"].apply(moeda)
            tabela_inativos["variacao_pct"] = tabela_inativos["variacao_pct"].apply(percentual)
            tabela_inativos.columns = ["Cliente", "Faturamento período anterior", "Faturamento período atual", "Variação", "Status"]
            st.dataframe(tabela_inativos, use_container_width=True, hide_index=True)

    st.divider()
    bl = kpis.backlog(itens_pedido)
    bloq = kpis.pedidos_bloqueados(itens_pedido)

    linha_alerta = st.columns(4)
    linha_alerta[0].metric(
        "Saldo a faturar (backlog)", moeda(bl["valor"]),
        help=f"Valor de pedidos ainda não entregues/faturados — {bl['qtd_pedidos']} pedido(s) com saldo em aberto.",
    )
    linha_alerta[1].metric(
        "Itens em backlog", numero(bl["qtd_itens"]),
        help="Quantidade de itens de pedido que ainda têm saldo pendente de entrega/faturamento.",
    )
    linha_alerta[2].metric(
        "Valor bloqueado", moeda(bloq["valor"]),
        help=f"Valor de itens travados por bloqueio comercial (ex: crédito, estoque) — {bloq['qtd_pedidos']} pedido(s) afetado(s).",
    )
    linha_alerta[3].metric(
        "Itens bloqueados", numero(bloq["qtd_itens"]),
        help="Quantidade de itens de pedido com algum tipo de bloqueio (ex: crédito, estoque) impedindo o faturamento.",
    )

    st.subheader("Maiores saldos a faturar por cliente")
    saldo_cli = kpis.saldo_a_faturar_por_cliente(itens_pedido, pedidos, top_n=10)
    if saldo_cli.empty:
        st.caption("Sem saldo em aberto no período.")
    else:
        saldo_cli = saldo_cli.sort_values("saldo")
        fig = go.Figure(go.Bar(
            x=saldo_cli["saldo"], y=saldo_cli["cliente"], orientation="h",
            marker_color=STATUS["warning"], marker_line_width=0,
            hovertemplate="%{y}<br>R$ %{x:,.2f}<extra></extra>",
        ))
        fig.update_layout(**PLOTLY_LAYOUT, height=360, showlegend=False)
        estiliza_eixos(fig)
        aplica_rotulos_esquerda(fig, saldo_cli["cliente"])
        grafico_clicavel(fig, "chart_saldo_cliente", 360, "y", "filtro_cliente")
