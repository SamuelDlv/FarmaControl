-- Migração 008: fluxo de convite administrativo com aceite legal do destinatário.
-- Execute após 007: mysql -uroot farmacontrol < 008_convites_cadastro.sql

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
