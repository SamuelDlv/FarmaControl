# Guia de manutenção — Atende consulta e manutenção do cadastro de clientes.
# Consulte docs/DESENVOLVIMENTO.md para executar as verificações desta camada.
"""routes.clientes: responsabilidades extraídas da aplicação Flask."""

from farmacontrol.core import database
from farmacontrol.core import responses
from farmacontrol.services.audit import commit_audit
from flask import request
import logging
import pymysql.cursors

log = logging.getLogger("farmacontrol")


# Consulta clientes.
def get_clientes():
    # Dependências SQL com nome literal nas consultas deste fluxo:
    # clientes.
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM clientes")
            clientes = cur.fetchall()
        return responses.ok({"clientes": clientes})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar clientes: %s", exc)
        return responses.err("Erro interno ao buscar clientes.", status=500)


# Consulta cliente.
def get_cliente(cliente_id):
    # Dependências SQL com nome literal nas consultas deste fluxo:
    # clientes.
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM clientes WHERE id = %s", (cliente_id,))
            cliente = cur.fetchone()
            if not cliente:
                return responses.err("Cliente não encontrado.", status=404)
        return responses.ok({"cliente": cliente})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar cliente: %s", exc)
        return responses.err("Erro interno ao buscar cliente.", status=500)


# Cadastra cliente.
# Recebe os campos do JSON da requisição; as validações abaixo definem o contrato aceito.
# A confirmação passa por commit_audit para manter a alteração e seu histórico juntos.
def create_cliente():
    # Chaves lidas do JSON neste fluxo (obrigatoriedade validada abaixo):
    # cpf, data_nascimento, email, endereco, nome, sobrenome.
    # telefone.
    # Dependências SQL com nome literal nas consultas deste fluxo:
    # clientes.
    data = request.get_json(silent=True) or {}
    nome = data.get("nome")
    sobrenome = data.get("sobrenome")
    cpf = data.get("cpf")
    telefone = data.get("telefone")
    email = data.get("email")
    endereco = data.get("endereco")
    data_nascimento = data.get("data_nascimento")

    if not nome or not sobrenome:
        return responses.err("Nome e sobrenome são obrigatórios.", status=400)

    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO clientes (nome, sobrenome, cpf, telefone, email, endereco, data_nascimento)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (nome, sobrenome, cpf, telefone, email, endereco, data_nascimento)
            )
            commit_audit(db, cur.lastrowid)
            return responses.ok({"mensagem": "Cliente criado com sucesso.", "id": cur.lastrowid}, status=201)
    except pymysql.IntegrityError as exc:
        # Desfaz as gravações ainda não confirmadas desta operação antes de responder à falha.
        db.rollback()
        if "Duplicate entry" in str(exc) and "cpf" in str(exc):
            return responses.err("CPF já cadastrado.", campo="cpf", status=409)
        if "Duplicate entry" in str(exc) and "email" in str(exc):
            return responses.err("Email já cadastrado.", campo="email", status=409)
        log.error("Erro DB ao criar cliente: %s", exc)
        return responses.err("Erro interno ao criar cliente.", status=500)
    except pymysql.MySQLError as exc:
        # Desfaz as gravações ainda não confirmadas desta operação antes de responder à falha.
        db.rollback()
        log.error("Erro DB ao criar cliente: %s", exc)
        return responses.err("Erro interno ao criar cliente.", status=500)


# Atualiza cliente.
# Recebe os campos do JSON da requisição; as validações abaixo definem o contrato aceito.
# A confirmação passa por commit_audit para manter a alteração e seu histórico juntos.
def update_cliente(cliente_id):
    # Chaves lidas do JSON neste fluxo (obrigatoriedade validada abaixo):
    # cpf, data_nascimento, email, endereco, nome, sobrenome.
    # telefone.
    # Dependências SQL com nome literal nas consultas deste fluxo:
    # clientes.
    data = request.get_json(silent=True) or {}
    nome = data.get("nome")
    sobrenome = data.get("sobrenome")
    cpf = data.get("cpf")
    telefone = data.get("telefone")
    email = data.get("email")
    endereco = data.get("endereco")
    data_nascimento = data.get("data_nascimento")

    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM clientes WHERE id = %s", (cliente_id,))
            if not cur.fetchone():
                return responses.err("Cliente não encontrado.", status=404)

            cur.execute(
                """
                UPDATE clientes SET nome = %s, sobrenome = %s, cpf = %s, telefone = %s, email = %s, endereco = %s, data_nascimento = %s
                WHERE id = %s
                """,
                (nome, sobrenome, cpf, telefone, email, endereco, data_nascimento, cliente_id)
            )
            commit_audit(db, cur.lastrowid)
            return responses.ok({"mensagem": "Cliente atualizado com sucesso."})
    except pymysql.IntegrityError as exc:
        # Desfaz as gravações ainda não confirmadas desta operação antes de responder à falha.
        db.rollback()
        if "Duplicate entry" in str(exc) and "cpf" in str(exc):
            return responses.err("CPF já cadastrado para outro cliente.", campo="cpf", status=409)
        if "Duplicate entry" in str(exc) and "email" in str(exc):
            return responses.err("Email já cadastrado para outro cliente.", campo="email", status=409)
        log.error("Erro DB ao atualizar cliente: %s", exc)
        return responses.err("Erro interno ao atualizar cliente.", status=500)
    except pymysql.MySQLError as exc:
        # Desfaz as gravações ainda não confirmadas desta operação antes de responder à falha.
        db.rollback()
        log.error("Erro DB ao atualizar cliente: %s", exc)
        return responses.err("Erro interno ao atualizar cliente.", status=500)


# Exclui cliente.
# A confirmação passa por commit_audit para manter a alteração e seu histórico juntos.
def delete_cliente(cliente_id):
    # Dependências SQL com nome literal nas consultas deste fluxo:
    # clientes.
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM clientes WHERE id = %s", (cliente_id,))
            if not cur.fetchone():
                return responses.err("Cliente não encontrado.", status=404)

            cur.execute("DELETE FROM clientes WHERE id = %s", (cliente_id,))
            commit_audit(db, cur.lastrowid)
            return responses.ok({"mensagem": "Cliente excluído com sucesso."})
    except pymysql.MySQLError as exc:
        # Desfaz as gravações ainda não confirmadas desta operação antes de responder à falha.
        db.rollback()
        log.error("Erro DB ao excluir cliente: %s", exc)
        return responses.err("Erro interno ao excluir cliente.", status=500)


# Liga URLs, métodos HTTP e nomes de endpoint à instância recebida.
# Alterar estes contratos exige revisar as telas e tests/fixtures/api_routes.json.
def register_routes(app):
    """Registra as URLs e nomes de endpoints existentes."""
    app.add_url_rule('/clientes', view_func=get_clientes, methods=['GET'])
    app.add_url_rule('/clientes/<int:cliente_id>', view_func=get_cliente, methods=['GET'])
    app.add_url_rule('/clientes', view_func=create_cliente, methods=['POST'])
    app.add_url_rule('/clientes/<int:cliente_id>', view_func=update_cliente, methods=['PUT'])
    app.add_url_rule('/clientes/<int:cliente_id>', view_func=delete_cliente, methods=['DELETE'])
