"""Reproduções de segurança isoladas; não conectam ao banco nem enviam e-mail."""
import unittest
from unittest.mock import patch
import test_backend as base
from farmacontrol.core.security import AuthLimiter

api = base.api


from farmacontrol.core import credentials as credentials_module
from farmacontrol.core import database
from farmacontrol.core.security import credential_stamp
from farmacontrol.services import email


class SecurityTests(unittest.TestCase):
    setUp = base.BackendTests.setUp
    login_session = base.BackendTests.login_session

    def test_auth_rate_limit_cannot_be_bypassed_with_forwarded_header(self):
        for index in range(5):
            response = self.client.post('/auth/login', json={},
                                        headers={'X-Forwarded-For': f'192.0.2.{index}'})
            self.assertEqual(response.status_code, 400)
        response = self.client.post('/auth/login', json={})
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response.headers['Retry-After']), 0)
        database.get_db.assert_not_called()

    def test_untrusted_origin_cannot_mutate_auth(self):
        response = self.client.post('/auth/login', json={}, headers={'Origin': 'https://evil.example'})
        self.assertEqual(response.status_code, 403)
        database.get_db.assert_not_called()

    def test_wrong_password_reports_remaining_attempts_and_wait_until_reset(self):
        api.app.extensions["auth_limiter"] = AuthLimiter(limit=2, window=300)
        credentials = {'email': 'teste@example.com', 'password': 'incorreta'}
        with patch('farmacontrol.core.security.time.monotonic', return_value=100), \
                patch.object(credentials_module, 'verificar_senha', return_value=False):
            first = self.client.post('/auth/login', json=credentials)
        self.assertEqual(first.status_code, 401)
        self.assertEqual(first.json['tentativas_restantes'], 1)
        self.assertEqual(first.json['aguarde_segundos'], 0)
        self.assertIn('1 tentativa disponível', first.json['mensagem'])
        with patch('farmacontrol.core.security.time.monotonic', return_value=110), \
                patch.object(credentials_module, 'verificar_senha', return_value=False):
            last = self.client.post('/auth/login', json=credentials)
        self.assertEqual(last.status_code, 401)
        self.assertEqual(last.json['tentativas_restantes'], 0)
        self.assertEqual(last.json['aguarde_segundos'], 290)
        self.assertIn('04:50', last.json['mensagem'])
        with patch('farmacontrol.core.security.time.monotonic', return_value=120):
            blocked = self.client.post('/auth/login', json=credentials)
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked.json['aguarde_segundos'], 280)
        self.assertEqual(blocked.headers['Retry-After'], '280')
        with patch('farmacontrol.core.security.time.monotonic', return_value=400), \
                patch.object(credentials_module, 'verificar_senha', return_value=False):
            renewed = self.client.post('/auth/login', json=credentials)
        self.assertEqual(renewed.status_code, 401)
        self.assertEqual(renewed.json['tentativas_restantes'], 1)

    def test_unknown_email_has_same_attempt_feedback_as_wrong_password(self):
        self.cur.fetchone.return_value = None
        response = self.client.post('/auth/login', json={
            'email': 'ausente@example.com', 'password': 'incorreta',
        })
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json['tentativas_restantes'], 4)
        self.assertEqual(response.json['aguarde_segundos'], 0)
        self.assertIn('E-mail ou senha incorretos.', response.json['mensagem'])

    def test_unicode_csrf_header_is_rejected_without_server_error(self):
        self.login_session()
        response = self.client.post('/estoque', json={}, headers={'X-CSRF-Token': 'é'})
        self.assertEqual(response.status_code, 403)
        self.db.commit.assert_not_called()

    def test_nested_permission_payload_is_rejected(self):
        self.login_session()
        response = self.client.put('/admin/perfis/permissoes',
                                   json={'perfis': {'atendente': [{}]}},
                                   headers={'X-CSRF-Token': 'teste-csrf'})
        self.assertEqual(response.status_code, 400)
        self.db.commit.assert_not_called()

    def test_invitation_consumption_failure_rolls_back_account(self):
        self.cur.fetchone.side_effect = [
            {'nome': 'Teste', 'sobrenome': 'Pessoa', 'email': 'a@example.com', 'perfil': 'atendente'},
            None, {'id': 2, 'nome': 'Atendente'},
        ]
        self.cur.rowcount = 0
        with patch.object(credentials_module, 'hash_senha', return_value='hash'), patch.object(email, 'enviar_email_brevo') as mail:
            response = self.client.post('/auth/register', json={
                'convite_token': 'token', 'password': 'abcdefgh',
                'accepts_terms': True, 'accepts_privacy': True})
        self.assertEqual(response.status_code, 410)
        self.db.rollback.assert_called_once()
        self.db.commit.assert_not_called()
        mail.assert_not_called()

    def test_invitation_creates_credential_bound_session(self):
        self.cur.fetchone.side_effect = [
            {'nome': 'Teste', 'sobrenome': 'Pessoa', 'email': 'a@example.com', 'perfil': 'atendente'},
            None, {'id': 2, 'nome': 'Atendente'},
        ]
        self.cur.rowcount = 1
        with patch.object(credentials_module, 'hash_senha', return_value='hash'):
            response = self.client.post('/auth/register', json={
                'convite_token': 'token', 'password': 'abcdefgh',
                'accepts_terms': True, 'accepts_privacy': True})
        self.assertEqual(response.status_code, 201)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess['credential_stamp'], credential_stamp(api.app.secret_key, 'hash'))

    def test_malformed_auth_inputs_are_client_errors(self):
        for data in ([], [1], 'text', {'email': 123}, {'password': ['x']},
                     {'password': 'x' * 73}, {'password': 'é' * 37},
                     {'password': '\ud800'}):
            with self.subTest(data=repr(data)):
                # Cada entrada é um cenário independente de validação.
                api.app.extensions["auth_limiter"] = AuthLimiter()
                self.assertEqual(self.client.post('/auth/login', json=data).status_code, 400)
        database.get_db.assert_not_called()

    def test_bcrypt_limit_is_bytes_and_boundary_is_accepted(self):
        self.cur.fetchone.return_value = None
        self.assertEqual(self.client.post('/auth/login', json={
            'email': 'a@example.com', 'password': 'é' * 36}).status_code, 401)

    def test_large_json_is_rejected_before_database(self):
        response = self.client.post('/auth/login', json={'email': 'a' * (1024 * 1024)})
        self.assertEqual(response.status_code, 413)
        self.assertFalse(response.json['ok'])
        database.get_db.assert_not_called()

    def test_password_change_revokes_existing_cookie(self):
        self.login_session()
        self.cur.fetchone.return_value['senha_hash'] = 'different-hash'
        self.assertEqual(self.client.get('/estoque').status_code, 401)
        with self.client.session_transaction() as sess:
            self.assertNotIn('usuario_id', sess)

    def test_legacy_session_requires_new_login(self):
        self.login_session()
        with self.client.session_transaction() as sess:
            sess.pop('credential_stamp')
        self.assertEqual(self.client.get('/estoque').status_code, 401)

    def test_cookie_stamp_does_not_expose_password_hash(self):
        stamp = credential_stamp('secret', 'bcrypt-value')
        self.assertNotIn('bcrypt-value', stamp)
        self.assertNotEqual(stamp, credential_stamp('other', 'bcrypt-value'))

    def test_reset_locks_token_before_consumption(self):
        self.cur.fetchone.return_value = {'id': 9}
        with patch.object(credentials_module, 'hash_senha', return_value='new-hash'):
            response = self.client.post('/auth/redefinir-senha', json={'token': 'token', 'password': 'abcdefgh'})
        self.assertEqual(response.status_code, 200)
        queries = [c.args[0] for c in self.cur.execute.call_args_list]
        self.assertIn('FOR UPDATE', next(q for q in queries if 'SELECT id FROM usuarios' in q))
        self.assertIn('token_reset = NULL', next(q for q in queries if 'SET senha_hash' in q))

    def test_admin_password_change_also_cancels_reset(self):
        self.login_session()
        with patch.object(credentials_module, 'hash_senha', return_value='new-hash'):
            response = self.client.put('/admin/usuarios/9', json={'senha': 'abcdefgh'},
                                       headers={'X-CSRF-Token': 'teste-csrf'})
        self.assertEqual(response.status_code, 200)
        query = next(c.args[0] for c in self.cur.execute.call_args_list if 'UPDATE usuarios SET' in c.args[0])
        self.assertIn('token_reset = NULL', query)

    def test_forwarded_ip_is_not_trusted_in_access_log(self):
        with api.app.test_request_context('/auth/login', headers={'X-Forwarded-For': 'forged'},
                                         environ_base={'REMOTE_ADDR': '127.0.0.1'}):
            credentials_module.registrar_acesso(self.cur, 42, False)
        self.assertEqual(self.cur.execute.call_args.args[1][1], '127.0.0.1')

    def test_headers_protect_errors_and_secret_responses(self):
        response = self.client.get('/estoque')
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(response.headers['X-Frame-Options'], 'DENY')
        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response.headers['Referrer-Policy'], 'no-referrer')
        self.assertIn("frame-ancestors 'none'", response.headers['Content-Security-Policy'])

    def test_limiter_expires_and_caps_memory_without_eviction_bypass(self):
        limiter = AuthLimiter(limit=1, window=10, capacity=1)
        with patch('farmacontrol.core.security.time.monotonic', return_value=0):
            self.assertEqual(limiter.check('a'), 0)
            self.assertEqual(limiter.check('a'), 10)
            self.assertEqual(limiter.check('b'), 10)
            self.assertEqual(len(limiter.entries), 1)
        with patch('farmacontrol.core.security.time.monotonic', return_value=11):
            self.assertEqual(limiter.check('b'), 0)
