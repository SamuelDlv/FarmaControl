"""Inspeciona ou aplica a migração de finalidade no banco local configurado."""
import argparse
from migrate_catalogo import connection


def migrate(db):
    with db.cursor() as cur:
        cur.execute("SHOW COLUMNS FROM movimentacoes_estoque")
        columns = {row['Field'] for row in cur.fetchall()}
        additions = []
        if 'finalidade' not in columns:
            additions.append("ADD COLUMN finalidade ENUM('descarte', 'venda', 'devolucao_fornecedor') NULL")
        if 'motivo' not in columns:
            additions.append('ADD COLUMN motivo VARCHAR(255) NULL')
        if additions:
            cur.execute('ALTER TABLE movimentacoes_estoque ' + ', '.join(additions))
    db.commit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Acrescentar as colunas ausentes; preserva histórico e saldos.')
    args = parser.parse_args()
    with connection() as db:
        if args.apply:
            migrate(db)
        with db.cursor() as cur:
            cur.execute("SHOW COLUMNS FROM movimentacoes_estoque WHERE Field IN ('finalidade', 'motivo')")
            print(cur.fetchall())
        print('Migração 022 aplicada; dados preservados.' if args.apply else 'Inspeção concluída, sem alterações.')
