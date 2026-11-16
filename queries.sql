-- =========================================================================
-- queries.sql
-- Copia de referencia das consultas usadas por db.py contra o dicionario
-- de dados do Protheus (SQL Server). Uteis para validar/ajustar com o time
-- de TI/Basis antes de tirar o dashboard do modo demo (DEMO_MODE=False).
--
-- Troque:
--   {SUF}    -> sufixo fisico das tabelas no seu ambiente (ex: 010)
--   {FILIAL} -> codigo da filial (ex: '01')
--   {DE}/{ATE} -> datas no formato AAAAMMDD (C5_EMISSAO/F2_EMISSAO sao CHAR(8))
--
-- NOTA: os nomes de alguns campos podem variar entre versoes/customizacoes
-- do Protheus. Nesta instalacao (confirmado via INFORMATION_SCHEMA.COLUMNS),
-- o campo de produto na SD2 e D2_COD (nao D2_PRODUTO), e a SF2 nao possui
-- campo F2_CANCEL - o filtro de nota cancelada/deletada fica so por conta
-- de D_E_L_E_T_ = ''.
-- =========================================================================

-- 1) Pedidos de venda (cabecalho) no periodo
SELECT
    C5.C5_NUM        AS pedido,
    C5.C5_EMISSAO    AS emissao_pedido,
    C5.C5_CLIENTE    AS cod_cliente,
    C5.C5_LOJACLI    AS loja_cliente,
    A1.A1_NOME       AS cliente,
    CC2.CC2_XREGIA   AS regiao,          -- confirmado via SX3: CC2_XREGIA = "Regiao"
    CC2.CC2_XREGIO   AS regional,        -- confirmado via SX3: CC2_XREGIO = "Regional"
    C5.C5_VEND1      AS cod_vendedor,
    A3.A3_NOME       AS vendedor
FROM SC5{SUF} C5
LEFT JOIN SA1{SUF} A1 ON A1.A1_COD = C5.C5_CLIENTE AND A1.A1_LOJA = C5.C5_LOJACLI AND A1.D_E_L_E_T_ = ''
LEFT JOIN CC2{SUF} CC2 ON UPPER(RTRIM(CC2.CC2_MUN)) = UPPER(RTRIM(A1.A1_MUN))
                      AND UPPER(RTRIM(CC2.CC2_EST)) = UPPER(RTRIM(A1.A1_EST))
                      AND CC2.D_E_L_E_T_ = ''
LEFT JOIN SA3{SUF} A3 ON A3.A3_COD = C5.C5_VEND1 AND A3.D_E_L_E_T_ = ''
WHERE C5.D_E_L_E_T_ = ''
  AND C5.C5_FILIAL = '{FILIAL}'
  AND C5.C5_EMISSAO BETWEEN '{DE}' AND '{ATE}';


-- 2) Itens do pedido de venda (para saldo a faturar / backlog)
--    grupo_produto ja vem formatado como "codigo - descricao" (ex: "1701 -
--    BIOD. NEMATICIDA - PA REVENDA"), via JOIN com SBM (confirmado nesta
--    instalacao: tabela SBM, campos BM_GRUPO/BM_DESC). Se a descricao nao
--    for encontrada, cai pro codigo sozinho (CASE com fallback).
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
FROM SC6{SUF} C6
INNER JOIN SC5{SUF} C5 ON C5.C5_NUM = C6.C6_NUM AND C5.C5_FILIAL = C6.C6_FILIAL AND C5.D_E_L_E_T_ = ''
LEFT JOIN SB1{SUF} B1 ON B1.B1_COD = C6.C6_PRODUTO AND B1.D_E_L_E_T_ = ''
LEFT JOIN SBM{SUF} BM ON BM.BM_GRUPO = B1.B1_GRUPO AND BM.D_E_L_E_T_ = ''
WHERE C6.D_E_L_E_T_ = ''
  AND C6.C6_FILIAL = '{FILIAL}'
  AND C5.C5_EMISSAO BETWEEN '{DE}' AND '{ATE}';


-- 3) Notas fiscais de saida = faturamento (cabecalho SF2 + itens SD2)
--    Use F2_EMISSAO BETWEEN ... para faturamento por data de emissao da NF,
--    ou troque pelo JOIN com SC5 e filtre por C5_EMISSAO para pegar o
--    faturamento originado de pedidos de um periodo especifico.
--    O campo de produto na SD2 e D2_COD (confirmado nesta instalacao via
--    INFORMATION_SCHEMA.COLUMNS) - outras instalacoes podem variar.
--    tipo_registro: classificacao FATURAMENTO/OUTRAS SAIDAS igual ao Objeto
--    de Negocio Smart View (TLPP) do cliente - ver nota "RESOLVIDO" abaixo.
SELECT
    F2.F2_DOC      AS nota,
    F2.F2_SERIE    AS serie,
    F2.F2_EMISSAO  AS emissao_nf,
    F2.F2_CLIENTE  AS cod_cliente,
    F2.F2_LOJA     AS loja_cliente,
    A1.A1_NOME     AS cliente,
    CC2.CC2_XREGIA AS regiao,
    CC2.CC2_XREGIO AS regional,
    F2.F2_VALFAT   AS valor_faturado,     -- valor do CABECALHO da NF (nao confiavel nesta instalacao - ver nota)
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
    D2.D2_TOTAL    AS valor_item,         -- valor do ITEM da NF (usar para somar sem duplicar)
    CASE
        WHEN F4.F4_DUPLIC = 'S' AND D2.D2_TIPO NOT IN ('D', 'B')
            THEN 'FATURAMENTO'
        ELSE 'OUTRAS SAIDAS'
    END AS tipo_registro
