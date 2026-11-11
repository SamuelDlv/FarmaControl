# Guia de manutenção — Testes de devolucao.
# Os cenários e asserts abaixo definem os contratos esperados e os casos de regressão.
# Leia os mocks e fixtures de cada caso antes de interpretar o resultado como integração real.
# Consulte docs/desenvolvimento.md para executar as verificações desta camada.
"""Regressoes da devolucao administrativa ao fornecedor."""
import unittest
import test_descarte as helpers


# Agrupa os cenários de teste e suas fixtures.
class DevolucaoTests(unittest.TestCase):
    setUp = helpers.DescarteTests.setUp
    login_session = helpers.DescarteTests.login_session
    prepare = helpers.DescarteTests.prepare
    writes = helpers.DescarteTests.writes

    def post(self, **changes):
        changes.setdefault('finalidade', 'devolucao_fornecedor')
        return helpers.DescarteTests.post(self, **changes)

    test_quantities = helpers.DescarteTests.test_invalid_disposal_quantities_never_write
    test_reason = helpers.DescarteTests.test_reason_is_required_and_bounded
    test_roles = helpers.DescarteTests.test_unauthorized_profiles_cannot_use_disposal
    test_permission = helpers.DescarteTests.test_disposal_requires_persisted_inventory_permission
    test_lot = helpers.DescarteTests.test_disposal_keeps_required_lot_validation
    test_rollback = helpers.DescarteTests.test_audit_failure_rolls_back_disposal
    test_concurrent_balance = helpers.DescarteTests.test_current_locked_balance_prevents_second_overdraw

    # Cenário de regressão: return 18 minus 4 with and without supplier and expired lot.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_return_18_minus_4_with_and_without_supplier_and_expired_lot(self):
        for expiry, supplier in [('2000-01-01', 7), ('2999-01-01', None)]:
            with self.subTest(expiry=expiry, supplier=supplier):
                self.prepare(expiry=expiry)
                self.cur.reset_mock()
                self.db.reset_mock()
                self.cur.fetchone.return_value['fornecedor_id'] = supplier
                self.item['quantidade'] = 18
                response = self.post(quantidade=4, observacao='Protocolo 123')
                self.assertEqual(response.status_code, 201, response.json)
                writes = self.writes()
                self.assertEqual(len(writes), 3)
                self.assertEqual(writes[0][1], (14, 8))
                self.assertEqual(writes[1][1], (8, 42, 'saida', 4, 'Protocolo 123', 'devolucao_fornecedor', 'Produto vencido', supplier))
                self.assertIn('devolu', writes[2][1][3])
                for detail in ('finalidade: devolucao_fornecedor', 'lote: LOTE-A', 'produto_id: 2', 'quantidade: 4', 'fornecedor_id:'):
                    self.assertIn(detail, writes[2][1][4])
                self.db.commit.assert_called_once()

    # Cenário de regressão: mismatched supplier and internal destination rejected.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_mismatched_supplier_and_internal_destination_rejected(self):
        self.prepare()
        self.cur.fetchone.return_value['fornecedor_id'] = 7
        for supplier in (8, 0, True, '7'):
            self.assertEqual(self.post(fornecedor_id=supplier).status_code, 400)
        self.assertEqual(self.post(estoque_destino_id=9).status_code, 400)
        self.assertEqual(self.writes(), [])
        self.assertEqual(self.post(fornecedor_id=7).status_code, 201)

    # Cenário de regressão: transfer rejects same nonexistent and different product destination.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_transfer_rejects_same_nonexistent_and_different_product_destination(self):
        self.prepare()
        for destination in (None, 8, 0, True, '9', 9):
            self.assertEqual(self.post(tipo_movimentacao='transferencia', finalidade=None, motivo=None, estoque_destino_id=destination).status_code, 400)
        self.cur.fetchall.return_value = [self.item, dict(self.item, id=9, produto_id=99)]
        self.assertEqual(self.post(tipo_movimentacao='transferencia', finalidade=None, motivo=None, estoque_destino_id=9).status_code, 400)
        self.assertEqual(self.writes(), [])

    # Cenário de regressão: csrf.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_csrf(self):
        self.prepare()
        response = self.client.post('/movimentacoes-estoque', json={'estoque_id': 8, 'tipo_movimentacao': 'saida', 'finalidade': 'devolucao_fornecedor', 'motivo': 'Recall', 'quantidade': 4})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.writes(), [])

    # Cenário de regressão: sale cannot use return purpose to bypass expiry.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_sale_cannot_use_return_purpose_to_bypass_expiry(self):
        self.prepare()
        auth = self.cur.fetchone.return_value
        self.cur.fetchone.side_effect = [auth, {'id': 2}, self.item]
        response = self.client.post('/vendas', json={
            'valor_total': 10, 'tipo_pagamento': 'pix', 'status': 'concluida',
            'finalidade': 'devolucao_fornecedor', 'itens': [{'produto_id': 2, 'quantidade': 5,
                'preco_unitario': 2, 'lote_vendido': 'LOTE-A', 'finalidade': 'devolucao_fornecedor'}]},
            headers={'X-CSRF-Token': 'teste-csrf'})
        self.assertEqual(response.status_code, 400, response.json)
        self.assertIn('vencido', response.json['mensagem'])
        self.db.commit.assert_not_called()

    # Cenário de regressão: history exposes supplier.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_history_exposes_supplier(self):
        self.prepare()
        self.cur.fetchall.return_value = [{'finalidade': 'devolucao_fornecedor', 'fornecedor_id': 7}]
        response = self.client.get('/estoque/8/historico')
        self.assertEqual(response.json['historico'][0]['fornecedor_id'], 7)
        query = next(c.args[0] for c in self.cur.execute.call_args_list if 'SELECT me.id' in c.args[0])
        self.assertIn('me.fornecedor_id', query)


if __name__ == '__main__':
    unittest.main()
