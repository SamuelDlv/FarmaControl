-- FarmaControl: roles técnicas do MySQL para a equipe de TI.
-- Execute com uma conta que possua CREATE ROLE e permissão de GRANT.
-- Não cria usuários, não define senhas e não atribui as roles a ninguém.
-- Os perfis funcionais da aplicação permanecem nas tabelas perfis e
-- perfil_permissoes; estas roles controlam apenas o acesso ao banco.

CREATE ROLE IF NOT EXISTS
  'fc_runtime_rw',
  'fc_schema_deployer',
  'fc_support_ro',
  'fc_database_admin';

-- Conta de execução do backend: dados e rotinas, sem DDL.
GRANT SELECT, INSERT, UPDATE, DELETE, EXECUTE
  ON farmacontrol.* TO 'fc_runtime_rw';

-- Conta/pipeline de deploy: aplica migrations e administra objetos do schema.
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP, INDEX, REFERENCES,
      CREATE VIEW, SHOW VIEW, TRIGGER, EVENT, CREATE ROUTINE, ALTER ROUTINE, EXECUTE
  ON farmacontrol.* TO 'fc_schema_deployer';

-- Diagnóstico e auditoria técnica sem escrita.
GRANT SELECT, SHOW VIEW
  ON farmacontrol.* TO 'fc_support_ro';

-- Administração delegável exclusivamente dentro do banco FarmaControl.
GRANT ALL PRIVILEGES
  ON farmacontrol.* TO 'fc_database_admin' WITH GRANT OPTION;
