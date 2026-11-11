# Guia de manutenção — Verificador de schema mysql.
# Este é um utilitário de validação; confira main e os argumentos antes de executá-lo.
# Os cenários usam servidor MySQL e bases de teste; valide o destino e os privilégios antes da execução.
# Consulte docs/desenvolvimento.md para executar as verificações desta camada.
"""Importa o schema completo duas vezes com conta restrita em base descartável."""

from pathlib import Path
import secrets
import uuid

from migrate_catalogo import connection, execute_sql


# Executa as consultas e validações de main.
def main():
    name = 'fc_schema_test_' + uuid.uuid4().hex
    user = 'fc_test_' + uuid.uuid4().hex[:20]
    password = secrets.token_hex(24)
    created_db = created_user = False
    with connection() as admin:
        try:
            with admin.cursor() as cur:
                # Em containers, o servidor enxerga o IP da bridge, não localhost.
                # Limita a conta descartável à mesma origem da conexão administrativa.
                cur.execute('SELECT USER() AS identity')
                client_host = cur.fetchone()['identity'].rsplit('@', 1)[1]
                cur.execute(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
                created_db = True
                cur.execute('CREATE USER %s@%s IDENTIFIED BY %s', (user, client_host, password))
                created_user = True
                cur.execute(f'GRANT ALL PRIVILEGES ON `{name}`.* TO %s@%s', (user, client_host))
            # Não utiliza a senha operacional para a conexão de importação.
            import pymysql
            with pymysql.connect(host=admin.host, port=admin.port, user=user,
                                 password=password, database=name, charset='utf8mb4',
                                 client_flag=pymysql.constants.CLIENT.MULTI_STATEMENTS) as db:
                schema = (Path(__file__).resolve().parents[1] / 'backend/schema.sql').read_text(encoding='utf-8')
                schema = schema.replace('CREATE DATABASE IF NOT EXISTS farmacontrol',
                                        f'CREATE DATABASE IF NOT EXISTS `{name}`')
                schema = schema.replace('USE farmacontrol;', f'USE `{name}`;')
                execute_sql(db, schema)
                db.commit()
                execute_sql(db, schema)
                db.commit()
                with db.cursor() as cur:
                    cur.execute('SELECT COUNT(*) FROM perfis')
                    assert cur.fetchone()[0] == 7
                    cur.execute('SELECT COUNT(*) FROM perfil_permissoes')
                    assert cur.fetchone()[0] > 0
                    cur.execute('SELECT VERSION()')
                    version = cur.fetchone()[0]
                print(f'Schema completo importado e reimportado sem privilégios globais: {version}')
        finally:
            with admin.cursor() as cur:
                if created_user:
                    cur.execute('DROP USER %s@%s', (user, client_host))
                if created_db:
                    cur.execute(f'DROP DATABASE `{name}`')


if __name__ == '__main__':
    main()
