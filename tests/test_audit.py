"""Regressões da rastreabilidade, sem acesso a banco real."""
import ast
import inspect
from unittest.mock import Mock
import unittest
import test_backend as base
from flask import g
from farmacontrol.services.audit import commit_audit

api = base.api


class AuditTests(unittest.TestCase):
    setUp = base.BackendTests.setUp
    login_session = base.BackendTests.login_session

    def event(self):
        return next(call.args[1] for call in self.cur.execute.call_args_list
                    if 'INSERT INTO log_atividades' in call.args[0])

    def test_supplier_has_actor_identity_and_created_record(self):
        self.login_session()
        response = self.client.post('/fornecedores', json={
            'nome_fantasia': 'Distribuidora Central', 'razao_social': 'Central Ltda',
            'cnpj': '12345678000199', 'contato_email': 'privado@example.com',
            'usuario_id': 999, 'senha': 'segredo'}, headers={'X-CSRF-Token': 'teste-csrf'})
        self.assertEqual(response.status_code, 201)
        event = self.event()
        self.assertEqual(event[0], 42)
        self.assertEqual(event[3], 'Cadastrou fornecedor')
        self.assertIn('Distribuidora Central', event[4])
        self.assertIn('registro=8', event[4])
        self.assertNotIn('privado@example.com', event[4])
        self.assertNotIn('segredo', event[4])

    def test_created_purchase_references_purchase_not_last_inserted_item(self):
        self.login_session()
        def execute(sql, *args):
            if 'INSERT INTO compras ' in sql:
                self.cur.lastrowid = 17
            elif 'INSERT INTO itens_compra ' in sql:
                self.cur.lastrowid = 93
        self.cur.execute.side_effect = execute
        response = self.client.post('/compras', json={
            'fornecedor_id': 2, 'valor_total': 20, 'itens': [
                {'produto_id': 5, 'quantidade': 2, 'preco_unitario': 10}]},
            headers={'X-CSRF-Token': 'teste-csrf'})
        self.assertEqual(response.status_code, 201, response.json)
        self.assertIn('registro=17', self.event()[4])
        self.assertNotIn('registro=93', self.event()[4])

    def test_details_preserve_all_items_and_commit_once(self):
        items = [{'produto_id': i, 'quantidade': 2, 'preco_unitario': 10, 'senha': 'segredo'} for i in range(100)]
        with api.app.test_request_context('/vendas', method='POST', json={'status': 'concluida', 'itens': items}):
            g.usuario_id = 42
            commit_audit(self.db, 78)
        event = self.event()
        self.assertEqual(event[3], 'Concluiu venda')
        self.assertIn('registro=78', event[4])
        self.assertIn('Item 100: produto_id=99', event[4])
        self.assertGreater(len(event[4]), 1000)
        self.assertNotIn('segredo', event[4])
        self.db.commit.assert_called_once()

    def test_sale_status_transition_is_explicit(self):
        with api.app.test_request_context('/vendas/7', method='PUT', json={'status': 'concluida'}):
            g.usuario_id = 42
            g.audit_previous_status = 'pendente'
            commit_audit(self.db)
        self.assertEqual(self.event()[3], 'Concluiu venda')
        self.assertIn('Status anterior: pendente', self.event()[4])
        self.assertIn('venda_id=7', self.event()[4])

    def test_same_status_does_not_claim_sale_concluded_again(self):
        with api.app.test_request_context('/vendas/7', method='PUT', json={'status': 'concluida'}):
            g.audit_previous_status = 'concluida'
            commit_audit(self.db)
        self.assertEqual(self.event()[3], 'Atualizou venda')

    def test_secret_invitation_url_is_never_logged(self):
        with api.app.test_request_context('/auth/convites/token-secreto/recusar', method='POST'):
            commit_audit(self.db)
        self.assertNotIn('token-secreto', str(self.event()))

    def test_search_and_activity_filter_use_bound_parameters(self):
        self.login_session()
        response = self.client.get('/admin/logs', query_string={
            'busca': "Central %_'", 'atividade': 'alteracoes', 'usuario_id': 42})
        self.assertEqual(response.status_code, 200)
        sql, params = self.cur.execute.call_args.args
        self.assertIn('detalhes NOT LIKE %s', sql)
        self.assertNotIn("Central", sql)
        self.assertEqual(params, (42, "Central %_'", "Central %_'", "Central %_'", 'GET %', 51))
        self.assertEqual(response.json['filtros']['atividade'], 'alteracoes')

    def test_invalid_search_filters_are_rejected(self):
        self.login_session()
        for query in ({'atividade': 'invalida'}, {'busca': 'a' * 121}):
            self.assertEqual(self.client.get('/admin/logs', query_string=query).status_code, 400)

    def test_every_mutation_endpoint_uses_transactional_audit(self):
        endpoints = {rule.endpoint for rule in api.app.url_map.iter_rules()
                     if rule.methods & {'POST', 'PUT', 'PATCH', 'DELETE'}}
        self.assertTrue(endpoints)
        for endpoint in endpoints:
            function = ast.parse(inspect.getsource(api.app.view_functions[endpoint]))
            with self.subTest(endpoint=endpoint):
                self.assertTrue(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                                    and n.func.id == 'commit_audit' for n in ast.walk(function)))
