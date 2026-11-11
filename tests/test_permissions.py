"""Matriz completa dos sete perfis: portas HTTP, HTML, escrita e logout."""
import json
import re
import unittest
from unittest.mock import Mock, patch
import pymysql
import test_backend as base
from farmacontrol.core import access
from farmacontrol.core import credentials
from farmacontrol.core.security import AuthLimiter

api = base.api
DEFAULTS = {
    'proprietario': {'dashboard','estoque','vencimentos','compras','financeiro','relatorios','usuarios','configuracoes'},
    'admin': {'dashboard','estoque','vencimentos','compras','financeiro','relatorios','usuarios','configuracoes'},
    'ti': {'dashboard','estoque','vencimentos','compras','financeiro','relatorios','usuarios','configuracoes'},
    'farmaceutico': {'dashboard','estoque','vencimentos','compras','relatorios'},
    'compras': {'dashboard','estoque','vencimentos','compras','relatorios'},
    'atendente': {'dashboard','estoque'},
    'visualizador': {'dashboard','estoque','vencimentos','relatorios'},
}
SALES = {'proprietario','admin','farmaceutico','atendente','ti'}
ADMINS = {'proprietario','admin','ti'}


def expected(role, modules, module, method):
    if method not in {'GET','HEAD','OPTIONS'}:
        if role == 'visualizador' or (role == 'atendente' and module in {'estoque','vencimentos'}):
            return False
    if module == 'vendas':
        return role in SALES
    if module == 'log':
        return role in ADMINS
    return module in modules


