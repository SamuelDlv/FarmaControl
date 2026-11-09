# Guia de manutenção — Coordena venda, baixa por lote e receita financeira, incluindo o PDV de balcão.
# Consulte docs/DESENVOLVIMENTO.md para executar as verificações desta camada.
"""routes.vendas: responsabilidades extraídas da aplicação Flask."""

from decimal import Decimal
from decimal import InvalidOperation
from farmacontrol.core import database
from farmacontrol.core import responses
from farmacontrol.services.audit import commit_audit
from farmacontrol.services.system_settings import read_settings
from farmacontrol.services.system_settings import require_usable_stock
from flask import g
from flask import request
import logging
import pymysql.cursors

log = logging.getLogger("farmacontrol")


# Consulta vendas.
def get_vendas():
    # Dependências SQL com nome literal nas consultas deste fluxo:
    # clientes, usuarios, vendas.
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT v.*, c.nome as cliente_nome, u.nome as usuario_nome FROM vendas v LEFT JOIN clientes c ON v.cliente_id = c.id LEFT JOIN usuarios u ON v.usuario_id = u.id")
            vendas = cur.fetchall()
        return responses.ok({"vendas": vendas})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar vendas: %s", exc)
        return responses.err("Erro interno ao buscar vendas.", status=500)


# Consulta comercial independente da permissão de edição de estoque.
def catalogo_pdv():
    """Consulta comercial independente da permissão de edição de estoque."""
    # Dependências SQL com nome literal nas consultas deste fluxo:
    # categorias_produto, estoque, produtos.
    try:
        with database.get_db().cursor() as cur:
            cur.execute("""SELECT p.id AS produto_id, p.nome, p.nome_generico,
                p.nome_generico AS principio_ativo,
                p.fabricante, p.codigo_barras, p.tipo_produto, p.requer_receita,
                p.preco_venda, c.nome AS categoria, e.id AS estoque_id,
                e.lote, e.quantidade, e.data_validade,
                (e.data_validade IS NULL OR e.data_validade >= CURDATE()) AS valido
                FROM produtos p LEFT JOIN categorias_produto c ON c.id=p.categoria_id
                LEFT JOIN estoque e ON e.produto_id=p.id WHERE p.ativo=1
                ORDER BY p.nome, e.data_validade""")
            rows = cur.fetchall()
        for row in rows:
            row['preco_venda'] = str(row['preco_venda'])
            if row.get('data_validade'):
                row['data_validade'] = row['data_validade'].isoformat()
        return responses.ok({'produtos': rows})
    except pymysql.MySQLError:
        return responses.err('Não foi possível consultar o catálogo.', status=503)


