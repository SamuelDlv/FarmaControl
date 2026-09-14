-- Migração 004: cria a tabela `alertas` usada pelos endpoints GET/POST /alertas
-- Executar: mysql -uroot farmacontrol < 004_tabela_alertas.sql

CREATE TABLE IF NOT EXISTS alertas (
  id INT PRIMARY KEY AUTO_INCREMENT,
  tipo_alerta VARCHAR(30) NOT NULL,
  referencia_id INT NULL,
  mensagem TEXT NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'ativo',
  criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  atualizado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_alertas_tipo (tipo_alerta),
  INDEX idx_alertas_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
