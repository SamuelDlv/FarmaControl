-- FarmaControl: permissões configuráveis por perfil
-- Aplicação segura em bases já existentes (MySQL 8+).

CREATE TABLE IF NOT EXISTS perfil_permissoes (
  perfil_id TINYINT UNSIGNED NOT NULL,
  modulo VARCHAR(40) NOT NULL,
  permitido TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (perfil_id, modulo),
  CONSTRAINT fk_perfil_permissao_perfil
    FOREIGN KEY (perfil_id) REFERENCES perfis(id)
    ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Insere apenas permissões ainda inexistentes; não altera personalizações já feitas.
INSERT IGNORE INTO perfil_permissoes (perfil_id, modulo, permitido)
SELECT p.id, m.modulo,
  CASE
    WHEN p.slug = 'admin' THEN 1
    WHEN p.slug = 'farmaceutico' AND m.modulo IN ('dashboard','estoque','vencimentos','relatorios','compras','vendas') THEN 1
    WHEN p.slug = 'atendente' AND m.modulo IN ('dashboard','estoque','vendas') THEN 1
    WHEN p.slug = 'visualizador' AND m.modulo IN ('dashboard','estoque','vencimentos','relatorios') THEN 1
    ELSE 0
  END
FROM perfis p
CROSS JOIN (
  SELECT 'dashboard' AS modulo UNION ALL SELECT 'estoque' UNION ALL SELECT 'vencimentos' UNION ALL SELECT 'relatorios'
  UNION ALL SELECT 'compras' UNION ALL SELECT 'financeiro' UNION ALL SELECT 'vendas' UNION ALL SELECT 'usuarios' UNION ALL SELECT 'configuracoes'
) AS m
WHERE p.slug IN ('admin', 'farmaceutico', 'atendente', 'visualizador');
