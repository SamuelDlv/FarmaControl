"""routes.relatorios: responsabilidades extraídas da aplicação Flask."""

from farmacontrol.core import database
from farmacontrol.core import responses
from farmacontrol.services.reporting import PERIOD_START
from farmacontrol.services.reporting import stock_report
from flask import request
import logging
import pymysql.cursors

log = logging.getLogger("farmacontrol")


def relatorio_estoque():
    """Relatório completo de posição de estoque com KPIs e listagem."""
    period = request.args.get('periodo', 'month')
    if period not in PERIOD_START:
        return responses.err('Período inválido.', campo='periodo', status=400)
    db = database.get_db()
    try:
        with db.cursor() as cur:
            report = stock_report(cur, period)
        return responses.ok(report)
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao gerar relatório de estoque: %s", exc)
        return responses.err("Erro interno ao gerar relatório de estoque.", status=500)


def relatorio_vencimentos():
    """Relatório de vencimentos com distribuição por faixa de prazo."""
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) AS total FROM estoque
                WHERE data_validade < CURDATE() AND quantidade > 0
            """)
            vencidos = cur.fetchone()["total"] or 0

            cur.execute("""
                SELECT COUNT(*) AS total FROM estoque
                WHERE data_validade BETWEEN CURDATE()
                                        AND DATE_ADD(CURDATE(), INTERVAL 30 DAY)
                  AND quantidade > 0
            """)
            ate_30 = cur.fetchone()["total"] or 0

            cur.execute("""
                SELECT COUNT(*) AS total FROM estoque
                WHERE data_validade BETWEEN DATE_ADD(CURDATE(), INTERVAL 31 DAY)
                                        AND DATE_ADD(CURDATE(), INTERVAL 60 DAY)
                  AND quantidade > 0
            """)
            ate_60 = cur.fetchone()["total"] or 0

            cur.execute("""
                SELECT COUNT(*) AS total FROM estoque
                WHERE data_validade > DATE_ADD(CURDATE(), INTERVAL 60 DAY)
                  AND quantidade > 0
            """)
            ok_count = cur.fetchone()["total"] or 0

        return responses.ok({
            "kpis": {
                "vencidos": int(vencidos),
                "ate_30":   int(ate_30),
                "ate_60":   int(ate_60),
                "ok":       int(ok_count),
            }
        })
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao gerar relatório de vencimentos: %s", exc)
        return responses.err("Erro interno ao gerar relatório de vencimentos.", status=500)


def relatorio_compras():
    """Relatório de compras com KPIs e movimentações."""
    period = request.args.get('periodo', 'month')
    if period not in PERIOD_START:
        return responses.err('Período inválido.', campo='periodo', status=400)
    scope = f"data_pedido >= {PERIOD_START[period]} AND data_pedido < CURDATE() + INTERVAL 1 DAY"
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS total FROM compras WHERE {scope}")
            total_pedidos = cur.fetchone()["total"] or 0

            cur.execute(f"""
                SELECT COALESCE(SUM(valor_total), 0) AS valor FROM compras
                WHERE status = 'recebido' AND {scope}
            """)
            valor_comprado = float(cur.fetchone()["valor"] or 0)

            cur.execute(f"SELECT COUNT(*) AS total FROM compras WHERE status = 'pendente' AND {scope}")
            pendentes = cur.fetchone()["total"] or 0

            # Fornecedores ativos por perfil de compra
            cur.execute("SELECT COUNT(DISTINCT id) AS total FROM fornecedores WHERE ativo = TRUE")
            fornecedores = cur.fetchone()["total"] or 0

            # Fornecedores com pedidos registrados (usados nas compras)
            cur.execute(f"""
                SELECT f.id, f.nome_fantasia, f.cnpj, COUNT(c.id) AS total_pedidos,
                       COALESCE(SUM(c.valor_total), 0) AS valor_total
                FROM   fornecedores f
                JOIN   compras c ON c.fornecedor_id = f.id
                WHERE {scope} AND c.status <> 'cancelado'
                GROUP  BY f.id, f.nome_fantasia, f.cnpj
                ORDER  BY valor_total DESC, f.id
            """)
            fornecedores_rank = cur.fetchall()
            for row in fornecedores_rank:
                row["valor_total"] = float(row["valor_total"] or 0)
                row["total_pedidos"] = int(row["total_pedidos"] or 0)

            # Pedidos por categoria (classificação por fornecedor)
            cur.execute(f"""
                SELECT DATE_FORMAT(c.data_pedido, '%Y-%m') AS mes,
                       COUNT(*) AS total,
                       COALESCE(SUM(c.valor_total), 0) AS valor
                FROM   compras c
                WHERE  {scope} AND c.status <> 'cancelado'
                GROUP  BY mes
                ORDER  BY mes ASC
            """)
            evolucao = cur.fetchall()
            for row in evolucao:
                row["total"] = int(row["total"] or 0)
                row["valor"] = float(row["valor"] or 0)

            # Categorias mais compradas (via categorias de produtos dos itens)
            cur.execute(f"""
                SELECT COALESCE(cp.nome, 'Sem Categoria') AS categoria,
                       COUNT(DISTINCT ic.compra_id) AS total_pedidos,
                       COALESCE(SUM(ic.quantidade * ic.preco_unitario), 0) AS valor
                FROM   itens_compra ic
                JOIN   produtos p        ON ic.produto_id = p.id
                LEFT JOIN categorias_produto cp ON p.categoria_id = cp.id
                JOIN   compras c         ON ic.compra_id = c.id
                WHERE  {scope} AND c.status <> 'cancelado'
                GROUP  BY cp.id, cp.nome
                ORDER  BY valor DESC
            """)
            categorias = cur.fetchall()
            for row in categorias:
                row["total_pedidos"] = int(row["total_pedidos"] or 0)
                row["valor"] = float(row["valor"] or 0)

        return responses.ok({
            "kpis": {
                "total_pedidos":   int(total_pedidos),
                "valor_comprado":  round(valor_comprado, 2),
                "pedidos_pendentes": int(pendentes),
                "fornecedores_ativos": int(fornecedores),
            },
            "fornecedores": fornecedores_rank,
            "categorias":    categorias,
            "evolucao":      evolucao,
        })
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao gerar relatório de compras: %s", exc)
        return responses.err("Erro interno ao gerar relatório de compras.", status=500)


def register_routes(app):
    """Registra as URLs e nomes de endpoints existentes."""
    app.add_url_rule('/relatorios/estoque', view_func=relatorio_estoque, methods=['GET'])
    app.add_url_rule('/relatorios/vencimentos', view_func=relatorio_vencimentos, methods=['GET'])
    app.add_url_rule('/relatorios/compras', view_func=relatorio_compras, methods=['GET'])
