"""Aplica as migrações 012 e 019 na instância local configurada em backend/.env."""
import argparse
from pathlib import Path
import pymysql
from pymysql.constants import CLIENT
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def connection(database=None):
    config = dotenv_values(ROOT / 'backend/.env')
    host = config.get('DB_HOST', 'localhost')
    if host not in ('localhost', '127.0.0.1', '::1'):
        raise SystemExit('Este utilitário aceita somente o banco local. Execute o SQL diretamente para outra instância.')
    return pymysql.connect(host=host, port=int(config.get('DB_PORT', 3306)),
        user=config.get('DB_USER', 'root'), password=config.get('DB_PASSWORD', ''),
        database=database or config.get('DB_NAME', 'farmacontrol'), charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor, client_flag=CLIENT.MULTI_STATEMENTS,
        connect_timeout=5, autocommit=False)


def execute_sql(db, sql):
    with db.cursor() as cursor:
        cursor.execute(sql)
        while cursor.nextset():
            pass


def migrate(db):
    execute_sql(db, (ROOT / 'backend/migrations/012_catalogo_multicategoria.sql').read_text(encoding='utf-8'))
    execute_sql(db, (ROOT / 'backend/migrations/019_reorganiza_categorias_produto.sql').read_text(encoding='utf-8'))
    db.commit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Aplicar migração; sem esta opção, apenas inspeciona.')
    args = parser.parse_args()
    with connection() as db:
        with db.cursor() as cur:
            cur.execute('SELECT DATABASE() AS banco, COUNT(*) AS produtos FROM produtos')
            before = cur.fetchone()
            print(before)
        if args.apply:
            migrate(db)
        with db.cursor() as cur:
            cur.execute("SHOW COLUMNS FROM produtos WHERE Field IN ('tipo_produto', 'exige_validade')")
            print(cur.fetchall())
            cur.execute('SELECT COUNT(*) AS total FROM produtos')
            assert cur.fetchone()['total'] == before['produtos'], 'A quantidade de produtos foi alterada.'
        print('Migração aplicada; produtos preservados.' if args.apply else 'Inspeção concluída; nenhuma alteração.')
