"""routes.financeiro: responsabilidades extraídas da aplicação Flask."""

from datetime import datetime
from datetime import timedelta
from farmacontrol.core import database
from farmacontrol.core import responses
from farmacontrol.services.audit import commit_audit
from flask import g
from flask import jsonify
from flask import request
import logging
import math
import pymysql.cursors

log = logging.getLogger("farmacontrol")


def _fin_tables_exist():
    """Verifica se as duas tabelas requeridas pelo módulo financeiro existem."""
    try:
        db = database.get_db()
        with db.cursor() as cur:
            cur.execute("SHOW TABLES LIKE 'financeiro_transacoes'")
            transacoes = cur.fetchone() is not None
            cur.execute("SHOW TABLES LIKE 'financeiro_categorias'")
            return transacoes and cur.fetchone() is not None
    except pymysql.MySQLError as exc:
        log.error("Erro ao verificar tabelas financeiras: %s", exc)
        return False


def financeiro_stats():
    """Retorna KPIs financeiros para o período selecionado."""
    if not _fin_tables_exist():
        return responses.err('Tabelas financeiras não configuradas. Execute a migração 005_tabela_financeiro.sql', status=503)
    days = request.args.get('days', '30', type=int)
    if days not in (7, 30, 90):
        days = 30
    db = database.get_db()
    try:
        with db.cursor() as cur:
            # Receitas do período
            cur.execute("""
                SELECT COALESCE(SUM(CASE WHEN fc.tipo = 'receita' THEN t.valor ELSE 0 END), 0) AS receitas,
                       COALESCE(SUM(CASE WHEN fc.tipo = 'despesa' THEN t.valor ELSE 0 END), 0) AS despesas
                FROM financeiro_transacoes t
                JOIN financeiro_categorias fc ON fc.id = t.categoria_id
                WHERE t.data_transacao >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                  AND t.data_transacao < CURDATE() + INTERVAL 1 DAY
                  AND t.status = 'pago'
            """, (days,))
            row = cur.fetchone()
            receitas = float(row['receitas'] or 0)
            despesas = float(row['despesas'] or 0)
            saldo = receitas - despesas

            # Ticket médio (vendas do período)
            cur.execute("""
                SELECT AVG(valor_total) AS ticket
                FROM vendas
                WHERE data_venda >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                  AND data_venda < CURDATE() + INTERVAL 1 DAY
                  AND status = 'concluida'
            """, (days,))
            ticket = float(cur.fetchone()['ticket'] or 0)

            # Delta (comparação com período anterior)
            cur.execute("""
                SELECT COALESCE(SUM(CASE WHEN fc.tipo = 'receita' THEN t.valor ELSE 0 END), 0) AS receitas_ant
                FROM financeiro_transacoes t
                JOIN financeiro_categorias fc ON fc.id = t.categoria_id
                WHERE t.data_transacao >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                  AND t.data_transacao < DATE_SUB(CURDATE(), INTERVAL %s DAY)
                  AND t.status = 'pago'
            """, (days * 2, days))
            receitas_ant = float(cur.fetchone()['receitas_ant'] or 0)
            delta_receitas = ((receitas - receitas_ant) / receitas_ant * 100) if receitas_ant > 0 else 0

            cur.execute("""
                SELECT COALESCE(SUM(CASE WHEN fc.tipo = 'despesa' THEN t.valor ELSE 0 END), 0) AS despesas_ant
                FROM financeiro_transacoes t
                JOIN financeiro_categorias fc ON fc.id = t.categoria_id
                WHERE t.data_transacao >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                  AND t.data_transacao < DATE_SUB(CURDATE(), INTERVAL %s DAY)
                  AND t.status = 'pago'
            """, (days * 2, days))
            despesas_ant = float(cur.fetchone()['despesas_ant'] or 0)
            delta_despesas = ((despesas - despesas_ant) / despesas_ant * 100) if despesas_ant > 0 else 0

            # Sparkline data (últimos 14 pontos)
            cur.execute("""
                SELECT DATE(t.data_transacao) AS dia,
                       SUM(CASE WHEN fc.tipo = 'receita' THEN t.valor ELSE -t.valor END) AS liquido
                FROM financeiro_transacoes t
                JOIN financeiro_categorias fc ON fc.id = t.categoria_id
                WHERE t.data_transacao >= DATE_SUB(CURDATE(), INTERVAL 14 DAY)
                  AND t.data_transacao < CURDATE() + INTERVAL 1 DAY
                  AND t.status = 'pago'
                GROUP BY DATE(t.data_transacao)
                ORDER BY dia ASC
            """)
            spark = [float(r['liquido'] or 0) for r in cur.fetchall()]

        return jsonify({
            'ok': True,
            'saldo': saldo,
            'receitas': receitas,
            'despesas': despesas,
            'ticket_medio': ticket,
            'delta_receitas': delta_receitas,
            'delta_despesas': delta_despesas,
            'spark': spark
        })
    except pymysql.MySQLError as exc:
        log.error("Erro DB em financeiro/stats: %s", exc)
        return responses.err('Erro interno ao consultar indicadores financeiros.', status=500)


