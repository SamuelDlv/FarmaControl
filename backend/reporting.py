"""Agregações de relatórios feitas no banco, sem truncar o histórico de movimentos."""

PERIOD_START = {
    'month': 'DATE_SUB(CURDATE(), INTERVAL (DAYOFMONTH(CURDATE()) - 1) DAY)',
    'quarter': 'MAKEDATE(YEAR(CURDATE()), 1) + INTERVAL (QUARTER(CURDATE()) - 1) QUARTER',
    'year': 'MAKEDATE(YEAR(CURDATE()), 1)',
}


def stock_report(cur, period):
    start = PERIOD_START[period]
    scope = f'me.data_movimentacao >= {start} AND me.data_movimentacao < CURDATE() + INTERVAL 1 DAY'
    cur.execute("""
        SELECT COALESCE(SUM(e.quantidade), 0) AS unidades,
               COALESCE(SUM(e.quantidade * p.preco_custo), 0) AS valor,
               COALESCE(SUM(e.quantidade > 0 AND
                   e.data_validade <= CURDATE() + INTERVAL 60 DAY), 0) AS alertas,
               COALESCE(SUM(e.quantidade = 0), 0) AS zerados
        FROM estoque e JOIN produtos p ON p.id = e.produto_id
    """)
    stock = cur.fetchone()
    cur.execute(f"""
        SELECT COALESCE(SUM(IF(me.tipo_movimentacao='saida', me.quantidade, 0)), 0) AS saidas,
               COALESCE(SUM(IF(me.tipo_movimentacao='entrada', me.quantidade, 0)), 0) AS entradas,
               COALESCE(SUM(IF(me.tipo_movimentacao='saida', me.quantidade*p.preco_custo, 0)), 0) AS valor_saidas,
               COALESCE(SUM(IF(me.tipo_movimentacao='entrada', me.quantidade*p.preco_custo, 0)), 0) AS valor_entradas,
               COUNT(DISTINCT DATE(me.data_movimentacao)) AS dias_operacao,
               COUNT(DISTINCT IF(me.tipo_movimentacao='saida' AND me.observacao LIKE 'Descarte:%%', me.estoque_id, NULL)) AS descartados
        FROM movimentacoes_estoque me
        JOIN estoque e ON e.id=me.estoque_id JOIN produtos p ON p.id=e.produto_id
        WHERE {scope}
    """)
    summary = {key: float(value or 0) for key, value in cur.fetchone().items()}
    cur.execute(f"""
        SELECT COALESCE(cp.nome, 'Sem categoria') AS categoria, SUM(me.quantidade) AS qtd_total
        FROM movimentacoes_estoque me
        JOIN estoque e ON e.id=me.estoque_id JOIN produtos p ON p.id=e.produto_id
        LEFT JOIN categorias_produto cp ON cp.id=p.categoria_id
        WHERE {scope} AND me.tipo_movimentacao='saida'
        GROUP BY cp.id, cp.nome ORDER BY qtd_total DESC
    """)
    categories = [dict(row, qtd_total=int(row['qtd_total'])) for row in cur.fetchall()]
    cur.execute(f"""
        SELECT p.nome, SUM(me.quantidade) AS quantidade
        FROM movimentacoes_estoque me
        JOIN estoque e ON e.id=me.estoque_id JOIN produtos p ON p.id=e.produto_id
        WHERE {scope} AND me.tipo_movimentacao='saida'
        GROUP BY p.id, p.nome ORDER BY quantidade DESC, p.nome LIMIT 10
    """)
    products = [dict(row, quantidade=int(row['quantidade'])) for row in cur.fetchall()]
    cur.execute(f"""
        SELECT DATE_FORMAT(me.data_movimentacao, '%Y-%m') AS mes,
               SUM(IF(me.tipo_movimentacao='saida', me.quantidade, 0)) AS saidas,
               SUM(IF(me.tipo_movimentacao='entrada', me.quantidade, 0)) AS entradas
        FROM movimentacoes_estoque me WHERE {scope}
        GROUP BY mes ORDER BY mes
    """)
    months = [dict(row, saidas=int(row['saidas']), entradas=int(row['entradas'])) for row in cur.fetchall()]
    cur.execute(f"SELECT {start} AS inicio, CURDATE() AS fim")
    dates = {key: str(value) for key, value in cur.fetchone().items()}
    units = int(stock['unidades'])
    return {
        'kpis': {'total_saidas': int(summary['saidas']), 'valor_estoque': float(stock['valor']),
                 'itens_alerta': int(stock['alertas']),
                 'giro_estoque': round(summary['saidas'] / units, 2) if units else 0},
        'resumo': dict(summary, zerados=int(stock['zerados'])),
        'por_categoria': categories, 'top_produtos': products, 'evolucao': months,
        'periodo': dict(dates, tipo=period),
    }
