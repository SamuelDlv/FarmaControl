-- Guia de manutenção: estrutura para instalação nova, não um runner de atualização.
-- Em instalações existentes, siga backend/migrations/README.md e preserve os SQLs registrados.
-- As FKs abaixo representam dependências: revise exclusões e ordem de criação ao mudar o modelo.
-- ═══════════════════════════════════════════════════════════════
--  FarmaControl — Schema MySQL 8 / MariaDB 10.4+ (instalação nova)
--  Ideal para novas instalações em localhost.
-- ═══════════════════════════════════════════════════════════════

CREATE DATABASE IF NOT EXISTS farmacontrol
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE farmacontrol;

-- Acessos técnicos opcionais: setup/technical_roles.sql (somente TI).
-- Este schema não cria contas/roles nem altera privilégios do servidor.

-- ───────────────────────────────────────────
--  1. Perfis de acesso (Roles)
-- ───────────────────────────────────────────
-- Cargos funcionais usados na autorização da aplicação. Os slugs são contratos com o backend e o menu.
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
  ('visualizador', 'Visualizador',            'Consulta de informações operacionais sem permissões administrativas.'),
  ('compras',      'Responsável por Compras', 'Gestão de suprimentos: pedidos de compra e análise de demanda.'),
  ('ti',           'TI / Suporte',            'Manutenção técnica: logs, configurações de sistema e integrações.')
ON DUPLICATE KEY UPDATE nome = VALUES(nome), descricao = VALUES(descricao);