# Valida o pedido antes de gravar e reconsulta preço, receita e saldo sob bloqueio.
# Venda, itens, baixa, movimentação, financeiro e auditoria precisam confirmar em conjunto.
# Recebe os campos do JSON da requisição; as validações abaixo definem o contrato aceito.
# A confirmação passa por commit_audit para manter a alteração e seu histórico juntos.
def concluir_pdv():
    """Saldo, preço, receita e financeiro validados na mesma transação."""
    # Chaves lidas do JSON neste fluxo (obrigatoriedade validada abaixo):
    # itens, receita_conferida, tipo_pagamento.
    # Dependências SQL com nome literal nas consultas deste fluxo:
    # estoque, financeiro_categorias, financeiro_transacoes, itens_venda, movimentacoes_estoque, produtos.
    # vendas.
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return responses.err('Venda inválida.')
    items = data.get('itens')
    payment = data.get('tipo_pagamento')
    if payment not in {'dinheiro', 'pix', 'cartao_credito', 'cartao_debito'}:
        return responses.err('Selecione a forma de pagamento.')
    if not isinstance(items, list) or not 1 <= len(items) <= 100:
        return responses.err('Adicione de 1 a 100 lotes à venda.')
    seen = set()
    for item in items:
        if (not isinstance(item, dict) or type(item.get('estoque_id')) is not int
                or type(item.get('quantidade')) is not int
                or not 1 <= item['quantidade'] <= 100000
                or item['estoque_id'] in seen):
            return responses.err('Quantidade ou lote inválido/duplicado.')
        seen.add(item['estoque_id'])
    db = database.get_db()
    try:
        with db.cursor() as cur:
            validated, total = [], Decimal('0.00')
            # Uma ordem estável reduz ciclos de espera entre duas vendas que usam
            # os mesmos lotes. FOR UPDATE mantém cada saldo protegido até o commit.
            for item in sorted(items, key=lambda value: value['estoque_id']):
                cur.execute("""SELECT e.*, p.nome, p.preco_venda, p.requer_receita,
                    (e.data_validade IS NULL OR e.data_validade >= CURDATE()) AS valido
                    FROM estoque e JOIN produtos p ON p.id=e.produto_id
                    WHERE e.id=%s FOR UPDATE""", (item['estoque_id'],))
                row = cur.fetchone()
                if not row or not row['valido'] or row['quantidade'] < item['quantidade']:
                    raise ValueError('Saldo indisponível ou lote vencido. Atualize o catálogo e revise a venda.')
                price = Decimal(str(row['preco_venda']))
                # O preço enviado pela tela é uma cotação, não a fonte de verdade.
                # A divergência obriga a atualizar o catálogo antes de confirmar.
                quoted = Decimal(str(item.get('preco_unitario', 'NaN')))
                if not price.is_finite() or price <= 0 or not quoted.is_finite() or quoted != price:
                    raise ValueError('O preço mudou ou está inválido. Atualize o catálogo e revise a venda.')
                if row['requer_receita'] and data.get('receita_conferida') is not True:
                    raise ValueError('Confirme a conferência da receita antes de concluir.')
                total += price * item['quantidade']
                validated.append((row, item['quantidade'], price))
            if total > Decimal('9999999999.99'):
                raise ValueError('Total acima do limite permitido.')
            cur.execute("SELECT id FROM financeiro_categorias WHERE slug='venda_medicamentos' AND tipo='receita'")
            category = cur.fetchone()
            if not category:
                raise ValueError('Categoria financeira de vendas não configurada.')
            cur.execute("""INSERT INTO vendas (usuario_id, valor_total, tipo_pagamento, status)
                VALUES (%s,%s,%s,'concluida')""", (g.usuario_id, total, payment))
            # Capture o ID do cabeçalho agora: os INSERTs de itens e movimentos
            # alteram lastrowid e não podem substituir a referência da venda.
            sale_id = cur.lastrowid
            for row, qty, price in validated:
                cur.execute('UPDATE estoque SET quantidade=quantidade-%s WHERE id=%s', (qty, row['id']))
                cur.execute("""INSERT INTO itens_venda
                    (venda_id,produto_id,quantidade,preco_unitario,desconto,lote_vendido)
                    VALUES (%s,%s,%s,%s,0,%s)""", (sale_id,row['produto_id'],qty,price,row['lote']))
                cur.execute("""INSERT INTO movimentacoes_estoque
                    (estoque_id,usuario_id,tipo_movimentacao,quantidade,observacao,finalidade)
                    VALUES (%s,%s,'saida',%s,%s,'venda')""", (row['id'],g.usuario_id,qty,f'Venda PDV {sale_id}'))
            cur.execute("""INSERT INTO financeiro_transacoes
                (categoria_id,usuario_id,venda_id,descricao,valor,status,metodo_pagamento)
                VALUES (%s,%s,%s,%s,%s,'pago',%s)""",
                (category['id'],g.usuario_id,sale_id,f'Venda PDV {sale_id}',total,payment))
            g.audit_values = {"status": "concluida", "valor_total": str(total), "itens": [
                {"produto_id": row["produto_id"], "estoque_id": row["id"],
                 "quantidade": qty, "preco_unitario": str(price), "lote_vendido": row["lote"]}
                for row, qty, price in validated]}
            commit_audit(db, sale_id)
        return responses.ok({'id': sale_id, 'valor_total': str(total)}, status=201)
    except (ValueError, InvalidOperation) as exc:
        # Desfaz as gravações ainda não confirmadas desta operação antes de responder à falha.
        db.rollback()
        return responses.err(str(exc) if isinstance(exc, ValueError) else 'Preço inválido.', status=409)
    except pymysql.MySQLError:
        # Desfaz as gravações ainda não confirmadas desta operação antes de responder à falha.
        db.rollback()
        log.exception('Falha ao concluir PDV')
        return responses.err('Não foi possível concluir a venda.', status=503)


# Consulta venda.
def get_venda(venda_id):
    # Dependências SQL com nome literal nas consultas deste fluxo:
    # clientes, usuarios, vendas.
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT v.*, c.nome as cliente_nome, u.nome as usuario_nome FROM vendas v LEFT JOIN clientes c ON v.cliente_id = c.id LEFT JOIN usuarios u ON v.usuario_id = u.id WHERE v.id = %s", (venda_id,))
            venda = cur.fetchone()
            if not venda:
                return responses.err("Venda não encontrada.", status=404)
        return responses.ok({"venda": venda})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar venda: %s", exc)
        return responses.err("Erro interno ao buscar venda.", status=500)


