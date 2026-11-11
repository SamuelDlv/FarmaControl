"""Correções financeiras: centavos exatos, autorização, concorrência e log atômico."""
from decimal import Decimal
import unittest
from unittest.mock import patch
import pymysql
import test_backend as base
from farmacontrol.routes import financeiro


class FinanceiroEdicaoTests(unittest.TestCase):
    setUp = base.BackendTests.setUp
    login_session = base.BackendTests.login_session

    def prepare(self):
        self.login_session()
        self.auth = dict(self.cur.fetchone.return_value)
        self.row = dict(id=12, valor=Decimal('150.75'), usuario_id=7, categoria_id=2,
                        status='pago', venda_id=None, compra_id=None)
        self.audit_fails = False

        def execute(sql, params=None):
            if 'INSERT INTO log_atividades' in sql and self.audit_fails:
                raise pymysql.OperationalError('auditoria indisponível')
            elif 'FROM usuarios u JOIN perfis' in sql:
                self.cur.fetchone.return_value = self.auth
            elif 'FOR UPDATE' in sql:
                self.cur.fetchone.return_value = self.row
        self.cur.execute.side_effect = execute
        tables = patch.object(financeiro, '_fin_tables_exist', return_value=True)
        tables.start()
        self.addCleanup(tables.stop)

    def save(self, **overrides):
        payload = dict(valor='100.25', valor_anterior='150.75', motivo='Erro de digitação')
        payload.update(overrides)
        return self.client.put('/financeiro/transacoes/12', json=payload,
                               headers={'X-CSRF-Token': 'teste-csrf'})

    def updates(self):
        return [call.args for call in self.cur.execute.call_args_list
                if 'UPDATE financeiro_transacoes SET' in call.args[0]]

    def test_correction_records_server_values_actor_reason_and_original_creator(self):
        self.prepare()
        response = self.save()
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['valor_anterior'], '150.75')
        self.assertEqual(response.json['valor'], '100.25')
        self.assertEqual(self.updates()[0][1], (Decimal('100.25'), 12))
        self.assertIn('FOR UPDATE', str(self.cur.execute.call_args_list))
        events = [call.args[1] for call in self.cur.execute.call_args_list if 'INSERT INTO log_atividades' in call.args[0]]
        self.assertEqual(len(events), 1)
        actor, _, _, action, details, status = events[0]
        self.assertEqual(actor, 42)
        self.assertEqual(action, 'Corrigiu valor de transação financeira')
        for text in ('transacao_id=12', 'Valor anterior (R$): 150.75', 'Valor novo (R$): 100.25',
                     'Erro de digitação', 'Usuário criador do lançamento: 7'):
            self.assertIn(text, details)
        self.db.commit.assert_called_once()

    def test_audit_failure_rolls_back_correction(self):
        self.prepare()
        self.audit_fails = True
        response = self.save()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(len(self.updates()), 1)
        self.db.rollback.assert_called_once()
        self.db.commit.assert_not_called()

    def test_stale_value_is_rejected_without_update(self):
        self.prepare()
        response = self.save(valor_anterior='150.74')
        self.assertEqual(response.status_code, 409)
        self.assertFalse(self.updates())
        self.db.commit.assert_not_called()

    def test_missing_transaction(self):
        self.prepare()
        self.row = None
        self.assertEqual(self.save().status_code, 404)
        self.assertFalse(self.updates())

    def test_linked_sale_or_purchase_cannot_diverge(self):
        self.prepare()
        for key in ('venda_id', 'compra_id'):
            with self.subTest(key=key):
                self.row[key] = 9
                self.assertEqual(self.save().status_code, 409)
                self.row[key] = None
        self.assertFalse(self.updates())

    def test_invalid_values_and_reason_are_rejected(self):
        self.prepare()
        for value in ('NaN', 'Infinity', '-1', '0', '1.005', '10000000000', None, True, {}, []):
            with self.subTest(value=value):
                self.assertEqual(self.save(valor=value).status_code, 400)
        for reason in ('', 'a', '  a  ', '\n  \n', 'x' * 256, None, []):
            with self.subTest(reason=reason):
                self.assertEqual(self.save(motivo=reason).status_code, 400)
        self.assertFalse(self.updates())

    def test_unchanged_value_and_extra_fields_are_rejected(self):
        self.prepare()
        self.assertEqual(self.save(valor='150.75').status_code, 400)
        for field in ('usuario_id', 'status', 'venda_id', 'categoria_id', 'audit_changes'):
            self.assertEqual(self.save(**{field: 'forjado'}).status_code, 400)
        self.assertFalse(self.updates())

    def test_missing_csrf_and_read_only_profile_are_denied(self):
        self.prepare()
        response = self.client.put('/financeiro/transacoes/12', json={})
        self.assertEqual(response.status_code, 403)
        self.auth['perfil'] = 'visualizador'
        self.assertEqual(self.save().status_code, 403)
        self.assertFalse(self.updates())

    def test_missing_session_is_denied(self):
        self.assertEqual(self.client.put('/financeiro/transacoes/12', json={}).status_code, 401)

    def test_decimal_limits_preserve_cents(self):
        self.prepare()
        for value in ('0.01', '9999999999.99', '0.10'):
            with self.subTest(value=value):
                response = self.save(valor=value)
                self.assertEqual(response.status_code, 200, response.json)
                self.assertEqual(response.json['valor'], value)

    def test_successive_corrections_preserve_each_before_and_after(self):
        self.prepare()
        self.assertEqual(self.save().status_code, 200)
        self.row['valor'] = Decimal('100.25')
        self.assertEqual(self.save(valor='80.10', valor_anterior='100.25',
                                   motivo='Conferência do comprovante').status_code, 200)
        events = [call.args[1][4] for call in self.cur.execute.call_args_list
                  if 'INSERT INTO log_atividades' in call.args[0]]
        self.assertEqual(len(events), 2)
        self.assertIn('Valor anterior (R$): 150.75', events[0])
        self.assertIn('Valor novo (R$): 100.25', events[0])
        self.assertIn('Valor anterior (R$): 100.25', events[1])
        self.assertIn('Valor novo (R$): 80.10', events[1])
        self.assertIn('Conferência do comprovante', events[1])
        for sql, _ in self.updates():
            self.assertEqual(sql, 'UPDATE financeiro_transacoes SET valor = %s WHERE id = %s')
