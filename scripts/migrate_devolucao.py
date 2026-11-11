# Guia de manutenção — Utilitário de manutenção de devolucao.
# Revise a conexão, as opções de aplicação e o SQL antes de executar em uma instalação.
# Consulte docs/desenvolvimento.md para executar as verificações desta camada.
"""Inspeciona/aplica a migracao 023 sem modificar saldos."""
import argparse
from migrate_catalogo import connection
from migrate_descarte import migrate as migrate_purpose


# Executa as consultas e validações de migrate.
def migrate(db):
    migrate_purpose(db)
    with db.cursor() as cur:
        cur.execute("SHOW COLUMNS FROM movimentacoes_estoque LIKE 'fornecedor_id'")
        if not cur.fetchone():
            cur.execute("ALTER TABLE movimentacoes_estoque ADD COLUMN fornecedor_id INT UNSIGNED NULL COMMENT 'Fornecedor na data da devolucao'")
    db.commit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    with connection() as db:
        if args.apply:
            migrate(db)
        with db.cursor() as cur:
            cur.execute("SHOW COLUMNS FROM movimentacoes_estoque WHERE Field IN ('finalidade', 'motivo', 'fornecedor_id')")
            print(cur.fetchall())
        print('Migracao 023 aplicada; saldos preservados.' if args.apply else 'Inspecao sem alteracoes.')