# Atualiza a receita existente e insere somente se ainda não houver vínculo.
# Usa o cursor da venda: não confirmar uma transação financeira separada aqui.
def sync_venda_financeiro(cur, venda_id):
    """Mantém a receita vinculada na mesma transação da venda (inclusive na API antiga)."""
    # Dependências SQL com nome literal nas consultas deste fluxo:
    # financeiro_categorias, financeiro_transacoes, vendas.
    cur.execute("SELECT id FROM financeiro_categorias WHERE slug='venda_medicamentos' AND tipo='receita'")
    category = cur.fetchone()
    if not category:
        raise ValueError('Categoria financeira de vendas não configurada.')
    cur.execute("""UPDATE financeiro_transacoes t JOIN vendas v ON v.id=t.venda_id
        SET t.valor=v.valor_total, t.metodo_pagamento=v.tipo_pagamento,
            t.status=CASE v.status WHEN 'concluida' THEN 'pago'
                WHEN 'cancelada' THEN 'cancelado' ELSE 'pendente' END,
            t.data_transacao=CASE WHEN v.status='concluida' THEN v.data_venda ELSE t.data_transacao END
        WHERE v.id=%s""", (venda_id,))
    cur.execute("""INSERT INTO financeiro_transacoes
        (categoria_id,usuario_id,venda_id,descricao,valor,data_transacao,status,metodo_pagamento)
        SELECT %s,v.usuario_id,v.id,CONCAT('Venda #',v.id),v.valor_total,v.data_venda,
            CASE v.status WHEN 'concluida' THEN 'pago'
                WHEN 'cancelada' THEN 'cancelado' ELSE 'pendente' END,v.tipo_pagamento
        FROM vendas v WHERE v.id=%s AND NOT EXISTS
            (SELECT 1 FROM financeiro_transacoes t WHERE t.venda_id=v.id)""",
        (category['id'], venda_id))


