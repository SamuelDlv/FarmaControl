"""routes.configuracoes: responsabilidades extraídas da aplicação Flask."""

from farmacontrol.core import database
from farmacontrol.core import responses
from farmacontrol.services.audit import commit_audit
from farmacontrol.services.system_settings import read_settings
from farmacontrol.services.system_settings import validate_settings
from flask import request
import logging
import os
import pymysql.cursors

log = logging.getLogger("farmacontrol")


def get_configuracoes_visuais():
    """Preferencias seguras usadas pelo login antes de existir uma sessao."""
    chaves = ("cor_destaque", "densidade_interface", "animacoes_interface")
    db = database.get_db()
    try:
        with db.cursor() as cur:
            placeholders = ", ".join(["%s"] * len(chaves))
            cur.execute(
                f"SELECT chave, valor FROM configuracoes_sistema WHERE chave IN ({placeholders})",
                chaves,
            )
            configuracoes = cur.fetchall()
        return responses.ok({"configuracoes": configuracoes})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar configuracoes visuais: %s", exc)
        return responses.err("Erro interno ao buscar configuracoes visuais.", status=500)


def get_configuracoes():
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM configuracoes_sistema")
            configuracoes = cur.fetchall()
        # Preferências aposentadas podem existir em instalações anteriores.
        configuracoes = [item for item in configuracoes if item["chave"] not in {"tema", "tema_efetivo"}]
        return responses.ok({"configuracoes": configuracoes, "email_disponivel": all(os.getenv(k) for k in ("BREVO_SMTP_LOGIN", "BREVO_SMTP_PASSWORD", "BREVO_SENDER_EMAIL"))})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar configurações: %s", exc)
        return responses.err("Erro interno ao buscar configurações.", status=500)


def save_configuracoes():
    """Salva o formulário inteiro em uma única transação, incluindo auditoria."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return responses.err("Informe as configurações para salvar.", status=400)
    db = database.get_db()
    try:
        with db.cursor() as cur:
            values = validate_settings(data.get('configuracoes'), read_settings(cur))
            for chave, valor in values.items():
                cur.execute("""INSERT INTO configuracoes_sistema (chave, valor, descricao)
                    VALUES (%s, %s, 'Configurações do sistema')
                    ON DUPLICATE KEY UPDATE valor = VALUES(valor)""", (chave, valor))
            commit_audit(db)
        return responses.ok({"mensagem": "Configurações salvas com sucesso.", "valores": values})
    except ValueError as exc:
        db.rollback()
        return responses.err(str(exc), status=400)
    except pymysql.MySQLError:
        db.rollback()
        log.exception("Erro ao salvar configurações")
        return responses.err("Não foi possível salvar as configurações. Tente novamente.", status=500)


def get_configuracao(chave):
    if chave in {"tema", "tema_efetivo"}:
        return responses.err("Esta preferência visual foi removida.", status=410)
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM configuracoes_sistema WHERE chave = %s", (chave,))
            configuracao = cur.fetchone()
            if not configuracao:
                return responses.err("Configuração não encontrada.", status=404)
        return responses.ok({"configuracao": configuracao})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar configuração: %s", exc)
        return responses.err("Erro interno ao buscar configuração.", status=500)


def create_configuracao():
    data = request.get_json(silent=True) or {}
    chave = data.get("chave")
    valor = data.get("valor")
    descricao = data.get("descricao")

    if chave in ("tema", "tema_efetivo"):
        return responses.err("Esta preferência visual foi removida.", campo="chave", status=410)

    if not chave or not valor:
        return responses.err("Chave e valor são obrigatórios.", status=400)

    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO configuracoes_sistema (chave, valor, descricao)
                VALUES (%s, %s, %s)
                """,
                (chave, valor, descricao)
            )
            commit_audit(db, cur.lastrowid)
            return responses.ok({"mensagem": "Configuração criada com sucesso."}, status=201)
    except pymysql.IntegrityError as exc:
        db.rollback()
        if "Duplicate entry" in str(exc) and "chave" in str(exc):
            return responses.err("Chave de configuração já existe.", campo="chave", status=409)
        log.error("Erro DB ao criar configuração: %s", exc)
        return responses.err("Erro interno ao criar configuração.", status=500)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao criar configuração: %s", exc)
        return responses.err("Erro interno ao criar configuração.", status=500)


def update_configuracao(chave):
    """Atualiza ou cria (upsert) uma configuração do sistema."""
    if chave in {"tema", "tema_efetivo"}:
        return responses.err("Esta preferência visual foi removida.", campo="chave", status=410)
    data = request.get_json(silent=True) or {}
    valor     = data.get("valor")
    descricao = data.get("descricao")

    db = database.get_db()
    try:
        with db.cursor() as cur:
            # INSERT ... ON DUPLICATE KEY UPDATE (upsert)
            cur.execute(
                """
                INSERT INTO configuracoes_sistema (chave, valor, descricao)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE valor = VALUES(valor),
                                        descricao = COALESCE(VALUES(descricao), descricao)
                """,
                (chave, valor, descricao)
            )
            commit_audit(db, cur.lastrowid)
            return responses.ok({"mensagem": "Configuração salva com sucesso."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao salvar configuração: %s", exc)
        return responses.err("Erro interno ao salvar configuração.", status=500)


def delete_configuracao(chave):
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT chave FROM configuracoes_sistema WHERE chave = %s", (chave,))
            if not cur.fetchone():
                return responses.err("Configuração não encontrada.", status=404)

            cur.execute("DELETE FROM configuracoes_sistema WHERE chave = %s", (chave,))
            commit_audit(db, cur.lastrowid)
            return responses.ok({"mensagem": "Configuração excluída com sucesso."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao excluir configuração: %s", exc)
        return responses.err("Erro interno ao excluir configuração.", status=500)


def register_routes(app):
    """Registra as URLs e nomes de endpoints existentes."""
    app.add_url_rule('/configuracoes/visual', view_func=get_configuracoes_visuais, methods=['GET'])
    app.add_url_rule('/configuracoes', view_func=get_configuracoes, methods=['GET'])
    app.add_url_rule('/configuracoes', view_func=save_configuracoes, methods=['PUT'])
    app.add_url_rule('/configuracoes/<string:chave>', view_func=get_configuracao, methods=['GET'])
    app.add_url_rule('/configuracoes', view_func=create_configuracao, methods=['POST'])
    app.add_url_rule('/configuracoes/<string:chave>', view_func=update_configuracao, methods=['PUT'])
    app.add_url_rule('/configuracoes/<string:chave>', view_func=delete_configuracao, methods=['DELETE'])
