-- Remove as permissões do módulo descontinuado de Previsão IA.
-- Executar na base existente após as migrações anteriores.
-- Idempotente: não altera permissões de outros módulos nem dados operacionais.
START TRANSACTION;
-- LIMIT permite executar com SQL_SAFE_UPDATES habilitado.
-- perfil_id é TINYINT UNSIGNED e a PK é (perfil_id, modulo):
-- existem no máximo 256 registros para um mesmo módulo.
DELETE FROM perfil_permissoes WHERE modulo = 'previsao' LIMIT 256;
COMMIT;
