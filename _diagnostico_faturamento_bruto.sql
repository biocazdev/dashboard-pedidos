-- Diagnostico: por que Faturamento total (c/ impostos), somado a partir de
-- F2_VALFAT, esta vindo MENOR que o Faturamento total (liquido), somado a
-- partir de D2_TOTAL? Isso nao deveria acontecer (o valor com impostos
-- deveria ser sempre >= o liquido). Rode esta consulta ajustando o periodo
-- e a filial conforme necessario, e envie o resultado (principalmente as
-- primeiras linhas, onde a diferenca e mais negativa).

SELECT
    F2.F2_DOC      AS nota,
    F2.F2_SERIE    AS serie,
    F2.F2_CLIENTE  AS cod_cliente,
    F2.F2_LOJA     AS loja_cliente,
    F2.F2_EMISSAO  AS emissao,
    F2.F2_VALFAT   AS valor_faturado_cabecalho,
    F2.F2_VALMERC  AS valor_mercadoria,
    SUM(D2.D2_TOTAL) AS soma_valor_itens,
    F2.F2_VALFAT - SUM(D2.D2_TOTAL) AS diferenca
FROM SF2010 F2
INNER JOIN SD2010 D2
       ON D2.D2_DOC = F2.F2_DOC
      AND D2.D2_SERIE = F2.F2_SERIE
      AND D2.D2_CLIENTE = F2.F2_CLIENTE
      AND D2.D2_LOJA = F2.F2_LOJA
      AND D2.D2_FILIAL = F2.F2_FILIAL
      AND D2.D_E_L_E_T_ = ''
WHERE F2.D_E_L_E_T_ = ''
  AND F2.F2_FILIAL = '010101'
  AND F2.F2_EMISSAO BETWEEN '20260815' AND '20261115'
GROUP BY F2.F2_DOC, F2.F2_SERIE, F2.F2_CLIENTE, F2.F2_LOJA, F2.F2_EMISSAO, F2.F2_VALFAT, F2.F2_VALMERC
ORDER BY diferenca ASC;
