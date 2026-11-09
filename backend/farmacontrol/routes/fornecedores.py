# Guia de manutenção — Mantém fornecedores e valida seus dados de contato e identificação.
# Consulte docs/DESENVOLVIMENTO.md para executar as verificações desta camada.
"""routes.fornecedores: responsabilidades extraídas da aplicação Flask."""

from farmacontrol.core import database
from farmacontrol.core import responses
from farmacontrol.services.audit import commit_audit
from farmacontrol.services.contact_rules import validate_supplier
from flask import request
import logging
import pymysql.cursors

log = logging.getLogger("farmacontrol")


# Consulta fornecedores.
def get_fornecedores():
    # Dependências SQL com nome literal nas consultas deste fluxo:
    # fornecedores.
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM fornecedores")
            fornecedores = cur.fetchall()
        return responses.ok({"fornecedores": fornecedores})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar fornecedores: %s", exc)
        return responses.err("Erro interno ao buscar fornecedores.", status=500)


# Consulta fornecedor.
def get_fornecedor(fornecedor_id):
    # Dependências SQL com nome literal nas consultas deste fluxo:
    # fornecedores.
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM fornecedores WHERE id = %s", (fornecedor_id,))
            fornecedor = cur.fetchone()
            if not fornecedor:
                return responses.err("Fornecedor não encontrado.", status=404)
        return responses.ok({"fornecedor": fornecedor})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar fornecedor: %s", exc)
        return responses.err("Erro interno ao buscar fornecedor.", status=500)


# Cadastra fornecedor.
# Recebe os campos do JSON da requisição; as validações abaixo definem o contrato aceito.
# A confirmação passa por commit_audit para manter a alteração e seu histórico juntos.
def create_fornecedor():
    # Chaves lidas do JSON neste fluxo (obrigatoriedade validada abaixo):
    # cnpj, contato_email, contato_nome, contato_telefone, endereco, nome_fantasia.
    # razao_social.
    # Dependências SQL com nome literal nas consultas deste fluxo:
    # fornecedores.
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return responses.err("Informe os dados do fornecedor.", status=400)
    try:
        validate_supplier(data)
    except ValueError as exc:
        return responses.err(str(exc), status=400)
    nome_fantasia = data.get("nome_fantasia")
    razao_social = data.get("razao_social")
    cnpj = data.get("cnpj")
    contato_nome = data.get("contato_nome")
    contato_telefone = data.get("contato_telefone")
    contato_email = data.get("contato_email")
    endereco = data.get("endereco")

    if not nome_fantasia or not razao_social or not cnpj:
        return responses.err("Nome fantasia, razão social e CNPJ são obrigatórios.", status=400)

    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO fornecedores (nome_fantasia, razao_social, cnpj, contato_nome, contato_telefone, contato_email, endereco)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (nome_fantasia, razao_social, cnpj, contato_nome, contato_telefone, contato_email, endereco)
            )
            commit_audit(db, cur.lastrowid)
            return responses.ok({"mensagem": "Fornecedor criado com sucesso.", "id": cur.lastrowid}, status=201)
    except pymysql.IntegrityError as exc:
        # Desfaz as gravações ainda não confirmadas desta operação antes de responder à falha.
        db.rollback()
        if "Duplicate entry" in str(exc) and "razao_social" in str(exc):
            return responses.err("Razão social já cadastrada.", campo="razao_social", status=409)
        if "Duplicate entry" in str(exc) and "cnpj" in str(exc):
            return responses.err("CNPJ já cadastrado.", campo="cnpj", status=409)
        log.error("Erro DB ao criar fornecedor: %s", exc)
        return responses.err("Erro interno ao criar fornecedor.", status=500)
    except pymysql.MySQLError as exc:
        # Desfaz as gravações ainda não confirmadas desta operação antes de responder à falha.
        db.rollback()
        log.error("Erro DB ao criar fornecedor: %s", exc)
        return responses.err("Erro interno ao criar fornecedor.", status=500)


