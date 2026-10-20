-- Recupera receitas de vendas concluídas que não têm lançamento vinculado.
-- Reexecutável: preserva lançamentos existentes e a data original da venda.
USE farmacontrol;
START TRANSACTION;
INSERT IGNORE INTO financeiro_categorias (nome,tipo,slug)
VALUES ('Venda de Medicamentos','receita','venda_medicamentos');
INSERT INTO financeiro_transacoes
    (categoria_id,usuario_id,venda_id,descricao,valor,data_transacao,status,metodo_pagamento)
SELECT c.id,v.usuario_id,v.id,CONCAT('Venda #',v.id),v.valor_total,v.data_venda,'pago',v.tipo_pagamento
FROM vendas v
JOIN financeiro_categorias c ON c.slug='venda_medicamentos' AND c.tipo='receita'
WHERE v.status='concluida'
AND NOT EXISTS (SELECT 1 FROM financeiro_transacoes t WHERE t.venda_id=v.id);
COMMIT;
