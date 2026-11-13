# Dashboard de Faturamento de Pedidos — Protheus

Dashboard local em Python/Streamlit para acompanhar o faturamento de pedidos
de venda, usando as tabelas do dicionário de dados do ERP Protheus (SC5, SC6,
SD2, SF2, SA1, SB1, SA3).

## Pasta de destino

Estes arquivos foram pensados para rodar em `C:\LDO\Pedidos`. Extraia/copie
todo o conteúdo do zip para essa pasta antes de executar.

## Como rodar (Windows)

1. Copie todos os arquivos para `C:\LDO\Pedidos`.
2. Dê duplo clique em **`run_dashboard.bat`**.
   - Na primeira execução ele cria um ambiente virtual Python (`venv`),
     instala as dependências e cria o arquivo `.env` a partir do
     `.env.example` (com `DEMO_MODE=True`).
   - O navegador abre sozinho com o dashboard, já usando **dados fictícios**
     para você testar a interface e os gráficos sem precisar de acesso ao
     banco agora.
3. Requisito: **Python 3.10+** instalado e no PATH
   (https://www.python.org/downloads/, marque "Add python.exe to PATH").

## Como conectar no Protheus de verdade

1. Abra o arquivo `.env` (criado na primeira execução) em um editor de texto.
2. Ajuste:
   - `DEMO_MODE=False`
   - `DB_SERVER`, `DB_PORT`, `DB_DATABASE`, `DB_USER`, `DB_PASSWORD`: dados de
     conexão do SQL Server do Protheus.
   - `DB_DRIVER`: nome do driver ODBC instalado na máquina (ex.:
     `ODBC Driver 17 for SQL Server`). Confira em "Fontes de Dados ODBC
     (64 bits)" no Windows, aba Drivers.
   - `PROTHEUS_TABLE_SUFFIX`: sufixo físico das tabelas do dicionário no seu
     ambiente (ex.: `SC5010` → sufixo `010`). Confirme com o time de
     TI/Basis do Protheus.
   - `FILIAL`: código da filial a ser considerada nas consultas.
3. Rode `run_dashboard.bat` novamente (ou `streamlit run app.py` se o venv
   já estiver ativo).

Você vai precisar do driver ODBC do SQL Server instalado na máquina
(Microsoft ODBC Driver 17 ou 18 for SQL Server) e de um usuário com permissão
de leitura nas tabelas do dicionário de dados.

## Tabelas Protheus utilizadas

| Tabela | Conteúdo |
|---|---|
| SC5 | Cabeçalho do pedido de venda |
| SC6 | Itens do pedido de venda (quantidade pedida/entregue, valor) |
| SF2 | Cabeçalho da nota fiscal de saída (faturamento) |
| SD2 | Itens da nota fiscal de saída |
| SA1 | Clientes |
| SB1 | Produtos |
| SA3 | Vendedores |

As consultas SQL completas estão comentadas em `queries.sql`, para revisão
do time de TI/Basis antes de ligar o modo produção/teste.

## KPIs incluídos

Além dos indicadores básicos de faturamento (total, nº de notas, nº de
pedidos, ticket médio), o dashboard traz indicadores adicionais mais úteis
para gestão comercial:

- **Faturamento total líquido (soma dos itens de NF)** e **faturamento com
  impostos (valor de cabeçalho da NF)** — separados para não confundir valor
  de mercadoria com valor total faturado.
- **Ticket médio por NF** e **ticket médio por pedido**.
- **Taxa de conversão pedido → nota fiscal**: quanto do valor pedido no
  período já foi efetivamente faturado.
- **Prazo médio de faturamento**: dias entre a emissão do pedido e a emissão
  da nota fiscal correspondente.
- **Saldo a faturar (backlog)**: valor de itens pedidos e ainda não
  totalmente entregues/faturados, com contagem de pedidos afetados.
- **Valor e itens bloqueados**: pedidos com item bloqueado (crédito,
  estoque etc.), que merecem atenção antes de virar faturamento.
- **Evolução mensal do faturamento**.
- **Top clientes, produtos e vendedores por faturamento**.
- **Faturamento por grupo de produto**.
- **Curva ABC de clientes** (classes A/B/C por concentração de faturamento).
- **Maiores saldos a faturar por cliente** (para priorizar cobrança de
  entrega/faturamento).

## Estrutura dos arquivos

```
C:\LDO\Pedidos\
├── app.py                 -> dashboard Streamlit (interface e gráficos)
├── db.py                  -> conexão com o Protheus (ou dados fictícios)
├── kpis.py                -> cálculo dos indicadores
├── mock_data.py           -> gerador de dados fictícios (modo demo)
├── queries.sql            -> cópia comentada das consultas SQL usadas
├── requirements.txt       -> dependências Python
├── .env.example           -> modelo de configuração
├── .env                   -> sua configuração (criado na 1ª execução)
├── .streamlit/config.toml -> tema visual do Streamlit
└── run_dashboard.bat      -> instala e roda o dashboard
```

## Observações

- Datas do Protheus (`C5_EMISSAO`, `F2_EMISSAO`) normalmente são gravadas
  como texto `AAAAMMDD`; o `db.py` já trata essa conversão.
- Todas as consultas filtram `D_E_L_E_T_ = ''`, obrigatório no dicionário de
  dados do Protheus para ignorar registros logicamente deletados.
- O usuário de banco usado no `.env` só precisa de permissão de **leitura**
  (SELECT) nas tabelas listadas acima.
- Este é um dashboard local para testes — como conversamos, ele considera
  uma **filial única** (definida em `FILIAL` no `.env`). Se depois você
  quiser evoluir para múltiplas filiais com seletor na tela, é só pedir.
