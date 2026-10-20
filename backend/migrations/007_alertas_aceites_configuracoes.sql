-- Migração 007: consolida estruturas que antes podiam ser criadas em runtime.
-- Execute depois das migrações 004, 005 e 006:
--   mysql -uroot farmacontrol < 007_alertas_aceites_configuracoes.sql
-- Compatível com MySQL 5.7+/MariaDB. O procedimento é removido ao final.

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

CREATE TABLE IF NOT EXISTS configuracoes_sistema (
  chave VARCHAR(120) PRIMARY KEY,
  valor TEXT NULL,
  descricao VARCHAR(255) NULL,
  criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

DELIMITER //

CREATE PROCEDURE fc_migracao_007_alertas()
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = DATABASE() AND table_name = 'alertas'
  ) THEN
    CREATE TABLE alertas (
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
  ELSE
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'alertas' AND column_name = 'resolvido_em'
    ) THEN
      ALTER TABLE alertas ADD COLUMN resolvido_em DATETIME NULL AFTER status;
    END IF;
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'alertas' AND column_name = 'resolvido_por_usuario_id'
    ) THEN
      ALTER TABLE alertas ADD COLUMN resolvido_por_usuario_id INT UNSIGNED NULL AFTER resolvido_em;
    END IF;
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.statistics
      WHERE table_schema = DATABASE() AND table_name = 'alertas' AND index_name = 'idx_alertas_resolvido_por'
    ) THEN
      ALTER TABLE alertas ADD INDEX idx_alertas_resolvido_por (resolvido_por_usuario_id);
    END IF;
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.table_constraints
      WHERE table_schema = DATABASE() AND table_name = 'alertas'
        AND constraint_name = 'fk_alerta_resolvido_usuario'
    ) THEN
      ALTER TABLE alertas
        ADD CONSTRAINT fk_alerta_resolvido_usuario
        FOREIGN KEY (resolvido_por_usuario_id) REFERENCES usuarios (id)
        ON UPDATE CASCADE ON DELETE SET NULL;
    END IF;
  END IF;
END//

DELIMITER ;
CALL fc_migracao_007_alertas();
DROP PROCEDURE fc_migracao_007_alertas;