def financeiro_fluxo():
    """Retorna dados para o gráfico de fluxo de caixa (receitas vs despesas por dia)."""
    if not _fin_tables_exist():
        return responses.err('Tabelas financeiras não configuradas. Execute a migração 005_tabela_financeiro.sql', status=503)
    days = request.args.get('days', '7', type=int)
    if days not in (7, 30, 90):
        days = 7
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    if bool(start_date) != bool(end_date):
        return responses.err('Informe data inicial e final juntas.', campo='start_date', status=400)
    if start_date and end_date:
        try:
            start_day = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_day = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return responses.err('Datas inválidas. Use o formato AAAA-MM-DD.', campo='start_date', status=400)
        if start_day > end_day:
            return responses.err('A data inicial deve ser anterior à final.', campo='start_date', status=400)
    else:
        end_day = datetime.now().date()
        start_day = end_day - timedelta(days=days)
    db = database.get_db()
    try:
        with db.cursor() as cur:
            query = """
                SELECT DATE(t.data_transacao) AS dia,
                       SUM(CASE WHEN fc.tipo = 'receita' THEN t.valor ELSE 0 END) AS receitas,
                       SUM(CASE WHEN fc.tipo = 'despesa' THEN t.valor ELSE 0 END) AS despesas
                FROM financeiro_transacoes t
                JOIN financeiro_categorias fc ON fc.id = t.categoria_id
                WHERE t.data_transacao >= {start_clause}
                  AND t.data_transacao < {end_clause}
                  AND t.status = 'pago'
                GROUP BY DATE(t.data_transacao)
                ORDER BY dia ASC
            """
            if start_date and end_date:
                cur.execute(query.format(start_clause='%s', end_clause='DATE_ADD(%s, INTERVAL 1 DAY)'), (start_day, end_day))
            else:
                cur.execute(query.format(start_clause='DATE_SUB(CURDATE(), INTERVAL %s DAY)', end_clause='CURDATE() + INTERVAL 1 DAY'), (days,))
            rows = cur.fetchall()

        # O gráfico representa o calendário, e não apenas os dias que tiveram
        # movimento. Assim, a coluna de hoje já existe e cresce durante o dia.
        by_day = {r['dia']: r for r in rows if r.get('dia')}
        days_in_range = (end_day - start_day).days + 1
        calendar_days = [start_day + timedelta(days=offset) for offset in range(days_in_range)]
        labels = [day.strftime('%d/%m') for day in calendar_days]
        receitas = [float((by_day.get(day) or {}).get('receitas') or 0) for day in calendar_days]
        despesas = [float((by_day.get(day) or {}).get('despesas') or 0) for day in calendar_days]

        return jsonify({
            'ok': True,
            'labels': labels,
            'dias': [day.isoformat() for day in calendar_days],
            'receitas': receitas,
            'despesas': despesas,
            'periodo': {'inicio': start_day.isoformat(), 'fim': end_day.isoformat()},
        })
    except pymysql.MySQLError as exc:
        log.error("Erro DB em financeiro/fluxo: %s", exc)
        return responses.err('Erro interno ao consultar fluxo de caixa.', status=500)


