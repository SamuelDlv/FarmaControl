"""routes.dashboard: responsabilidades extraídas da aplicação Flask."""

from farmacontrol.core import database
from farmacontrol.core import responses
from farmacontrol.services.system_settings import active_alerts
from farmacontrol.services.system_settings import read_settings
import logging
import pymysql.cursors

log = logging.getLogger("farmacontrol")


def get_dashboard_stats():
    """Retorna estatísticas consolidadas para o dashboard do proprietário."""
    db = database.get_db()
    try:
        with db.cursor() as cur:
            # Total de itens distintos em estoque
            cur.execute("SELECT COUNT(*) AS total FROM estoque WHERE quantidade > 0")
            total_itens = cur.fetchone()["total"] or 0

            # Valor total em estoque (quantidade * preco_custo)
            cur.execute("""
                SELECT COALESCE(SUM(e.quantidade * p.preco_custo), 0) AS valor
                FROM   estoque e
                JOIN   produtos p ON e.produto_id = p.id
            """)
            valor_estoque = float(cur.fetchone()["valor"] or 0)

            # Itens com estoque crítico (quantidade <= estoque_minimo do produto)
            cur.execute("""
                SELECT COUNT(*) AS total
                FROM   estoque e
                JOIN   produtos p ON e.produto_id = p.id
                WHERE  e.quantidade >= 0
                  AND  e.quantidade <= COALESCE(p.estoque_minimo, 10)
            """)
            estoque_critico = cur.fetchone()["total"] or 0

            # Itens com estoque baixo (até 2x o mínimo, mas acima do crítico)
            cur.execute("""
                SELECT COUNT(*) AS total
                FROM   estoque e
                JOIN   produtos p ON e.produto_id = p.id
                WHERE  e.quantidade > COALESCE(p.estoque_minimo, 10)
                  AND  e.quantidade <= COALESCE(p.estoque_minimo, 10) * 2
            """)
            estoque_baixo = cur.fetchone()["total"] or 0

            # Itens vencidos
            cur.execute("""
                SELECT COUNT(*) AS total
                FROM   estoque
                WHERE  data_validade < CURDATE() AND quantidade > 0
                  AND  data_validade IS NOT NULL
            """)
            vencidos = cur.fetchone()["total"] or 0

            # Vencendo em até 30 dias
            cur.execute("""
                SELECT COUNT(*) AS total
                FROM   estoque
                WHERE  data_validade BETWEEN CURDATE()
                                         AND DATE_ADD(CURDATE(), INTERVAL 30 DAY)
                  AND  quantidade > 0
                  AND  data_validade IS NOT NULL
            """)
            vencendo_30 = cur.fetchone()["total"] or 0

            # Vencendo em até 60 dias
            cur.execute("""
                SELECT COUNT(*) AS total
                FROM   estoque
                WHERE  data_validade BETWEEN DATE_ADD(CURDATE(), INTERVAL 31 DAY)
                                         AND DATE_ADD(CURDATE(), INTERVAL 60 DAY)
                  AND  quantidade > 0
                  AND  data_validade IS NOT NULL
            """)
            vencendo_60 = cur.fetchone()["total"] or 0

            # Saídas hoje
            cur.execute("""
                SELECT COALESCE(SUM(quantidade), 0) AS total
                FROM   movimentacoes_estoque
                WHERE  tipo_movimentacao = 'saida'
                  AND  DATE(data_movimentacao) = CURDATE()
            """)
            saidas_hoje = int(cur.fetchone()["total"] or 0)

            # Entradas hoje
            cur.execute("""
                SELECT COALESCE(SUM(quantidade), 0) AS total
                FROM   movimentacoes_estoque
                WHERE  tipo_movimentacao = 'entrada'
                  AND  DATE(data_movimentacao) = CURDATE()
            """)
            entradas_hoje = int(cur.fetchone()["total"] or 0)

            # Total de compras pendentes
            cur.execute("SELECT COUNT(*) AS total FROM compras WHERE status = 'pendente'")
            compras_pendentes = cur.fetchone()["total"] or 0

            # Total de fornecedores ativos
            cur.execute("SELECT COUNT(*) AS total FROM fornecedores WHERE ativo = TRUE")
            fornecedores_ativos = cur.fetchone()["total"] or 0

            # Movimentações dos últimos 7 dias (entradas e saídas por dia)
            cur.execute("""
                SELECT DATE(data_movimentacao) AS dia,
                       tipo_movimentacao,
                       SUM(quantidade) AS total
                FROM   movimentacoes_estoque
                WHERE  data_movimentacao >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
                  AND  tipo_movimentacao IN ('entrada', 'saida')
                GROUP  BY dia, tipo_movimentacao
                ORDER  BY dia ASC
            """)
            movs_semana = cur.fetchall()
            for row in movs_semana:
                if row.get("dia") and hasattr(row["dia"], "isoformat"):
                    row["dia"] = row["dia"].isoformat()

            # Top 5 produtos mais movimentados (saídas nos últimos 30 dias)
            cur.execute("""
                SELECT p.nome AS produto_nome,
                       SUM(me.quantidade) AS total_saidas
                FROM   movimentacoes_estoque me
                JOIN   estoque e  ON me.estoque_id = e.id
                JOIN   produtos p ON e.produto_id  = p.id
                WHERE  me.tipo_movimentacao = 'saida'
                  AND  me.data_movimentacao >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                GROUP  BY p.id, p.nome
                ORDER  BY total_saidas DESC
                LIMIT  5
            """)
            top_produtos = cur.fetchall()

            # Produtos Críticos para a tabela do dashboard
            cur.execute("""
                SELECT e.id AS estoque_id, p.id AS produto_id, p.nome, 
                       COALESCE(cp.nome, 'Sem Categoria') as categoria,
                       e.lote, 
                       e.quantidade, 
                       COALESCE(p.estoque_minimo, 10) AS estoque_minimo, 
                       e.data_validade,
                       CASE 
                         WHEN e.quantidade <= COALESCE(p.estoque_minimo, 10)
                           OR (e.data_validade IS NOT NULL
                               AND e.data_validade <= CURDATE() + INTERVAL 30 DAY) THEN 'crit'
                         ELSE 'low'
                       END as status_classe
                FROM   estoque e
                JOIN   produtos p ON e.produto_id = p.id
                LEFT JOIN categorias_produto cp ON p.categoria_id = cp.id
                WHERE  e.quantidade <= COALESCE(p.estoque_minimo, 10) * 2
                   OR (e.data_validade IS NOT NULL
                       AND e.data_validade <= CURDATE() + INTERVAL 30 DAY)
                ORDER  BY CASE
                            WHEN e.data_validade IS NULL THEN 1
                            ELSE 0
                          END,
                          e.data_validade ASC,
                          e.quantidade ASC,
                          p.nome ASC
            """)
            produtos_criticos = cur.fetchall()
            for row in produtos_criticos:
                if row.get("data_validade") and hasattr(row["data_validade"], "isoformat"):
                    row["data_validade"] = row["data_validade"].isoformat()

            cur.execute("""
                SELECT e.id, p.nome, e.lote, e.quantidade, e.data_validade,
                       DATEDIFF(e.data_validade, CURDATE()) AS dias
                FROM estoque e JOIN produtos p ON p.id=e.produto_id
                WHERE e.quantidade > 0 AND e.data_validade BETWEEN CURDATE() AND CURDATE() + INTERVAL 60 DAY
                ORDER BY e.data_validade, p.nome, e.id
            """)
            vencimentos_proximos = cur.fetchall()
            for row in vencimentos_proximos:
                row['data_validade'] = row['data_validade'].isoformat()

            alertas_ativos = active_alerts(cur, read_settings(cur))

        return responses.ok({
            "alertas_ativos": alertas_ativos,
            "kpis": {
                "total_itens":        int(total_itens),
                "valor_estoque":      round(valor_estoque, 2),
                "estoque_critico":    int(estoque_critico),
                "estoque_baixo":      int(estoque_baixo),
                "vencidos":           int(vencidos),
                "vencendo_30":        int(vencendo_30),
                "vencendo_60":        int(vencendo_60),
                "saidas_hoje":        saidas_hoje,
                "entradas_hoje":      entradas_hoje,
                "compras_pendentes":  int(compras_pendentes),
                "fornecedores_ativos": int(fornecedores_ativos),
            },
            "movimentacoes_semana": movs_semana,
            "top_produtos":         top_produtos,
            "produtos_criticos":    produtos_criticos,
            "vencimentos_proximos": vencimentos_proximos,
        })
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar estatísticas do dashboard: %s", exc)
        return responses.err("Erro interno ao buscar estatísticas do dashboard.", status=500)


def register_routes(app):
    """Registra as URLs e nomes de endpoints existentes."""
    app.add_url_rule('/dashboard/stats', view_func=get_dashboard_stats, methods=['GET'])
