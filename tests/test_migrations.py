# Guia de manutenção — Testes de migrations.
# Os cenários e asserts abaixo definem os contratos esperados e os casos de regressão.
# Leia os mocks e fixtures de cada caso antes de interpretar o resultado como integração real.
# Consulte docs/DESENVOLVIMENTO.md para executar as verificações desta camada.
"""Contratos de descoberta de migrações; não conecta a banco."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('fc_migration_runner', ROOT / 'scripts/migrate.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


# Agrupa os cenários de teste e suas fixtures.
class MigrationDiscoveryTests(unittest.TestCase):
    # Cenário de regressão: pending files sort numerically and reject duplicate versions.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_pending_files_sort_numerically_and_reject_duplicate_versions(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            for name in ('1000_futuro.sql', '025_segunda.sql', '024_primeira.sql'):
                (path / name).write_text('SELECT 1;', encoding='utf-8')
            self.assertEqual([m['version'] for m in runner.discover(path)], [24, 25, 1000])
            (path / '024_duplicada.sql').write_text('SELECT 1;', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'duplicada'):
                runner.discover(path)

    # Cenário de regressão: legacy and nonstandard names are not accepted.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_legacy_and_nonstandard_names_are_not_accepted(self):
        for name in ('023_legado.sql', '24_curto.sql', '024_Nome.sql', 'limpeza.sql'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                (Path(folder) / name).write_text('SELECT 1;', encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'inválido'):
                    runner.discover(folder)

    # Cenário de regressão: checksum ignores platform line endings but detects sql change.
    # Os asserts abaixo especificam o resultado e os efeitos que precisam permanecer estáveis.
    def test_checksum_ignores_platform_line_endings_but_detects_sql_change(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '024_teste.sql'
            path.write_bytes(b'SELECT 1;\n')
            digest = runner.checksum(path)
            path.write_bytes(b'SELECT 1;\r\n')
            self.assertEqual(digest, runner.checksum(path))
            path.write_bytes(b'SELECT 2;\n')
            self.assertNotEqual(digest, runner.checksum(path))


if __name__ == '__main__':
    unittest.main()