def financeiro_categorias():
    """Retorna categorias financeiras com totais agrupados."""
    if not _fin_tables_exist():
        return responses.err('Tabelas financeiras não configuradas. Execute a migração 005_tabela_financeiro.sql', status=503)
    days = request.args.get('days', '30', type=int)
    tipo = request.args.get('tipo', None)
    if days not in (7, 30, 90):
        days = 30
    if tipo not in (None, 'receita', 'despesa'):
        return responses.err('Tipo inválido.', campo='tipo', status=400)
    db = database.get_db()
    try:
        with db.cursor() as cur:
            tipo_clause = "WHERE fc.tipo = %s" if tipo else ""
            params = (days,) + ((tipo,) if tipo else ())
            cur.execute(f"""
                SELECT fc.id, fc.nome, fc.tipo,
                       COALESCE(SUM(IF(t.status='pago', t.valor, 0)), 0) AS valor,
                       COALESCE(SUM(IF(t.status='pendente', t.valor, 0)), 0) AS pendente,
                       COUNT(t.id) AS qtd
                FROM financeiro_categorias fc
                LEFT JOIN financeiro_transacoes t ON t.categoria_id = fc.id
                    AND t.data_transacao >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                    AND t.data_transacao < CURDATE() + INTERVAL 1 DAY
                    AND t.status IN ('pago', 'pendente')
                {tipo_clause}
                GROUP BY fc.id, fc.nome, fc.tipo
                ORDER BY valor DESC
            """, params)
            rows = cur.fetchall()

        categorias = [{'id': r['id'], 'nome': r['nome'], 'tipo': r['tipo'],
                       'valor': float(r['valor'] or 0), 'pendente': float(r.get('pendente') or 0), 'qtd': r['qtd']} for r in rows]

        return jsonify({'ok': True, 'categorias': categorias})
    except pymysql.MySQLError as exc:
        log.error("Erro DB em financeiro/categorias: %s", exc)
        return responses.err('Erro interno ao consultar categorias financeiras.', status=500)


