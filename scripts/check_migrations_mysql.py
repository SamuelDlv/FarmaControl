# Guia de manutenção — Verificador de migrations mysql.
# Este é um utilitário de validação; confira main e os argumentos antes de executá-lo.
# Os cenários usam servidor MySQL e bases de teste; valide o destino e os privilégios antes da execução.
# Consulte docs/desenvolvimento.md para executar as verificações desta camada.
"""Valida o controle de versões em banco MySQL temporário, incluindo falhas de DDL."""
import json
import re
from tempfile import TemporaryDirectory
from pathlib import Path
import uuid

import pymysql
from migrate_catalogo import ROOT, connection, execute_sql
import migrate


def rejected(call, text):
    try:
        call()
    except ValueError as exc:
        assert text in str(exc), str(exc)
    else:
        raise AssertionError('Operação deveria ser rejeitada: ' + text)


# Executa as consultas e validações de main.
def main():
    name = 'farmacontrol_migrations_test_' + uuid.uuid4().hex
    db = connection()
    created = False
    checks = []
    try:
        with db.cursor() as cur:
            cur.execute(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
            created = True
        db.select_db(name)
        with TemporaryDirectory(prefix='fc_migrations_') as folder:
            directory = Path(folder)
            assert migrate.status(db, directory)['baseline'] is False
            assert migrate.history(db) == []
            rejected(lambda: migrate.apply(db, directory), 'baseline')
            rejected(lambda: migrate.baseline(db, directory=directory), '--legacy-reviewed')
            rejected(lambda: migrate.baseline(db, directory=directory, legacy_reviewed=True), 'Faltam')
            assert migrate.history(db) == []
            checks.append('status sem escrita; baseline bloqueia falta de revisão e schema incompleto')

            schema = (ROOT / 'backend/schema.sql').read_text(encoding='utf-8')
            execute_sql(db, schema[schema.index('CREATE TABLE IF NOT EXISTS perfis'):])
            assert migrate.baseline(db, directory=directory, legacy_reviewed=True)['baseline']
            assert len(migrate.baseline(db, directory=directory, legacy_reviewed=True)['applied']) == 1
            checks.append('baseline idempotente em schema atual')

            first = directory / '024_tabela_teste.sql'
            first.write_text('CREATE TABLE migration_probe (id INT PRIMARY KEY);\nINSERT INTO migration_probe VALUES (1);\n', encoding='utf-8')
            assert len(migrate.status(db, directory)['pending']) == 1
            migrate.apply(db, directory)
            migrate.apply(db, directory)
            with db.cursor() as cur:
                cur.execute('SELECT COUNT(*) AS n FROM migration_probe')
                assert cur.fetchone()['n'] == 1
            checks.append('apply executa uma única vez e registra checksum')

            original = first.read_text(encoding='utf-8')
            first.write_text(original.replace('\n', '\r\n'), encoding='utf-8', newline='')
            assert not migrate.status(db, directory)['pending']
            first.write_text(original + '-- alterado\n', encoding='utf-8')
            rejected(lambda: migrate.apply(db, directory), 'alterado')
            first.write_text(original, encoding='utf-8')
            first.unlink()
            rejected(lambda: migrate.status(db, directory), 'sem arquivo')
            first.write_text(original, encoding='utf-8')
            duplicate = directory / '024_duplicada.sql'
            duplicate.write_text('SELECT 1;', encoding='utf-8')
            rejected(lambda: migrate.status(db, directory), 'duplicada')
            duplicate.unlink()
            checks.append('checksum estável em CRLF/LF; alteração, remoção e versão duplicada bloqueadas')

            with migrate.migration_lock(db):
                with connection(database=name) as second:
                    rejected(lambda: migrate.apply(second, directory), 'Outra migração')
            checks.append('lock impede execução simultânea por outra conexão')

            failing = directory / '025_falha_parcial.sql'
            failing.write_text('CREATE TABLE partial_probe (id INT);\nINSERT INTO tabela_que_nao_existe VALUES (1);', encoding='utf-8')
            try:
                migrate.apply(db, directory)
            except pymysql.MySQLError:
                pass
            else:
                raise AssertionError('SQL inválido deveria falhar')
            assert migrate.history(db)[-1]['state'] == 'failed'
            rejected(lambda: migrate.apply(db, directory), 'failed')
            with db.cursor() as cur:
                cur.execute("SHOW TABLES LIKE 'partial_probe'")
                assert cur.fetchone(), 'DDL MySQL tem commit implícito; falha parcial deve permanecer diagnosticável'
            checks.append('falha parcial de DDL registrada e reaplicação automática bloqueada')
        print(json.dumps({'passed': True, 'checks': checks}, ensure_ascii=True, indent=2))
    finally:
        if created:
            assert re.fullmatch(r'farmacontrol_migrations_test_[0-9a-f]{32}', name)
            with db.cursor() as cur:
                cur.execute(f'DROP DATABASE `{name}`')
        db.close()


if __name__ == '__main__':
    main()
