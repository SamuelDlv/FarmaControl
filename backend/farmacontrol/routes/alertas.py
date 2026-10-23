"""routes.alertas: responsabilidades extraídas da aplicação Flask."""

from farmacontrol.core import database
from farmacontrol.core import responses
from farmacontrol.services.audit import commit_audit
from flask import g
from flask import request
import logging
import pymysql.cursors

log = logging.getLogger("farmacontrol")


def get_alertas():
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM alertas")
            alertas = cur.fetchall()
        return responses.ok({"alertas": alertas})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar alertas: %s", exc)
        return responses.err("Erro interno ao buscar alertas.", status=500)


def get_alerta(alerta_id):
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM alertas WHERE id = %s", (alerta_id,))
            alerta = cur.fetchone()
            if not alerta:
                return responses.err("Alerta não encontrado.", status=404)
        return responses.ok({"alerta": alerta})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar alerta: %s", exc)
        return responses.err("Erro interno ao buscar alerta.", status=500)


def create_alerta():
    data = request.get_json(silent=True) or {}
    tipo_alerta = data.get("tipo_alerta")
    referencia_id = data.get("referencia_id")
    mensagem = data.get("mensagem")
    status = data.get("status", "ativo")

    if not tipo_alerta or not mensagem:
        return responses.err("Tipo de alerta e mensagem são obrigatórios.", status=400)
    if tipo_alerta not in ["vencimento", "estoque_baixo", "outros"]:
        return responses.err("Tipo de alerta inválido.", status=400)

    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO alertas (tipo_alerta, referencia_id, mensagem, status)
                VALUES (%s, %s, %s, %s)
                """,
                (tipo_alerta, referencia_id, mensagem, status)
            )
            commit_audit(db, cur.lastrowid)
            return responses.ok({"mensagem": "Alerta criado com sucesso.", "id": cur.lastrowid}, status=201)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao criar alerta: %s", exc)
        return responses.err("Erro interno ao criar alerta.", status=500)


def update_alerta(alerta_id):
    data = request.get_json(silent=True) or {}
    tipo_alerta = data.get("tipo_alerta")
    referencia_id = data.get("referencia_id")
    mensagem = data.get("mensagem")
    status = data.get("status")

    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM alertas WHERE id = %s", (alerta_id,))
            if not cur.fetchone():
                return responses.err("Alerta não encontrado.", status=404)

            if tipo_alerta and tipo_alerta not in ["vencimento", "estoque_baixo", "outros"]:
                return responses.err("Tipo de alerta inválido.", status=400)
            if status and status not in ["ativo", "resolvido"]:
                return responses.err("Status de alerta inválido.", status=400)

            update_fields = []
            update_values = []
            if tipo_alerta: update_fields.append("tipo_alerta = %s"); update_values.append(tipo_alerta)
            if referencia_id: update_fields.append("referencia_id = %s"); update_values.append(referencia_id)
            if mensagem: update_fields.append("mensagem = %s"); update_values.append(mensagem)
            if status: update_fields.append("status = %s"); update_values.append(status)
            if status == "resolvido":
                # A autoria vem da sessão autenticada, nunca do corpo enviado
                # pelo cliente; a migração 007 fornece ambas as colunas.
                update_fields.append("resolvido_por_usuario_id = %s"); update_values.append(g.usuario_id)
                update_fields.append("resolvido_em = NOW()")
            elif status == "ativo":
                update_fields.append("resolvido_por_usuario_id = NULL")
                update_fields.append("resolvido_em = NULL")

            if not update_fields:
                return responses.err("Nenhum dado para atualizar.", status=400)

            query = f"UPDATE alertas SET {', '.join(update_fields)} WHERE id = %s"
            cur.execute(query, (*update_values, alerta_id))
            commit_audit(db, cur.lastrowid)
            return responses.ok({"mensagem": "Alerta atualizado com sucesso."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao atualizar alerta: %s", exc)
        return responses.err("Erro interno ao atualizar alerta.", status=500)


def delete_alerta(alerta_id):
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM alertas WHERE id = %s", (alerta_id,))
            if not cur.fetchone():
                return responses.err("Alerta não encontrado.", status=404)

            cur.execute("DELETE FROM alertas WHERE id = %s", (alerta_id,))
            commit_audit(db, cur.lastrowid)
            return responses.ok({"mensagem": "Alerta excluído com sucesso."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao excluir alerta: %s", exc)
        return responses.err("Erro interno ao excluir alerta.", status=500)


def register_routes(app):
    """Registra as URLs e nomes de endpoints existentes."""
    app.add_url_rule('/alertas', view_func=get_alertas, methods=['GET'])
    app.add_url_rule('/alertas/<int:alerta_id>', view_func=get_alerta, methods=['GET'])
    app.add_url_rule('/alertas', view_func=create_alerta, methods=['POST'])
    app.add_url_rule('/alertas/<int:alerta_id>', view_func=update_alerta, methods=['PUT'])
    app.add_url_rule('/alertas/<int:alerta_id>', view_func=delete_alerta, methods=['DELETE'])
