"""routes.compras: responsabilidades extraídas da aplicação Flask."""

from farmacontrol.core import database
from farmacontrol.core import responses
from farmacontrol.services.audit import commit_audit
from farmacontrol.services.product_rules import validate_expiry
from farmacontrol.services.system_settings import read_settings
from farmacontrol.services.system_settings import require_lot
from flask import g
from flask import request
import logging
import pymysql.cursors

log = logging.getLogger("farmacontrol")


def get_compras():
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT c.*,
                       f.nome_fantasia                     AS fornecedor_nome,
                       u.nome                           AS usuario_nome,
                       (
                           SELECT COUNT(*)
                           FROM   itens_compra ic
                           WHERE  ic.compra_id = c.id
                       )                                AS itens_count,
                       c.data_recebimento               AS data_entrega_prevista
                FROM   compras c
                LEFT JOIN fornecedores f ON c.fornecedor_id = f.id
                LEFT JOIN usuarios u    ON c.usuario_id    = u.id
                ORDER  BY c.criado_em DESC
            """)
            compras = cur.fetchall()
        # Carrega os itens de todas as compras em uma única consulta (N+1)
        ids = [c["id"] for c in compras]
        itens_map = {}
        if ids:
            with db.cursor() as cur2:
                cur2.execute("""
                    SELECT ic.*, p.nome AS produto_nome, p.exige_validade
                    FROM   itens_compra ic
                    JOIN   produtos p ON ic.produto_id = p.id
                    WHERE  ic.compra_id IN (%s)
                """ % (",".join(["%s"] * len(ids)),), tuple(ids))
                for item in cur2.fetchall():
                    itens_map.setdefault(item["compra_id"], []).append(item)
        for row in compras:
            for k in ("criado_em", "data_pedido", "data_recebimento", "atualizado_em", "data_entrega_prevista"):
                if row.get(k) and hasattr(row[k], "isoformat"):
                    row[k] = row[k].isoformat()
            if row.get("valor_total") is not None:
                row["valor_total"] = float(row["valor_total"])
            row["itens"] = itens_map.get(row["id"], [])
            for item in row["itens"]:
                if item.get("data_validade_recebida") and hasattr(item["data_validade_recebida"], "isoformat"):
                    item["data_validade_recebida"] = item["data_validade_recebida"].isoformat()
        return responses.ok({"compras": compras})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar compras: %s", exc)
        return responses.err("Erro interno ao buscar compras.", status=500)


def get_compra(compra_id):
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT c.*,
                       f.nome_fantasia AS fornecedor_nome,
                       u.nome          AS usuario_nome
                FROM   compras c
                LEFT JOIN fornecedores f ON c.fornecedor_id = f.id
                LEFT JOIN usuarios u    ON c.usuario_id    = u.id
                WHERE  c.id = %s
            """, (compra_id,))
            compra = cur.fetchone()
            if not compra:
                return responses.err("Compra não encontrada.", status=404)
        for k in ("criado_em", "data_recebimento", "atualizado_em", "data_pedido"):
            if compra.get(k) and hasattr(compra[k], "isoformat"):
                compra[k] = compra[k].isoformat()
        # Busca itens da compra
        with db.cursor() as cur2:
            cur2.execute("""
                SELECT ic.*, p.nome AS produto_nome
                FROM   itens_compra ic
                JOIN   produtos p ON ic.produto_id = p.id
                WHERE  ic.compra_id = %s
            """, (compra_id,))
            compra["itens"] = cur2.fetchall()
        return responses.ok({"compra": compra})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar compra: %s", exc)
        return responses.err("Erro interno ao buscar compra.", status=500)


