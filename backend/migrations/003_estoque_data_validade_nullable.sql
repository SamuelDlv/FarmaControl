-- ============================================================
-- Migracao 003: tornar data_validade NULL na tabela estoque
-- ============================================================
-- Problema: ao criar uma compra com status "Recebido", o sistema
-- tenta dar entrada no estoque com data_validade = NULL, mas a
-- coluna era NOT NULL, gerando o erro:
--   (1048, "Column 'data_validade' cannot be null")
-- Solucao: permitir NULL (data de validade nem sempre e'
-- conhecida no recebimento). O frontend de Compras tambem passa
-- a oferecer o campo "Validade" no item da compra.
--
-- Como aplicar:
--   mysql -u root -p farmacontrol < migrations/003_estoque_data_validade_nullable.sql

ALTER TABLE estoque MODIFY COLUMN data_validade DATE NULL;
