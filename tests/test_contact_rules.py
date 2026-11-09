# Guia de manutenção — Testes de contact rules.
# Os cenários e asserts abaixo definem os contratos esperados e os casos de regressão.
# Leia os mocks e fixtures de cada caso antes de interpretar o resultado como integração real.
# Consulte docs/DESENVOLVIMENTO.md para executar as verificações desta camada.
"""Regressões de formato e rejeição antes de gravar dados de fornecedores."""
import unittest
import test_backend as backend_tests
from farmacontrol.services.contact_rules import validate_cnpj, validate_phone
from farmacontrol.services.system_settings import validate_settings


# Agrupa os cenários de teste e suas fixtures.
class ContactRulesTests(unittest.TestCase):
    setUp = backend_tests.BackendTests.setUp
    login_session = backend_tests.BackendTests.login_session

    # Cenário de regressão: cnpj format preserves leading zero and accepts legacy mask.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_cnpj_format_preserves_leading_zero_and_accepts_legacy_mask(self):
        for value in ('00123456000199', '00.123.456/0001-99'):
            validate_cnpj(value)
        for value in ('abc', '0012345600019', '-0123456000199', '0012345600019a', 123, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_cnpj(value)

    # Cenário de regressão: phone and settings.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_phone_and_settings(self):
        for value in ('', None, '(11) 99999-9999', '+55 11 99999-9999'):
            validate_phone(value)
        for values in ({'cnpj': 'letras'}, {'telefone': 'ligue amanhã'}, {'telefone': '---'}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                validate_settings(values)
        self.assertEqual(validate_settings({'cnpj': '00123456000199'})['cnpj'], '00123456000199')

    # Cenário de regressão: invalid supplier create and update never write.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_invalid_supplier_create_and_update_never_write(self):
        self.login_session()
        valid = {'nome_fantasia': 'Distribuidora 123', 'razao_social': 'Empresa Ltda',
                 'cnpj': '00123456000199'}
        for method, route in (('post', '/fornecedores'), ('put', '/fornecedores/8')):
            for invalid in ({'cnpj': 'AB123456000199'}, {'contato_telefone': 'abc'},
                            {'contato_email': 'sem-arroba'}, {'nome_fantasia': 'x' * 151}):
                with self.subTest(method=method, invalid=invalid):
                    self.cur.execute.reset_mock()
                    response = getattr(self.client, method)(route, json={**valid, **invalid},
                        headers={'X-CSRF-Token': 'teste-csrf'})
                    self.assertEqual(response.status_code, 400, response.json)
                    self.db.commit.assert_not_called()
                    self.assertFalse(any('INSERT INTO fornecedores' in call.args[0] or
                                         'UPDATE fornecedores' in call.args[0]
                                         for call in self.cur.execute.call_args_list))

    # Cenário de regressão: supplier accepts valid values.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_supplier_accepts_valid_values(self):
        self.login_session()
        response = self.client.post('/fornecedores', json={
            'nome_fantasia': 'Distribuidora 123', 'razao_social': 'Empresa Ltda',
            'cnpj': '00123456000199', 'contato_telefone': '(11) 99999-9999',
            'contato_email': 'compras@example.com'}, headers={'X-CSRF-Token': 'teste-csrf'})
        self.assertEqual(response.status_code, 201, response.json)


if __name__ == '__main__':
    unittest.main()
