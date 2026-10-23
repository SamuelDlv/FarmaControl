"""routes.catalogo: responsabilidades extraídas da aplicação Flask."""

from farmacontrol.core import database
from farmacontrol.core import responses
from farmacontrol.services.audit import commit_audit
from farmacontrol.services.product_rules import normalize_product
from farmacontrol.services.product_rules import save_product
from farmacontrol.services.system_settings import read_settings
from flask import request
import logging
import pymysql.cursors

log = logging.getLogger("farmacontrol")


def get_categorias_produto():
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM categorias_produto")
            categorias = cur.fetchall()
        return responses.ok({"categorias": categorias})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar categorias de produto: %s", exc)
        return responses.err("Erro interno ao buscar categorias de produto.", status=500)


def get_categoria_produto(categoria_id):
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM categorias_produto WHERE id = %s", (categoria_id,))
            categoria = cur.fetchone()
            if not categoria:
                return responses.err("Categoria de produto não encontrada.", status=404)
        return responses.ok({"categoria": categoria})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar categoria de produto: %s", exc)
        return responses.err("Erro interno ao buscar categoria de produto.", status=500)


def create_categoria_produto():
    data = request.get_json(silent=True) or {}
    nome = data.get("nome")
    descricao = data.get("descricao")

    if not nome:
        return responses.err("Nome da categoria é obrigatório.", status=400)

    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO categorias_produto (nome, descricao)
                VALUES (%s, %s)
                """,
                (nome, descricao)
            )
            commit_audit(db, cur.lastrowid)
            return responses.ok({"mensagem": "Categoria de produto criada com sucesso.", "id": cur.lastrowid}, status=201)
    except pymysql.IntegrityError as exc:
        db.rollback()
        if "Duplicate entry" in str(exc) and "nome" in str(exc):
            return responses.err("Nome da categoria já existe.", campo="nome", status=409)
        log.error("Erro DB ao criar categoria de produto: %s", exc)
        return responses.err("Erro interno ao criar categoria de produto.", status=500)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao criar categoria de produto: %s", exc)
        return responses.err("Erro interno ao criar categoria de produto.", status=500)


def update_categoria_produto(categoria_id):
    data = request.get_json(silent=True) or {}
    nome = data.get("nome")
    descricao = data.get("descricao")

    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM categorias_produto WHERE id = %s", (categoria_id,))
            if not cur.fetchone():
                return responses.err("Categoria de produto não encontrada.", status=404)

            cur.execute(
                """
                UPDATE categorias_produto SET nome = %s, descricao = %s
                WHERE id = %s
                """,
                (nome, descricao, categoria_id)
            )
            commit_audit(db, cur.lastrowid)
            return responses.ok({"mensagem": "Categoria de produto atualizada com sucesso."})
    except pymysql.IntegrityError as exc:
        db.rollback()
        if "Duplicate entry" in str(exc) and "nome" in str(exc):
            return responses.err("Nome da categoria já existe para outra categoria.", campo="nome", status=409)
        log.error("Erro DB ao atualizar categoria de produto: %s", exc)
        return responses.err("Erro interno ao atualizar categoria de produto.", status=500)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao atualizar categoria de produto: %s", exc)
        return responses.err("Erro interno ao atualizar categoria de produto.", status=500)


def delete_categoria_produto(categoria_id):
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM categorias_produto WHERE id = %s", (categoria_id,))
            if not cur.fetchone():
                return responses.err("Categoria de produto não encontrada.", status=404)

            cur.execute("DELETE FROM categorias_produto WHERE id = %s", (categoria_id,))
            commit_audit(db, cur.lastrowid)
            return responses.ok({"mensagem": "Categoria de produto excluída com sucesso."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao excluir categoria de produto: %s", exc)
        return responses.err("Erro interno ao excluir categoria de produto.", status=500)


def get_produtos():
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT p.*, cp.nome as categoria_nome FROM produtos p LEFT JOIN categorias_produto cp ON p.categoria_id = cp.id")
            produtos = cur.fetchall()
        return responses.ok({"produtos": produtos})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar produtos: %s", exc)
        return responses.err("Erro interno ao buscar produtos.", status=500)


def get_produto(produto_id):
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT p.*, cp.nome as categoria_nome FROM produtos p LEFT JOIN categorias_produto cp ON p.categoria_id = cp.id WHERE p.id = %s", (produto_id,))
            produto = cur.fetchone()
            if not produto:
                return responses.err("Produto não encontrado.", status=404)
        return responses.ok({"produto": produto})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar produto: %s", exc)
        return responses.err("Erro interno ao buscar produto.", status=500)


def create_produto():
    data = request.get_json(silent=True) or {}
    try:
        product = normalize_product(data)
    except ValueError as exc:
        return responses.err(str(exc), status=400)

    db = database.get_db()
    try:
        with db.cursor() as cur:
            if "estoque_minimo" not in data:
                product["estoque_minimo"] = int(read_settings(cur)["estoque_minimo_padrao"])
            product_id = save_product(cur, product)
            commit_audit(db, cur.lastrowid)
            return responses.ok({"mensagem": "Produto criado com sucesso.", "id": product_id}, status=201)
    except ValueError as exc:
        db.rollback()
        return responses.err(str(exc), status=400)
    except pymysql.IntegrityError as exc:
        db.rollback()
        if "Duplicate entry" in str(exc) and "codigo_barras" in str(exc):
            return responses.err("Código de barras já cadastrado.", campo="codigo_barras", status=409)
        log.error("Erro DB ao criar produto: %s", exc)
        return responses.err("Erro interno ao criar produto.", status=500)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao criar produto: %s", exc)
        return responses.err("Erro interno ao criar produto.", status=500)


def update_produto(produto_id):
    data = request.get_json(silent=True) or {}

    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM produtos WHERE id = %s FOR UPDATE", (produto_id,))
            current = cur.fetchone()
            if not current:
                return responses.err("Produto não encontrado.", status=404)
            product = normalize_product(data, current)
            save_product(cur, product, produto_id)
            commit_audit(db, cur.lastrowid)
            return responses.ok({"mensagem": "Produto atualizado com sucesso."})
    except ValueError as exc:
        db.rollback()
        return responses.err(str(exc), status=400)
    except pymysql.IntegrityError as exc:
        db.rollback()
        if "Duplicate entry" in str(exc) and "codigo_barras" in str(exc):
            return responses.err("Código de barras já cadastrado para outro produto.", campo="codigo_barras", status=409)
        log.error("Erro DB ao atualizar produto: %s", exc)
        return responses.err("Erro interno ao atualizar produto.", status=500)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao atualizar produto: %s", exc)
        return responses.err("Erro interno ao atualizar produto.", status=500)


def delete_produto(produto_id):
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM produtos WHERE id = %s", (produto_id,))
            if not cur.fetchone():
                return responses.err("Produto não encontrado.", status=404)

            cur.execute("DELETE FROM produtos WHERE id = %s", (produto_id,))
            commit_audit(db, cur.lastrowid)
            return responses.ok({"mensagem": "Produto excluído com sucesso."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao excluir produto: %s", exc)
        return responses.err("Erro interno ao excluir produto.", status=500)


def register_routes(app):
    """Registra as URLs e nomes de endpoints existentes."""
    app.add_url_rule('/categorias-produto', view_func=get_categorias_produto, methods=['GET'])
    app.add_url_rule('/categorias-produto/<int:categoria_id>', view_func=get_categoria_produto, methods=['GET'])
    app.add_url_rule('/categorias-produto', view_func=create_categoria_produto, methods=['POST'])
    app.add_url_rule('/categorias-produto/<int:categoria_id>', view_func=update_categoria_produto, methods=['PUT'])
    app.add_url_rule('/categorias-produto/<int:categoria_id>', view_func=delete_categoria_produto, methods=['DELETE'])
    app.add_url_rule('/produtos', view_func=get_produtos, methods=['GET'])
    app.add_url_rule('/produtos/<int:produto_id>', view_func=get_produto, methods=['GET'])
    app.add_url_rule('/produtos', view_func=create_produto, methods=['POST'])
    app.add_url_rule('/produtos/<int:produto_id>', view_func=update_produto, methods=['PUT'])
    app.add_url_rule('/produtos/<int:produto_id>', view_func=delete_produto, methods=['DELETE'])
