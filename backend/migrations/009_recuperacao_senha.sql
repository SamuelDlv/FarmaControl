-- Migração 009: tokens de recuperação de senha, armazenados apenas como hash.
-- Execute após 008: mysql -uroot farmacontrol < 009_recuperacao_senha.sql
-- Compatível com versões do MySQL que não suportam ADD COLUMN IF NOT EXISTS.

SET @schema_atual = DATABASE();

SET @sql = (
  SELECT IF(COUNT(*) = 0,
    'ALTER TABLE usuarios ADD COLUMN token_reset VARCHAR(255) NULL',
    'SELECT 1'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @schema_atual
    AND TABLE_NAME = 'usuarios'
    AND COLUMN_NAME = 'token_reset'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(COUNT(*) = 0,
    'ALTER TABLE usuarios ADD COLUMN token_expira_em DATETIME NULL',
    'SELECT 1'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @schema_atual
    AND TABLE_NAME = 'usuarios'
    AND COLUMN_NAME = 'token_expira_em'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
