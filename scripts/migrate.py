# Guia de manutenção — Controla baseline, checksums e aplicação ordenada de migrações novas.
# Consulte docs/desenvolvimento.md para executar as verificações desta camada.
"""Histórico de migrações MySQL: status (somente leitura), baseline e apply."""
import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re

from migrate_catalogo import ROOT, connection, execute_sql

DIRECTORY = ROOT / 'backend/migrations/managed'
BASELINE = ROOT / 'backend/migrations/baseline_023.json'
BASE_VERSION = 23
TABLE = 'schema_migrations'


# A leitura normaliza finais de linha para manter identidade entre Windows e Linux.
# Mesmo comentários alteram o checksum: migrações registradas devem permanecer imutáveis.
def checksum(path):
    # CRLF e LF representam o mesmo SQL no Windows e no CI Linux.
    return hashlib.sha256(path.read_text(encoding='utf-8-sig').encode('utf-8')).hexdigest()


def discover(directory=DIRECTORY):
    migrations = []
    versions = set()
    for path in sorted(Path(directory).glob('*.sql')):
        match = re.fullmatch(r'([0-9]{3,})_([a-z][a-z0-9_]*)\.sql', path.name)
        if not match or int(match[1]) <= BASE_VERSION:
            raise ValueError(f'Nome inválido de migração: {path.name}; use 024_descricao.sql ou posterior.')
        version = int(match[1])
        if version in versions:
            raise ValueError(f'Versão duplicada: {version}.')
        versions.add(version)
        migrations.append({'version': version, 'filename': path.name,
                           'checksum': checksum(path), 'path': path})
    return sorted(migrations, key=lambda item: item['version'])


# Executa as consultas e validações de baseline contract.
def baseline_contract(db, path=BASELINE):
    contract = json.loads(path.read_text(encoding='utf-8'))
    with db.cursor() as cur:
        cur.execute('SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE()')
        actual = {(row['TABLE_NAME'], row['COLUMN_NAME']) for row in cur.fetchall()}
    missing = [f'{table}.{column}' for table, columns in contract['tables'].items()
               for column in columns if (table, column) not in actual]
    if missing:
        raise ValueError('Base anterior à 023 ou incompleta. Faltam: ' + ', '.join(missing))


# Executa as consultas e validações de history.
def history(db):
    with db.cursor() as cur:
        cur.execute('SELECT COUNT(*) AS n FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s', (TABLE,))
        if not cur.fetchone()['n']:
            return []
        cur.execute('SELECT version, filename, checksum, state FROM schema_migrations ORDER BY version')
        return cur.fetchall()


# Confere arquivos contra o histórico, incluindo checksum e estados interrompidos.
# A consulta não deve aplicar DDL nem tentar reparar automaticamente divergências.
def status(db, directory=DIRECTORY, baseline_path=BASELINE):
    migrations = discover(directory)
    recorded = history(db)
    expected = {BASE_VERSION: {'filename': baseline_path.name, 'checksum': checksum(baseline_path)},
                **{m['version']: m for m in migrations}}
    for row in recorded:
        source = expected.get(row['version'])
        if source is None:
            raise ValueError(f"Migração registrada sem arquivo: {row['version']}.")
        if (row['filename'], row['checksum']) != (source['filename'], source['checksum']):
            raise ValueError(f"Arquivo alterado após registro: {row['filename']}.")
        if row['state'] != 'applied':
            raise ValueError(f"Migração {row['filename']} em estado {row['state']}; revise o banco antes de continuar.")
    applied = {row['version'] for row in recorded}
    if applied and BASE_VERSION not in applied:
        raise ValueError('Histórico inconsistente: baseline ausente.')
    pending = [m for m in migrations if m['version'] not in applied]
    if any(m['version'] < max(applied, default=BASE_VERSION) for m in pending):
        raise ValueError('Migração pendente inserida antes de uma versão já aplicada.')
    return {'baseline': BASE_VERSION in applied, 'applied': recorded,
            'pending': [{k: v for k, v in m.items() if k != 'path'} for m in pending]}


