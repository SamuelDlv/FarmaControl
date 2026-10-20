-- FarmaControl — manutenção 014: usuário de teste aprovado
--
-- Cria ou atualiza teste@gmail.com com a senha 123467 e acesso de proprietário.
-- Execute manualmente somente em ambiente de desenvolvimento/teste.
-- Troque a senha ou remova este usuário antes de usar uma base em produção.

INSERT INTO usuarios (nome, sobrenome, email, senha_hash, perfil_id, status)
SELECT
  'Usuário',
  'Teste',
  'teste@gmail.com',
  '$2b$12$lGDWdL92EMujlAN63DZMcOz6kKGZCVjEKSKahvlFt1Q2Nnmb3RZ8G',
  perfis.id,
  'aprovado'
FROM perfis
WHERE perfis.slug = 'proprietario'
ON DUPLICATE KEY UPDATE
  nome = 'Usuário',
  sobrenome = 'Teste',
  senha_hash = '$2b$12$lGDWdL92EMujlAN63DZMcOz6kKGZCVjEKSKahvlFt1Q2Nnmb3RZ8G',
  perfil_id = (SELECT id FROM perfis WHERE slug = 'proprietario'),
  status = 'aprovado',
  token_reset = NULL,
  token_expira_em = NULL;
