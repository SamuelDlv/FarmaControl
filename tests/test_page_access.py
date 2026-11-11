# Guia de manutenção — Testes de page access.
# Os cenários e asserts abaixo definem os contratos esperados e os casos de regressão.
# Leia os mocks e fixtures de cada caso antes de interpretar o resultado como integração real.
# Consulte docs/desenvolvimento.md para executar as verificações desta camada.
"""Acesso direto a HTML usa a sessão real do cliente Flask e banco simulado."""
import unittest
from unittest.mock import patch
import test_backend as base

api = base.api


from farmacontrol.core import database
from farmacontrol.routes import frontend
import pymysql


# Agrupa os cenários de teste e suas fixtures.
class PageAccessTests(unittest.TestCase):
    setUp = base.BackendTests.setUp
    login_session = base.BackendTests.login_session
    dashboard = '/pages/sistema/dashboard/dashboard.html'

    # Cenário de regressão: every system page and legacy alias redirect without delivering html.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_every_system_page_and_legacy_alias_redirect_without_delivering_html(self):
        for path in (base.ROOT / 'frontend/src/pages/sistema').rglob('*.html'):
            relative = path.relative_to(base.ROOT / 'frontend/src/pages/sistema').as_posix()
            for prefix in ('/pages/sistema/', '/pages/proprietario/'):
                for method in ('GET', 'HEAD'):
                    with self.subTest(page=relative, prefix=prefix, method=method):
                        response = self.client.open(prefix + relative, method=method)
                        self.assertEqual(response.status_code, 302)
                        self.assertEqual(response.headers['Location'], '/pages/acesso/acesso.html')
                        self.assertEqual(response.headers['Cache-Control'], 'no-store')
                        self.assertNotIn(b'<html lang="pt-BR">', response.data)
        self.db.cursor.assert_not_called()

    # Cenário de regressão: public login and resources remain available.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_public_login_and_resources_remain_available(self):
        for path in ('/pages/acesso/acesso.html', '/pages/convite/convite.html',
                     '/pages/redefinir-senha/redefinir-senha.html',
                     '/utils/auth-guard.js', '/pages/sistema/dashboard/dashboard.css'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
        self.db.cursor.assert_not_called()

    # Cenário de regressão: generic file handler cannot bypass page protection.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_generic_file_handler_cannot_bypass_page_protection(self):
        with api.app.test_request_context('/pages/sistema/dashboard/dashboard.html'):
            response = frontend.serve_frontend_asset('pages/sistema/dashboard/dashboard.html')
        self.assertEqual(response.status_code, 302)

    # Cenário de regressão: account revocation and password change deny html.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_account_revocation_and_password_change_deny_html(self):
        for changes in ({'status': 'inativo'}, {'senha_hash': 'nova-senha-hash'}):
            with self.subTest(changes=changes):
                self.login_session()
                self.cur.fetchone.return_value.update(changes)
                response = self.client.get(self.dashboard)
                self.assertEqual(response.status_code, 302)
                with self.client.session_transaction() as sess:
                    self.assertNotIn('usuario_id', sess)

    # Cenário de regressão: forged cookie cannot open dashboard.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_forged_cookie_cannot_open_dashboard(self):
        self.client.set_cookie('session', 'cookie-inventado')
        self.assertEqual(self.client.get(self.dashboard).status_code, 302)
        self.db.cursor.assert_not_called()

    # Cenário de regressão: valid session can open page without browser session storage.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_valid_session_can_open_page_without_browser_session_storage(self):
        self.login_session()
        response = self.client.get(self.dashboard)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'auth-guard.js', response.data)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    # Cenário de regressão: logout prevents reopening page.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_logout_prevents_reopening_page(self):
        self.login_session()
        self.assertEqual(self.client.get(self.dashboard).status_code, 200)
        self.assertEqual(self.client.post('/auth/logout', headers={
            'X-CSRF-Token': 'teste-csrf'}).status_code, 200)
        self.assertEqual(self.client.get(self.dashboard).status_code, 302)
        self.assertEqual(self.client.get('/dashboard/stats').status_code, 401)

    # Cenário de regressão: database failure does not deliver html.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_database_failure_does_not_deliver_html(self):
        self.login_session()
        with patch.object(database, 'get_db', side_effect=pymysql.OperationalError('offline')):
            response = self.client.get(self.dashboard)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b'auth-guard.js', response.data)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    # Cenário de regressão: module permission also protects html.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_module_permission_also_protects_html(self):
        self.login_session('atendente')
        self.assertEqual(self.client.get(self.dashboard).status_code, 200)
        for page in ('financeiro', 'usuarios', 'log'):
            response = self.client.get(f'/pages/sistema/{page}/{page}.html')
            self.assertEqual(response.status_code, 403)
            self.assertNotIn(b'auth-guard.js', response.data)