-- ───────────────────────────────────────────
--  2. Permissões configuráveis por perfil
-- ───────────────────────────────────────────
-- Matriz de acesso por cargo e módulo. A chave composta impede permissões duplicadas para o mesmo par.
CREATE TABLE IF NOT EXISTS perfil_permissoes (
  perfil_id TINYINT UNSIGNED NOT NULL,
  modulo VARCHAR(40) NOT NULL,
  permitido TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (perfil_id, modulo),
  CONSTRAINT fk_perfil_permissao_perfil
    FOREIGN KEY (perfil_id) REFERENCES perfis(id)
    ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

-- Padrão inicial. INSERT IGNORE preserva personalizações se este schema for
-- executado novamente em uma base já existente.
INSERT IGNORE INTO perfil_permissoes (perfil_id, modulo, permitido)
SELECT p.id, m.modulo,
  CASE
    WHEN p.slug IN ('proprietario', 'admin', 'ti') THEN 1
    WHEN p.slug = 'farmaceutico' AND m.modulo IN ('dashboard','estoque','vencimentos','relatorios','compras') THEN 1
    WHEN p.slug = 'atendente' AND m.modulo IN ('dashboard','estoque') THEN 1
    WHEN p.slug = 'visualizador' AND m.modulo IN ('dashboard','estoque','vencimentos','relatorios') THEN 1
    WHEN p.slug = 'compras' AND m.modulo IN ('dashboard','estoque','vencimentos','relatorios','compras') THEN 1
    ELSE 0
  END
FROM perfis p
CROSS JOIN (
  SELECT 'dashboard' AS modulo UNION ALL SELECT 'estoque' UNION ALL SELECT 'vencimentos' UNION ALL SELECT 'relatorios'
  UNION ALL SELECT 'compras' UNION ALL SELECT 'financeiro' UNION ALL SELECT 'usuarios' UNION ALL SELECT 'configuracoes'
) AS m
WHERE p.slug IN ('proprietario', 'admin', 'farmaceutico', 'atendente', 'visualizador', 'compras', 'ti');


-- ───────────────────────────────────────────
--  3. Usuários
-- ───────────────────────────────────────────
-- Contas autenticadas: perfil, aprovação e credenciais. Senhas e tokens devem seguir os hashes previstos no backend.
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

-- Compatibilidade da recuperação de senha para bases criadas antes deste
-- schema. O CREATE TABLE acima atende instalações novas; este trecho atualiza
-- uma tabela usuarios já existente em versões antigas do MySQL.
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

-- ───────────────────────────────────────────
--  4. Auditoria e Logs
-- ───────────────────────────────────────────
-- Rastreia a decisão de aprovação ou rejeição e o responsável pela análise do cadastro.
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

-- Histórico específico das tentativas de autenticação; não confundir com o log geral de operações.
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
-- Cadastro referenciado pelos fluxos comerciais e de receitas. Revise as FKs antes de excluir registros.
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

-- Classificação dos produtos. As referências do catálogo dependem dos identificadores desta tabela.
CREATE TABLE IF NOT EXISTS categorias_produto (
  id              TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
  nome            VARCHAR(100)     NOT NULL UNIQUE,
  descricao       VARCHAR(255)     NULL,
  criado_em       DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  atualizado_em   DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
) ENGINE=InnoDB;

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

-- Origem comercial dos produtos e compras; devoluções também preservam a referência ao fornecedor.
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

-- Cadastro comercial compartilhado pelos lotes. Preço e exigência de receita/validade são regras do produto.
CREATE TABLE IF NOT EXISTS produtos (
  id              INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  nome            VARCHAR(255)     NOT NULL,
  tipo_produto    ENUM('medicamento', 'outro') NOT NULL DEFAULT 'medicamento',
  exige_validade  BOOLEAN          NOT NULL DEFAULT TRUE,
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

-- Saldo físico por produto e lote. Alterações concorrentes de quantidade exigem bloqueio e transação no backend.
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

-- Rastro das entradas, saídas e ajustes. Finalidade, motivo e fornecedor contextualizam saídas administrativas.
CREATE TABLE IF NOT EXISTS movimentacoes_estoque (
  id                  BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
  estoque_id          INT UNSIGNED     NOT NULL,
  usuario_id          INT UNSIGNED     NOT NULL,
  tipo_movimentacao   ENUM('entrada', 'saida', 'ajuste', 'transferencia') NOT NULL,
  finalidade          ENUM('descarte', 'venda', 'devolucao_fornecedor') NULL,
  motivo              VARCHAR(255) NULL,
  fornecedor_id       INT UNSIGNED NULL COMMENT 'Fornecedor registrado na devolução; preservado como referência histórica',
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
-- Cabeçalho do pedido: fornecedor, responsável, valores e estado. O recebimento é coordenado com os itens e o saldo.
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

-- Detalha produtos, quantidades e os dados dos lotes recebidos que alimentam o estoque.
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

-- Cabeçalho comercial da venda. Mudanças de estado precisam permanecer coerentes com estoque e financeiro.
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

-- Preserva quantidade, preço e lote da operação. Não recalcular o histórico usando o preço atual do catálogo.
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
-- Cadastro de receitas referenciado pelos atendimentos; dados deste domínio não devem ir para logs genéricos.
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

-- Relaciona a receita aos produtos prescritos e seus dados de uso.
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
-- Preferências e regras por chave. Os padrões e valores aceitos são definidos em services/system_settings.py.
CREATE TABLE IF NOT EXISTS configuracoes_sistema (
  chave VARCHAR(120) PRIMARY KEY,
  valor TEXT NULL,
  descricao VARCHAR(255) NULL,
  criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Aceites de termos e privacidade registrados no momento do cadastro.
-- Registra o aceite associado à conta. A criação de convite administrativo não representa consentimento.
CREATE TABLE IF NOT EXISTS aceites_legais (
  id                  INT UNSIGNED NOT NULL AUTO_INCREMENT,
  usuario_id          INT UNSIGNED NOT NULL,
  termos_versao       VARCHAR(32) NOT NULL,
  privacidade_versao  VARCHAR(32) NOT NULL,
  aceito_em           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ip                  VARCHAR(64) NULL,
  PRIMARY KEY (id),
  INDEX idx_aceites_legais_usuario (usuario_id),
  CONSTRAINT fk_aceite_usuario FOREIGN KEY (usuario_id)
    REFERENCES usuarios (id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

-- Convites com estado e expiração. O token enviado no link deve ser armazenado em forma de hash.
CREATE TABLE IF NOT EXISTS convites_cadastro (
  id                         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  nome                       VARCHAR(80) NOT NULL,
  sobrenome                  VARCHAR(80) NOT NULL,
  email                      VARCHAR(180) NOT NULL,
  perfil_id                  TINYINT UNSIGNED NOT NULL,
  convidado_por_usuario_id   INT UNSIGNED NOT NULL,
  token_hash                 CHAR(64) NOT NULL UNIQUE,
  status                     ENUM('pendente','aceito','recusado','expirado') NOT NULL DEFAULT 'pendente',
  expira_em                  DATETIME NOT NULL,
  respondido_em              DATETIME NULL,
  aceito_usuario_id          INT UNSIGNED NULL,
  criado_em                  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  INDEX idx_convites_email_status (email, status),
  CONSTRAINT fk_convite_perfil FOREIGN KEY (perfil_id) REFERENCES perfis (id) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_convite_criador FOREIGN KEY (convidado_por_usuario_id) REFERENCES usuarios (id) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_convite_aceito_usuario FOREIGN KEY (aceito_usuario_id) REFERENCES usuarios (id) ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB;

-- Alertas operacionais e sua resolução auditável.
-- Ocorrências operacionais e seu estado de resolução; a identidade do responsável vem da sessão autenticada.
CREATE TABLE IF NOT EXISTS alertas (
  id                         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  tipo_alerta                VARCHAR(30) NOT NULL,
  referencia_id              INT NULL,
  mensagem                   TEXT NOT NULL,
  status                     VARCHAR(20) NOT NULL DEFAULT 'ativo',
  resolvido_em               DATETIME NULL,
  resolvido_por_usuario_id   INT UNSIGNED NULL,
  criado_em                  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  atualizado_em              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  INDEX idx_alertas_tipo (tipo_alerta),
  INDEX idx_alertas_status (status),
  INDEX idx_alertas_resolvido_por (resolvido_por_usuario_id),
  CONSTRAINT fk_alerta_resolvido_usuario FOREIGN KEY (resolvido_por_usuario_id)
    REFERENCES usuarios (id) ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB;

-- ───────────────────────────────────────────
--  6. Financeiro
-- ───────────────────────────────────────────
-- Classificação de receitas e despesas. Os slugs usados pelas vendas devem continuar estáveis.
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
  ('Venda de Produtos', 'receita', 'venda_medicamentos'),
  ('Serviços Farmacêuticos', 'receita', 'servicos'),
  ('Pagamento de Fornecedores', 'despesa', 'fornecedores'),
  ('Folha de Pagamento', 'despesa', 'salarios'),
  ('Aluguel e Contas', 'despesa', 'fixos'),
  ('Impostos', 'despesa', 'impostos'),
  ('Marketing', 'despesa', 'marketing'),
  ('Outras Receitas', 'receita', 'outros_receita'),
  ('Outras Despesas', 'despesa', 'outros_despesa');

-- Lançamentos financeiros e seus vínculos comerciais; a receita de venda acompanha a transação da venda.
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

-- Historico preservado mesmo apos exclusao do usuario (identidade por snapshot).
-- Auditoria geral: ator, operação e detalhes permitidos. O backend filtra segredos antes de gravar.
CREATE TABLE IF NOT EXISTS log_atividades (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NULL,
    usuario_nome VARCHAR(255) NOT NULL,
    perfil VARCHAR(40) NOT NULL,
    acao VARCHAR(255) NOT NULL,
    detalhes MEDIUMTEXT NOT NULL,
    status_http SMALLINT UNSIGNED NOT NULL,
    criado_em DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
    INDEX idx_log_usuario (usuario_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
