"""Contratos do catálogo misto, sem acesso ao banco instalado."""
import unittest
import test_backend as harness
from farmacontrol.services.product_rules import normalize_product, validate_expiry, PRODUCT_FIELDS


class ProductRulesTests(unittest.TestCase):
    def test_legacy_product_defaults_to_medicine(self):
        p = normalize_product({"nome": "Dipirona", "preco_custo": 1, "preco_venda": 2})
        self.assertEqual(p["tipo_produto"], "medicamento")
        self.assertTrue(p["exige_validade"])

    def test_non_medicine_can_have_expiry(self):
        p = normalize_product({"nome": "Água", "tipo_produto": "outro", "preco_custo": 1, "preco_venda": 2})
        self.assertEqual(validate_expiry("2027-03-01", p), "2027-03-01")
        with self.assertRaises(ValueError):
            validate_expiry(None, p)

    def test_optional_expiry_is_null_but_recorded_dates_remain(self):
        self.assertIsNone(validate_expiry(None, {"exige_validade": False}))
        self.assertEqual(validate_expiry("2027-03-01", {"exige_validade": False}), "2027-03-01")
        with self.assertRaises(ValueError):
            validate_expiry("2027-02-30", {"exige_validade": False})

    def test_medical_rules_cannot_be_bypassed(self):
        base = {"nome": "Teste", "preco_custo": 1, "preco_venda": 2}
        for fields in ({"tipo_produto": "outro", "requer_receita": True},
                       {"tipo_produto": "medicamento", "exige_validade": False},
                       {"tipo_produto": "inexistente"}, {"exige_validade": "false"}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                normalize_product(dict(base, **fields))

    def test_other_products_clear_active_ingredient_and_keep_zero_minimum(self):
        p = normalize_product({"nome": "Escova", "tipo_produto": "outro", "nome_generico": "antigo",
                               "estoque_minimo": 0, "preco_custo": 1, "preco_venda": 2})
        self.assertIsNone(p["nome_generico"])
        self.assertEqual(p["estoque_minimo"], 0)


class CatalogApiTests(unittest.TestCase):
    setUp = harness.BackendTests.setUp
    login_session = harness.BackendTests.login_session

    def prepare(self, *rows):
        self.login_session()
        self.cur.fetchone.side_effect = [{"senha_hash": "hash-simulado", "status": "aprovado", "perfil": "proprietario"}, *rows]

    def post(self, path, data):
        return self.client.post(path, json=data, headers={"X-CSRF-Token": "teste-csrf"})

    def test_create_other_stock_without_expiry(self):
        self.prepare(None, {"id": 4})
        response = self.post('/estoque', {"produto_nome": "Escova", "produto_tipo": "outro",
            "produto_exige_validade": False, "produto_categoria_id": 4,
            "produto_codigo_barras": "00123", "estoque_minimo": 0, "quantidade": 3})
        self.assertEqual(response.status_code, 201, response.json)
        inserts = {args[0].split()[2]: args[1] for args, _ in self.cur.execute.call_args_list if args[0].lstrip().startswith('INSERT')}
        product = dict(zip(PRODUCT_FIELDS, inserts['produtos']))
        self.assertEqual(product['tipo_produto'], 'outro')
        self.assertEqual(product['codigo_barras'], '00123')
        self.assertEqual(product['categoria_id'], 4)
        self.assertEqual(product['estoque_minimo'], 0)
        self.assertIsNone(inserts['estoque'][3])
        self.assertEqual(inserts['estoque'][1], 'SEM-LOTE')

    def test_existing_product_uses_stored_expiry_rule(self):
        self.prepare({"id": 2, "tipo_produto": "medicamento", "exige_validade": True})
        response = self.post('/estoque', {"produto_id": 2, "quantidade": 1, "produto_exige_validade": False})
        self.assertEqual(response.status_code, 400)
        self.db.commit.assert_not_called()

    def test_new_lot_keeps_existing_product_identity(self):
        self.prepare({"id": 2, "tipo_produto": "outro", "exige_validade": False})
        response = self.post('/estoque', {"produto_id": 2, "quantidade": 1})
        self.assertEqual(response.status_code, 201)
        self.assertFalse(any('INSERT INTO produtos' in args[0] for args, _ in self.cur.execute.call_args_list))

    def test_same_name_requires_explicit_existing_product(self):
        self.prepare({"id": 2})
        response = self.post('/estoque', {"produto_nome": "Água", "produto_tipo": "outro", "quantidade": 1})
        self.assertEqual(response.status_code, 409)
        self.db.commit.assert_not_called()

    def test_edit_preserves_omitted_fields_and_clears_optional_expiry(self):
        self.prepare({"id": 9, "produto_id": 2, "quantidade": 1, "data_validade": "2027-01-01"},
                     {"id": 2, "nome": "Escova", "tipo_produto": "outro", "exige_validade": False,
                      "preco_custo": 2, "preco_venda": 4, "fornecedor_id": 8, "categoria_id": 3},
                     {"id": 7}, {"id": 8})
        response = self.client.put('/estoque/9', json={"produto_categoria_id": 7, "estoque_minimo": 0,
                                   "data_validade": None}, headers={"X-CSRF-Token": "teste-csrf"})
        self.assertEqual(response.status_code, 200, response.json)
        update = next(args[1] for args, _ in self.cur.execute.call_args_list if args[0].startswith('UPDATE produtos'))
        product = dict(zip(PRODUCT_FIELDS, update))
        self.assertEqual(product['fornecedor_id'], 8)
        self.assertEqual(product['categoria_id'], 7)
        self.assertEqual(product['estoque_minimo'], 0)
        stock = next(args[1] for args, _ in self.cur.execute.call_args_list if args[0].startswith('UPDATE estoque'))
        self.assertIsNone(stock[0])

    def test_purchase_receives_non_perishable_without_lot(self):
        self.prepare({"id": 4}, {"id": 2, "exige_validade": False}, None)
        response = self.post('/compras', {"fornecedor_id": 4, "valor_total": 4, "status": "recebido",
            "itens": [{"produto_id": 2, "quantidade": 2, "preco_unitario": 2}]})
        self.assertEqual(response.status_code, 201, response.json)
        values = next(args[1] for args, _ in self.cur.execute.call_args_list if 'INSERT INTO estoque (' in args[0])
        self.assertEqual(values[1], 'SEM-LOTE')
        self.assertIsNone(values[3])

    def test_purchase_rejects_missing_required_expiry_atomically(self):
        self.prepare({"id": 4}, {"id": 2, "exige_validade": True})
        response = self.post('/compras', {"fornecedor_id": 4, "valor_total": 4, "status": "recebido",
            "itens": [{"produto_id": 2, "quantidade": 2, "preco_unitario": 2}]})
        self.assertEqual(response.status_code, 400)
        self.db.rollback.assert_called_once()
        self.db.commit.assert_not_called()

    def test_sale_of_product_without_lot_decrements_stock(self):
        self.prepare({"id": 2}, {"id": 9, "quantidade": 3}, {"id": 3})
        response = self.post('/vendas', {"valor_total": 4, "tipo_pagamento": "pix", "status": "concluida",
            "itens": [{"produto_id": 2, "quantidade": 1, "preco_unitario": 4}]})
        self.assertEqual(response.status_code, 201, response.json)
        stock_query = next(args for args, _ in self.cur.execute.call_args_list if 'FROM estoque WHERE produto_id' in args[0])
        self.assertEqual(stock_query[1], (2, 'SEM-LOTE'))
        self.assertTrue(any('quantidade = quantidade -' in args[0] for args, _ in self.cur.execute.call_args_list))