FROM SF2{SUF} F2
INNER JOIN SD2{SUF} D2
       ON D2.D2_DOC = F2.F2_DOC
      AND D2.D2_SERIE = F2.F2_SERIE
      AND D2.D2_CLIENTE = F2.F2_CLIENTE
      AND D2.D2_LOJA = F2.F2_LOJA
      AND D2.D2_FILIAL = F2.F2_FILIAL
      AND D2.D_E_L_E_T_ = ''
LEFT JOIN SA1{SUF} A1 ON A1.A1_COD = F2.F2_CLIENTE AND A1.A1_LOJA = F2.F2_LOJA AND A1.D_E_L_E_T_ = ''
LEFT JOIN CC2{SUF} CC2 ON UPPER(RTRIM(CC2.CC2_MUN)) = UPPER(RTRIM(A1.A1_MUN))
                      AND UPPER(RTRIM(CC2.CC2_EST)) = UPPER(RTRIM(A1.A1_EST))
                      AND CC2.D_E_L_E_T_ = ''
LEFT JOIN SB1{SUF} B1 ON B1.B1_COD = D2.D2_COD AND B1.D_E_L_E_T_ = ''
LEFT JOIN SBM{SUF} BM ON BM.BM_GRUPO = B1.B1_GRUPO AND BM.D_E_L_E_T_ = ''
LEFT JOIN SF4{SUF} F4 ON F4.F4_CODIGO = D2.D2_TES AND F4.D_E_L_E_T_ = ''
WHERE F2.D_E_L_E_T_ = ''
  AND F2.F2_FILIAL = '{FILIAL}'
  AND F2.F2_EMISSAO BETWEEN '{DE}' AND '{ATE}';


-- 4) Devolucao de VENDA (cliente devolvendo mercadoria) - lancada como nota
--    de ENTRADA no Protheus (SD1/D1_TIPO='D'), NUNCA aparece em SF2/SD2.
--    Filtra pela data de DIGITACAO (D1_DTDIGIT), igual ao Objeto de Negocio
--    Smart View (TLPP) do cliente. O JOIN com SF2 (nota de saida original,
--    via D1_NFORI/D1_SERIORI/D1_FORNECE/D1_LOJA) serve so para recuperar o
--    vendedor (F2_VEND1) da venda que foi devolvida.
--    valor_item e quantidade saem NEGATIVOS (sinal de devolucao), para que,
--    ao juntar com a consulta 3) acima, a soma por cliente/vendedor/produto
--    ja fique liquida de devolucao automaticamente.
SELECT
    D1.D1_DOC      AS nota,
    D1.D1_SERIE    AS serie,
    D1.D1_DTDIGIT  AS emissao_nf,
    D1.D1_FORNECE  AS cod_cliente,        -- na devolucao de venda, o campo "fornecedor" guarda o codigo do CLIENTE
    D1.D1_LOJA     AS loja_cliente,
    A1.A1_NOME     AS cliente,
    CC2.CC2_XREGIA AS regiao,
    CC2.CC2_XREGIO AS regional,
    F2.F2_VEND1    AS cod_vendedor,
    -D1.D1_QUANT   AS quantidade,
    -D1.D1_TOTAL   AS valor_item,
    'DEVOLUCAO'    AS tipo_registro
FROM SD1{SUF} D1
LEFT JOIN SF2{SUF} F2 ON F2.F2_DOC = D1.D1_NFORI AND F2.F2_SERIE = D1.D1_SERIORI
                      AND F2.F2_CLIENTE = D1.D1_FORNECE AND F2.F2_LOJA = D1.D1_LOJA
                      AND F2.D_E_L_E_T_ = ''
LEFT JOIN SA1{SUF} A1 ON A1.A1_COD = D1.D1_FORNECE AND A1.A1_LOJA = D1.D1_LOJA AND A1.D_E_L_E_T_ = ''
LEFT JOIN CC2{SUF} CC2 ON UPPER(RTRIM(CC2.CC2_MUN)) = UPPER(RTRIM(A1.A1_MUN))
                      AND UPPER(RTRIM(CC2.CC2_EST)) = UPPER(RTRIM(A1.A1_EST))
                      AND CC2.D_E_L_E_T_ = ''
