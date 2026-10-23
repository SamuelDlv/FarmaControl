import unittest
from unittest.mock import patch
import pymysql
from datetime import datetime
import test_backend as backend_tests
from farmacontrol.services.system_settings import DEFAULTS, validate_settings, active_alerts, require_usable_stock
from farmacontrol.services.settings_notifications import send_due


class SettingsTests(unittest.TestCase):
    setUp = backend_tests.BackendTests.setUp
    login_session = backend_tests.BackendTests.login_session

    def save(self, values):
        self.login_session()
        return self.client.put('/configuracoes', json={'configuracoes': values},
                               headers={'X-CSRF-Token': 'teste-csrf'})

    def test_batch_saves_all_sections_and_commits_once(self):
        values = {'nome_farmacia': 'Farmácia Central', 'telefone': '',
                  'alerta_vencimento': False, 'estoque_minimo_padrao': 0}
        response = self.save(values)
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['valores']['alerta_vencimento'], 'false')
        self.db.commit.assert_called_once()
        inserts = [c for c in self.cur.execute.call_args_list if 'INSERT INTO configuracoes_sistema' in c.args[0]]
        self.assertEqual(len(inserts), 4)

    def test_invalid_batch_writes_nothing(self):
        response = self.save({'nome_farmacia': 'Nova', 'prazo_vencimento': '0'})
        self.assertEqual(response.status_code, 400)
        self.db.commit.assert_not_called()
        self.assertFalse(any('INSERT INTO configuracoes_sistema' in c.args[0] for c in self.cur.execute.call_args_list))

    def test_database_failure_rolls_back_whole_batch(self):
        def execute(sql, *args):
            if 'INSERT INTO configuracoes_sistema' in sql:
                raise pymysql.OperationalError('falha simulada')
        self.cur.execute.side_effect = execute
        self.assertEqual(self.save({'nome_farmacia': 'Nova'}).status_code, 500)
        self.db.rollback.assert_called()
        self.db.commit.assert_not_called()

    def test_validation_email_ranges_and_booleans(self):
        for values in ({'notificacoes_email': True}, {'email_notificacao': 'invalido'},
                       {'ponto_reposicao': '101'}, {'prazo_vencimento': '1.5'},
                       {'alerta_vencimento': 'talvez'}, {'estoque_minimo_padrao': '200'}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                validate_settings(values)

    def test_alert_toggles_and_expiry_window(self):
        settings = {**DEFAULTS, 'alerta_estoque_minimo': 'false',
                    'alertas_pedidos_pendentes': 'false', 'prazo_vencimento': '75'}
        self.cur.fetchall.return_value = [{'nome': 'Teste', 'lote': 'A1', 'data_validade': '2026-11-30'}]
        alerts = active_alerts(self.cur, settings)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(self.cur.execute.call_args.args[1], (75,))
        self.cur.reset_mock()
        self.assertEqual(active_alerts(self.cur, {**settings, 'alerta_vencimento': 'false'}), [])
        self.cur.execute.assert_not_called()

    def test_expired_output_and_required_lot(self):
        with self.assertRaises(ValueError):
            require_usable_stock(DEFAULTS, {'lote': 'A1', 'data_validade': '2000-01-01'})
        require_usable_stock({**DEFAULTS, 'bloquear_produtos_vencidos': 'false'},
                             {'lote': 'A1', 'data_validade': '2000-01-01'})
        with self.assertRaises(ValueError):
            require_usable_stock({**DEFAULTS, 'controle_lote_obrigatorio': 'true'}, {'lote': 'SEM-LOTE'})

    def test_inventory_defaults_do_not_disclose_contacts(self):
        self.login_session('atendente')
        self.cur.fetchall.return_value = [{'chave': 'nome_farmacia', 'valor': 'Privado'},
                                         {'chave': 'estoque_minimo_padrao', 'valor': '25'}]
        response = self.client.get('/estoque/parametros')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['parametros']['estoque_minimo_padrao'], '25')
        self.assertNotIn('nome_farmacia', response.json['parametros'])

    def test_save_requires_csrf(self):
        self.login_session()
        self.assertEqual(self.client.put('/configuracoes', json={'configuracoes': {'nome_farmacia': 'X'}}).status_code, 403)

    def test_notifications_do_not_repeat_successful_daily_send(self):
        settings = {**DEFAULTS, 'notificacoes_email': 'true', 'email_notificacao': 'teste@example.com',
                    'notificacao.ultimo_dia': '2026-10-12'}
        with patch('farmacontrol.services.settings_notifications.read_settings', return_value=settings), \
                patch('farmacontrol.services.settings_notifications.active_alerts', return_value=[]):
            sender = unittest.mock.Mock(return_value=True)
            send_due(self.cur, sender, datetime(2026, 10, 12))
            sender.assert_not_called()
            send_due(self.cur, sender, datetime(2026, 10, 13))
            sender.assert_called_once()
            self.assertEqual(self.cur.execute.call_args.args[1], ('notificacao.ultimo_dia', '2026-10-13'))

    def test_failed_email_is_not_marked_delivered(self):
        settings = {**DEFAULTS, 'notificacoes_email': 'true', 'email_notificacao': 'teste@example.com'}
        with patch('farmacontrol.services.settings_notifications.read_settings', return_value=settings), \
                patch('farmacontrol.services.settings_notifications.active_alerts', return_value=[]):
            sender = unittest.mock.Mock(return_value=False)
            send_due(self.cur, sender, datetime(2026, 10, 12))
            self.cur.execute.assert_not_called()


if __name__ == '__main__':
    unittest.main()
