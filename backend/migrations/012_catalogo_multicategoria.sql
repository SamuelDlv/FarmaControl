-- Catálogo de medicamentos e demais produtos. MySQL/MariaDB; reaplicável.
-- Execute no banco selecionado, antes de iniciar a nova versão da API.
-- Não remove/reclassifica produtos, lotes ou históricos existentes.
SET @sql = IF(
  EXISTS(SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'produtos' AND COLUMN_NAME = 'tipo_produto'),
  'SELECT 1',
  'ALTER TABLE produtos ADD COLUMN tipo_produto ENUM(''medicamento'', ''outro'') NOT NULL DEFAULT ''medicamento'' AFTER nome'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(
  EXISTS(SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'produtos' AND COLUMN_NAME = 'exige_validade'),
  'SELECT 1',
  'ALTER TABLE produtos ADD COLUMN exige_validade BOOLEAN NOT NULL DEFAULT TRUE AFTER tipo_produto'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

ALTER TABLE estoque MODIFY COLUMN data_validade DATE NULL;

INSERT IGNORE INTO categorias_produto (nome, descricao) VALUES
  ('Medicamentos', 'Medicamentos e especialidades farmacêuticas'),
  ('Alimentos', 'Alimentos, bebidas, doces e itens de conveniência'),
  ('Higiene pessoal', 'Cuidados e higiene pessoal'),
  ('Cosméticos e dermocosméticos', 'Cremes, beleza e cuidados com a pele'),
  ('Saúde sexual', 'Preservativos, lubrificantes e cuidados íntimos'),
  ('Infantil e bebê', 'Fraldas e cuidados infantis'),
  ('Suplementos', 'Suplementos alimentares'),
  ('Acessórios', 'Acessórios e utensílios'),
  ('Primeiros socorros', 'Materiais de primeiros socorros'),
  ('Outros produtos', 'Demais produtos do catálogo');

-- Mantém o slug e os IDs usados pelos lançamentos financeiros anteriores.
UPDATE financeiro_categorias SET nome = 'Venda de Produtos'
WHERE slug = 'venda_medicamentos' AND nome = 'Venda de Medicamentos';
