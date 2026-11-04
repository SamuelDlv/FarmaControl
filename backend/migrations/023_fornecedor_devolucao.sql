-- Aplicar depois da 022; preserva saldos e registros existentes.
ALTER TABLE movimentacoes_estoque ADD COLUMN IF NOT EXISTS fornecedor_id INT UNSIGNED NULL COMMENT 'Fornecedor na data da devolucao';
