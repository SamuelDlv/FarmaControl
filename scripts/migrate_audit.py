"""Amplia os detalhes do histórico no banco local, preservando os eventos existentes."""
import argparse
from migrate_catalogo import ROOT, connection, execute_sql


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Aplicar a migração 020 no banco local.')
    args = parser.parse_args()
    with connection() as db:
        with db.cursor() as cur:
            cur.execute("SHOW COLUMNS FROM log_atividades LIKE 'detalhes'")
            print(cur.fetchone())
        if args.apply:
            execute_sql(db, (ROOT / 'backend/migrations/020_detalhes_auditoria.sql').read_text(encoding='utf-8'))
            db.commit()
            with db.cursor() as cur:
                cur.execute("SHOW COLUMNS FROM log_atividades LIKE 'detalhes'")
                assert cur.fetchone()['Type'] == 'mediumtext'
            print('Migração 020 aplicada; histórico preservado.')