WHERE D1.D_E_L_E_T_ = ''
  AND D1.D1_FILIAL = '{FILIAL}'
  AND D1.D1_TIPO = 'D'
  AND D1.D1_DTDIGIT BETWEEN '{DE}' AND '{ATE}';


-- Observacoes importantes:
-- * Regiao/Regional vem de campos CUSTOMIZADOS na tabela de Municipio (CC2),
--   especificos desta instalacao - confirmados via SX3 (dicionario de campos):
--   CC2_XREGIA = "Regiao" e CC2_XREGIO = "Regional" (nomes parecidos pois o
--   Protheus trunca nomes de campo em 10 caracteres). O vinculo cliente -> CC2
--   e feito por NOME do municipio + UF (SA1.A1_MUN/A1_EST guardam o nome, nao
--   um codigo), por isso o JOIN usa UPPER(RTRIM(...)) dos dois lados.
-- * Grupo de produto: a descricao vem da tabela SBM (Grupos de Produto),
--   confirmada nesta instalacao via INFORMATION_SCHEMA.COLUMNS - campos
--   BM_GRUPO (codigo) e BM_DESC (descricao, varchar 30), ligada por
--   BM_GRUPO = B1_GRUPO. Sem essa descricao o dashboard so teria o codigo
--   numerico (ex: 1701), sem significado pra quem olha o grafico/filtro.
-- * Datas do Protheus (C5_EMISSAO, F2_EMISSAO...) normalmente sao CHAR(8) "AAAAMMDD",
--   nao um tipo DATE nativo. Por isso a comparacao acima e por string.
-- * D_E_L_E_T_ = '' e obrigatorio em toda tabela do dicionario Protheus para
--   ignorar registros logicamente deletados/cancelados.
-- * Para "Faturamento Total" some D2.D2_TOTAL (nivel item) e nao F2.F2_VALFAT
--   por linha, senao o valor do cabecalho é somado uma vez por item (duplicando).
--   F2.F2_VALFAT deve ser somado apos DISTINCT por (nota, serie).
-- * O sufixo das tabelas (SUF) e o codigo da filial variam por ambiente/instalacao;
--   confirme com o time de TI/Basis do Protheus.
-- * Nomes de campo tambem podem variar entre versoes/customizacoes. Se outra
--   consulta falhar com "Invalid column name", rode:
--     SELECT TABLE_NAME, COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
--     WHERE TABLE_NAME IN ('SC5xxx','SC6xxx','SD2xxx','SF2xxx','SA1xxx','SB1xxx','SA3xxx')
--   para descobrir os nomes reais.
-- * CONHECIDO/RESOLVIDO (investigacao em 2026-11-15/16, com o usuario
--   Lealdo). Linha do tempo:
--   1) F2_VALFAT (usado originalmente no KPI "Faturamento total c/
--      impostos") nao e preenchido de forma confiavel nesta instalacao -
--      varias notas com F2_VALFAT = 0, pelo menos uma divergente.
--   2) Teste seguinte mostrou F2_VALMERC e F2_VALBRUT batendo EXATAMENTE
--      com SUM(D2_TOTAL) nas 18 notas do periodo testado - levou a crer,
--      por um momento, que bruto/liquido se diferenciavam por imposto (e
--      que nesta empresa nao haveria imposto "por fora" no cabecalho).
--   3) O usuario compartilhou o codigo-fonte TLPP do Objeto de Negocio
--      Smart View "Acompanhamento Gerencial de Faturamento" que ele ja usa
--      direto no Protheus (relatorio oficial de referencia). Esse codigo
--      mostrou que a hipotese do passo 2 estava incompleta: la, bruto e
--      liquido NUNCA incluem IPI/ST (ambos ja vem "sem imposto por fora")
--      - a diferenca real entre eles e DEVOLUCAO DE VENDA, lancada como
--      nota de ENTRADA (SD1/D1_TIPO='D'), que nunca aparece em SF2/SD2 e
--      por isso nunca tinha sido considerada no dashboard. O mesmo codigo
--      tambem mostrou que nem todo item de SD2 e receita: so conta quando
--      a TES gera duplicata (F4_DUPLIC='S') e o tipo nao e devolucao a
--      fornecedor ('D') nem beneficiamento ('B') - o resto (remessa,
--      bonificacao, amostra, devolucao a fornecedor, beneficiamento) e
--      "outras saidas", que nunca deveria contar como faturamento.
--   RESOLUCAO (2026-11-16): dashboard passou a replicar essa logica -
--   consulta 3) acima classifica FATURAMENTO vs OUTRAS SAIDAS via SF4/
--   D2_TIPO, e a consulta 4) traz devolucao de venda via SD1. kpis.py:
--   faturamento_bruto() = soma FATURAMENTO; devolucoes_total() = soma
--   DEVOLUCAO; faturamento_total() (liquido) = bruto - devolucoes. Pendente
--   apenas confirmar com o time fiscal/TI se ha algum outro imposto "por
--   fora" nao capturado em nenhum campo testado (F2_VALFAT/VALMERC/
--   VALBRUT) - se confirmado, revisar novamente.
