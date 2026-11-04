"""routes.estoque: responsabilidades extraídas da aplicação Flask."""

from farmacontrol.core.access import INVENTORY_ROLES
from farmacontrol.core import database
from farmacontrol.core import responses
from farmacontrol.core.query import QueryError, query_int, search_text
from farmacontrol.services.audit import commit_audit
from farmacontrol.services.product_rules import normalize_product
from farmacontrol.services.product_rules import save_product
from farmacontrol.services.product_rules import stock_product_data
from farmacontrol.services.product_rules import validate_expiry
from farmacontrol.services.reporting import PERIOD_START
from farmacontrol.services.system_settings import read_settings
from farmacontrol.services.system_settings import require_lot
from farmacontrol.services.system_settings import require_usable_stock
from flask import g
from flask import request
import logging
import pymysql.cursors

log = logging.getLogger("farmacontrol")


def get_estoque():
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT e.*,
                       p.nome                        AS produto_nome,
                       p.tipo_produto, p.exige_validade, p.requer_receita,
                       p.preco_venda, p.categoria_id,
                       p.nome_generico               AS principio_ativo,
                       p.fabricante                  AS produto_fabricante,
                       COALESCE(p.preco_custo, 0)    AS preco_custo,
                       p.codigo_barras               AS produto_codigo_barras,
                       COALESCE(p.estoque_minimo, 0) AS estoque_minimo,
                       cp.nome                       AS categoria,
                       p.fornecedor_id               AS fornecedor_id,
                       f.nome_fantasia               AS fornecedor_nome,
                       COALESCE((
                           SELECT SUM(me.quantidade)
                           FROM   movimentacoes_estoque me
                           WHERE  me.estoque_id = e.id
                             AND  me.tipo_movimentacao = 'saida'
                             AND  me.data_movimentacao >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                       ), 0) AS saidas_30d
                FROM   estoque e
                JOIN   produtos p              ON e.produto_id   = p.id
                LEFT JOIN categorias_produto cp ON p.categoria_id = cp.id
                LEFT JOIN fornecedores f        ON p.fornecedor_id = f.id
                ORDER BY (e.data_validade IS NULL), e.data_validade ASC
            """)
            estoque = cur.fetchall()
        for row in estoque:
            for k in ("data_validade", "criado_em", "atualizado_em"):
                if row.get(k) and hasattr(row[k], "isoformat"):
                    row[k] = row[k].isoformat()
            for k in ("preco_custo", "saidas_30d"):
                if row.get(k) is not None:
                    row[k] = float(row[k])
        return responses.ok({"estoque": estoque})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar estoque: %s", exc)
        return responses.err("Erro interno ao buscar estoque.", status=500)


def get_parametros_estoque():
    db = database.get_db()
    try:
        with db.cursor() as cur:
            settings = read_settings(cur)
        keys = ('estoque_minimo_padrao', 'estoque_maximo_padrao', 'ponto_reposicao',
                'controle_lote_obrigatorio', 'bloquear_produtos_vencidos', 'unidade_medida_padrao')
        return responses.ok({'parametros': {key: settings[key] for key in keys}})
    except pymysql.MySQLError:
        return responses.err('Erro ao carregar parâmetros de estoque.', status=500)


def get_item_estoque(estoque_id):
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT e.*,
                       p.nome          AS produto_nome,
                       p.tipo_produto, p.exige_validade, p.requer_receita,
                       p.preco_venda, p.categoria_id, p.fornecedor_id, p.estoque_minimo,
                       p.nome_generico AS produto_principio,
                       p.fabricante    AS produto_fabricante,
                       p.preco_custo   AS produto_preco_custo,
                       p.codigo_barras AS produto_codigo_barras,
                       cp.nome         AS produto_categoria
                FROM   estoque e
                JOIN   produtos p             ON e.produto_id   = p.id
                LEFT JOIN categorias_produto cp ON p.categoria_id = cp.id
                WHERE  e.id = %s
            """, (estoque_id,))
            item_estoque = cur.fetchone()
            if not item_estoque:
                return responses.err("Item de estoque não encontrado.", status=404)
        for k in ("data_validade", "criado_em", "atualizado_em"):
            if item_estoque.get(k) and hasattr(item_estoque[k], "isoformat"):
                item_estoque[k] = item_estoque[k].isoformat()
        return responses.ok({"item_estoque": item_estoque})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar item de estoque: %s", exc)
        return responses.err("Erro interno ao buscar item de estoque.", status=500)


