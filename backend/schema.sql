-- ═══════════════════════════════════════════════════════════════
--  FarmaControl — Schema MySQL Completo (Versão Atualizada)
--  Ideal para novas instalações em localhost.
-- ═══════════════════════════════════════════════════════════════

CREATE DATABASE IF NOT EXISTS farmacontrol
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE farmacontrol;

-- ───────────────────────────────────────────
--  1. Perfis de acesso (Roles)
-- ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS perfis (
  id          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
  slug        VARCHAR(30)      NOT NULL UNIQUE,
  nome        VARCHAR(80)      NOT NULL,
  descricao   VARCHAR(255)     NOT NULL,
  criado_em   DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
) ENGINE=InnoDB;

-- Inserção dos perfis individuais (Proprietário separado de Farmacêutico)
INSERT INTO perfis (slug, nome, descricao) VALUES
  ('proprietario', 'Proprietário',           'Visão total do negócio: financeiro, relatórios estratégicos e gestão de usuários.'),
  ('farmaceutico', 'Farmacêutico',           'Responsável técnico: controle de estoque, validade e dispensação de controlados.'),
  ('admin',        'Gerente / Administrador', 'Gestão operacional completa: estoque, compras e relatórios de vendas.'),
  ('atendente',    'Atendente / Balconista',  'Frente de loja: consulta de produtos e registro de vendas.'),
  ('compras',      'Responsável por Compras', 'Gestão de suprimentos: pedidos de compra e análise de demanda.'),
  ('ti',           'TI / Suporte',            'Manutenção técnica: logs, configurações de sistema e integrações.')
ON DUPLICATE KEY UPDATE nome = VALUES(nome), descricao = VALUES(descricao);

