"""routes.receitas: responsabilidades extraídas da aplicação Flask."""

from farmacontrol.core import database
from farmacontrol.core import responses
from farmacontrol.services.audit import commit_audit
from flask import request
import logging
import pymysql.cursors

log = logging.getLogger("farmacontrol")


def get_receitas():
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT r.*, c.nome as cliente_nome FROM receitas r LEFT JOIN clientes c ON r.cliente_id = c.id")
            receitas = cur.fetchall()
        return responses.ok({"receitas": receitas})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar receitas: %s", exc)
        return responses.err("Erro interno ao buscar receitas.", status=500)


def get_receita(receita_id):
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT r.*, c.nome as cliente_nome FROM receitas r LEFT JOIN clientes c ON r.cliente_id = c.id WHERE r.id = %s", (receita_id,))
            receita = cur.fetchone()
            if not receita:
                return responses.err("Receita não encontrada.", status=404)
        return responses.ok({"receita": receita})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar receita: %s", exc)
        return responses.err("Erro interno ao buscar receita.", status=500)


def create_receita():
    data = request.get_json(silent=True) or {}
    cliente_id = data.get("cliente_id")
    medico_nome = data.get("medico_nome")
    crm = data.get("crm")
    data_prescricao = data.get("data_prescricao")
    data_validade = data.get("data_validade")
    observacoes = data.get("observacoes")
    arquivo_receita_url = data.get("arquivo_receita_url")
    itens = data.get("itens", []) # Lista de dicionários com produto_id, quantidade, dosagem, instrucoes_uso

    if not cliente_id or not medico_nome or not crm or not data_prescricao:
        return responses.err("Cliente, nome do médico, CRM e data da prescrição são obrigatórios.", status=400)

    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM clientes WHERE id = %s", (cliente_id,))
            if not cur.fetchone():
                return responses.err("Cliente não encontrado.", campo="cliente_id", status=400)

            cur.execute(
                """
                INSERT INTO receitas (cliente_id, medico_nome, crm, data_prescricao, data_validade, observacoes, arquivo_receita_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (cliente_id, medico_nome, crm, data_prescricao, data_validade, observacoes, arquivo_receita_url)
            )
            receita_id = cur.lastrowid

            for item in itens:
                produto_id = item.get("produto_id")
                quantidade = item.get("quantidade")
                dosagem = item.get("dosagem")
                instrucoes_uso = item.get("instrucoes_uso")

                if not produto_id or not quantidade:
                    db.rollback()
                    return responses.err("Dados incompletos para item de receita.", status=400)

                cur.execute("SELECT id FROM produtos WHERE id = %s", (produto_id,))
                if not cur.fetchone():
                    db.rollback()
                    return responses.err(f"Produto com ID {produto_id} não encontrado.", status=400)

                cur.execute(
                    """
                    INSERT INTO receitas_itens (receita_id, produto_id, quantidade, dosagem, instrucoes_uso)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (receita_id, produto_id, quantidade, dosagem, instrucoes_uso)
                )

            commit_audit(db, cur.lastrowid)
            return responses.ok({"mensagem": "Receita criada com sucesso.", "id": receita_id}, status=201)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao criar receita: %s", exc)
        return responses.err("Erro interno ao criar receita.", status=500)


def update_receita(receita_id):
    data = request.get_json(silent=True) or {}
    cliente_id = data.get("cliente_id")
    medico_nome = data.get("medico_nome")
    crm = data.get("crm")
    data_prescricao = data.get("data_prescricao")
    data_validade = data.get("data_validade")
    observacoes = data.get("observacoes")
    arquivo_receita_url = data.get("arquivo_receita_url")

    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM receitas WHERE id = %s", (receita_id,))
            if not cur.fetchone():
                return responses.err("Receita não encontrada.", status=404)

            if cliente_id:
                cur.execute("SELECT id FROM clientes WHERE id = %s", (cliente_id,))
                if not cur.fetchone():
                    return responses.err("Cliente não encontrado.", campo="cliente_id", status=400)

            cur.execute(
                """
                UPDATE receitas SET cliente_id = %s, medico_nome = %s, crm = %s, data_prescricao = %s, data_validade = %s, observacoes = %s, arquivo_receita_url = %s
                WHERE id = %s
                """,
                (cliente_id, medico_nome, crm, data_prescricao, data_validade, observacoes, arquivo_receita_url, receita_id)
            )
            commit_audit(db, cur.lastrowid)
            return responses.ok({"mensagem": "Receita atualizada com sucesso."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao atualizar receita: %s", exc)
        return responses.err("Erro interno ao atualizar receita.", status=500)


def delete_receita(receita_id):
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM receitas WHERE id = %s", (receita_id,))
            if not cur.fetchone():
                return responses.err("Receita não encontrada.", status=404)

            cur.execute("DELETE FROM receitas WHERE id = %s", (receita_id,))
            commit_audit(db, cur.lastrowid)
            return responses.ok({"mensagem": "Receita excluída com sucesso."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao excluir receita: %s", exc)
        return responses.err("Erro interno ao excluir receita.", status=500)


def register_routes(app):
    """Registra as URLs e nomes de endpoints existentes."""
    app.add_url_rule('/receitas', view_func=get_receitas, methods=['GET'])
    app.add_url_rule('/receitas/<int:receita_id>', view_func=get_receita, methods=['GET'])
    app.add_url_rule('/receitas', view_func=create_receita, methods=['POST'])
    app.add_url_rule('/receitas/<int:receita_id>', view_func=update_receita, methods=['PUT'])
    app.add_url_rule('/receitas/<int:receita_id>', view_func=delete_receita, methods=['DELETE'])
