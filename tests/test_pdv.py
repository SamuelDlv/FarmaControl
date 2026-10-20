from unittest.mock import patch
import test_backend as base
import unittest
api = base.api


class PdvTests(unittest.TestCase):
    setUp = base.BackendTests.setUp
    login_session = base.BackendTests.login_session

    def payload(self):
        return {'tipo_pagamento':'pix','itens':[{'estoque_id':2,'quantidade':2,'preco_unitario':'12.50'}]}

    def post(self, data):
        return self.client.post('/vendas/balcao',json=data,headers={'X-CSRF-Token':'teste-csrf'})

    def prepare(self, **changes):
        self.login_session('atendente')
        row={'id':2,'produto_id':7,'preco_venda':'12.50','requer_receita':False,'quantidade':4,'lote':'L1','valido':1}
        row.update(changes)
        self.cur.fetchone.side_effect=[{'senha_hash':'hash-simulado','status':'aprovado','perfil':'atendente'},row,{'id':3}]

    def test_access_roles(self):
        for role in api.PERFIS_VALIDOS:
            self.login_session(role)
            response=self.client.get('/vendas/catalogo')
            self.assertEqual(response.status_code,200 if role in api.SALES_ROLES else 403)

    def test_invalid_quantities_do_not_write(self):
        self.login_session()
        for qty in [-1,0,True,1.5,'2']:
            data=self.payload();data['itens'][0]['quantidade']=qty
            self.assertEqual(self.post(data).status_code,400)
        self.db.commit.assert_not_called()

    def test_sale_is_atomic_and_total_is_server_calculated(self):
        self.prepare()
        response=self.post(self.payload())
        self.assertEqual(response.status_code,201,response.json)
        self.assertEqual(response.json['valor_total'],'25.00')
        sql=' '.join(call.args[0] for call in self.cur.execute.call_args_list)
        for fragment in ['FOR UPDATE','INSERT INTO vendas','INSERT INTO itens_venda','INSERT INTO movimentacoes_estoque','INSERT INTO financeiro_transacoes','INSERT INTO log_atividades']:
            self.assertIn(fragment,sql)
        self.db.commit.assert_called_once()

    def test_changed_price_insufficient_stock_expiry_and_prescription(self):
        for changes in [{'preco_venda':'13.00'},{'quantidade':1},{'valido':0},{'requer_receita':True}]:
            self.prepare(**changes)
            self.assertEqual(self.post(self.payload()).status_code,409)
        self.db.commit.assert_not_called()
        self.assertEqual(self.db.rollback.call_count,4)

    def test_financial_failure_rolls_back_stock_and_sale(self):
        self.prepare()
        def execute(sql,*args):
            if 'INSERT INTO financeiro_transacoes' in sql:
                raise api.pymysql.OperationalError('simulado')
        self.cur.execute.side_effect=execute
        self.assertEqual(self.post(self.payload()).status_code,503)
        self.db.rollback.assert_called_once()
        self.db.commit.assert_not_called()

    def test_csrf_required(self):
        self.login_session('atendente')
        self.assertEqual(self.client.post('/vendas/balcao',json=self.payload()).status_code,403)

    def test_legacy_sale_registers_financial_entry_atomically(self):
        self.login_session()
        response = self.client.post('/vendas', json={
            'valor_total': 25, 'tipo_pagamento': 'pix', 'status': 'concluida',
        }, headers={'X-CSRF-Token': 'teste-csrf'})
        self.assertEqual(response.status_code, 201, response.json)
        sql = ' '.join(call.args[0] for call in self.cur.execute.call_args_list)
        self.assertIn('INSERT INTO financeiro_transacoes', sql)
        self.assertIn('NOT EXISTS', sql)
        self.db.commit.assert_called_once()

    def test_audit_contains_validated_sale_total_and_items(self):
        self.prepare()
        payload = self.payload()
        payload['valor_total'] = '9999.00'
        self.assertEqual(self.post(payload).status_code, 201)
        event = next(call.args[1] for call in self.cur.execute.call_args_list
                     if 'INSERT INTO log_atividades' in call.args[0])
        self.assertEqual(event[0], 42)
        self.assertEqual(event[3], 'Concluiu venda')
        self.assertIn('valor_total: 25.00', event[4])
        self.assertIn('produto_id=7', event[4])
        self.assertIn('lote_vendido=L1', event[4])
        self.assertNotIn('9999.00', event[4])

    def test_legacy_sale_rolls_back_on_financial_failure(self):
        self.login_session()
        def execute(sql, *args):
            if 'INSERT INTO financeiro_transacoes' in sql:
                raise api.pymysql.OperationalError('simulado')
        self.cur.execute.side_effect = execute
        response = self.client.post('/vendas', json={
            'valor_total': 25, 'tipo_pagamento': 'pix', 'status': 'concluida',
        }, headers={'X-CSRF-Token': 'teste-csrf'})
        self.assertEqual(response.status_code, 500)
        self.db.rollback.assert_called_once()
        self.db.commit.assert_not_called()