# Cadastra venda.
# Recebe os campos do JSON da requisição; as validações abaixo definem o contrato aceito.
# A confirmação passa por commit_audit para manter a alteração e seu histórico juntos.
def create_venda():
    # Chaves lidas do JSON neste fluxo (obrigatoriedade validada abaixo):
    # cliente_id, itens, status, tipo_pagamento, valor_total.
    # Dependências SQL com nome literal nas consultas deste fluxo:
    # clientes, estoque, itens_venda, movimentacoes_estoque, produtos, vendas.
    data = request.get_json(silent=True) or {}
    cliente_id = data.get("cliente_id")
    usuario_id = g.usuario_id
    valor_total = data.get("valor_total")
    tipo_pagamento = data.get("tipo_pagamento")
    status = data.get("status", "pendente")
    itens = data.get("itens", []) # Lista de dicionários com produto_id, quantidade, preco_unitario, desconto, lote_vendido

    if not valor_total or not tipo_pagamento:
        return responses.err("Valor total e tipo de pagamento são obrigatórios.", status=400)
    if valor_total <= 0:
        return responses.err("Valor total deve ser maior que zero.", status=400)
    if tipo_pagamento not in ["dinheiro", "cartao_credito", "cartao_debito", "pix"]:
        return responses.err("Tipo de pagamento inválido.", status=400)
    if status not in ["concluida", "cancelada", "pendente"]:
        return responses.err("Status de venda inválido.", status=400)

    db = database.get_db()
    try:
        with db.cursor() as cur:
            if cliente_id:
                cur.execute("SELECT id FROM clientes WHERE id = %s", (cliente_id,))
                if not cur.fetchone():
                    return responses.err("Cliente não encontrado.", campo="cliente_id", status=400)

            cur.execute(
                """
                INSERT INTO vendas (cliente_id, usuario_id, valor_total, tipo_pagamento, status)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (cliente_id, usuario_id, valor_total, tipo_pagamento, status)
            )
            venda_id = cur.lastrowid

            for item in itens:
                produto_id = item.get("produto_id")
                quantidade = item.get("quantidade")
                preco_unitario = item.get("preco_unitario")
                desconto = item.get("desconto", 0.00)
                lote_vendido = (item.get("lote_vendido") or "").strip() or "SEM-LOTE"

                if not produto_id or not quantidade or not preco_unitario:
                    # Desfaz as gravações ainda não confirmadas desta operação antes de responder à falha.
                    db.rollback()
                    return responses.err("Dados incompletos para item de venda.", status=400)

                cur.execute("SELECT id FROM produtos WHERE id = %s", (produto_id,))
                if not cur.fetchone():
                    # Desfaz as gravações ainda não confirmadas desta operação antes de responder à falha.
                    db.rollback()
                    return responses.err(f"Produto com ID {produto_id} não encontrado.", status=400)

                # Verifica e atualiza estoque
                if status == "concluida":
                    cur.execute("SELECT id, quantidade, lote, data_validade FROM estoque WHERE produto_id = %s AND lote = %s FOR UPDATE", (produto_id, lote_vendido))
                    estoque_item = cur.fetchone()
                    if not estoque_item or estoque_item["quantidade"] < quantidade:
                        # Desfaz as gravações ainda não confirmadas desta operação antes de responder à falha.
                        db.rollback()
                        return responses.err(f"Estoque insuficiente para o produto {produto_id} no lote {lote_vendido}.", status=400)

                    require_usable_stock(read_settings(cur), estoque_item)
                    cur.execute("UPDATE estoque SET quantidade = quantidade - %s WHERE id = %s", (quantidade, estoque_item["id"]))
                    # Registrar movimentação de estoque
                    cur.execute(
                        """
                        INSERT INTO movimentacoes_estoque (estoque_id, usuario_id, tipo_movimentacao, quantidade, observacao, finalidade)
                        VALUES (%s, %s, %s, %s, %s, 'venda')
                        """,
                        (estoque_item["id"], usuario_id, "saida", quantidade, f"Saída por venda {venda_id}")
                    )

                cur.execute(
                    """
                    INSERT INTO itens_venda (venda_id, produto_id, quantidade, preco_unitario, desconto, lote_vendido)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (venda_id, produto_id, quantidade, preco_unitario, desconto, lote_vendido)
                )

            sync_venda_financeiro(cur, venda_id)
            g.audit_values = {"status": status}
            commit_audit(db, venda_id)
            return responses.ok({"mensagem": "Venda criada com sucesso.", "id": venda_id}, status=201)
    except ValueError as exc:
        # Desfaz as gravações ainda não confirmadas desta operação antes de responder à falha.
        db.rollback()
        return responses.err(str(exc), status=400)
    except pymysql.MySQLError as exc:
        # Desfaz as gravações ainda não confirmadas desta operação antes de responder à falha.
        db.rollback()
        log.error("Erro DB ao criar venda: %s", exc)
        return responses.err("Erro interno ao criar venda.", status=500)


