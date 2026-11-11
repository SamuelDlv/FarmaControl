"""Falhas por conta e cota por IP: cenários HTTP e concorrência sem banco real."""
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch
import pymysql
import test_backend as base
from farmacontrol.core import database, credentials
from farmacontrol.core.security import AuthLimiter, LoginFailureLimiter, login_account_key

api = base.api


class LoginLimitsTests(unittest.TestCase):
    setUp = base.BackendTests.setUp
    login_session = base.BackendTests.login_session

    def prepare(self):
        self.login_session()
        self.cur.fetchone.return_value.update(nome='Teste', sobrenome='Conta', email='conta@example.com',
                                             perfil_nome='Proprietário')
        checker = patch.object(credentials, 'verificar_senha', side_effect=lambda password, _: password == 'correta')
        checker.start()
        self.addCleanup(checker.stop)

    def login(self, password='incorreta', email='conta@example.com', ip='127.0.0.1', client=None):
        return (client or self.client).post('/auth/login', json={'email':email,'password':password},
                                          environ_base={'REMOTE_ADDR':ip})

    def test_four_errors_success_logout_and_new_failure_start_fresh(self):
        self.prepare()
        for remaining in (4,3,2,1):
            response = self.login()
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json['tentativas_restantes'], remaining)
            self.assertEqual(response.json['limite_escopo'], 'conta')
        success = self.login('correta')
        self.assertEqual(success.status_code, 200, success.json)
        self.assertEqual(api.app.extensions['login_failure_limiter'].entries, {})
        self.assertEqual(api.app.extensions['auth_limiter'].entries['127.0.0.1'][1], 5)
        self.assertEqual(self.client.post('/auth/logout', headers={
            'X-CSRF-Token':success.json['csrf_token']}).status_code, 200)
        self.assertEqual(api.app.extensions['auth_limiter'].entries['127.0.0.1'][1], 5)
        response = self.login()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json['tentativas_restantes'], 4)

    def test_account_block_is_shared_across_ips_but_does_not_block_another_account(self):
        self.prepare()
        for i in range(5):
            self.assertEqual(self.login(email=' CONTA@EXAMPLE.COM ', ip=f'192.0.2.{i}').status_code, 401)
        blocked = self.login('correta', ip='192.0.2.99')
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked.json['limite_escopo'], 'conta')
        self.cur.fetchone.return_value.update(id=4, email='outra@example.com')
        other = self.login('correta', email='outra@example.com', ip='192.0.2.99')
        self.assertEqual(other.status_code, 200)
        # Entrar em outra conta não limpa o bloqueio anterior.
        self.cur.fetchone.return_value.update(id=3, email='conta@example.com')
        self.assertEqual(self.login('correta').status_code, 429)

    def test_logout_does_not_clear_failures(self):
        self.prepare()
        other = api.app.test_client()
        for _ in range(4):
            self.assertEqual(self.login(client=other).status_code, 401)
        self.assertEqual(self.client.post('/auth/logout', headers={'X-CSRF-Token':'teste-csrf'}).status_code, 200)
        self.assertEqual(self.login().json['tentativas_restantes'], 0)

    def test_real_default_ip_limit_is_100_and_logout_stays_available(self):
        for _ in range(100):
            self.assertEqual(self.client.post('/auth/login', json={}).status_code, 400)
        blocked = self.client.post('/auth/login', json={})
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked.json['limite_escopo'], 'ip')
        self.assertGreater(int(blocked.headers['Retry-After']), 0)
        self.assertEqual(self.client.post('/auth/login', json={}, environ_base={'REMOTE_ADDR':'192.0.2.2'}).status_code, 400)
        self.assertEqual(self.client.post('/auth/logout').status_code, 200)
        self.assertEqual(self.client.post('/auth/login', json={}).status_code, 429)
        self.db.cursor.assert_not_called()

    def test_success_does_not_reset_ip_quota(self):
        self.prepare()
        api.app.extensions['auth_limiter'] = AuthLimiter(limit=3)
        for _ in range(3):
            self.assertEqual(self.login('correta').status_code, 200)
        blocked = self.login('correta')
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked.json['limite_escopo'], 'ip')
        self.assertEqual(api.app.extensions['login_failure_limiter'].entries, {})

    def test_registration_and_recovery_have_separate_smaller_budgets(self):
        self.prepare()
        for _ in range(5):
            self.assertEqual(self.client.post('/auth/register', json={}).status_code, 400)
        blocked = self.client.post('/auth/register', json={})
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked.json['limite_escopo'], 'acao')
        self.assertEqual(self.client.post('/auth/recuperar-senha', json={}).status_code, 200)
        self.assertEqual(self.login('correta').status_code, 200)

    def test_connection_failures_release_reservations_without_counting_wrong_passwords(self):
        self.prepare()
        with patch.object(database, 'get_db', side_effect=pymysql.OperationalError('offline')):
            for _ in range(6):
                self.assertEqual(self.login('correta').status_code, 500)
        self.assertEqual(api.app.extensions['login_failure_limiter'].entries, {})
        self.assertEqual(self.login('correta').status_code, 200)

    def test_failed_audit_does_not_reset_previous_failures(self):
        self.prepare()
        for _ in range(4):
            self.assertEqual(self.login().status_code, 401)
        def execute(sql, params=None):
            if 'INSERT INTO log_atividades' in sql:
                raise pymysql.OperationalError('auditoria indisponível')
        self.cur.execute.side_effect = execute
        self.assertEqual(self.login('correta').status_code, 500)
        key = login_account_key(api.app.secret_key, 'id:3')
        entry = api.app.extensions['login_failure_limiter'].entries[key]
        self.assertEqual(entry['failures'], 4)
        self.assertFalse(entry['pending'])

    def test_unknown_email_and_wrong_password_have_equal_feedback(self):
        self.prepare()
        known = self.login(email='conhecida@example.com')
        self.cur.fetchone.return_value = None
        unknown = self.login(email='ausente@example.com')
        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known.json, unknown.json)


