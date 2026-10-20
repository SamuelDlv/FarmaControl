-- Limpeza opcional de preferências aposentadas. Requer a migração 007.
-- Revise/aplique na instância escolhida; a aplicação já ignora essas chaves.
-- Remove somente as duas preferências sem uso, preservando cor e densidade.
START TRANSACTION;
DELETE FROM configuracoes_sistema
WHERE chave IN ('tema', 'tema_efetivo');
COMMIT;
