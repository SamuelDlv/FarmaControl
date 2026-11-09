-- Opcional: executar como administrador após schema.sql, em servidor saudável.
-- MySQL 8+ / MariaDB 10.4+. Não cria usuários nem atribui roles.
-- Os perfis funcionais da aplicação independem destas roles técnicas.
USE farmacontrol;

CREATE ROLE IF NOT EXISTS
  'fc_runtime_rw',
  'fc_schema_deployer',
  'fc_support_ro',
  'fc_database_admin';

-- Backend: manipula dados e executa rotinas, sem poder alterar o schema.
GRANT SELECT, INSERT, UPDATE, DELETE, EXECUTE
  ON farmacontrol.* TO 'fc_runtime_rw';

-- Deploy/migrações: altera objetos somente dentro do banco FarmaControl.
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP, INDEX, REFERENCES,
      CREATE VIEW, SHOW VIEW, TRIGGER, EVENT, CREATE ROUTINE, ALTER ROUTINE, EXECUTE
  ON farmacontrol.* TO 'fc_schema_deployer';

-- Suporte: diagnóstico sem alteração de dados.
GRANT SELECT, SHOW VIEW
  ON farmacontrol.* TO 'fc_support_ro';

-- Administração do banco da aplicação, com delegação controlada pela TI.
GRANT ALL PRIVILEGES
  ON farmacontrol.* TO 'fc_database_admin' WITH GRANT OPTION;