class PermissionTests(unittest.TestCase):
    setUp = base.BackendTests.setUp
    login_session = base.BackendTests.login_session

    def test_every_api_route_for_every_default_profile(self):
        # Isola os handlers de negócio: uma negação não pode chegar ao handler.
        # Login, CSRF, matriz e middleware são os reais da aplicação.
        rules = [rule for rule in api.app.url_map.iter_rules()
                 if rule.rule.startswith(access.PROTECTED_API_PREFIXES)
                 and rule.rule != '/configuracoes/visual']
        handlers = {rule.endpoint: Mock(side_effect=lambda **kw: {'ok': True}) for rule in rules}
        with patch.dict(api.app.view_functions, handlers):
            for role, modules in DEFAULTS.items():
                self.login_session(role)
                for rule in rules:
                    path = re.sub(r'<[^:]+:\w+>', '1', rule.rule)
                    module = 'log' if path == '/admin/logs' else access.modulo_da_rota(path)
                    for method in rule.methods - {'OPTIONS','HEAD'}:
                        with self.subTest(role=role, path=path, method=method):
                            handler = handlers[rule.endpoint]
                            handler.reset_mock()
                            response = self.client.open(path, method=method, json={}, headers={'X-CSRF-Token':'teste-csrf'})
                            allowed = expected(role, modules, module, method)
                            self.assertEqual(response.status_code, 200 if allowed else 403)
                            self.assertEqual(handler.call_count, int(allowed))

    def test_every_html_and_legacy_alias_matches_default_matrix(self):
        for role, modules in DEFAULTS.items():
            self.login_session(role)
            for folder in (base.ROOT / 'frontend/src/pages/sistema').iterdir():
                if not folder.is_dir():
                    continue
                module = folder.name
                for prefix in ('sistema', 'proprietario'):
                    with self.subTest(role=role, module=module, prefix=prefix):
                        response = self.client.get(f'/pages/{prefix}/{module}/{module}.html')
                        allowed = expected(role, modules, module, 'GET')
                        self.assertEqual(response.status_code, 200 if allowed else 403)
                        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_explicit_module_grants_preserve_fixed_sales_log_and_read_only_rules(self):
        for role in DEFAULTS:
            self.login_session(role)
            self.profile_permissions[role] = set(access.PERMISSION_MODULES)
            for module in (*access.PERMISSION_MODULES, 'vendas', 'log'):
                for method in ('GET', 'PUT'):
                    with self.subTest(role=role, module=module, method=method):
                        self.assertEqual(access.pode_acessar_modulo(role, self.profile_permissions[role], module,
                            escrita=method == 'PUT'), expected(role, self.profile_permissions[role], module, method))

    def test_logout_works_for_all_roles_even_when_auth_budget_is_exhausted(self):
        api.app.extensions['auth_limiter'] = AuthLimiter(limit=5)
        other = api.app.test_client()
        for _ in range(5):
            self.assertEqual(other.post('/auth/login', json={}).status_code, 400)
        self.assertEqual(other.post('/auth/login', json={}).status_code, 429)
        limiter = api.app.extensions['auth_limiter']
        before = dict(limiter.entries)
        for role in DEFAULTS:
            self.login_session(role)
            self.profile_permissions[role] = set()  # Sair independe de módulos.
            response = self.client.post('/auth/logout', headers={'X-CSRF-Token':'teste-csrf'})
            self.assertEqual(response.status_code, 200, (role, response.json))
            with self.client.session_transaction() as sess:
                self.assertNotIn('usuario_id', sess)
        self.assertEqual(limiter.entries, before)
        self.assertEqual(other.post('/auth/login', json={}).status_code, 429)

    def test_logout_still_checks_csrf_origin_and_atomic_audit(self):
        self.login_session('atendente')
        for headers in ({}, {'X-CSRF-Token':'errado'},
                        {'X-CSRF-Token':'teste-csrf','Origin':'https://invalid.example'}):
            self.assertEqual(self.client.post('/auth/logout', headers=headers).status_code, 403)
            with self.client.session_transaction() as sess:
                self.assertEqual(sess['usuario_id'], 42)
        self.db.commit.assert_not_called()
        self.cur.execute.side_effect = pymysql.OperationalError('falha de auditoria')
        self.assertEqual(self.client.post('/auth/logout', headers={'X-CSRF-Token':'teste-csrf'}).status_code, 503)
        self.db.rollback.assert_called_once()
        with self.client.session_transaction() as sess:
            self.assertEqual(sess['usuario_id'], 42)

    def test_server_context_uses_revalidated_profile_not_old_browser_cache(self):
        self.login_session()
        self.cur.fetchone.return_value['perfil'] = 'atendente'
        response = self.client.get('/pages/sistema/estoque/estoque.html')
        self.assertEqual(response.status_code, 200)
        payload = re.search(rb'id="fc-session-context">(.*?)</script>', response.data).group(1)
        context = json.loads(payload)
        self.assertEqual(context['perfil'], 'atendente')
        self.assertEqual(set(context['permissoes']), DEFAULTS['atendente'])
        self.assertEqual(context['modulos_escrita'], ['vendas'])
        self.assertNotIn('senha', payload.decode())
        self.assertEqual(context['csrf_token'], 'teste-csrf')

    def test_home_never_points_to_a_denied_dashboard(self):
        self.assertEqual(access.pagina_inicial('atendente', set()), '/pages/sistema/vendas/vendas.html')
        self.assertEqual(access.pagina_inicial('compras', {'compras'}), '/pages/sistema/compras/compras.html')
        self.assertIsNone(access.pagina_inicial('visualizador', set()))

    def test_login_response_has_an_allowed_home_for_all_seven_profiles(self):
        for role in DEFAULTS:
            with self.subTest(role=role):
                self.login_session(role)
                self.profile_permissions[role] = DEFAULTS[role] - {'dashboard'}
                self.cur.fetchone.return_value.update(nome='Teste', sobrenome='Perfil', email='teste@example.com',
                                                     perfil_nome=role)
                api.app.extensions['auth_limiter'] = AuthLimiter()
                with patch.object(credentials, 'verificar_senha', return_value=True):
                    response = self.client.post('/auth/login', json={'email':'teste@example.com','password':'senha-teste'})
                self.assertEqual(response.status_code, 200, response.json)
                first = 'vendas' if role in SALES else 'estoque'
                self.assertEqual(response.json['pagina_inicial'], f'/pages/sistema/{first}/{first}.html')
