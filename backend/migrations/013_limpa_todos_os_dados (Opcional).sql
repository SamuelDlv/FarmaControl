-- FarmaControl — manutenção 013: limpeza completa dos dados
--
-- ATENÇÃO: este script é irreversível. Execute somente na base que deve ser
-- reiniciada e depois de gerar um backup. Ele preserva a estrutura das tabelas,
-- remove todos os dados operacionais e de usuários e recria os catálogos padrão
-- necessários para que o sistema volte a funcionar.
--
-- Execução manual (exemplo):
--   mysql -u SEU_USUARIO -p farmacontrol < 013_limpa_todos_os_dados.sql
--
-- Não execute este arquivo como parte de uma implantação automática em produção.

-- O Workbench costuma ativar SQL_SAFE_UPDATES e bloquear DELETE sem WHERE.
-- A configuração é válida apenas para esta conexão e é restaurada no fim.
SET @sql_safe_updates_anterior = @@SQL_SAFE_UPDATES;
SET SQL_SAFE_UPDATES = 0;
SET FOREIGN_KEY_CHECKS = 0;

-- Dados dependentes e histórico operacional.
DELETE FROM financeiro_transacoes;
DELETE FROM itens_venda;
DELETE FROM itens_compra;
DELETE FROM receitas_itens;
DELETE FROM receitas;
DELETE FROM movimentacoes_estoque;
DELETE FROM estoque;
DELETE FROM vendas;
DELETE FROM compras;
DELETE FROM alertas;
DELETE FROM convites_cadastro;
DELETE FROM aceites_legais;
DELETE FROM log_acessos;
DELETE FROM analises_cadastro;

-- Cadastros e configurações da instalação anterior.
DELETE FROM produtos;
DELETE FROM clientes;
DELETE FROM fornecedores;
DELETE FROM configuracoes_sistema;
DELETE FROM usuarios;

-- Catálogos serão recriados abaixo com os valores padrão da aplicação.
DELETE FROM perfil_permissoes;
DELETE FROM perfis;
DELETE FROM categorias_produto;
DELETE FROM financeiro_categorias;

-- Reinicia os identificadores das tabelas que possuem AUTO_INCREMENT.
ALTER TABLE financeiro_transacoes AUTO_INCREMENT = 1;
ALTER TABLE itens_venda AUTO_INCREMENT = 1;
ALTER TABLE itens_compra AUTO_INCREMENT = 1;
ALTER TABLE receitas_itens AUTO_INCREMENT = 1;
ALTER TABLE receitas AUTO_INCREMENT = 1;
ALTER TABLE movimentacoes_estoque AUTO_INCREMENT = 1;
ALTER TABLE estoque AUTO_INCREMENT = 1;
ALTER TABLE vendas AUTO_INCREMENT = 1;
ALTER TABLE compras AUTO_INCREMENT = 1;
ALTER TABLE alertas AUTO_INCREMENT = 1;
ALTER TABLE convites_cadastro AUTO_INCREMENT = 1;
ALTER TABLE aceites_legais AUTO_INCREMENT = 1;
ALTER TABLE log_acessos AUTO_INCREMENT = 1;
ALTER TABLE analises_cadastro AUTO_INCREMENT = 1;
ALTER TABLE produtos AUTO_INCREMENT = 1;
ALTER TABLE clientes AUTO_INCREMENT = 1;
ALTER TABLE fornecedores AUTO_INCREMENT = 1;
ALTER TABLE usuarios AUTO_INCREMENT = 1;
ALTER TABLE perfis AUTO_INCREMENT = 1;
ALTER TABLE categorias_produto AUTO_INCREMENT = 1;
ALTER TABLE financeiro_categorias AUTO_INCREMENT = 1;

-- Perfis e permissões padrão.
INSERT INTO perfis (slug, nome, descricao) VALUES
  ('proprietario', 'Proprietário', 'Visão total do negócio: financeiro, relatórios estratégicos e gestão de usuários.'),
  ('farmaceutico', 'Farmacêutico', 'Responsável técnico: controle de estoque, validade e dispensação de controlados.'),
  ('admin', 'Gerente / Administrador', 'Gestão operacional completa: estoque, compras e relatórios de vendas.'),
  ('atendente', 'Atendente / Balconista', 'Frente de loja: consulta de produtos e registro de vendas.'),
  ('visualizador', 'Visualizador', 'Consulta de informações operacionais sem permissões administrativas.'),
  ('compras', 'Responsável por Compras', 'Gestão de suprimentos: pedidos de compra e análise de demanda.'),
  ('ti', 'TI / Suporte', 'Manutenção técnica: logs, configurações de sistema e integrações.');

INSERT INTO perfil_permissoes (perfil_id, modulo, permitido)
SELECT p.id, m.modulo,
  CASE
    WHEN p.slug IN ('proprietario', 'admin', 'ti') THEN 1
    WHEN p.slug = 'farmaceutico' AND m.modulo IN ('dashboard', 'estoque', 'vencimentos', 'relatorios', 'compras') THEN 1
    WHEN p.slug = 'atendente' AND m.modulo IN ('dashboard', 'estoque') THEN 1
    WHEN p.slug = 'visualizador' AND m.modulo IN ('dashboard', 'estoque', 'vencimentos', 'relatorios') THEN 1
    WHEN p.slug = 'compras' AND m.modulo IN ('dashboard', 'estoque', 'vencimentos', 'relatorios', 'compras') THEN 1
    ELSE 0
  END
FROM perfis AS p
CROSS JOIN (
  SELECT 'dashboard' AS modulo UNION ALL SELECT 'estoque' UNION ALL SELECT 'vencimentos'
  UNION ALL SELECT 'relatorios' UNION ALL SELECT 'compras' UNION ALL SELECT 'financeiro'
  UNION ALL SELECT 'usuarios' UNION ALL SELECT 'configuracoes'
) AS m;

-- Categorias padrão de produtos e financeiro.
INSERT INTO categorias_produto (nome, descricao) VALUES
  ('Medicamentos', 'Medicamentos e especialidades farmacêuticas'),
  ('Alimentos', 'Alimentos, bebidas, doces e itens de conveniência'),
  ('Higiene pessoal', 'Cuidados e higiene pessoal'),
  ('Cosméticos e dermocosméticos', 'Cremes, beleza e cuidados com a pele'),
  ('Saúde sexual', 'Preservativos, lubrificantes e cuidados íntimos'),
  ('Infantil e bebê', 'Fraldas e cuidados infantis'),
  ('Suplementos', 'Suplementos alimentares'),
  ('Acessórios', 'Acessórios e utensílios'),
  ('Primeiros socorros', 'Materiais de primeiros socorros'),
  ('Outros produtos', 'Demais produtos do catálogo');

INSERT INTO financeiro_categorias (nome, tipo, slug) VALUES
  ('Venda de Produtos', 'receita', 'venda_medicamentos'),
  ('Serviços Farmacêuticos', 'receita', 'servicos'),
  ('Pagamento de Fornecedores', 'despesa', 'fornecedores'),
  ('Folha de Pagamento', 'despesa', 'salarios'),
  ('Aluguel e Contas', 'despesa', 'fixos'),
  ('Impostos', 'despesa', 'impostos'),
  ('Marketing', 'despesa', 'marketing'),
  ('Outras Receitas', 'receita', 'outros_receita'),
  ('Outras Despesas', 'despesa', 'outros_despesa');

SET FOREIGN_KEY_CHECKS = 1;
SET SQL_SAFE_UPDATES = @sql_safe_updates_anterior;