def create_compra():
    data = request.get_json(silent=True) or {}
    fornecedor_id = data.get("fornecedor_id")
    usuario_id = g.usuario_id
    valor_total = data.get("valor_total")
    status = data.get("status", "pendente")
    itens = data.get("itens", []) # Lista de dicionários com produto_id, quantidade, preco_unitario, lote_recebido, data_validade_recebida

    if not fornecedor_id or not valor_total:
        return responses.err("Fornecedor e valor total são obrigatórios.", status=400)
    if valor_total <= 0:
        return responses.err("Valor total deve ser maior que zero.", status=400)
    if status not in ["pendente", "recebido", "cancelado"]:
        return responses.err("Status de compra inválido.", status=400)

    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM fornecedores WHERE id = %s", (fornecedor_id,))
            if not cur.fetchone():
                return responses.err("Fornecedor não encontrado.", campo="fornecedor_id", status=400)

            cur.execute(
                """
                INSERT INTO compras (fornecedor_id, usuario_id, valor_total, status)
                VALUES (%s, %s, %s, %s)
                """,
                (fornecedor_id, usuario_id, valor_total, status)
            )
            compra_id = cur.lastrowid

            for item in itens:
                produto_id = item.get("produto_id")
                quantidade = item.get("quantidade")
                preco_unitario = item.get("preco_unitario")
                lote_recebido = (item.get("lote_recebido") or "").strip() or "SEM-LOTE"
                data_validade_recebida = item.get("data_validade_recebida")

                if not produto_id or not quantidade or not preco_unitario:
                    db.rollback()
                    return responses.err("Dados incompletos para item de compra.", status=400)

                cur.execute("SELECT id, exige_validade FROM produtos WHERE id = %s", (produto_id,))
                product = cur.fetchone()
                if not product:
                    db.rollback()
                    return responses.err(f"Produto com ID {produto_id} não encontrado.", status=400)

                data_validade_recebida = validate_expiry(
                    data_validade_recebida, product if status == "recebido" else {"exige_validade": False})

                cur.execute(
                    """
                    INSERT INTO itens_compra (compra_id, produto_id, quantidade, preco_unitario, lote_recebido, data_validade_recebida)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (compra_id, produto_id, quantidade, preco_unitario, lote_recebido, data_validade_recebida)
                )

                # Se a compra foi recebida, atualiza o estoque
                if status == "recebido":
                    require_lot(read_settings(cur), lote_recebido)
                    cur.execute("SELECT id FROM estoque WHERE produto_id = %s AND lote = %s FOR UPDATE", (produto_id, lote_recebido))
                    estoque_item = cur.fetchone()
                    if estoque_item:
                        cur.execute("UPDATE estoque SET quantidade = quantidade + %s WHERE id = %s", (quantidade, estoque_item["id"]))
                    else:
                        cur.execute(
                            """
                            INSERT INTO estoque (produto_id, lote, quantidade, data_validade)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (produto_id, lote_recebido, quantidade, data_validade_recebida)
                        )
                    # Registrar movimentação de estoque
                    cur.execute(
                        """
                        INSERT INTO movimentacoes_estoque (estoque_id, usuario_id, tipo_movimentacao, quantidade, observacao)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (cur.lastrowid if not estoque_item else estoque_item["id"], usuario_id, "entrada", quantidade, f"Entrada por compra {compra_id}")
                    )

            g.audit_values = {"status": status}
            commit_audit(db, compra_id)
            return responses.ok({"mensagem": "Compra criada com sucesso.", "id": compra_id}, status=201)
    except ValueError as exc:
        db.rollback()
        return responses.err(str(exc), status=400)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao criar compra: %s", exc)
        return responses.err("Erro interno ao criar compra.", status=500)


def update_compra(compra_id):
    data = request.get_json(silent=True) or {}
    fornecedor_id = data.get("fornecedor_id")
    usuario_id = g.usuario_id
    valor_total = data.get("valor_total")
    status = data.get("status")
    data_recebimento = data.get("data_recebimento")

    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id, status, usuario_id, valor_total, fornecedor_id FROM compras WHERE id = %s FOR UPDATE", (compra_id,))
            compra_existente = cur.fetchone()
            if not compra_existente:
                return responses.err("Compra não encontrada.", status=404)

            if fornecedor_id:
                cur.execute("SELECT id FROM fornecedores WHERE id = %s", (fornecedor_id,))
                if not cur.fetchone():
                    return responses.err("Fornecedor não encontrado.", campo="fornecedor_id", status=400)

            if status and status not in ["pendente", "recebido", "cancelado"]:
                return responses.err("Status de compra inválido.", status=400)
            if status and status != compra_existente["status"] and compra_existente["status"] == "recebido":
                return responses.err("Uma compra recebida não pode voltar de status; registre uma devolução de estoque para preservar a auditoria.", campo="status", status=409)

            # Lógica para atualizar estoque se o status mudar para 'recebido'
            if status == "recebido" and compra_existente["status"] != "recebido":
                cur.execute("SELECT id, produto_id, quantidade, lote_recebido, data_validade_recebida FROM itens_compra WHERE compra_id = %s", (compra_id,))
                itens_compra = cur.fetchall()
                recebimentos = data.get("itens_recebimento", [])
                if not isinstance(recebimentos, list):
                    raise ValueError("Informe uma lista de itens para recebimento.")
                recebimentos_por_id = {}
                ids_compra = {item["id"] for item in itens_compra}
                for recebido in recebimentos:
                    if not isinstance(recebido, dict) or recebido.get("id") not in ids_compra:
                        raise ValueError("Item de recebimento não pertence a esta compra.")
                    if recebido["id"] in recebimentos_por_id:
                        raise ValueError("Item de recebimento duplicado.")
                    recebimentos_por_id[recebido["id"]] = recebido
                # A confirmação é sempre atribuída à sessão que a executou.
                usuario_recebimento = g.usuario_id
                for item in itens_compra:
                    produto_id = item["produto_id"]
                    quantidade = item["quantidade"]
                    lote_recebido = item["lote_recebido"]
                    data_validade_recebida = item["data_validade_recebida"]
                    recebido = recebimentos_por_id.get(item["id"], {})
                    lote_recebido = recebido.get("lote_recebido", lote_recebido)
                    data_validade_recebida = recebido.get("data_validade_recebida", data_validade_recebida)

                    cur.execute("SELECT id, exige_validade FROM produtos WHERE id = %s", (produto_id,))
                    product = cur.fetchone()
                    data_validade_recebida = validate_expiry(data_validade_recebida, product or {})

                    lote_estoque = (lote_recebido or "").strip() or "SEM-LOTE"
                    require_lot(read_settings(cur), lote_estoque)
                    cur.execute("UPDATE itens_compra SET lote_recebido = %s, data_validade_recebida = %s WHERE id = %s",
                                (lote_estoque, data_validade_recebida, item["id"]))
                    cur.execute("SELECT id FROM estoque WHERE produto_id = %s AND lote = %s FOR UPDATE", (produto_id, lote_estoque))
                    estoque_item = cur.fetchone()
                    if estoque_item:
                        cur.execute("UPDATE estoque SET quantidade = quantidade + %s WHERE id = %s", (quantidade, estoque_item["id"]))
                    else:
                        cur.execute(
                            """
                            INSERT INTO estoque (produto_id, lote, quantidade, data_validade)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (produto_id, lote_estoque, quantidade, data_validade_recebida)
                        )
                    # Registrar movimentação de estoque
                    cur.execute(
                        """
                        INSERT INTO movimentacoes_estoque (estoque_id, usuario_id, tipo_movimentacao, quantidade, observacao)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (cur.lastrowid if not estoque_item else estoque_item["id"], usuario_recebimento, "entrada", quantidade, f"Entrada por compra {compra_id}")
                    )

            # Update parcial: somente os campos enviados pelo frontend são alterados,
            # mantendo os valores atuais para o que não foi informado (evita erro de NULL)
            if status and status == "recebido" and not data_recebimento:
                data_recebimento = "NOW()"
                use_now = True
            else:
                use_now = False

            set_parts = []
            params = []
            if fornecedor_id is not None:
                set_parts.append("fornecedor_id = %s"); params.append(fornecedor_id)
            if valor_total is not None:
                set_parts.append("valor_total = %s"); params.append(valor_total)
            if status is not None:
                set_parts.append("status = %s"); params.append(status)
            if use_now:
                set_parts.append("data_recebimento = NOW()")
            elif data_recebimento is not None:
                set_parts.append("data_recebimento = %s"); params.append(data_recebimento)

            if set_parts:
                params.append(compra_id)
                cur.execute(f"UPDATE compras SET {', '.join(set_parts)} WHERE id = %s", params)
            g.audit_previous_status = compra_existente["status"]
            commit_audit(db)
            return responses.ok({"mensagem": "Compra atualizada com sucesso."})
    except ValueError as exc:
        db.rollback()
        return responses.err(str(exc), status=400)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao atualizar compra: %s", exc)
        return responses.err("Erro interno ao atualizar compra.", status=500)


def delete_compra(compra_id):
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM compras WHERE id = %s", (compra_id,))
            if not cur.fetchone():
                return responses.err("Compra não encontrada.", status=404)

            cur.execute("DELETE FROM compras WHERE id = %s", (compra_id,))
            commit_audit(db, cur.lastrowid)
            return responses.ok({"mensagem": "Compra excluída com sucesso."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao excluir compra: %s", exc)
        return responses.err("Erro interno ao excluir compra.", status=500)


def register_routes(app):
    """Registra as URLs e nomes de endpoints existentes."""
    app.add_url_rule('/compras', view_func=get_compras, methods=['GET'])
    app.add_url_rule('/compras/<int:compra_id>', view_func=get_compra, methods=['GET'])
    app.add_url_rule('/compras', view_func=create_compra, methods=['POST'])
    app.add_url_rule('/compras/<int:compra_id>', view_func=update_compra, methods=['PUT'])
    app.add_url_rule('/compras/<int:compra_id>', view_func=delete_compra, methods=['DELETE'])
