-- Completa instalações que já receberam a migração 20261005.
INSERT IGNORE INTO perfil_permissoes (perfil_id, modulo, permitido)
SELECT p.id, m.modulo,
  CASE
    WHEN p.slug = 'admin' THEN 1
    WHEN p.slug = 'farmaceutico' AND m.modulo = 'vendas' THEN 1
    WHEN p.slug = 'atendente' AND m.modulo = 'vendas' THEN 1
    ELSE 0
  END
FROM perfis p
CROSS JOIN (SELECT 'financeiro' AS modulo UNION ALL SELECT 'vendas') AS m
WHERE p.slug IN ('admin', 'farmaceutico', 'atendente', 'visualizador');
