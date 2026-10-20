-- Carga MASSIVA OPCIONAL, exclusivamente para desenvolvimento/teste.
-- MySQL 8 / MariaDB. Execute após o schema atual (incluindo migrações 012 e 016).
-- Selecione o banco desejado ANTES de executar; este arquivo não usa USE.
-- MySQL CLI: mysql -u root -p --default-character-set=utf8mb4 farmacontrol
-- Depois: SOURCE backend/migrations/017_popula_farmacia_teste (Opcional).sql;
-- No Workbench, selecione o schema e execute o arquivo completo.
-- Requer CREATE ROUTINE, ALTER ROUTINE e permissões de leitura/escrita.
-- Não execute dentro de outra transação: CREATE/DROP PROCEDURE fazem commit.
-- Não apaga dados existentes. Conflitos abortam TODA a carga (ROLLBACK).
-- A chave seed.farmacia.017 em configuracoes_sistema impede duplicação.
-- Usuários: usuario001@farmacia.example.invalid até usuario028@farmacia.example.invalid.
-- Senha de teste: FarmaciaTeste@2026. O primeiro usuário é proprietário.
-- Contatos e documentos são fictícios; não usar em integrações externas.
-- Padrão: 28 usuários, 20 fornecedores, 500 clientes, 200 produtos, 600 lotes,
-- 800 compras, 6000 vendas com 2 itens, receitas, alertas, logs e financeiro.
-- Datas relativas ao dia da execução; vendas distribuídas pelos últimos 180 dias.
-- Ajuste o volume na chamada final (200 produtos: mínimo 20, máximo 2000;
-- vendas: mínimo 180, máximo 100000). Reexecução não altera a carga existente.