def financeiro_transacoes():
    """Retorna lista de transações do período."""
    if not _fin_tables_exist():
        return responses.err('Tabelas financeiras não configuradas. Execute a migração 005_tabela_financeiro.sql', status=503)
    days = request.args.get('days', '30', type=int)
    if days not in (7, 30, 90):
        days = 30
    limit = request.args.get('limit', 50, type=int)
    limit = min(max(limit, 1), 500)
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT t.id, t.descricao, t.valor, t.data_transacao,
                       t.status, t.metodo_pagamento,
                       fc.tipo, fc.nome AS categoria_nome
                FROM financeiro_transacoes t
                JOIN financeiro_categorias fc ON fc.id = t.categoria_id
                WHERE t.data_transacao >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                  AND t.data_transacao < CURDATE() + INTERVAL 1 DAY
                ORDER BY t.data_transacao DESC
                LIMIT %s
            """, (days, limit))
            rows = cur.fetchall()

        transacoes = [{
            'id': r['id'],
            'descricao': r['descricao'],
            'valor': float(r['valor']),
            'data_transacao': r['data_transacao'].strftime('%Y-%m-%d %H:%M:%S') if r['data_transacao'] else '—',
            'status': r['status'],
            'metodo_pagamento': r['metodo_pagamento'],
            'tipo': r['tipo'],
            'categoria_nome': r['categoria_nome']
        } for r in rows]

        return jsonify({'ok': True, 'transacoes': transacoes})
    except pymysql.MySQLError as exc:
        log.error("Erro DB em financeiro/transacoes: %s", exc)
        return responses.err('Erro interno ao consultar transações financeiras.', status=500)


def create_financeiro_transacao():
    """Cria uma nova transação financeira."""
    if not _fin_tables_exist():
        return jsonify({'ok': False, 'mensagem': 'Tabelas financeiras não configuradas. Execute a migração 005_tabela_financeiro.sql'}), 503
    data = request.get_json(silent=True) or {}
    tipo = (data.get('tipo') or '').strip().lower()
    categoria_id = data.get('categoria_id')
    descricao = (data.get('descricao') or '').strip()
    valor = data.get('valor')
    data_transacao = (data.get('data_transacao') or '').strip()
    metodo = (data.get('metodo_pagamento') or '').strip()

    if tipo not in ('receita', 'despesa'):
        return jsonify({'ok': False, 'mensagem': 'Tipo inválido.'}), 400
    if not categoria_id:
        return jsonify({'ok': False, 'mensagem': 'Selecione uma categoria.'}), 400
    if not descricao:
        return jsonify({'ok': False, 'mensagem': 'Informe uma descrição.'}), 400
    # Mantém números e strings numéricas aceitos pela API, mas impede que
    # conversões inválidas escapem como HTTP 500 ou levem NaN/Infinity ao SQL.
    try:
        valor = float(valor)
    except (TypeError, ValueError, OverflowError):
        return jsonify({'ok': False, 'mensagem': 'Informe um valor válido.'}), 400
    if not math.isfinite(valor) or valor <= 0:
        return jsonify({'ok': False, 'mensagem': 'Informe um valor válido.'}), 400
    if metodo not in ('dinheiro', 'pix', 'cartao_credito', 'cartao_debito', 'boleto', 'transferencia'):
        return jsonify({'ok': False, 'mensagem': 'Método de pagamento inválido.'}), 400
    if data_transacao:
        try:
            # O formulário envia somente a data; armazenamos o início desse dia
            # para que os agrupamentos de fluxo e categoria a considerem nele.
            data_transacao = datetime.strptime(data_transacao, '%Y-%m-%d').strftime('%Y-%m-%d 00:00:00')
        except ValueError:
            return jsonify({'ok': False, 'mensagem': 'Informe uma data válida no formato AAAA-MM-DD.'}), 400

    db = database.get_db()
    try:
        with db.cursor() as cur:
            # Verifica categoria
            cur.execute("SELECT id, tipo FROM financeiro_categorias WHERE id = %s", (categoria_id,))
            cat = cur.fetchone()
            if not cat:
                return jsonify({'ok': False, 'mensagem': 'Categoria não encontrada.'}), 404
            if cat['tipo'] != tipo:
                return jsonify({'ok': False, 'mensagem': 'Categoria não corresponde ao tipo.'}), 400

            # A data é um parâmetro, nunca um fragmento SQL. Ausência mantém
            # o horário do banco (NOW), como no contrato anterior.
            cur.execute("""
                INSERT INTO financeiro_transacoes (categoria_id, usuario_id, descricao, valor, data_transacao, metodo_pagamento, status)
                VALUES (%s, %s, %s, %s, COALESCE(%s, NOW()), %s, 'pago')
            """, (categoria_id, g.usuario_id, descricao, valor, data_transacao or None, metodo))
            commit_audit(db, cur.lastrowid)

        log.info("Nova transação financeira: %s %s", tipo, descricao)
        return jsonify({'ok': True, 'mensagem': 'Transação registrada com sucesso.'}), 201
    except Exception as exc:
        db.rollback()
        log.error("Erro DB em create_transacao: %s", exc)
        return jsonify({'ok': False, 'mensagem': 'Erro ao salvar transação.'}), 400


def register_routes(app):
    """Registra as URLs e nomes de endpoints existentes."""
    app.add_url_rule('/financeiro/stats', view_func=financeiro_stats, methods=['GET'])
    app.add_url_rule('/financeiro/fluxo', view_func=financeiro_fluxo, methods=['GET'])
    app.add_url_rule('/financeiro/categorias', view_func=financeiro_categorias, methods=['GET'])
    app.add_url_rule('/financeiro/transacoes', view_func=financeiro_transacoes, methods=['GET'])
    app.add_url_rule('/financeiro/transacoes', view_func=create_financeiro_transacao, methods=['POST'])