# Atualiza venda.
# Recebe os campos do JSON da requisição; as validações abaixo definem o contrato aceito.
# A confirmação passa por commit_audit para manter a alteração e seu histórico juntos.
def update_venda(venda_id):
    # Chaves lidas do JSON neste fluxo (obrigatoriedade validada abaixo):
    # cliente_id, status, tipo_pagamento, valor_total.
    # Dependências SQL com nome literal nas consultas deste fluxo:
    # clientes, estoque, itens_venda, movimentacoes_estoque, vendas.
    data = request.get_json(silent=True) or {}
    cliente_id = data.get("cliente_id")
    usuario_id = g.usuario_id
    valor_total = data.get("valor_total")
    tipo_pagamento = data.get("tipo_pagamento")
    status = data.get("status")

    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id, status FROM vendas WHERE id = %s FOR UPDATE", (venda_id,))
            venda_existente = cur.fetchone()
            if not venda_existente:
                return responses.err("Venda não encontrada.", status=404)

            if cliente_id:
                cur.execute("SELECT id FROM clientes WHERE id = %s", (cliente_id,))
                if not cur.fetchone():
                    return responses.err("Cliente não encontrado.", campo="cliente_id", status=400)

            if tipo_pagamento and tipo_pagamento not in ["dinheiro", "cartao_credito", "cartao_debito", "pix"]:
                return responses.err("Tipo de pagamento inválido.", status=400)
            if status and status not in ["concluida", "cancelada", "pendente"]:
                return responses.err("Status de venda inválido.", status=400)
            if status and status != venda_existente["status"] and venda_existente["status"] == "concluida":
                return responses.err("Uma venda concluída não pode voltar de status; registre uma devolução de estoque para preservar a auditoria.", campo="status", status=409)

            # Lógica para atualizar estoque se o status mudar para 'concluida' e antes não era
            if status == "concluida" and venda_existente["status"] != "concluida":
                cur.execute("SELECT produto_id, quantidade, lote_vendido FROM itens_venda WHERE venda_id = %s", (venda_id,))
                itens_venda = cur.fetchall()
                for item in itens_venda:
                    produto_id = item["produto_id"]
                    quantidade = item["quantidade"]
                    lote_vendido = item["lote_vendido"] or "SEM-LOTE"

                    cur.execute("SELECT id, quantidade, lote, data_validade FROM estoque WHERE produto_id = %s AND lote = %s FOR UPDATE", (produto_id, lote_vendido))
                    estoque_item = cur.fetchone()
                    if not estoque_item or estoque_item["quantidade"] < quantidade:
                        # Desfaz as gravações ainda não confirmadas desta operação antes de responder à falha.
                        db.rollback()
                        return responses.err(f"Estoque insuficiente para o produto {produto_id} no lote {lote_vendido}.", status=400)

                    require_usable_stock(read_settings(cur), estoque_item)
                    cur.execute("UPDATE estoque SET quantidade = quantidade - %s WHERE id = %s", (quantidade, estoque_item["id"]))
                    # Registrar movimentação de estoque
                    cur.execute(
                        """
                        INSERT INTO movimentacoes_estoque (estoque_id, usuario_id, tipo_movimentacao, quantidade, observacao, finalidade)
                        VALUES (%s, %s, %s, %s, %s, 'venda')
                        """,
                        (estoque_item["id"], usuario_id, "saida", quantidade, f"Saída por venda {venda_id}")
                    )

            cur.execute(
                """
                UPDATE vendas SET data_venda = CASE
                    WHEN status <> 'concluida' AND %s = 'concluida' THEN NOW() ELSE data_venda END,
                    cliente_id = %s, valor_total = %s, tipo_pagamento = %s, status = %s
                WHERE id = %s
                """,
                (status, cliente_id, valor_total, tipo_pagamento, status, venda_id)
            )
            sync_venda_financeiro(cur, venda_id)
            g.audit_previous_status = venda_existente["status"]
            commit_audit(db, venda_id)
            return responses.ok({"mensagem": "Venda atualizada com sucesso."})
    except ValueError as exc:
        # Desfaz as gravações ainda não confirmadas desta operação antes de responder à falha.
        db.rollback()
        return responses.err(str(exc), status=400)
    except pymysql.MySQLError as exc:
        # Desfaz as gravações ainda não confirmadas desta operação antes de responder à falha.
        db.rollback()
        log.error("Erro DB ao atualizar venda: %s", exc)
        return responses.err("Erro interno ao atualizar venda.", status=500)


# Exclui venda.
# A confirmação passa por commit_audit para manter a alteração e seu histórico juntos.
def delete_venda(venda_id):
    # Dependências SQL com nome literal nas consultas deste fluxo:
    # vendas.
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM vendas WHERE id = %s", (venda_id,))
            if not cur.fetchone():
                return responses.err("Venda não encontrada.", status=404)

            cur.execute("DELETE FROM vendas WHERE id = %s", (venda_id,))
            commit_audit(db, cur.lastrowid)
            return responses.ok({"mensagem": "Venda excluída com sucesso."})
    except pymysql.MySQLError as exc:
        # Desfaz as gravações ainda não confirmadas desta operação antes de responder à falha.
        db.rollback()
        log.error("Erro DB ao excluir venda: %s", exc)
        return responses.err("Erro interno ao excluir venda.", status=500)


# Liga URLs, métodos HTTP e nomes de endpoint à instância recebida.
# Alterar estes contratos exige revisar as telas e tests/fixtures/api_routes.json.
def register_routes(app):
    """Registra as URLs e nomes de endpoints existentes."""
    app.add_url_rule('/vendas', view_func=get_vendas, methods=['GET'])
    app.add_url_rule('/vendas/catalogo', view_func=catalogo_pdv, methods=['GET'])
    app.add_url_rule('/vendas/balcao', view_func=concluir_pdv, methods=['POST'])
    app.add_url_rule('/vendas/<int:venda_id>', view_func=get_venda, methods=['GET'])
    app.add_url_rule('/vendas', view_func=create_venda, methods=['POST'])
    app.add_url_rule('/vendas/<int:venda_id>', view_func=update_venda, methods=['PUT'])
    app.add_url_rule('/vendas/<int:venda_id>', view_func=delete_venda, methods=['DELETE'])
