-- =========================================================================
-- Consultas de diagnostico - Area Comercial
-- Rode cada bloco no DBeaver e me mande o resultado (pode ser print/tabela
-- colada mesmo). Troque {SUF} pelo sufixo das tabelas deste ambiente (ja
-- confirmado como 010 no seu .env) se copiar direto sem o find/replace.
-- =========================================================================


-- #########################################################################
-- PARTE 1) REGIAO e REGIONAL (campos customizados na tabela de Municipio)
-- #########################################################################

-- 1.1) Lista TODOS os campos da tabela de Municipio (CC2) - os campos
--      customizados de regiao/regional devem aparecer aqui, normalmente
--      com nome tipo CC2_XREGIAO, CC2_XREGIONAL (prefixo X = campo customizado).
SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME LIKE 'CC2%'
ORDER BY TABLE_NAME, ORDINAL_POSITION;

-- 1.2) Confirma os campos do cliente (SA1) que ligam ao municipio
--      (A1_MUN e A1_EST normalmente), para eu poder fazer o JOIN com CC2.
SELECT TOP 5 A1_COD, A1_LOJA, A1_NOME, A1_MUN, A1_EST
FROM SA1010
WHERE D_E_L_E_T_ = '';

-- 1.3) Depois de ver os nomes reais dos campos customizados no resultado
--      da consulta 1.1, rode esta amostra trocando <CAMPO_REGIAO> e
--      <CAMPO_REGIONAL> pelos nomes reais, so para eu ver os valores:
-- SELECT TOP 15 CC2_MUN, CC2_EST, CC2_MUNDESC, <CAMPO_REGIAO>, <CAMPO_REGIONAL>
-- FROM CC2010
-- WHERE D_E_L_E_T_ = '';


-- #########################################################################
-- PARTE 2) METAS DE VENDAS por vendedor
-- #########################################################################

-- 2.1) Lista TODOS os campos do cadastro de vendedores (SA3) - caso exista
--      um campo padrao de cota/meta mensal, ele aparece aqui (nao vou
--      supor o nome, ja fui pego nisso antes com D2_PRODUTO/F2_CANCEL).
SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME LIKE 'SA3%'
ORDER BY TABLE_NAME, ORDINAL_POSITION;

-- 2.2) Procura por TABELAS cujo nome sugira meta/orcamento/quota/cota de vendas
SELECT TABLE_NAME
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_NAME LIKE '%META%'
   OR TABLE_NAME LIKE '%ORC%'
   OR TABLE_NAME LIKE '%QUOTA%'
   OR TABLE_NAME LIKE '%COTA%'
ORDER BY TABLE_NAME;

-- 2.3) Procura por CAMPOS (em qualquer tabela) cujo nome sugira meta/orcamento/quota
SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE COLUMN_NAME LIKE '%META%'
   OR COLUMN_NAME LIKE '%QUOTA%'
   OR COLUMN_NAME LIKE '%COTA%'
   OR COLUMN_NAME LIKE '%ORCT%'
   OR COLUMN_NAME LIKE '%ORCA%'
ORDER BY TABLE_NAME, COLUMN_NAME;

-- 2.4) Localiza a tabela de dicionario do Protheus (SX2) para ver se existe
--      algum CADASTRO PADRAO ja nomeado como "orcamento de vendas" /
--      "metas" / "cotas" (as vezes existe o cadastro mas nunca foi usado).
--      Primeiro descubra o nome exato da SX2 neste ambiente:
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE 'SX2%';
-- Depois troque SX2010 abaixo pelo nome que apareceu acima:
SELECT X2_CHAVE, X2_NOME, X2_MODO
FROM SX2010
WHERE X2_NOME LIKE '%META%'
   OR X2_NOME LIKE '%ORCAMENTO%'
   OR X2_NOME LIKE '%QUOTA%'
   OR X2_NOME LIKE '%COTA%'
   OR X2_NOME LIKE '%OBJETIVO%'
ORDER BY X2_NOME;


-- #########################################################################
-- PARTE 3) Esclarecer os achados (rodar depois das Partes 1 e 2 acima)
-- #########################################################################

-- 3.1) O Protheus trunca nome de campo em 10 caracteres, por isso CC2_XREGIO
--      e CC2_XREGIA ficaram parecidos. A SX3 e o dicionario de CAMPOS do
--      Protheus - o titulo/descricao completa de cada campo esta la.
--      Primeiro confirme o nome exato da SX3 neste ambiente:
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE 'SX3%';
-- Depois troque SX3010 abaixo pelo nome que apareceu acima:
SELECT X3_CAMPO, X3_TITULO, X3_DESCRIC, X3_ARQUIVO
FROM SX3010
WHERE X3_CAMPO IN ('CC2_XREGIO','CC2_XREGIA','A3_REGIAO','UO_META','UO_METAOP')
ORDER BY X3_CAMPO;

-- 3.2) Amostra de valores reais dos dois campos customizados de municipio,
--      para eu ver na pratica qual e regiao (ex: Sul/Sudeste/Nordeste) e
--      qual e regional (ex: nome de uma area/equipe comercial):
SELECT TOP 20 CC2_MUN, CC2_EST, CC2_XREGIO, CC2_XREGIA
FROM CC2010
WHERE D_E_L_E_T_ = ''
  AND (CC2_XREGIO <> '' OR CC2_XREGIA <> '');

-- 3.3) Estrutura completa da SUO010 (candidata a tabela de meta) - preciso
--      ver se ela tem algum campo de vendedor/representante e de periodo
--      (mes/ano), para saber se serve como "meta de vendas por vendedor"
--      ou se e orcamento de outra natureza (ex: centro de custo):
SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME LIKE 'SUO%'
ORDER BY TABLE_NAME, ORDINAL_POSITION;


-- #########################################################################
-- PARTE 4) Descricao do Grupo de Produto (hoje aparece so o codigo, ex: 1701)
-- #########################################################################

-- 4.1) No Protheus, a descricao do grupo de produto normalmente fica numa
--      tabela separada chamada SBM (Grupos de Produto), ligada por
--      B1_GRUPO = BM_GRUPO. Confirme se ela existe neste ambiente:
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE 'SBM%';

-- 4.2) Lista os campos dela (nao vou supor o nome exato do campo de
--      descricao - pode ser BM_DESC ou outro). Troque SBM010 abaixo pelo
--      nome que apareceu em 4.1 se for diferente:
SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME LIKE 'SBM%'
ORDER BY TABLE_NAME, ORDINAL_POSITION;

-- 4.3) Amostra de dados - preciso ver os grupos que aparecem no dashboard
--      (1701, 1702, 1703, 1704, 1804) com a descricao ao lado. Troque
--      BM_DESC pelo nome real do campo encontrado em 4.2 se for diferente:
SELECT BM_GRUPO, BM_DESC
FROM SBM010
WHERE D_E_L_E_T_ = ''
  AND BM_GRUPO IN ('1701','1702','1703','1704','1804');

-- 4.4) Lista completa de todos os grupos cadastrados (pra cobrir tambem
--      codigos que ainda nao apareceram no periodo filtrado hoje):
SELECT BM_GRUPO, BM_DESC
FROM SBM010
WHERE D_E_L_E_T_ = ''
ORDER BY BM_GRUPO;
