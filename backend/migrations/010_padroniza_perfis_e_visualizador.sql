-- Cria o cargo que não existia em instalações antigas antes de padronizar
-- todos os cargos na matriz de módulos exibidos pela tela Usuários.
INSERT IGNORE INTO perfis (slug, nome, descricao)
VALUES (
  'visualizador',
  'Visualizador',
  'Consulta de informações operacionais sem permissões administrativas.'
);

-- INSERT IGNORE preserva personalizações já gravadas para os quatro cargos
-- anteriormente editáveis e adiciona a matriz aos demais cargos.
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
  SELECT 'dashboard' AS modulo UNION ALL SELECT 'estoque' UNION ALL SELECT 'vencimentos'
  UNION ALL SELECT 'relatorios' UNION ALL SELECT 'compras' UNION ALL SELECT 'financeiro'
  UNION ALL SELECT 'usuarios' UNION ALL SELECT 'configuracoes'
) AS m
WHERE p.slug IN ('proprietario', 'admin', 'farmaceutico', 'atendente', 'visualizador', 'compras', 'ti');
