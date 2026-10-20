-- Reaplicável em instalações existentes; preserva produtos, lotes e históricos.
-- A categoria combinada não identifica a finalidade de cada produto:
-- seus produtos ficam em Acessórios para posterior revisão pelo cadastro.
START TRANSACTION;

INSERT INTO categorias_produto (nome, descricao)
SELECT 'Alimentos', 'Alimentos, bebidas, doces e itens de conveniência'
WHERE NOT EXISTS (SELECT 1 FROM categorias_produto WHERE nome = 'Alimentos');

-- Preserva o ID da categoria combinada quando Acessórios ainda não existe.
UPDATE categorias_produto antiga
LEFT JOIN categorias_produto destino ON destino.nome = 'Acessórios'
SET antiga.nome = 'Acessórios', antiga.descricao = 'Acessórios e utensílios'
WHERE antiga.nome = 'Acessórios e primeiros socorros' AND destino.id IS NULL;

INSERT INTO categorias_produto (nome, descricao)
SELECT 'Acessórios', 'Acessórios e utensílios'
WHERE NOT EXISTS (SELECT 1 FROM categorias_produto WHERE nome = 'Acessórios');

INSERT INTO categorias_produto (nome, descricao)
SELECT 'Primeiros socorros', 'Materiais de primeiros socorros'
WHERE NOT EXISTS (SELECT 1 FROM categorias_produto WHERE nome = 'Primeiros socorros');

UPDATE produtos p
JOIN categorias_produto antiga ON antiga.id = p.categoria_id
JOIN categorias_produto destino ON destino.nome = CASE antiga.nome
  WHEN 'Bebidas' THEN 'Alimentos'
  WHEN 'Acessórios e primeiros socorros' THEN 'Acessórios' END
SET p.categoria_id = destino.id
WHERE antiga.nome IN ('Bebidas', 'Acessórios e primeiros socorros');

DELETE FROM categorias_produto
WHERE nome IN ('Bebidas', 'Acessórios e primeiros socorros');

UPDATE categorias_produto
SET descricao = 'Alimentos, bebidas, doces e itens de conveniência'
WHERE nome = 'Alimentos';

COMMIT;
