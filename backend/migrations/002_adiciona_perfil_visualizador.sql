-- Migração 002: Adiciona o perfil "Visualizador" (consulta apenas)
-- Necessário para a página de Usuários do proprietário.
INSERT INTO perfis (slug, nome, descricao) VALUES
  ('visualizador', 'Visualizador', 'Acesso somente leitura: consulta de dashboard, estoque e relatórios.')
ON DUPLICATE KEY UPDATE nome = VALUES(nome), descricao = VALUES(descricao);
