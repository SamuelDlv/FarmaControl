# Guia de manutenção — Verificador de devolucao mysql.
# Este é um utilitário de validação; confira main e os argumentos antes de executá-lo.
# Os cenários usam servidor MySQL e bases de teste; valide o destino e os privilégios antes da execução.
# Consulte docs/desenvolvimento.md para executar as verificações desta camada.
"""Integração real de descarte/devolução; usa e remove somente uma base aleatória.

Execute: python scripts/check_devolucao_mysql.py --browser
Credenciais: backend/.env. Chrome instalado e Playwright Python para --browser.
Não aplica migrações nem modifica dados na base operacional.
"""
import argparse
import json
import os
import re
import secrets
import sys
import threading
import uuid
from pathlib import Path

from dotenv import dotenv_values
from migrate_catalogo import ROOT, connection, execute_sql


# Executa as consultas e validações de main.
def main(browser=False):
    name = 'farmacontrol_devolucao_test_' + uuid.uuid4().hex
    report = {'checks': [], 'browser': [], 'database_removed': False}
    output = ROOT / '.audit-backup/integration-20261105'
    output.mkdir(parents=True, exist_ok=True)
    db = connection()
    server = None
    created = False
    try:
        with db.cursor() as cur:
            cur.execute('SELECT VERSION() AS version, @@collation_server AS collation')
            report['mysql'] = cur.fetchone()
            cur.execute(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
            created = True
        db.select_db(name)
        schema = (ROOT / 'backend/schema.sql').read_text(encoding='utf-8')
        # Exclui CREATE DATABASE, USE e roles globais do schema distribuído.
        execute_sql(db, schema[schema.index('CREATE TABLE IF NOT EXISTS perfis'):])
        report['checks'].append('schema atual criado sem alterar roles globais')
        with db.cursor() as cur:
            cur.execute('ALTER TABLE movimentacoes_estoque DROP COLUMN fornecedor_id, DROP COLUMN finalidade, DROP COLUMN motivo')
        execute_sql(db, (ROOT / 'backend/migrations/022_finalidade_movimentacao.sql').read_text(encoding='utf-8'))
        sql = (ROOT / 'backend/migrations/023_fornecedor_devolucao.sql').read_text(encoding='utf-8')
        execute_sql(db, sql)
        execute_sql(db, sql)
        report['checks'].append('migrações 022 e 023 e reaplicação de 023 aprovadas')

        config = {**dotenv_values(ROOT / 'backend/.env'), **os.environ}
        for key in ('DB_HOST', 'DB_PORT', 'DB_USER', 'DB_PASSWORD'):
            if config.get(key) is not None:
                os.environ[key] = config[key]
        os.environ.update(DB_NAME=name, APP_ENV='test', APP_DEBUG='false', COOKIE_SECURE='false',
                          SECRET_KEY=secrets.token_hex(32))
        sys.path.insert(0, str(ROOT / 'backend'))
        from farmacontrol import create_app
        from farmacontrol.core.credentials import hash_senha
        app = create_app()
        app.config.update(TESTING=True)
        password = secrets.token_urlsafe(18)
        with db.cursor() as cur:
            cur.execute("INSERT INTO usuarios (nome,sobrenome,email,senha_hash,perfil_id,status) SELECT 'Teste','Integração','integracao@example.invalid',%s,id,'aprovado' FROM perfis WHERE slug='proprietario'", (hash_senha(password),))
            user_id = cur.lastrowid
            cur.execute("INSERT INTO fornecedores (nome_fantasia,razao_social,cnpj) VALUES ('Fornecedor teste','Fornecedor teste','00000000000000')")
            supplier = cur.lastrowid
            stocks = []
            for i, supplier_id in enumerate((supplier, None, supplier)):
                cur.execute("INSERT INTO produtos (nome,preco_custo,preco_venda,fornecedor_id) VALUES (%s,2,4,%s)", (f'Produto integração {i}', supplier_id))
                cur.execute("INSERT INTO estoque (produto_id,lote,data_validade,quantidade) VALUES (%s,%s,'2000-01-01',23)", (cur.lastrowid, f'TESTE-{i}'))
                stocks.append(cur.lastrowid)
        db.commit()

        # Executa as consultas e validações de query.
        def query(sql, args=()):
            db.commit()  # encerra snapshot REPEATABLE READ antes de ler commits HTTP
            with db.cursor() as cur:
                cur.execute(sql, args)
                return cur.fetchall()

        client = app.test_client()
        login = client.post('/auth/login', json={'email': 'integracao@example.invalid', 'password': password})
        assert login.status_code == 200, login.json
        headers = {'X-CSRF-Token': login.json['csrf_token']}
        report['checks'].append('login real, sessão assinada e CSRF')

        def move(stock, purpose='descarte', qty=5, **extra):
            payload = dict(estoque_id=stock, tipo_movimentacao='saida', finalidade=purpose,
                           quantidade=qty, motivo='Produto vencido')
            payload.update(extra)
            return client.post('/movimentacoes-estoque', json=payload, headers=headers)

        assert move(stocks[0]).status_code == 201
        assert query('SELECT quantidade FROM estoque WHERE id=%s', (stocks[0],))[0]['quantidade'] == 18
        assert move(stocks[0], 'devolucao_fornecedor', 4).status_code == 201
        assert query('SELECT quantidade FROM estoque WHERE id=%s', (stocks[0],))[0]['quantidade'] == 14
        events = query('SELECT finalidade,quantidade,motivo,fornecedor_id,usuario_id FROM movimentacoes_estoque ORDER BY id')
        assert events[0]['finalidade'] == 'descarte' and events[0]['fornecedor_id'] is None
        assert events[1]['finalidade'] == 'devolucao_fornecedor' and events[1]['fornecedor_id'] == supplier
        assert all(e['usuario_id'] == user_id and e['motivo'] == 'Produto vencido' for e in events)
        assert move(stocks[1], 'devolucao_fornecedor', 4).status_code == 201
        assert query('SELECT fornecedor_id FROM movimentacoes_estoque WHERE estoque_id=%s', (stocks[1],))[0]['fornecedor_id'] is None
        report['checks'].append('lote vencido: descarte 23→18, devolução 18→14; fornecedor capturado e referência nula permitida')
        for qty in (0, -1, 1.5, 999, True, '5'):
            assert move(stocks[0], qty=qty).status_code == 400
        assert move(stocks[0], motivo='').status_code == 400
        assert move(stocks[0], 'devolucao_fornecedor', fornecedor_id=supplier + 999).status_code == 400
        assert move(stocks[0], None, motivo=None).status_code == 400
        assert client.post('/movimentacoes-estoque', json={'estoque_id': stocks[0]}).status_code == 403
        assert query('SELECT quantidade FROM estoque WHERE id=%s', (stocks[0],))[0]['quantidade'] == 14
        assert len(query('SELECT id FROM movimentacoes_estoque')) == 3
        report['checks'].append('quantidade inválida, excesso, motivo vazio, fornecedor divergente, saída comum vencida e ausência de CSRF rejeitados sem baixa')
        history = client.get(f'/estoque/{stocks[0]}/historico')
        assert history.status_code == 200 and len(history.json['historico']) == 2
        listing = client.get('/movimentacoes-estoque?busca=Produto&limite=2&offset=0')
        assert listing.status_code == 200, listing.json
        assert listing.json['total'] == 3 and len(listing.json['movimentacoes']) == 2
        assert listing.json['tem_mais'] and listing.json['proximo_offset'] == 2
        empty = client.get('/movimentacoes-estoque?busca=inexistente&offset=0')
        assert empty.json['total'] == 0 and empty.json['movimentacoes'] == []
        assert client.get('/movimentacoes-estoque?limite=invalido').status_code == 400
        audit = query('SELECT * FROM log_atividades')
        assert any('devolucao_fornecedor' in str(row) for row in audit)
        assert any('descarte' in str(row) for row in audit)
        report['checks'].append('histórico, consulta de movimentações, validação de paginação e auditoria persistida')

        if browser:
            from werkzeug.serving import make_server
            from playwright.sync_api import sync_playwright
            server = make_server('127.0.0.1', 0, app, threaded=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            origin = f'http://127.0.0.1:{server.server_port}'
            with sync_playwright() as pw:
                chrome_path = os.environ.get('CHROME_PATH')
                local_chrome = Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe')
                if not chrome_path and os.name == 'nt' and local_chrome.exists():
                    chrome_path = str(local_chrome)
                chrome = pw.chromium.launch(executable_path=chrome_path, headless=True)
                try:
                    page = chrome.new_page(viewport={'width': 1440, 'height': 1000})
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(origin + '/pages/acesso/acesso.html')
                    page.locator('#login-email').fill('integracao@example.invalid')
                    page.locator('#login-password').fill(password)
                    page.locator('#btn-login').click()
                    page.wait_for_url('**/dashboard/dashboard.html', timeout=30000)
                    page.goto(origin + '/pages/sistema/vencimentos/vencimentos.html')
                    button = page.locator(f'[data-action="descarte"][data-id="{stocks[2]}"]')
                    button.wait_for()
                    for purpose, qty, balance in (('descarte', 5, 18), ('devolucao', 4, 14)):
                        button.click()
                        assert page.locator('#baixa-title').inner_text() == 'Registrar Descarte'
                        assert page.locator('#baixa-description').inner_text().startswith('Descarte retira')
                        page.locator('#descarte-qty').fill(str(qty))
                        if purpose == 'devolucao':
                            page.locator('#baixa-btn-devolucao').click()
                            assert page.locator('#baixa-title').inner_text() == 'Registrar Devolução ao Fornecedor'
                            assert page.locator('#baixa-description').inner_text().startswith('Devolução ao fornecedor')
                            page.locator('#baixa-btn-descarte').click()
                            assert page.locator('#baixa-title').inner_text() == 'Registrar Descarte'
                            assert page.locator('#baixa-description').inner_text().startswith('Descarte retira')
                            page.locator('#baixa-btn-devolucao').click()
                            page.screenshot(path=str(output / 'devolucao-desktop.png'), full_page=True)
                        with page.expect_response(lambda res: res.url.endswith('/movimentacoes-estoque') and res.request.method == 'POST') as response:
                            page.locator('#descarte-save').click()
                        assert response.value.status == 201, response.value.text()
                        page.wait_for_function("!document.getElementById('descarte-overlay').classList.contains('open')")
                        page.wait_for_function('(value) => lotes.find(x => x.id === value.id)?.qty === value.qty', arg={'id': stocks[2], 'qty': balance})
                        assert query('SELECT quantidade FROM estoque WHERE id=%s', (stocks[2],))[0]['quantidade'] == balance
                        report['browser'].append(f'{purpose}: clique real → HTTP 201 → MySQL saldo {balance} → tela atualizada')
                    button.click()
                    page.locator('#descarte-qty').fill('999')
                    page.locator('#descarte-save').click()
                    assert page.locator('#descarte-overlay').evaluate("el => el.classList.contains('open')")
                    assert query('SELECT quantidade FROM estoque WHERE id=%s', (stocks[2],))[0]['quantidade'] == 14
                    page.screenshot(path=str(output / 'vencimentos-desktop.png'), full_page=True)
                    page.set_viewport_size({'width': 390, 'height': 844})
                    page.wait_for_function("document.querySelector('.sidebar').getBoundingClientRect().right <= 1")
                    page.screenshot(path=str(output / 'vencimentos-mobile.png'), full_page=True)
                    assert page.locator('#descarte-overlay .modal').bounding_box()['width'] <= 390
                    page.locator('#baixa-btn-devolucao').click()
                    assert page.locator('#baixa-title').inner_text() == 'Registrar Devolução ao Fornecedor'
                    page.screenshot(path=str(output / 'devolucao-mobile.png'), full_page=True)
                    assert not errors, errors
                    report['browser'].extend(['título e explicação acompanham seleção, alternância e reabertura do modal', 'quantidade excessiva bloqueada pela interface', 'modal cabe em 390px; screenshots desktop/mobile; sem exceções JavaScript'])
                    report['chrome'] = chrome.version
                finally:
                    chrome.close()
        report['passed'] = True
    finally:
        if server:
            server.shutdown()
        if created:
            assert re.fullmatch(r'farmacontrol_devolucao_test_[0-9a-f]{32}', name)
            with db.cursor() as cur:
                cur.execute(f'DROP DATABASE `{name}`')
            report['database_removed'] = True
        db.close()
        (output / 'devolucao-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', action='store_true')
    main(parser.parse_args().browser)
