# Guia de manutenção — Testes de descarte.
# Os cenários e asserts abaixo definem os contratos esperados e os casos de regressão.
# Leia os mocks e fixtures de cada caso antes de interpretar o resultado como integração real.
# Consulte docs/desenvolvimento.md para executar as verificações desta camada.
"""Regressões HTTP do descarte administrativo, com banco isolado."""
import unittest
from unittest.mock import patch
import pymysql
import test_backend as base
from farmacontrol.routes import estoque
from farmacontrol.services.system_settings import DEFAULTS


# Agrupa os cenários de teste e suas fixtures.
class DescarteTests(unittest.TestCase):
    setUp = base.BackendTests.setUp
    login_session = base.BackendTests.login_session

    def prepare(self, role='farmaceutico', expiry='2000-01-01'):
        self.login_session(role)
        self.item = {'id': 8, 'produto_id': 2, 'quantidade': 23,
                     'lote': 'LOTE-A', 'data_validade': expiry}
        self.cur.fetchall.return_value = [self.item]
        reader = patch.object(estoque, 'read_settings', return_value=dict(DEFAULTS))
        self.settings = reader.start().return_value
        self.addCleanup(reader.stop)

    def post(self, **changes):
        data = {'estoque_id': 8, 'tipo_movimentacao': 'saida', 'quantidade': 5,
                'finalidade': 'descarte', 'motivo': 'Produto vencido', 'usuario_id': 999}
        data.update(changes)
        return self.client.post('/movimentacoes-estoque', json=data,
                                headers={'X-CSRF-Token': 'teste-csrf'})

    def writes(self):
        return [c.args for c in self.cur.execute.call_args_list
                if c.args[0].lstrip().startswith(('INSERT', 'UPDATE'))]

    # Cenário de regressão: expired disposal records balance purpose reason and session author.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_expired_disposal_records_balance_purpose_reason_and_session_author(self):
        self.prepare()
        response = self.post(motivo='  Produto vencido  ')
        self.assertEqual(response.status_code, 201, response.json)
        self.assertEqual(response.json['id'], 8)
        writes = self.writes()
        self.assertEqual(writes[0][1], (18, 8))
        self.assertEqual(writes[1][1], (8, 42, 'saida', 5, None, 'descarte', 'Produto vencido', None))
        self.assertEqual(writes[2][1][0], 42)
        self.assertEqual(writes[2][1][3], 'Registrou descarte de estoque')
        for detail in ('finalidade: descarte', 'motivo: Produto vencido', 'lote: LOTE-A', 'quantidade: 5'):
            self.assertIn(detail, writes[2][1][4])
        lock = next(c.args[0] for c in self.cur.execute.call_args_list if 'FROM estoque WHERE id IN' in c.args[0])
        self.assertIn('FOR UPDATE', lock)
        self.db.commit.assert_called_once()

    # Cenário de regressão: expired normal output and text prefix remain blocked.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_expired_normal_output_and_text_prefix_remain_blocked(self):
        self.prepare()
        for purpose in (None, 'venda'):
            with self.subTest(purpose=purpose):
                response = self.post(finalidade=purpose,
                    motivo=None,
                    observacao='Descarte: texto não autoriza a baixa')
                self.assertEqual(response.status_code, 400, response.json)
                self.assertIn('vencido', response.json['mensagem'])
        self.assertEqual(self.writes(), [])
        self.db.commit.assert_not_called()

    # Cenário de regressão: invalid disposal quantities never write.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_invalid_disposal_quantities_never_write(self):
        self.prepare()
        for qty in (0, -1, 1.5, 24, True, '5'):
            with self.subTest(qty=qty):
                self.assertEqual(self.post(quantidade=qty).status_code, 400)
        self.assertEqual(self.writes(), [])

    # Cenário de regressão: reason is required and bounded.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_reason_is_required_and_bounded(self):
        self.prepare()
        for reason in (None, '', '  ', 123, [], 'x' * 256):
            with self.subTest(reason=reason):
                self.assertEqual(self.post(motivo=reason).status_code, 400)
        self.assertEqual(self.writes(), [])

    # Cenário de regressão: unauthorized profiles cannot use disposal.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_unauthorized_profiles_cannot_use_disposal(self):
        for role in ('atendente', 'visualizador'):
            self.prepare(role)
            self.assertEqual(self.post().status_code, 403)
        self.assertEqual(self.writes(), [])

    # Cenário de regressão: disposal requires persisted inventory permission.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_disposal_requires_persisted_inventory_permission(self):
        self.prepare()
        self.profile_permissions['farmaceutico'] = {'vencimentos'}
        self.assertEqual(self.post().status_code, 403)
        self.assertEqual(self.writes(), [])

    # Cenário de regressão: disposal requires csrf.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_disposal_requires_csrf(self):
        self.prepare()
        response = self.client.post('/movimentacoes-estoque', json={
            'estoque_id': 8, 'tipo_movimentacao': 'saida', 'quantidade': 5,
            'finalidade': 'descarte', 'motivo': 'Vencido'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.writes(), [])

    # Cenário de regressão: nonexpired damaged product can be disposed.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_nonexpired_damaged_product_can_be_disposed(self):
        self.prepare(expiry='2999-01-01')
        self.assertEqual(self.post(motivo='Embalagem danificada').status_code, 201)

    # Cenário de regressão: unknown or incompatible purpose is rejected.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_unknown_or_incompatible_purpose_is_rejected(self):
        self.prepare()
        for purpose in ('qualquer', {}, True):
            self.assertEqual(self.post(finalidade=purpose).status_code, 400)
        for kind in ('entrada', 'ajuste', 'transferencia'):
            self.assertEqual(self.post(tipo_movimentacao=kind).status_code, 400)
        self.assertEqual(self.writes(), [])

    # Cenário de regressão: disposal keeps required lot validation.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_disposal_keeps_required_lot_validation(self):
        self.prepare()
        self.settings['controle_lote_obrigatorio'] = 'true'
        self.item['lote'] = 'SEM-LOTE'
        self.assertEqual(self.post().status_code, 400)
        self.assertEqual(self.writes(), [])

    # Cenário de regressão: current locked balance prevents second overdraw.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_current_locked_balance_prevents_second_overdraw(self):
        self.prepare()
        def execute(sql, params=None):
            if sql.startswith('UPDATE estoque SET quantidade = %s'):
                self.item['quantidade'] = params[0]
        self.cur.execute.side_effect = execute
        self.assertEqual(self.post().status_code, 201)
        self.assertEqual(self.item['quantidade'], 18)
        self.assertEqual(self.post(quantidade=19).status_code, 400)
        self.assertEqual(self.item['quantidade'], 18)
        self.db.commit.assert_called_once()

    # Cenário de regressão: audit failure rolls back disposal.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_audit_failure_rolls_back_disposal(self):
        self.prepare()
        def execute(sql, params=None):
            if 'INSERT INTO log_atividades' in sql:
                raise pymysql.OperationalError('falha simulada')
        self.cur.execute.side_effect = execute
        self.assertEqual(self.post().status_code, 500)
        self.db.rollback.assert_called_once()
        self.db.commit.assert_not_called()

    # Cenário de regressão: existing movement contracts still work.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_existing_movement_contracts_still_work(self):
        self.prepare(expiry='2999-01-01')
        for kind, qty, balance in (('entrada', 5, 28), ('saida', 5, 18), ('ajuste', -5, 18)):
            self.cur.reset_mock()
            response = self.post(tipo_movimentacao=kind, quantidade=qty, finalidade=None, motivo=None)
            self.assertEqual(response.status_code, 201, response.json)
            self.assertEqual(self.writes()[0][1], (balance, 8))

    # Cenário de regressão: transfer still requires destination and updates both lots.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_transfer_still_requires_destination_and_updates_both_lots(self):
        self.prepare(expiry='2999-01-01')
        self.assertEqual(self.post(tipo_movimentacao='transferencia', finalidade=None, motivo=None).status_code, 400)
        self.cur.fetchall.return_value = [self.item, dict(self.item, id=9, quantidade=2)]
        response = self.post(tipo_movimentacao='transferencia', finalidade=None, motivo=None, estoque_destino_id=9)
        self.assertEqual(response.status_code, 201, response.json)
        self.assertEqual(self.writes()[0][1], (18, 8))
        self.assertEqual(self.writes()[1][1], (5, 9))

    # Cenário de regressão: expiry setting still controls normal output.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_expiry_setting_still_controls_normal_output(self):
        self.prepare()
        self.settings['bloquear_produtos_vencidos'] = 'false'
        self.assertEqual(self.post(finalidade=None, motivo=None).status_code, 201)

    # Cenário de regressão: history exposes structured disposal fields.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_history_exposes_structured_disposal_fields(self):
        self.prepare()
        row = {'id': 1, 'tipo_movimentacao': 'saida', 'finalidade': 'descarte',
               'motivo': 'Vencido', 'quantidade': 5, 'usuario_nome': 'Farmacêutico'}
        self.cur.fetchall.return_value = [row]
        response = self.client.get('/estoque/8/historico')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['historico'][0]['finalidade'], 'descarte')
        query = next(c.args[0] for c in self.cur.execute.call_args_list if 'SELECT me.id' in c.args[0])
        self.assertIn('me.finalidade, me.motivo', query)

    # Cenário de regressão: legacy sale cannot disguise expired stock as disposal.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_legacy_sale_cannot_disguise_expired_stock_as_disposal(self):
        self.prepare()
        auth = self.cur.fetchone.return_value
        self.cur.fetchone.side_effect = [auth, {'id': 2}, self.item]
        response = self.client.post('/vendas', json={
            'valor_total': 10, 'tipo_pagamento': 'pix', 'status': 'concluida',
            'finalidade': 'descarte', 'itens': [{'produto_id': 2, 'quantidade': 5,
                'preco_unitario': 2, 'lote_vendido': 'LOTE-A', 'finalidade': 'descarte'}]},
            headers={'X-CSRF-Token': 'teste-csrf'})
        self.assertEqual(response.status_code, 400, response.json)
        self.assertIn('vencido', response.json['mensagem'])
        self.assertFalse(any('UPDATE estoque' in sql for sql, *_ in self.writes()))
        self.db.rollback.assert_called_once()
        self.db.commit.assert_not_called()


    # Cenário de regressão: reports separate disposal from commercial output.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_reports_separate_disposal_from_commercial_output(self):
        from farmacontrol.services.reporting import stock_report
        import sqlite3
        from datetime import date
        # Executa as agregações reais em memória; adapta apenas funções de data
        # do MySQL, sem modificar os predicados de finalidade nem as somas.
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.row_factory = sqlite3.Row
        db.create_function('IF', 3, lambda condition, yes, no: yes if condition else no)
        db.create_function('DATE_FORMAT', 2, lambda value, fmt: value[:7])
        db.executescript("""
            CREATE TABLE categorias_produto (id INTEGER, nome TEXT);
            CREATE TABLE produtos (id INTEGER, nome TEXT, preco_custo REAL, categoria_id INTEGER);
            CREATE TABLE estoque (id INTEGER, produto_id INTEGER, quantidade INTEGER, data_validade TEXT);
            CREATE TABLE movimentacoes_estoque (id INTEGER, estoque_id INTEGER,
                tipo_movimentacao TEXT, quantidade INTEGER, finalidade TEXT, data_movimentacao TEXT);
            INSERT INTO produtos VALUES (2, 'Teste', 2, 1);
            INSERT INTO categorias_produto VALUES (1, 'Teste');
            INSERT INTO estoque VALUES (8, 2, 18, '2000-01-01');
        """)
        for idx, (purpose, qty) in enumerate((('descarte', 5), ('venda', 3), (None, 2), ('devolucao_fornecedor', 4))):
            db.execute("INSERT INTO movimentacoes_estoque VALUES (?,8,'saida',?,?,?)",
                       (idx, qty, purpose, date.today().isoformat()))
        # Agrupa os cenários de teste e suas fixtures.
        class Cursor:
            # Executa as consultas e validações de execute.
            def execute(self, sql):
                sql = sql.replace('DATE_SUB(CURDATE(), INTERVAL (DAYOFMONTH(CURDATE()) - 1) DAY)', "date('now', 'start of month')")
                sql = sql.replace('CURDATE() + INTERVAL 1 DAY', "date('now', '+1 day')")
                sql = sql.replace('CURDATE() + INTERVAL 60 DAY', "date('now', '+60 day')")
                self.result = db.execute(sql.replace('CURDATE()', "date('now')"))
            def fetchone(self):
                return dict(self.result.fetchone())
            def fetchall(self):
                return [dict(row) for row in self.result.fetchall()]
        report = stock_report(Cursor(), 'month')
        self.assertEqual(report['kpis']['total_saidas'], 5)
        self.assertEqual(report['resumo']['valor_saidas'], 10)
        self.assertEqual(report['resumo']['descartados'], 1)
        self.assertEqual(report['por_categoria'][0]['qtd_total'], 5)
        self.assertEqual(report['top_produtos'][0]['quantidade'], 5)
        self.assertEqual(report['evolucao'][0]['saidas'], 5)


if __name__ == '__main__':
    unittest.main()