class FailureLimiterTests(unittest.TestCase):
    def test_concurrent_reservations_cannot_exceed_budget_and_finish_is_idempotent(self):
        limiter = LoginFailureLimiter()
        with ThreadPoolExecutor(max_workers=20) as executor:
            attempts = list(executor.map(lambda _: limiter.begin('account'), range(20)))
        accepted = [a for a in attempts if a['ticket'] is not None]
        self.assertEqual(len(accepted), 5)
        for attempt in accepted:
            limiter.finish('account', attempt['ticket'], 'failure')
            limiter.finish('account', attempt['ticket'], 'failure')
        self.assertEqual(limiter.entries['account']['failures'], 5)
        self.assertGreater(limiter.begin('account')['retry_after'], 0)

    def test_success_keeps_other_inflight_failures_traceable(self):
        limiter = LoginFailureLimiter()
        a, b = limiter.begin('account'), limiter.begin('account')
        limiter.finish('account', a['ticket'], 'success')
        result = limiter.finish('account', b['ticket'], 'failure')
        self.assertEqual(result['remaining'], 4)

    def test_capacity_and_expiration_do_not_evict_active_failures(self):
        limiter = LoginFailureLimiter(window=10, capacity=1)
        with patch('farmacontrol.core.security.time.monotonic', return_value=0):
            old = limiter.begin('a')
            limiter.finish('a', old['ticket'], 'failure')
            self.assertIsNone(limiter.begin('b')['ticket'])
            self.assertEqual(limiter.entries['a']['failures'], 1)
        with patch('farmacontrol.core.security.time.monotonic', return_value=11):
            new = limiter.begin('a')
            self.assertIsNotNone(new['ticket'])
            limiter.finish('a', old['ticket'], 'failure')
            self.assertEqual(limiter.entries['a']['failures'], 0)
            limiter.finish('a', new['ticket'])
            self.assertEqual(limiter.entries, {})

    def test_account_keys_are_normalized_and_opaque(self):
        key = login_account_key('segredo', ' A@EXAMPLE.COM ')
        self.assertEqual(key, login_account_key('segredo', 'a@example.com'))
        self.assertNotIn('example', key)
        self.assertNotEqual(key, login_account_key('outro-segredo', 'a@example.com'))
