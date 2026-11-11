"""Tela real de login e API Flask com banco simulado; nunca usa contas reais."""
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch
import json
import sys
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import test_backend as base
from farmacontrol.core import access, credentials


def main():
    harness = base.BackendTests()
    harness.setUp()
    harness.profile_permissions = {'proprietario': set(access.PERMISSION_MODULES)}
    harness.cur.fetchone.return_value.update(nome='Teste', sobrenome='Login', email='conta@example.com', perfil_nome='Proprietário')
    out = ROOT / '.audit-backup/limites-login'
    out.mkdir(parents=True, exist_ok=True)
    errors = []
    try:
        with patch.object(credentials, 'verificar_senha', side_effect=lambda password, _: password == 'SenhaCorreta123!'), sync_playwright() as p:
            browser = p.chromium.launch(channel='chrome', headless=True)
            page = browser.new_page(viewport={'width':1280,'height':950})
            page.on('pageerror', lambda error: errors.append(str(error)))

            def route_request(route):
                request = route.request
                parsed = urlsplit(request.url)
                if parsed.hostname != 'rate.test':
                    route.abort()
                    return
                if parsed.path.startswith('/pages/sistema/'):
                    route.fulfill(content_type='text/html', body='<h1>Login concluído</h1>')
                    return
                if parsed.path == '/configuracoes/visual':
                    route.fulfill(content_type='application/json', body=json.dumps({'ok':True,'configuracoes':[]}))
                    return
                response = harness.client.open(parsed.path + ('?' + parsed.query if parsed.query else ''),
                    base_url='http://rate.test', method=request.method, data=request.post_data,
                    headers={key:value for key,value in request.headers.items() if key.lower() not in {'host','content-length','cookie'}})
                route.fulfill(status=response.status_code, body=response.data, content_type=response.content_type)

            page.route('**/*', route_request)
            page.goto('http://rate.test/pages/acesso/acesso.html')
            page.locator('#login-email').fill('conta@example.com')
            page.locator('#login-password').fill('incorreta')
            for remaining in (4,3,2,1):
                with page.expect_response('**/auth/login') as result:
                    page.locator('#btn-login').click()
                data = result.value.json()
                assert result.value.status == 401
                assert data['tentativas_restantes'] == remaining, data
                page.wait_for_function("!document.getElementById('btn-login').disabled")
            page.screenshot(path=str(out / 'quatro-falhas.png'))
            page.locator('#login-password').fill('SenhaCorreta123!')
            page.locator('#btn-login').click()
            page.wait_for_url('**/pages/sistema/dashboard/dashboard.html')
            assert page.evaluate('''async () => {
              const response = await fetch('/auth/logout', {method:'POST', headers:{'X-CSRF-Token':sessionStorage.getItem('farmacontrol_csrf')}});
              return response.status;
            }''') == 200
            page.goto('http://rate.test/pages/acesso/acesso.html')
            page.locator('#login-email').fill('conta@example.com')
            page.locator('#login-password').fill('incorreta')
            with page.expect_response('**/auth/login') as result:
                page.locator('#btn-login').click()
            data = result.value.json()
            assert result.value.status == 401
            assert data['tentativas_restantes'] == 4, data
            assert data['limite_escopo'] == 'conta'
            assert not errors, errors
            browser.close()
        print('OK: quatro falhas, login correto, logout e novo erro com quatro tentativas disponíveis (Flask real/banco simulado).')
    finally:
        harness.doCleanups()


if __name__ == '__main__':
    main()