# Atualiza fornecedor.
# Recebe os campos do JSON da requisição; as validações abaixo definem o contrato aceito.
# A confirmação passa por commit_audit para manter a alteração e seu histórico juntos.
def update_fornecedor(fornecedor_id):
    # Chaves lidas do JSON neste fluxo (obrigatoriedade validada abaixo):
    # cnpj, contato_email, contato_nome, contato_telefone, endereco, nome_fantasia.
    # razao_social.
    # Dependências SQL com nome literal nas consultas deste fluxo:
    # fornecedores.
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return responses.err("Informe os dados do fornecedor.", status=400)
    try:
        validate_supplier(data)
    except ValueError as exc:
        return responses.err(str(exc), status=400)
    nome_fantasia = data.get("nome_fantasia")
    razao_social = data.get("razao_social")
    cnpj = data.get("cnpj")
    contato_nome = data.get("contato_nome")
    contato_telefone = data.get("contato_telefone")
    contato_email = data.get("contato_email")
    endereco = data.get("endereco")

    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM fornecedores WHERE id = %s", (fornecedor_id,))
            if not cur.fetchone():
                return responses.err("Fornecedor não encontrado.", status=404)

            cur.execute(
                """
                UPDATE fornecedores SET nome_fantasia = %s, razao_social = %s, cnpj = %s, contato_nome = %s, contato_telefone = %s, contato_email = %s, endereco = %s
                WHERE id = %s
                """,
                (nome_fantasia, razao_social, cnpj, contato_nome, contato_telefone, contato_email, endereco, fornecedor_id)
            )
            commit_audit(db, cur.lastrowid)
            return responses.ok({"mensagem": "Fornecedor atualizado com sucesso."})
    except pymysql.IntegrityError as exc:
        # Desfaz as gravações ainda não confirmadas desta operação antes de responder à falha.
        db.rollback()
        if "Duplicate entry" in str(exc) and "razao_social" in str(exc):
            return responses.err("Razão social já cadastrada para outro fornecedor.", campo="razao_social", status=409)
        if "Duplicate entry" in str(exc) and "cnpj" in str(exc):
            return responses.err("CNPJ já cadastrado para outro fornecedor.", campo="cnpj", status=409)
        log.error("Erro DB ao atualizar fornecedor: %s", exc)
        return responses.err("Erro interno ao atualizar fornecedor.", status=500)
    except pymysql.MySQLError as exc:
        # Desfaz as gravações ainda não confirmadas desta operação antes de responder à falha.
        db.rollback()
        log.error("Erro DB ao atualizar fornecedor: %s", exc)
        return responses.err("Erro interno ao atualizar fornecedor.", status=500)


# Exclui fornecedor.
# A confirmação passa por commit_audit para manter a alteração e seu histórico juntos.
def delete_fornecedor(fornecedor_id):
    # Dependências SQL com nome literal nas consultas deste fluxo:
    # fornecedores.
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM fornecedores WHERE id = %s", (fornecedor_id,))
            if not cur.fetchone():
                return responses.err("Fornecedor não encontrado.", status=404)

            cur.execute("DELETE FROM fornecedores WHERE id = %s", (fornecedor_id,))
            commit_audit(db, cur.lastrowid)
            return responses.ok({"mensagem": "Fornecedor excluído com sucesso."})
    except pymysql.IntegrityError as exc:
        # Desfaz as gravações ainda não confirmadas desta operação antes de responder à falha.
        db.rollback()
        msg = str(exc)
        if "1451" in msg or "fk_compra_fornecedor" in msg:
            return responses.err(
                "Este fornecedor não pode ser excluído porque possui pedidos de compra registrados. "
                "Exclua ou desvincule as compras antes, ou mantenha o fornecedor cadastrado para preservar o histórico.",
                status=409,
            )
        log.error("Erro DB ao excluir fornecedor: %s", exc)
        return responses.err("Erro interno ao excluir fornecedor.", status=500)
    except pymysql.MySQLError as exc:
        # Desfaz as gravações ainda não confirmadas desta operação antes de responder à falha.
        db.rollback()
        log.error("Erro DB ao excluir fornecedor: %s", exc)
        return responses.err("Erro interno ao excluir fornecedor.", status=500)


# Liga URLs, métodos HTTP e nomes de endpoint à instância recebida.
# Alterar estes contratos exige revisar as telas e tests/fixtures/api_routes.json.
def register_routes(app):
    """Registra as URLs e nomes de endpoints existentes."""
    app.add_url_rule('/fornecedores', view_func=get_fornecedores, methods=['GET'])
    app.add_url_rule('/fornecedores/<int:fornecedor_id>', view_func=get_fornecedor, methods=['GET'])
    app.add_url_rule('/fornecedores', view_func=create_fornecedor, methods=['POST'])
    app.add_url_rule('/fornecedores/<int:fornecedor_id>', view_func=update_fornecedor, methods=['PUT'])
    app.add_url_rule('/fornecedores/<int:fornecedor_id>', view_func=delete_fornecedor, methods=['DELETE'])