-- ───────────────────────────────────────────
--  2. Usuários
-- ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS usuarios (
  id              INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  nome            VARCHAR(80)      NOT NULL,
  sobrenome       VARCHAR(80)      NOT NULL,
  email           VARCHAR(180)     NOT NULL UNIQUE,
  senha_hash      VARCHAR(255)     NOT NULL,
  perfil_id       TINYINT UNSIGNED NOT NULL,
  status          ENUM('pendente','aprovado','rejeitado') NOT NULL DEFAULT 'pendente',
  ultimo_login    DATETIME         NULL,
  token_reset     VARCHAR(255)     NULL,
  token_expira_em DATETIME         NULL,
  criado_em       DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  atualizado_em   DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  INDEX idx_email  (email),
  INDEX idx_status (status),
  CONSTRAINT fk_usuario_perfil FOREIGN KEY (perfil_id) REFERENCES perfis (id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ───────────────────────────────────────────
--  3. Auditoria e Logs
-- ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analises_cadastro (
  id              INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  usuario_id      INT UNSIGNED     NOT NULL,
  analisado_por   INT UNSIGNED     NULL,
  decisao         ENUM('aprovado','rejeitado') NOT NULL,
  motivo          VARCHAR(500)     NULL,
  analisado_em    DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  CONSTRAINT fk_analise_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_analise_admin FOREIGN KEY (analisado_por) REFERENCES usuarios (id) ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS log_acessos (
  id          BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
  usuario_id  INT UNSIGNED     NOT NULL,
  ip          VARCHAR(45)      NULL,
  user_agent  VARCHAR(500)     NULL,
  sucesso     TINYINT(1)       NOT NULL DEFAULT 1,
  motivo_falha VARCHAR(200)    NULL,
  criado_em   DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  CONSTRAINT fk_log_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

-- ───────────────────────────────────────────
--  4. Gestão de Produtos e Estoque
-- ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS clientes (
  id              INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  nome            VARCHAR(80)      NOT NULL,
  sobrenome       VARCHAR(80)      NOT NULL,
  cpf             VARCHAR(14)      UNIQUE NULL,
  telefone        VARCHAR(20)      NULL,
  email           VARCHAR(180)     UNIQUE NULL,
  endereco        VARCHAR(255)     NULL,
  data_nascimento DATE             NULL,
  criado_em       DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  atualizado_em   DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS categorias_produto (
  id              TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
  nome            VARCHAR(100)     NOT NULL UNIQUE,
  descricao       VARCHAR(255)     NULL,
  criado_em       DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  atualizado_em   DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS fornecedores (
  id              INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  nome_fantasia   VARCHAR(150)     NOT NULL,
  razao_social    VARCHAR(255)     NOT NULL UNIQUE,
  cnpj            VARCHAR(18)      NOT NULL UNIQUE,
  contato_nome    VARCHAR(100)     NULL,
  contato_telefone VARCHAR(20)     NULL,
  contato_email   VARCHAR(180)     NULL,
  endereco        VARCHAR(255)     NULL,
  ativo           BOOLEAN          NOT NULL DEFAULT TRUE,
  criado_em       DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  atualizado_em   DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS produtos (
  id              INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  nome            VARCHAR(255)     NOT NULL,
  nome_generico   VARCHAR(255)     NULL,
  descricao       TEXT             NULL,
  fabricante      VARCHAR(150)     NULL,
  preco_custo     DECIMAL(10, 2)   NOT NULL,
  preco_venda     DECIMAL(10, 2)   NOT NULL,
  codigo_barras   VARCHAR(50)      UNIQUE NULL,
  categoria_id    TINYINT UNSIGNED NULL,
  requer_receita  BOOLEAN          NOT NULL DEFAULT FALSE,
  ativo           BOOLEAN          NOT NULL DEFAULT TRUE,
  estoque_minimo  INT UNSIGNED     NOT NULL DEFAULT 10,
  fornecedor_id   INT UNSIGNED     NULL,
  criado_em       DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  atualizado_em   DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  CONSTRAINT fk_produto_categoria FOREIGN KEY (categoria_id) REFERENCES categorias_produto (id) ON UPDATE CASCADE ON DELETE SET NULL,
  CONSTRAINT fk_produto_fornecedor FOREIGN KEY (fornecedor_id) REFERENCES fornecedores (id) ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS estoque (
  id              INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  produto_id      INT UNSIGNED     NOT NULL,
  lote            VARCHAR(50)      NOT NULL,
  quantidade      INT UNSIGNED     NOT NULL,
  data_validade   DATE             NULL,
  localizacao     VARCHAR(100)     NULL,
  criado_em       DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  atualizado_em   DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_produto_lote (produto_id, lote),
  CONSTRAINT fk_estoque_produto FOREIGN KEY (produto_id) REFERENCES produtos (id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS movimentacoes_estoque (
  id                  BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
  estoque_id          INT UNSIGNED     NOT NULL,
  usuario_id          INT UNSIGNED     NOT NULL,
  tipo_movimentacao   ENUM('entrada', 'saida', 'ajuste', 'transferencia') NOT NULL,
  quantidade          INT              NOT NULL,
  observacao          VARCHAR(255)     NULL,
  data_movimentacao   DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  CONSTRAINT fk_movimentacao_estoque FOREIGN KEY (estoque_id) REFERENCES estoque (id) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_movimentacao_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ───────────────────────────────────────────
--  5. Compras e Vendas
-- ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS compras (
  id              INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  fornecedor_id   INT UNSIGNED     NOT NULL,
  usuario_id      INT UNSIGNED     NOT NULL,
  data_pedido     DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  data_recebimento DATETIME        NULL,
  valor_total     DECIMAL(10, 2)   NOT NULL,
  status          ENUM('pendente', 'recebido', 'cancelado') NOT NULL DEFAULT 'pendente',
  criado_em       DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  atualizado_em   DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  CONSTRAINT fk_compra_fornecedor FOREIGN KEY (fornecedor_id) REFERENCES fornecedores (id) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_compra_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS itens_compra (
  id                  INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  compra_id           INT UNSIGNED     NOT NULL,
  produto_id          INT UNSIGNED     NOT NULL,
  quantidade          INT UNSIGNED     NOT NULL,
  preco_unitario      DECIMAL(10, 2)   NOT NULL,
  lote_recebido       VARCHAR(50)      NULL,
  data_validade_recebida DATE          NULL,
  PRIMARY KEY (id),
  CONSTRAINT fk_item_compra_compra FOREIGN KEY (compra_id) REFERENCES compras (id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_item_compra_produto FOREIGN KEY (produto_id) REFERENCES produtos (id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS vendas (
  id              INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  cliente_id      INT UNSIGNED     NULL,
  usuario_id      INT UNSIGNED     NOT NULL,
  data_venda      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  valor_total     DECIMAL(10, 2)   NOT NULL,
  tipo_pagamento  ENUM('dinheiro', 'cartao_credito', 'cartao_debito', 'pix') NOT NULL,
  status          ENUM('concluida', 'cancelada', 'pendente') NOT NULL DEFAULT 'pendente',
  criado_em       DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  atualizado_em   DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  CONSTRAINT fk_venda_cliente FOREIGN KEY (cliente_id) REFERENCES clientes (id) ON UPDATE CASCADE ON DELETE SET NULL,
  CONSTRAINT fk_venda_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS itens_venda (
  id              INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  venda_id        INT UNSIGNED     NOT NULL,
  produto_id      INT UNSIGNED     NOT NULL,
  quantidade      INT UNSIGNED     NOT NULL,
  preco_unitario  DECIMAL(10, 2)   NOT NULL,
  desconto        DECIMAL(5, 2)    NOT NULL DEFAULT 0.00,
  lote_vendido    VARCHAR(50)      NULL,
  PRIMARY KEY (id),
  CONSTRAINT fk_item_venda_venda FOREIGN KEY (venda_id) REFERENCES vendas (id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_item_venda_produto FOREIGN KEY (produto_id) REFERENCES produtos (id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ───────────────────────────────────────────
--  6. Receitas e Itens de Receita
-- ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS receitas (
  id                  INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  cliente_id          INT UNSIGNED     NOT NULL,
  medico_nome         VARCHAR(150)     NOT NULL,
  crm                 VARCHAR(20)      NOT NULL,
  data_prescricao     DATE             NOT NULL,
  data_validade       DATE             NULL,
  observacoes         TEXT             NULL,
  arquivo_receita_url VARCHAR(255)     NULL,
  criado_em           DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  atualizado_em       DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  CONSTRAINT fk_receita_cliente FOREIGN KEY (cliente_id) REFERENCES clientes (id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS receitas_itens (
  id              INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  receita_id      INT UNSIGNED     NOT NULL,
  produto_id      INT UNSIGNED     NOT NULL,
  quantidade      INT UNSIGNED     NOT NULL,
  dosagem         VARCHAR(100)     NULL,
  instrucoes_uso  TEXT             NULL,
  PRIMARY KEY (id),
  CONSTRAINT fk_receita_item_receita FOREIGN KEY (receita_id) REFERENCES receitas (id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_receita_item_produto FOREIGN KEY (produto_id) REFERENCES produtos (id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;


-- Configurações do sistema
CREATE TABLE IF NOT EXISTS configuracoes_sistema (
  chave VARCHAR(120) PRIMARY KEY,
  valor TEXT NULL,
  descricao VARCHAR(255) NULL,
  criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- ───────────────────────────────────────────
--  6. Financeiro
-- ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS financeiro_categorias (
  id          INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  nome        VARCHAR(80)      NOT NULL,
  tipo        ENUM('receita', 'despesa') NOT NULL,
  slug        VARCHAR(40)      NOT NULL UNIQUE,
  criado_em   DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
) ENGINE=InnoDB;

-- Categorias financeiras padrão
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
