# Guia de manutenção — Testes de runtime config.
# Os cenários e asserts abaixo definem os contratos esperados e os casos de regressão.
# Leia os mocks e fixtures de cada caso antes de interpretar o resultado como integração real.
# Consulte docs/DESENVOLVIMENTO.md para executar as verificações desta camada.
"""Política de inicialização, sem ler .env ou conectar ao banco."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from farmacontrol.core.runtime_config import runtime_config


# Agrupa os cenários de teste e suas fixtures.
class RuntimeConfigTests(unittest.TestCase):
    # Cenário de regressão: local defaults do not reuse a public secret.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_local_defaults_do_not_reuse_a_public_secret(self):
        first, second = runtime_config({}), runtime_config({})
        self.assertFalse(first['DEBUG'])
        self.assertEqual(first['ALLOWED_ORIGINS'], [])
        self.assertNotEqual(first['SECRET_KEY'], second['SECRET_KEY'])
        self.assertTrue(first['EPHEMERAL_SECRET'])

    # Cenário de regressão: production requires secret and secure cookies.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_production_requires_secret_and_secure_cookies(self):
        base = {'APP_ENV': 'production', 'SECRET_KEY': 'a' * 64}
        config = runtime_config(base)
        self.assertTrue(config['SESSION_COOKIE_SECURE'])
        self.assertFalse(config['DEBUG'])
        self.assertFalse(config['EPHEMERAL_SECRET'])
        for extra in ({'SECRET_KEY': ''}, {'SECRET_KEY': 'dev-secret-insecuro'},
                      {'SECRET_KEY': 'substitua-por-um-segredo-longo-e-aleatorio'},
                      {'APP_DEBUG': 'true'}, {'COOKIE_SECURE': 'false'}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                runtime_config({**base, **extra})

    # Cenário de regressão: only explicit origins are accepted.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_only_explicit_origins_are_accepted(self):
        for origin in ('*', 'null', 'https://*.example.com', 'https://example.com/path',
                       'https://user:password@example.com', 'https://example.com?q=1'):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                runtime_config({'ALLOWED_ORIGINS': origin})
        config = runtime_config({'ALLOWED_ORIGINS': 'http://localhost:5500,https://example.com'})
        self.assertEqual(len(config['ALLOWED_ORIGINS']), 2)
        with self.assertRaises(ValueError):
            runtime_config({'APP_ENV': 'production', 'SECRET_KEY': 'a' * 64,
                            'ALLOWED_ORIGINS': 'http://example.com'})

    # Cenário de regressão: configuration typos do not silently enable development.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_configuration_typos_do_not_silently_enable_development(self):
        for extra in ({'APP_ENV': 'prod'}, {'APP_DEBUG': '1'}, {'SESSION_HOURS': '0'},
                      {'COOKIE_SECURE': 'yes'}, {'SESSION_HOURS': '169'}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                runtime_config(extra)
