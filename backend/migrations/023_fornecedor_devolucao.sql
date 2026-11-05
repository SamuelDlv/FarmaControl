-- Aplicar depois da 022; preserva saldos e registros existentes.
-- Verifica a coluna antes de adicionar, com sintaxe compativel com MySQL.
SET @sql = (
  SELECT IF(COUNT(*) = 0,
    'ALTER TABLE movimentacoes_estoque ADD COLUMN fornecedor_id INT UNSIGNED NULL COMMENT ''Fornecedor na data da devolucao''',
    'SELECT 1'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'movimentacoes_estoque'
    AND COLUMN_NAME = 'fornecedor_id'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
