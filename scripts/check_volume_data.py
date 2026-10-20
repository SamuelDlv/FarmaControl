"""Validação somente leitura da base local e snapshots para o teste de navegador.

Não executa a carga 017, migrações, login ou auditoria. A transação é READ ONLY.
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

from migrate_catalogo import connection, ROOT

sys.path.insert(0, str(ROOT / 'backend'))
import app as api


def main():
    db = connection()
    snapshots = {}
    try:
        with db.cursor() as cur:
            cur.execute('START TRANSACTION READ ONLY')
        routes = {
            '/estoque': api.get_estoque,
            '/produtos': api.get_produtos,
            '/compras': api.get_compras,
            '/fornecedores': api.get_fornecedores,
            '/dashboard/stats': api.get_dashboard_stats,
            '/relatorios/compras': api.relatorio_compras,
        }
        for period in ('month', 'quarter', 'year'):
            routes[f'/relatorios/estoque?periodo={period}'] = api.relatorio_estoque
            routes[f'/relatorios/compras?periodo={period}'] = api.relatorio_compras
            routes[f'/movimentacoes-estoque?periodo={period}&limite=10&offset=0'] = api.get_movimentacoes_estoque
        routes['/movimentacoes-estoque?periodo=year&limite=10&offset=1000&tipo=saida&busca=Teste'] = api.get_movimentacoes_estoque
        for days in (7, 30, 90):
            routes[f'/financeiro/categorias?tipo=despesa&days={days}'] = api.financeiro_categorias
            routes[f'/financeiro/stats?days={days}'] = api.financeiro_stats
            routes[f'/financeiro/fluxo?days={days}'] = api.financeiro_fluxo
        # Histórico completo via páginas para validar conjuntos acima de 1.000.
        with patch.object(api, 'get_db', return_value=db):
            for url, fn in routes.items():
                with api.app.test_request_context(url):
                    response = api.app.make_response(fn())
                    assert response.status_code == 200, (url, response.get_json())
                    data = response.get_json()
                    assert data['ok'], url
                    snapshots[url] = data
            rows = []
            total = None
            while total is None or len(rows) < total:
                with api.app.test_request_context(f'/movimentacoes-estoque?limite=1000&offset={len(rows)}'):
                    data = api.app.make_response(api.get_movimentacoes_estoque()).get_json()
                total = data['total']
                assert data['movimentacoes'] or len(rows) == total
                rows.extend(data['movimentacoes'])
            assert len({row['id'] for row in rows}) == total
            snapshots['/movimentacoes-estoque'] = {'ok': True, 'movimentacoes': rows, 'total': total}
        with db.cursor() as cur:
            cur.execute("""SELECT SUM(quantidade) AS total FROM movimentacoes_estoque
                WHERE tipo_movimentacao='saida' AND data_movimentacao >= DATE_FORMAT(CURDATE(), '%Y-%m-01')
                AND data_movimentacao < CURDATE() + INTERVAL 1 DAY""")
            expected = int(cur.fetchone()['total'] or 0)
        report = snapshots['/relatorios/estoque?periodo=month']
        assert report['kpis']['total_saidas'] == expected
        assert sum(row['qtd_total'] for row in report['por_categoria']) == expected
        assert sum(row['saidas'] for row in report['evolucao']) == expected
        output = ROOT / '.audit-backup/volume'
        output.mkdir(parents=True, exist_ok=True)
        (output / 'api.json').write_text(json.dumps(snapshots, ensure_ascii=False), encoding='utf-8')
        print(json.dumps({'lotes': len(snapshots['/estoque']['estoque']), 'movimentacoes': total,
                          'saidas_mes': expected, 'endpoints': len(routes), 'somente_leitura': True}))
    finally:
        db.rollback()
        db.close()


if __name__ == '__main__':
    main()