# Executa as consultas e validações de migration lock.
@contextmanager
def migration_lock(db):
    # Conexão exclusiva do runner: abandona snapshots de status anteriores.
    db.rollback()
    with db.cursor() as cur:
        cur.execute('SELECT DATABASE() AS name')
        database = cur.fetchone()['name']
        lock_name = 'fc_migrate_' + hashlib.sha256(database.encode()).hexdigest()[:48]
        cur.execute('SELECT GET_LOCK(%s, 0) AS acquired', (lock_name,))
        if cur.fetchone()['acquired'] != 1:
            raise ValueError('Outra migração está em execução neste banco.')
    try:
        yield
    finally:
        db.rollback()
        with db.cursor() as cur:
            cur.execute('SELECT RELEASE_LOCK(%s)', (lock_name,))


# Registra a adoção do histórico após revisão explícita do legado e conferência estrutural.
# A presença de colunas não comprova tipos, índices nem transformações de dados antigas.
def baseline(db, *, legacy_reviewed=False, directory=DIRECTORY, baseline_path=BASELINE):
    if not legacy_reviewed:
        raise ValueError('Revise as migrações legadas e use --legacy-reviewed para registrar a base 023.')
    with migration_lock(db):
        current = status(db, directory, baseline_path)
        if current['baseline']:
            return current
        baseline_contract(db, baseline_path)
        execute_sql(db, '''CREATE TABLE IF NOT EXISTS schema_migrations (
            version INT UNSIGNED NOT NULL PRIMARY KEY,
            filename VARCHAR(255) NOT NULL,
            checksum CHAR(64) NOT NULL,
            state ENUM('running','applied','failed') NOT NULL,
            started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            applied_at TIMESTAMP NULL
        ) ENGINE=InnoDB''')
        with db.cursor() as cur:
            cur.execute("INSERT INTO schema_migrations (version,filename,checksum,state,applied_at) VALUES (%s,%s,%s,'applied',CURRENT_TIMESTAMP)",
                        (BASE_VERSION, baseline_path.name, checksum(baseline_path)))
        db.commit()
        return status(db, directory, baseline_path)


# Aplica migrações pendentes sob bloqueio e registra o estado de cada versão.
# DDL no MySQL pode confirmar implicitamente: falhas parciais exigem inspeção, não repetição cega.
def apply(db, directory=DIRECTORY, baseline_path=BASELINE):
    with migration_lock(db):
        current = status(db, directory, baseline_path)
        if not current['baseline']:
            raise ValueError('Registre primeiro a baseline 023 após revisar a base existente.')
        for migration in current['pending']:
            path = Path(directory) / migration['filename']
            # Lê uma única vez; o checksum registrado corresponde ao SQL executado.
            sql = path.read_text(encoding='utf-8-sig')
            if hashlib.sha256(sql.encode('utf-8')).hexdigest() != migration['checksum']:
                raise ValueError('Migração mudou durante o planejamento: ' + path.name)
            with db.cursor() as cur:
                cur.execute("INSERT INTO schema_migrations (version,filename,checksum,state) VALUES (%s,%s,%s,'running')",
                            (migration['version'], migration['filename'], migration['checksum']))
            db.commit()
            try:
                execute_sql(db, sql)
                with db.cursor() as cur:
                    cur.execute("UPDATE schema_migrations SET state='applied', applied_at=CURRENT_TIMESTAMP WHERE version=%s", (migration['version'],))
                db.commit()
            except Exception:
                db.rollback()
                with db.cursor() as cur:
                    cur.execute("UPDATE schema_migrations SET state='failed' WHERE version=%s", (migration['version'],))
                db.commit()
                raise
        return status(db, directory, baseline_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('status', 'baseline', 'apply'), nargs='?', default='status')
    parser.add_argument('--legacy-reviewed', action='store_true', help='Confirma a revisão manual das migrações e dados anteriores à 024.')
    args = parser.parse_args()
    try:
        with connection() as db:
            result = (baseline(db, legacy_reviewed=args.legacy_reviewed) if args.command == 'baseline'
                      else apply(db) if args.command == 'apply' else status(db))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            if not result['baseline']:
                print('Baseline não registrada; status não modifica o banco.')
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Erro: {exc}\n')


if __name__ == '__main__':
    main()