def create_item_estoque():
    """
    Cria item de estoque. Aceita produto_id (int) OU produto_nome (str).
    Se produto_nome for enviado sem produto_id, tenta encontrar o produto pelo nome
    ou cria um novo produto com preco_custo e preco_venda padrão.
    """
    data = request.get_json(silent=True) or {}
    produto_id    = data.get("produto_id")
    produto_nome  = (data.get("produto_nome") or "").strip()
    lote          = (data.get("lote") or "").strip() or "SEM-LOTE"
    quantidade    = data.get("quantidade")
    data_validade = data.get("data_validade")
    localizacao   = data.get("localizacao")
    usuario_id    = g.usuario_id

    if not produto_id and not produto_nome:
        return responses.err("Informe produto_id ou produto_nome.", status=400)
    if isinstance(quantidade, bool) or not isinstance(quantidade, int) or quantidade <= 0:
        return responses.err("Quantidade deve ser maior que zero.", status=400)

    db = database.get_db()
    try:
        with db.cursor() as cur:
            if produto_id:
                cur.execute("SELECT * FROM produtos WHERE id = %s FOR UPDATE", (produto_id,))
                prod = cur.fetchone()
                if not prod:
                    return responses.err("Produto não encontrado.", status=404)
            else:
                # Evita que itens homônimos sejam silenciosamente fundidos.
                cur.execute("SELECT id FROM produtos WHERE nome = %s LIMIT 1", (produto_nome,))
                if cur.fetchone():
                    return responses.err("Já existe um produto com esse nome. Informe produto_id para adicionar um lote ao cadastro existente.", status=409)
                fields = stock_product_data(data)
                fields.setdefault("preco_custo", 0.01)
                fields.setdefault("preco_venda", 0.01)
                fields.setdefault("estoque_minimo", int(read_settings(cur)["estoque_minimo_padrao"]))
                prod = normalize_product(fields)
            require_lot(read_settings(cur), lote)
            data_validade = validate_expiry(data_validade, prod)
            if not produto_id:
                produto_id = save_product(cur, prod)

            cur.execute(
                """
                INSERT INTO estoque (produto_id, lote, quantidade, data_validade, localizacao)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (produto_id, lote, quantidade, data_validade, localizacao)
            )
            estoque_id = cur.lastrowid

            cur.execute(
                """
                INSERT INTO movimentacoes_estoque
                       (estoque_id, usuario_id, tipo_movimentacao, quantidade, observacao)
                VALUES (%s, %s, 'entrada', %s, %s)
                """,
                (estoque_id, usuario_id, quantidade, "Cadastro inicial de estoque")
            )

            g.audit_values = {"produto_id": produto_id}
            commit_audit(db, estoque_id)
            return responses.ok({"mensagem": "Item de estoque criado com sucesso.",
                       "id": estoque_id, "produto_id": produto_id}, status=201)
    except ValueError as exc:
        db.rollback()
        return responses.err(str(exc), status=400)
    except pymysql.IntegrityError as exc:
        db.rollback()
        if "Duplicate entry" in str(exc) and "uk_produto_lote" in str(exc):
            return responses.err("Lote já cadastrado para este produto.", campo="lote", status=409)
        log.error("Erro DB ao criar item de estoque: %s", exc)
        return responses.err("Erro interno ao criar item de estoque.", status=500)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao criar item de estoque: %s", exc)
        return responses.err("Erro interno ao criar item de estoque.", status=500)


def update_item_estoque(estoque_id):
    """
    Atualiza item de estoque. Aceita campos do produto (nome, principio, categoria)
    para atualizar o produto associado. Registra ajuste de movimentação com
    a autoria da sessão quando a quantidade muda.
    """
    data = request.get_json(silent=True) or {}
    produto_id        = data.get("produto_id")
    lote              = data.get("lote")
    quantidade        = data.get("quantidade")
    data_validade     = data.get("data_validade")
    localizacao       = data.get("localizacao")
    usuario_id        = g.usuario_id

    if quantidade is not None:
        if not isinstance(quantidade, int) or isinstance(quantidade, bool) or quantidade < 0:
            return responses.err("Quantidade deve ser um número inteiro igual ou maior que zero.", campo="quantidade", status=400)

    db = database.get_db()
    try:
        with db.cursor() as cur:
            # O bloqueio protege o cálculo do ajuste contra outra baixa/entrada
            # concorrente no mesmo lote até o commit desta transação.
            cur.execute("SELECT id, produto_id, quantidade, data_validade FROM estoque WHERE id = %s FOR UPDATE", (estoque_id,))
            item_atual = cur.fetchone()
            if not item_atual:
                return responses.err("Item de estoque não encontrado.", status=404)

            if lote is not None:
                require_lot(read_settings(cur), lote.strip())
            pid = produto_id or item_atual["produto_id"]

            cur.execute("SELECT * FROM produtos WHERE id = %s FOR UPDATE", (pid,))
            current = cur.fetchone()
            if not current:
                return responses.err("Produto não encontrado.", status=404)
            product_fields = stock_product_data(data)
            product = normalize_product(product_fields, current)
            if "data_validade" in data or "exige_validade" in product_fields or produto_id is not None:
                data_validade = validate_expiry(data.get("data_validade", item_atual["data_validade"]), product)
            if product_fields:
                save_product(cur, product, pid)

            # Monta campos de estoque a atualizar
            campos, valores = [], []
            if produto_id is not None:
                campos.append("produto_id = %s"); valores.append(produto_id)
            if lote is not None:
                campos.append("lote = %s"); valores.append(lote.strip() or "SEM-LOTE")
            if quantidade is not None:
                campos.append("quantidade = %s"); valores.append(quantidade)
            if "data_validade" in data:
                campos.append("data_validade = %s"); valores.append(data_validade)
            if localizacao is not None:
                campos.append("localizacao = %s"); valores.append(localizacao)

            if campos:
                valores.append(estoque_id)
                cur.execute(
                    f"UPDATE estoque SET {', '.join(campos)} WHERE id = %s",
                    valores
                )

            # Registra ajuste de movimentação se quantidade mudou
            if quantidade is not None:
                delta = quantidade - item_atual["quantidade"]
                if delta != 0:
                    cur.execute(
                        """
                        INSERT INTO movimentacoes_estoque
                               (estoque_id, usuario_id, tipo_movimentacao, quantidade, observacao)
                        VALUES (%s, %s, 'ajuste', %s, %s)
                        """,
                        (estoque_id, usuario_id, abs(delta),
                         f"Ajuste manual: {'entrada' if delta > 0 else 'saída'} de {abs(delta)} unidades")
                    )

            commit_audit(db, cur.lastrowid)
            return responses.ok({"mensagem": "Item de estoque atualizado com sucesso."})
    except ValueError as exc:
        db.rollback()
        return responses.err(str(exc), status=400)
    except pymysql.IntegrityError as exc:
        db.rollback()
        if "Duplicate entry" in str(exc) and "uk_produto_lote" in str(exc):
            return responses.err("Lote já cadastrado para este produto.", campo="lote", status=409)
        log.error("Erro DB ao atualizar item de estoque: %s", exc)
        return responses.err("Erro interno ao atualizar item de estoque.", status=500)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao atualizar item de estoque: %s", exc)
        return responses.err("Erro interno ao atualizar item de estoque.", status=500)


def delete_item_estoque(estoque_id):
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM estoque WHERE id = %s FOR UPDATE", (estoque_id,))
            if not cur.fetchone():
                return responses.err("Item de estoque não encontrado.", status=404)

            # Histórico de estoque é trilha de auditoria: um lote que já teve
            # movimentação não pode ser apagado silenciosamente.
            cur.execute("SELECT 1 FROM movimentacoes_estoque WHERE estoque_id = %s LIMIT 1", (estoque_id,))
            if cur.fetchone():
                return responses.err("Não é possível excluir um item com movimentações. Zere o saldo por ajuste e mantenha o histórico.", status=409)
            cur.execute("DELETE FROM estoque WHERE id = %s", (estoque_id,))
            commit_audit(db, cur.lastrowid)
            return responses.ok({"mensagem": "Item de estoque excluído com sucesso."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao excluir item de estoque: %s", exc)
        return responses.err("Erro interno ao excluir item de estoque.", status=500)


def get_historico_estoque(estoque_id):
    """Retorna o histórico de movimentações de um item de estoque específico."""
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM estoque WHERE id = %s", (estoque_id,))
            if not cur.fetchone():
                return responses.err("Item de estoque não encontrado.", status=404)
            cur.execute("""
                SELECT me.id, me.tipo_movimentacao, me.finalidade, me.motivo, me.fornecedor_id, me.quantidade, me.observacao,
                       me.data_movimentacao,
                       u.nome AS usuario_nome
                FROM   movimentacoes_estoque me
                JOIN   usuarios u ON me.usuario_id = u.id
                WHERE  me.estoque_id = %s
                ORDER  BY me.data_movimentacao DESC
                LIMIT  50
            """, (estoque_id,))
            historico = cur.fetchall()
        for row in historico:
            if row.get("data_movimentacao") and hasattr(row["data_movimentacao"], "isoformat"):
                row["data_movimentacao"] = row["data_movimentacao"].isoformat()
        return responses.ok({"historico": historico})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar histórico de estoque: %s", exc)
        return responses.err("Erro interno ao buscar histórico de estoque.", status=500)


def get_movimentacoes_estoque():
    try:
        produto_id = query_int(request.args, "produto_id", minimum=1)
        periodo_dias = query_int(request.args, "periodo_dias", minimum=1, maximum=3650)
        limite = query_int(request.args, "limite", default=1000, minimum=1, maximum=5000)
        offset = query_int(request.args, "offset", default=0)
        search = search_text(request.args)
    except QueryError as exc:
        return responses.err(str(exc), campo=exc.campo)
    tipo = request.args.get("tipo")
    period = request.args.get("periodo")
    if period is not None and period not in PERIOD_START:
        return responses.err('Período inválido.', campo='periodo', status=400)
    tipos_validos = {"entrada", "saida", "ajuste", "transferencia"}
    if tipo and tipo not in tipos_validos:
        return responses.err("Tipo de movimentação inválido.", campo="tipo", status=400)
    filtros, parametros = [], []
    if produto_id is not None:
        filtros.append("e.produto_id = %s")
        parametros.append(produto_id)
    if tipo:
        filtros.append("me.tipo_movimentacao = %s")
        parametros.append(tipo)
    if periodo_dias is not None:
        filtros.append("me.data_movimentacao >= DATE_SUB(CURDATE(), INTERVAL %s DAY)")
        parametros.append(periodo_dias)
    if period:
        filtros.append(f"me.data_movimentacao >= {PERIOD_START[period]} AND me.data_movimentacao < CURDATE() + INTERVAL 1 DAY")
    if search:
        filtros.append("p.nome LIKE %s")
        parametros.append('%' + search + '%')
    where = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    try:
        db = database.get_db()
        with db.cursor() as cur:
            cur.execute("""
                SELECT me.*, e.lote, p.nome AS produto_nome,
                       COALESCE(cp.nome, 'Sem Categoria') AS categoria,
                       COALESCE(p.preco_custo, 0) AS valor_unitario,
                       u.nome AS usuario_nome
                FROM   movimentacoes_estoque me
                JOIN   estoque e   ON me.estoque_id = e.id
                JOIN   produtos p  ON e.produto_id  = p.id
                LEFT JOIN categorias_produto cp ON p.categoria_id = cp.id
                JOIN   usuarios u  ON me.usuario_id = u.id
                {where}
                ORDER  BY me.data_movimentacao DESC, me.id DESC
                LIMIT  %s OFFSET %s
            """.format(where=where), (*parametros, limite, offset))
            movimentacoes = cur.fetchall()
            total = None
            if 'offset' in request.args:
                cur.execute(f"""SELECT COUNT(*) AS total FROM movimentacoes_estoque me
                    JOIN estoque e ON me.estoque_id=e.id JOIN produtos p ON e.produto_id=p.id
                    JOIN usuarios u ON me.usuario_id=u.id {where}""", tuple(parametros))
                total = int(cur.fetchone()['total'])
        for row in movimentacoes:
            if row.get("data_movimentacao") and hasattr(row["data_movimentacao"], "isoformat"):
                row["data_movimentacao"] = row["data_movimentacao"].isoformat()
            if row.get("valor_unitario") is not None:
                row["valor_unitario"] = float(row["valor_unitario"])
        result = {"movimentacoes": movimentacoes, "limite": limite, "offset": offset}
        if total is not None:
            more = bool(movimentacoes) and offset + len(movimentacoes) < total
            result.update(total=total, tem_mais=more,
                          proximo_offset=offset + len(movimentacoes) if more else None)
        return responses.ok(result)
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar movimentações de estoque: %s", exc)
        return responses.err("Erro interno ao buscar movimentações de estoque.", status=500)


def get_movimentacao_estoque(movimentacao_id):
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT me.*, e.lote, p.nome as produto_nome, u.nome as usuario_nome FROM movimentacoes_estoque me JOIN estoque e ON me.estoque_id = e.id JOIN produtos p ON e.produto_id = p.id JOIN usuarios u ON me.usuario_id = u.id WHERE me.id = %s", (movimentacao_id,))
            movimentacao = cur.fetchone()
            if not movimentacao:
                return responses.err("Movimentação de estoque não encontrada.", status=404)
        return responses.ok({"movimentacao": movimentacao})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar movimentação de estoque: %s", exc)
        return responses.err("Erro interno ao buscar movimentação de estoque.", status=500)


def create_movimentacao_estoque():
    data = request.get_json(silent=True) or {}
    estoque_id = data.get("estoque_id")
    usuario_id = g.usuario_id
    tipo_movimentacao = data.get("tipo_movimentacao")
    quantidade = data.get("quantidade")
    observacao = data.get("observacao")
    estoque_destino_id = data.get("estoque_destino_id")
    finalidade = data.get("finalidade")
    motivo = data.get("motivo")
    fornecedor_id = None
    if data.get("fornecedor_id") is not None:
        supplied = data["fornecedor_id"]
        if finalidade != "devolucao_fornecedor" or isinstance(supplied, bool) or not isinstance(supplied, int) or supplied <= 0:
            return responses.err("Fornecedor inválido para esta operação.", campo="fornecedor_id", status=400)
    if finalidade == "devolucao_fornecedor" and estoque_destino_id is not None:
        return responses.err("Devolução ao fornecedor não possui estoque interno de destino.", campo="estoque_destino_id", status=400)
    if finalidade is not None:
        if not isinstance(finalidade, str) or finalidade not in {"descarte", "venda", "devolucao_fornecedor"}:
            return responses.err("Finalidade inválida.", campo="finalidade", status=400)
        if tipo_movimentacao != "saida":
            return responses.err("Finalidade só é permitida em saídas.", campo="finalidade", status=400)
    if finalidade in ("descarte", "devolucao_fornecedor"):
        # Autorização administrativa adicional à permissão persistida de estoque
        # e ao CSRF verificados pelo middleware. Nunca deriva de texto livre.
        if g.usuario_perfil not in INVENTORY_ROLES or "estoque" not in g.usuario_permissoes:
            return responses.err("Seu perfil não tem permissão para baixa administrativa.", status=403)
        if not isinstance(motivo, str) or not motivo.strip() or len(motivo.strip()) > 255:
            return responses.err("Informe um motivo de até 255 caracteres.", campo="motivo", status=400)
        motivo = motivo.strip()
    elif motivo is not None:
        return responses.err("Motivo exige uma finalidade administrativa.", campo="motivo", status=400)
    if observacao is not None and (not isinstance(observacao, str) or len(observacao) > 255):
        return responses.err("Observação deve ter até 255 caracteres.", campo="observacao", status=400)

    if not estoque_id or not tipo_movimentacao or not quantidade:
        return responses.err("ID do estoque, tipo de movimentação e quantidade são obrigatórios.", status=400)
    if not isinstance(quantidade, int) or isinstance(quantidade, bool):
        return responses.err("Quantidade deve ser um número inteiro.", campo="quantidade", status=400)
    if tipo_movimentacao not in ["entrada", "saida", "ajuste", "transferencia"]:
        return responses.err("Tipo de movimentação inválido.", status=400)
    if tipo_movimentacao == "ajuste":
        if quantidade == 0:
            return responses.err("Ajuste deve ser diferente de zero.", campo="quantidade", status=400)
    elif quantidade <= 0:
        return responses.err("Quantidade deve ser maior que zero.", campo="quantidade", status=400)
    if tipo_movimentacao == "transferencia":
        if not isinstance(estoque_destino_id, int) or isinstance(estoque_destino_id, bool) or estoque_destino_id <= 0:
            return responses.err("Informe o estoque de destino para a transferência.", campo="estoque_destino_id", status=400)
        if estoque_destino_id == estoque_id:
            return responses.err("O estoque de destino deve ser diferente da origem.", campo="estoque_destino_id", status=400)

    db = database.get_db()
    try:
        with db.cursor() as cur:
            # Em transferências, a ordem fixa evita deadlock quando dois lotes
            # são transferidos simultaneamente em sentidos opostos.
            ids_bloqueio = sorted({estoque_id, estoque_destino_id}) if tipo_movimentacao == "transferencia" else [estoque_id]
            cur.execute(
                "SELECT id, produto_id, quantidade, lote, data_validade FROM estoque WHERE id IN (" + ", ".join(["%s"] * len(ids_bloqueio)) + ") FOR UPDATE",
                ids_bloqueio,
            )
            itens = {item["id"]: item for item in cur.fetchall()}
            item_estoque = itens.get(estoque_id)
            if not item_estoque:
                return responses.err("Item de estoque não encontrado.", campo="estoque_id", status=400)
            item_destino = itens.get(estoque_destino_id) if tipo_movimentacao == "transferencia" else None
            if tipo_movimentacao == "transferencia" and not item_destino:
                return responses.err("Item de estoque de destino não encontrado.", campo="estoque_destino_id", status=400)
            if tipo_movimentacao == "transferencia" and item_destino["produto_id"] != item_estoque["produto_id"]:
                return responses.err("A transferência deve ocorrer entre lotes do mesmo produto.", campo="estoque_destino_id", status=400)

            if finalidade == "devolucao_fornecedor":
                # Captura o vínculo vigente no cadastro, sem aceitar fornecedor arbitrário.
                cur.execute("SELECT fornecedor_id FROM produtos WHERE id = %s FOR UPDATE", (item_estoque["produto_id"],))
                produto = cur.fetchone()
                if not produto:
                    return responses.err("Produto não encontrado.", status=400)
                fornecedor_id = produto.get("fornecedor_id")
                if data.get("fornecedor_id") is not None and data["fornecedor_id"] != fornecedor_id:
                    return responses.err("Fornecedor não corresponde ao cadastro do produto.", campo="fornecedor_id", status=400)

            settings = read_settings(cur)
            if tipo_movimentacao == 'saida' and finalidade not in ('descarte', 'devolucao_fornecedor'):
                require_usable_stock(settings, item_estoque)
            elif tipo_movimentacao in ('entrada', 'transferencia') or finalidade in ('descarte', 'devolucao_fornecedor'):
                require_lot(settings, item_estoque.get('lote'))
                if item_destino:
                    require_lot(settings, item_destino.get('lote'))
            nova_quantidade_estoque = item_estoque["quantidade"]
            if tipo_movimentacao == "entrada":
                nova_quantidade_estoque += quantidade
            elif tipo_movimentacao == "saida":
                if nova_quantidade_estoque < quantidade:
                    return responses.err("Quantidade em estoque insuficiente para saída.", status=400)
                nova_quantidade_estoque -= quantidade
            elif tipo_movimentacao == "ajuste":
                if nova_quantidade_estoque + quantidade < 0:
                    return responses.err("Quantidade em estoque insuficiente para ajuste de saída.", status=400)
                nova_quantidade_estoque += quantidade
            elif tipo_movimentacao == "transferencia":
                if nova_quantidade_estoque < quantidade:
                    return responses.err("Quantidade em estoque insuficiente para transferência.", status=400)
                nova_quantidade_estoque -= quantidade

            cur.execute(
                "UPDATE estoque SET quantidade = %s WHERE id = %s",
                (nova_quantidade_estoque, estoque_id)
            )

            if tipo_movimentacao == "transferencia":
                cur.execute("UPDATE estoque SET quantidade = quantidade + %s WHERE id = %s", (quantidade, estoque_destino_id))

            cur.execute(
                """
                INSERT INTO movimentacoes_estoque (estoque_id, usuario_id, tipo_movimentacao, quantidade, observacao, finalidade, motivo, fornecedor_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (estoque_id, usuario_id, tipo_movimentacao, quantidade, observacao, finalidade, motivo, fornecedor_id)
            )
            if tipo_movimentacao == "transferencia":
                cur.execute(
                    """
                    INSERT INTO movimentacoes_estoque (estoque_id, usuario_id, tipo_movimentacao, quantidade, observacao)
                    VALUES (%s, %s, 'transferencia', %s, %s)
                    """,
                    (estoque_destino_id, usuario_id, quantidade, observacao or f"Transferência recebida do lote {estoque_id}"),
                )
            movimentacao_id = cur.lastrowid
            if finalidade in ("descarte", "devolucao_fornecedor"):
                g.audit_values = {"finalidade": finalidade, "motivo": motivo, "lote": item_estoque["lote"], "produto_id": item_estoque["produto_id"], "fornecedor_id": fornecedor_id}
            commit_audit(db, movimentacao_id)
            return responses.ok({"mensagem": "Movimentação de estoque criada com sucesso.", "id": movimentacao_id}, status=201)
    except ValueError as exc:
        db.rollback()
        return responses.err(str(exc), status=400)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao criar movimentação de estoque: %s", exc)
        return responses.err("Erro interno ao criar movimentação de estoque.", status=500)


def register_routes(app):
    """Registra as URLs e nomes de endpoints existentes."""
    app.add_url_rule('/estoque', view_func=get_estoque, methods=['GET'])
    app.add_url_rule('/estoque/parametros', view_func=get_parametros_estoque, methods=['GET'])
    app.add_url_rule('/estoque/<int:estoque_id>', view_func=get_item_estoque, methods=['GET'])
    app.add_url_rule('/estoque', view_func=create_item_estoque, methods=['POST'])
    app.add_url_rule('/estoque/<int:estoque_id>', view_func=update_item_estoque, methods=['PUT'])
    app.add_url_rule('/estoque/<int:estoque_id>', view_func=delete_item_estoque, methods=['DELETE'])
    app.add_url_rule('/estoque/<int:estoque_id>/historico', view_func=get_historico_estoque, methods=['GET'])
    app.add_url_rule('/movimentacoes-estoque', view_func=get_movimentacoes_estoque, methods=['GET'])
    app.add_url_rule('/movimentacoes-estoque/<int:movimentacao_id>', view_func=get_movimentacao_estoque, methods=['GET'])
    app.add_url_rule('/movimentacoes-estoque', view_func=create_movimentacao_estoque, methods=['POST'])
