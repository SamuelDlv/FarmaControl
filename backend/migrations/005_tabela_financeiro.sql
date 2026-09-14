-- ═══════════════════════════════════════════════════════════════
--  FarmaControl — Migração 005: Tabela Financeiro
--  Compatível com MySQL 5.7+ e MySQL 8.0
-- ═══════════════════════════════════════════════════════════════

USE farmacontrol;

-- 1. Tabela de Categorias Financeiras
CREATE TABLE IF NOT EXISTS financeiro_categorias (
  id          INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  nome        VARCHAR(80)      NOT NULL,
  tipo        ENUM('receita', 'despesa') NOT NULL,
  slug        VARCHAR(40)      NOT NULL UNIQUE,
  criado_em   DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
) ENGINE=InnoDB;

-- Inserção de categorias padrão (usa IGNORE para não duplicar)
INSERT IGNORE INTO financeiro_categorias (nome, tipo, slug) VALUES
  ('Venda de Medicamentos', 'receita', 'venda_medicamentos'),
  ('Serviços Farmacêuticos', 'receita', 'servicos'),
  ('Pagamento de Fornecedores', 'despesa', 'fornecedores'),
  ('Folha de Pagamento', 'despesa', 'salarios'),
  ('Aluguel e Contas', 'despesa', 'fixos'),
  ('Impostos', 'despesa', 'impostos'),
  ('Marketing', 'despesa', 'marketing'),
  ('Outras Receitas', 'receita', 'outros_receita'),
  ('Outras Despesas', 'despesa', 'outros_despesa');

-- 2. Tabela de Fluxo de Caixa (Transações)
CREATE TABLE IF NOT EXISTS financeiro_transacoes (
  id              INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  categoria_id    INT UNSIGNED     NOT NULL,
  usuario_id      INT UNSIGNED     NOT NULL,
  venda_id        INT UNSIGNED     NULL,
  compra_id       INT UNSIGNED     NULL,
  descricao       VARCHAR(255)     NOT NULL,
  valor           DECIMAL(12, 2)   NOT NULL,
  data_transacao  DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  status          ENUM('pago', 'pendente', 'cancelado') NOT NULL DEFAULT 'pago',
  metodo_pagamento ENUM('dinheiro', 'cartao_credito', 'cartao_debito', 'pix', 'boleto', 'transferencia') NOT NULL,
  criado_em       DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  atualizado_em   DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  INDEX idx_data (data_transacao),
  CONSTRAINT fk_fin_categoria FOREIGN KEY (categoria_id) REFERENCES financeiro_categorias (id) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_fin_usuario   FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_fin_venda     FOREIGN KEY (venda_id) REFERENCES vendas (id) ON UPDATE CASCADE ON DELETE SET NULL,
  CONSTRAINT fk_fin_compra    FOREIGN KEY (compra_id) REFERENCES compras (id) ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB;

-- 3. Inserção de dados iniciais fictícios para o dashboard financeiro
INSERT INTO financeiro_transacoes (categoria_id, usuario_id, descricao, valor, data_transacao, metodo_pagamento, status)
SELECT
    (SELECT id FROM financeiro_categorias WHERE slug = 'venda_medicamentos' LIMIT 1),
    (SELECT id FROM usuarios LIMIT 1),
    'Venda consolidada do dia',
    1250.00 + (RAND() * 500),
    DATE_SUB(NOW(), INTERVAL seq.n DAY),
    'pix',
    'pago'
FROM (
  SELECT 0 AS n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL
  SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL
  SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL
  SELECT 9 UNION ALL SELECT 10
) AS seq
WHERE (SELECT id FROM financeiro_categorias WHERE slug = 'venda_medicamentos' LIMIT 1) IS NOT NULL
  AND (SELECT id FROM usuarios LIMIT 1) IS NOT NULL;

INSERT INTO financeiro_transacoes (categoria_id, usuario_id, descricao, valor, data_transacao, metodo_pagamento, status)
SELECT
    (SELECT id FROM financeiro_categorias WHERE slug = 'fixos' LIMIT 1),
    (SELECT id FROM usuarios LIMIT 1),
    'Aluguel Mensal',
    3500.00,
    DATE_SUB(NOW(), INTERVAL 5 DAY),
    'transferencia',
    'pago'
WHERE (SELECT id FROM financeiro_categorias WHERE slug = 'fixos' LIMIT 1) IS NOT NULL
  AND (SELECT id FROM usuarios LIMIT 1) IS NOT NULL;