SET NAMES utf8mb4;
DELIMITER $$
DROP PROCEDURE IF EXISTS fc_seed_farmacia_017$$
CREATE PROCEDURE fc_seed_farmacia_017(IN p_produtos INT, IN p_vendas INT)
seed: BEGIN
    DECLARE i, j, k, v_usuario, v_admin, v_comprador, v_cliente INT;
    DECLARE v_produto, v_fornecedor, v_categoria, v_estoque, v_compra, v_venda, v_receita INT;
    DECLARE v_fin_venda, v_fin_compra, v_qtd, v_inicial, v_saldo INT;
    DECLARE v_custo, v_preco, v_total DECIMAL(12,2);
    DECLARE v_perfil VARCHAR(30);
    DECLARE v_nome, v_generico, v_categoria_nome VARCHAR(255);
    DECLARE v_lote VARCHAR(50);
    DECLARE v_status, v_pagamento VARCHAR(30);
    DECLARE v_validade DATE;
    DECLARE v_data DATETIME;
    DECLARE v_base DATETIME;
    DECLARE v_exige, v_medicamento, v_requer BOOLEAN;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    IF p_produtos IS NULL OR p_vendas IS NULL OR p_produtos NOT BETWEEN 20 AND 2000
        OR p_vendas NOT BETWEEN 180 AND 100000 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Volume inválido para a carga 017.';
    END IF;
    START TRANSACTION;
    IF EXISTS (SELECT 1 FROM configuracoes_sistema WHERE chave = 'seed.farmacia.017') THEN
        COMMIT;
        SELECT 'Carga 017 já aplicada; nenhum dado alterado.' AS resultado;
        LEAVE seed;
    END IF;
    -- A chave única também impede duas cargas simultâneas de serem confirmadas.
    INSERT INTO configuracoes_sistema (chave, valor, descricao)
    VALUES ('seed.farmacia.017', CONCAT('produtos=', p_produtos, ';vendas=', p_vendas),
        'Carga fictícia 017 aplicada; não remover esta chave para repetir a carga.');
    IF (SELECT COUNT(*) FROM perfis WHERE slug IN
        ('proprietario','admin','farmaceutico','atendente','compras','ti','visualizador')) <> 7 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Aplique o schema/perfis atuais antes da carga.';
    END IF;
    SET v_base = DATE_SUB(CURDATE(), INTERVAL 190 DAY);
    SET v_fin_venda = (SELECT id FROM financeiro_categorias WHERE slug = 'venda_medicamentos');
    SET v_fin_compra = (SELECT id FROM financeiro_categorias WHERE slug = 'fornecedores');
    IF v_fin_venda IS NULL OR v_fin_compra IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Categorias financeiras obrigatórias ausentes.';
    END IF;

    SET i = 1;
    WHILE i <= 28 DO
        SET v_perfil = ELT(1 + MOD(i-1,7), 'proprietario','admin','farmaceutico','atendente','compras','ti','visualizador');
        INSERT INTO usuarios (nome, sobrenome, email, senha_hash, perfil_id, status, criado_em)
        SELECT ELT(1 + MOD(i-1,7),'Ana','Bruno','Carla','Diego','Elisa','Fabio','Gabriela'),
            CONCAT('Teste ', LPAD(i,3,'0')), CONCAT('usuario',LPAD(i,3,'0'),'@farmacia.example.invalid'),
            '$2b$12$6hTCGoEi8BHJp84nD9L1tufByVbin.IkjBge/lJZUxfId7p7Ce/dK', id,
            CASE WHEN i = 27 THEN 'pendente' WHEN i = 28 THEN 'rejeitado' ELSE 'aprovado' END, v_base
        FROM perfis WHERE slug = v_perfil;
        SET v_usuario = LAST_INSERT_ID();
        IF i = 1 THEN SET v_admin = v_usuario; END IF;
        IF i = 5 THEN SET v_comprador = v_usuario; END IF;
        INSERT INTO aceites_legais (usuario_id, termos_versao, privacidade_versao, aceito_em, ip)
        VALUES (v_usuario, 'teste-017', 'teste-017', v_base, '127.0.0.1');
        IF i <> 27 THEN
            INSERT INTO analises_cadastro (usuario_id, analisado_por, decisao, motivo, analisado_em)
            VALUES (v_usuario, v_admin, IF(i=28,'rejeitado','aprovado'), 'Simulação de cadastro 017', v_base);
        END IF;
        SET i = i + 1;
    END WHILE;

    SET i = 1;
    WHILE i <= 20 DO
        INSERT INTO fornecedores (nome_fantasia, razao_social, cnpj, contato_nome, contato_email, endereco, criado_em)
        VALUES (CONCAT('Distribuidora Teste ', i), CONCAT('SEED017 Distribuidora Farmacêutica ', i, ' Ltda'),
            CONCAT('TESTE017', LPAD(i,6,'0')), CONCAT('Representante ',i),
            CONCAT('fornecedor',i,'@farmacia.example.invalid'), 'Rua Fictícia, 100 - São Paulo/SP', v_base);
        SET i = i + 1;
    END WHILE;
    SET i = 1;
    WHILE i <= 500 DO
        INSERT INTO clientes (nome, sobrenome, email, endereco, data_nascimento, criado_em)
        VALUES (ELT(1+MOD(i,10),'Ana','Carlos','Mariana','João','Beatriz','Pedro','Juliana','Lucas','Helena','Rafael'),
            CONCAT('Cliente Teste ',i), CONCAT('cliente',LPAD(i,4,'0'),'@farmacia.example.invalid'),
            CONCAT('Rua de Teste, ',i,' - São Paulo/SP'), DATE_SUB('2005-01-01', INTERVAL (i*37) DAY), v_base);
        SET i = i + 1;
    END WHILE;

    -- Catálogo: 8 medicamentos e 12 produtos de outras categorias a cada 20 SKUs.
    -- As categorias são resolvidas por nome; nenhum ID fixo é presumido.
    SET i = 1;
    WHILE i <= p_produtos DO
        SET k = 1 + MOD(i-1,20);
        SET v_medicamento = k <= 8;
        SET v_requer = k IN (5,6,7,8);
        SET v_exige = k NOT IN (19,20);
        SET v_nome = ELT(k,'Paracetamol 500 mg','Dipirona 500 mg','Ibuprofeno 200 mg','Loratadina 10 mg',
            'Losartana 50 mg','Metformina 500 mg','Amoxicilina 500 mg','Sinvastatina 20 mg',
            'Barra de cereal','Água mineral 500 ml','Sabonete neutro','Shampoo 200 ml','Protetor solar FPS 50',
            'Hidratante corporal','Preservativos 3 unidades','Fraldas infantis M','Lenços umedecidos',
            'Suplemento alimentar','Termômetro digital','Escova dental');
        SET v_generico = IF(v_medicamento, SUBSTRING_INDEX(v_nome,' ',1), NULL);
        SET v_categoria_nome = CASE
            WHEN k <= 8 THEN 'Medicamentos' WHEN k IN (9,10) THEN 'Alimentos'
            WHEN k IN (11,12,20) THEN 'Higiene pessoal' WHEN k IN (13,14) THEN 'Cosméticos e dermocosméticos'
            WHEN k = 15 THEN 'Saúde sexual' WHEN k IN (16,17) THEN 'Infantil e bebê'
            WHEN k = 18 THEN 'Suplementos' ELSE 'Acessórios' END;
        SET v_categoria = (SELECT id FROM categorias_produto WHERE nome = v_categoria_nome);
        IF v_categoria IS NULL THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Categorias do catálogo ausentes; aplique a migração 012.';
        END IF;
        SET v_fornecedor = (SELECT id FROM fornecedores WHERE cnpj = CONCAT('TESTE017',LPAD(1+MOD(i-1,20),6,'0')));
        SET v_custo = 3 + MOD(i*137,7000)/100;
        SET v_preco = ROUND(v_custo*1.65,2);
        INSERT INTO produtos (nome, tipo_produto, exige_validade, nome_generico, descricao, fabricante,
            preco_custo, preco_venda, codigo_barras, categoria_id, requer_receita, estoque_minimo, fornecedor_id, criado_em)
        VALUES (CONCAT(v_nome,' - Teste ',LPAD(i,4,'0')), IF(v_medicamento,'medicamento','outro'), v_exige,
            v_generico, 'Produto fictício da carga 017; sem finalidade clínica.', CONCAT('Laboratório Teste ',1+MOD(i,12)),
            v_custo, v_preco, CONCAT('SEED017-',LPAD(i,6,'0')), v_categoria, v_requer, 20, v_fornecedor, v_base);
        SET v_produto = LAST_INSERT_ID();
        SET j = 1;
        WHILE j <= 4 DO
            SET v_lote = CONCAT('SEED017-',LPAD(i,4,'0'),'-',j);
            SET v_validade = IF(NOT v_exige, NULL, DATE_ADD(CURDATE(), INTERVAL
                (CASE j WHEN 1 THEN 365 WHEN 2 THEN 15+MOD(i,60) ELSE -1-MOD(i,30) END) DAY));
            -- Lote principal suporta qualquer volume permitido; demais testam vencimentos.
            SET v_inicial = IF(j=1, CEIL(p_vendas/p_produtos)*12+100, 10+MOD(i,15));
            SET v_status = IF(j<=3,'recebido',IF(MOD(i,2)=0,'pendente','cancelado'));
            SET v_data = IF(j<=3, DATE_ADD(v_base, INTERVAL j DAY), DATE_SUB(CURDATE(), INTERVAL 2 DAY));
            INSERT INTO compras (fornecedor_id, usuario_id, data_pedido, data_recebimento, valor_total, status, criado_em)
            VALUES (v_fornecedor, v_comprador, v_data, IF(j<=3,DATE_ADD(v_data, INTERVAL 1 DAY),NULL),
                v_custo*v_inicial, v_status, v_data);
            SET v_compra = LAST_INSERT_ID();
            INSERT INTO itens_compra (compra_id, produto_id, quantidade, preco_unitario, lote_recebido, data_validade_recebida)
            VALUES (v_compra,v_produto,v_inicial,v_custo,IF(j<=3,v_lote,NULL),IF(j<=3,v_validade,NULL));
            INSERT INTO financeiro_transacoes (categoria_id, usuario_id, compra_id, descricao, valor, data_transacao,
                status, metodo_pagamento, criado_em)
            VALUES (v_fin_compra,v_comprador,v_compra,CONCAT('SEED017 Compra #',v_compra),v_custo*v_inicial,v_data,
                IF(j<=3,'pago',IF(v_status='pendente','pendente','cancelado')),'boleto',v_data);
            IF j <= 3 THEN
                INSERT INTO estoque (produto_id,lote,quantidade,data_validade,localizacao,criado_em)
                VALUES (v_produto,v_lote,v_inicial,v_validade,IF(j=3 AND v_exige,'Quarentena - teste',CONCAT('Prateleira ',1+MOD(i,20))),
                    DATE_ADD(v_data,INTERVAL 1 DAY));
                SET v_estoque = LAST_INSERT_ID();
                INSERT INTO movimentacoes_estoque (estoque_id,usuario_id,tipo_movimentacao,quantidade,observacao,data_movimentacao)
                VALUES (v_estoque,v_comprador,'entrada',v_inicial,CONCAT('SEED017 Recebimento da compra #',v_compra),DATE_ADD(v_data,INTERVAL 1 DAY));
            END IF;
            SET j = j + 1;
        END WHILE;
        SET i = i + 1;
    END WHILE;

    SET i = 1;
    WHILE i <= p_vendas DO
        SET v_data = DATE_SUB(CURDATE(), INTERVAL (179-FLOOR((i-1)*180/p_vendas)) DAY);
        SET v_cliente = (SELECT id FROM clientes WHERE email = CONCAT('cliente',LPAD(1+MOD(i-1,500),4,'0'),'@farmacia.example.invalid'));
        SET v_usuario = (SELECT id FROM usuarios WHERE email = CONCAT('usuario',LPAD(4+7*MOD(i,3),3,'0'),'@farmacia.example.invalid'));
        SET v_status = CASE WHEN MOD(i,20)=0 THEN 'cancelada' WHEN MOD(i,17)=0 THEN 'pendente' ELSE 'concluida' END;
        SET v_pagamento = ELT(1+MOD(i,4),'dinheiro','cartao_credito','cartao_debito','pix');
        INSERT INTO vendas (cliente_id,usuario_id,data_venda,valor_total,tipo_pagamento,status,criado_em)
        VALUES (v_cliente,v_usuario,v_data,0,v_pagamento,v_status,v_data);
        SET v_venda = LAST_INSERT_ID();
        SET v_total = 0;
        SET j = 1;
        WHILE j <= 2 DO
            SET k = 1 + MOD(i+j*37-2,p_produtos);
            SELECT id,preco_venda,requer_receita INTO v_produto,v_preco,v_requer
                FROM produtos WHERE codigo_barras = CONCAT('SEED017-',LPAD(k,6,'0'));
            SET v_lote = CONCAT('SEED017-',LPAD(k,4,'0'),'-1');
            SET v_qtd = 1+MOD(i+j,3);
            INSERT INTO itens_venda (venda_id,produto_id,quantidade,preco_unitario,desconto,lote_vendido)
            VALUES (v_venda,v_produto,v_qtd,v_preco,0,v_lote);
            SET v_total = v_total + v_preco*v_qtd;
            IF v_status = 'concluida' THEN
                SELECT id,quantidade INTO v_estoque,v_saldo FROM estoque WHERE produto_id=v_produto AND lote=v_lote;
                IF v_saldo < v_qtd THEN
                    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Saldo insuficiente na simulação; carga revertida.';
                END IF;
                UPDATE estoque SET quantidade = quantidade-v_qtd WHERE id=v_estoque;
                INSERT INTO movimentacoes_estoque (estoque_id,usuario_id,tipo_movimentacao,quantidade,observacao,data_movimentacao)
                VALUES (v_estoque,v_usuario,'saida',v_qtd,CONCAT('SEED017 Venda #',v_venda),v_data);
                IF v_requer THEN
                    INSERT INTO receitas (cliente_id,medico_nome,crm,data_prescricao,data_validade,observacoes,criado_em)
                    VALUES (v_cliente,'Profissional Fictício','TESTE-017',DATE_SUB(v_data,INTERVAL 1 DAY),
                        DATE_ADD(v_data,INTERVAL 29 DAY),CONCAT('Simulação sem validade clínica. Venda #',v_venda),v_data);
                    SET v_receita = LAST_INSERT_ID();
                    INSERT INTO receitas_itens (receita_id,produto_id,quantidade,instrucoes_uso)
                    VALUES (v_receita,v_produto,v_qtd,'Registro fictício para testes; não utilizar como orientação de uso.');
                END IF;
            END IF;
            SET j = j + 1;
        END WHILE;
        UPDATE vendas SET valor_total=v_total WHERE id=v_venda;
        INSERT INTO financeiro_transacoes (categoria_id,usuario_id,venda_id,descricao,valor,data_transacao,status,metodo_pagamento,criado_em)
        VALUES (v_fin_venda,v_usuario,v_venda,CONCAT('SEED017 Venda #',v_venda),v_total,v_data,
            CASE v_status WHEN 'concluida' THEN 'pago' WHEN 'cancelada' THEN 'cancelado' ELSE 'pendente' END,v_pagamento,v_data);
        INSERT INTO log_atividades (usuario_id,usuario_nome,perfil,acao,detalhes,status_http,criado_em)
        SELECT id,CONCAT(nome,' ',sobrenome),'atendente','Simulação de venda',CONCAT('SEED017 Venda #',v_venda),201,v_data
        FROM usuarios WHERE id=v_usuario;
        SET i = i + 1;
    END WHILE;

    -- Consumo/perdas de alguns SKUs deixa casos reais de ruptura e estoque baixo.
    -- Toda redução tem saída correspondente: saldo = entradas - saídas.
    INSERT INTO movimentacoes_estoque (estoque_id,usuario_id,tipo_movimentacao,quantidade,observacao,data_movimentacao)
    SELECT e.id,v_admin,'saida',e.quantidade-IF(e.lote LIKE '%-1',MOD(CAST(SUBSTRING(p.codigo_barras,9) AS UNSIGNED) DIV 10,2)*5,0),
        'SEED017 Baixa simulada por avaria/inventário',CURDATE()
    FROM estoque e JOIN produtos p ON p.id=e.produto_id
    WHERE p.codigo_barras LIKE 'SEED017-%' AND MOD(CAST(SUBSTRING(p.codigo_barras,9) AS UNSIGNED),10)=0;
    UPDATE estoque e JOIN produtos p ON p.id=e.produto_id
    SET e.quantidade=IF(e.lote LIKE '%-1',MOD(CAST(SUBSTRING(p.codigo_barras,9) AS UNSIGNED) DIV 10,2)*5,0)
    WHERE p.codigo_barras LIKE 'SEED017-%' AND MOD(CAST(SUBSTRING(p.codigo_barras,9) AS UNSIGNED),10)=0;
    INSERT INTO alertas (tipo_alerta,referencia_id,mensagem,status)
    SELECT 'vencimento',e.id,CONCAT('SEED017 ',p.nome,' / ',e.lote,' vence em ',e.data_validade),'ativo'
    FROM estoque e JOIN produtos p ON p.id=e.produto_id
    WHERE p.codigo_barras LIKE 'SEED017-%' AND e.quantidade>0 AND e.data_validade<=DATE_ADD(CURDATE(),INTERVAL 60 DAY);
    INSERT INTO alertas (tipo_alerta,referencia_id,mensagem,status)
    SELECT 'estoque_baixo',p.id,CONCAT('SEED017 Repor ',p.nome),'ativo'
    FROM produtos p JOIN estoque e ON e.produto_id=p.id WHERE p.codigo_barras LIKE 'SEED017-%'
    GROUP BY p.id,p.nome,p.estoque_minimo HAVING SUM(e.quantidade)<p.estoque_minimo;

    -- Seis meses de despesas operacionais, serviços e aporte inicial.
    SET i = 0;
    WHILE i < 6 DO
        SET v_data = DATE_SUB(CURDATE(),INTERVAL i MONTH);
        INSERT INTO financeiro_transacoes (categoria_id,usuario_id,descricao,valor,data_transacao,status,metodo_pagamento,criado_em)
        SELECT id,v_admin,CONCAT('SEED017 ',nome,' / mês ',i),
            CASE slug WHEN 'salarios' THEN 18500 WHEN 'fixos' THEN 4800 WHEN 'impostos' THEN 2100
                WHEN 'marketing' THEN 850 ELSE 1700 END,v_data,IF(i=0 AND tipo='despesa','pendente','pago'),'transferencia',v_data
        FROM financeiro_categorias WHERE slug IN ('salarios','fixos','impostos','marketing','servicos');
        SET i = i + 1;
    END WHILE;
    INSERT INTO financeiro_transacoes (categoria_id,usuario_id,descricao,valor,data_transacao,status,metodo_pagamento,criado_em)
    SELECT id,v_admin,'SEED017 Aporte inicial de capital',500000,v_base,'pago','transferencia',v_base
    FROM financeiro_categorias WHERE slug='outros_receita';
    INSERT INTO log_acessos (usuario_id,ip,user_agent,sucesso,criado_em)
    SELECT u.id,'127.0.0.1','SEED017 Navegador de teste',1,DATE_SUB(CURDATE(),INTERVAL d.n DAY)
    FROM usuarios u CROSS JOIN (SELECT 0 n UNION ALL SELECT 1 UNION ALL SELECT 7 UNION ALL SELECT 30) d
    WHERE u.email LIKE 'usuario%@farmacia.example.invalid' AND u.status='aprovado';
    UPDATE usuarios u SET ultimo_login=CURDATE()
    WHERE u.email LIKE 'usuario%@farmacia.example.invalid' AND u.status='aprovado';
    COMMIT;
    SELECT 'Carga 017 concluída' AS resultado, p_produtos AS produtos, p_produtos*3 AS lotes,
        p_produtos*4 AS compras, p_vendas AS vendas, p_vendas*2 AS itens_venda;
END$$
CALL fc_seed_farmacia_017(200, 6000)$$
DROP PROCEDURE fc_seed_farmacia_017$$
DELIMITER ;
