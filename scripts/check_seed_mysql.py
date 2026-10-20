"""Valida a carga 017 em banco descartável, sem popular o banco da aplicação."""
import re
import uuid

from migrate_catalogo import ROOT, connection, execute_sql


def run_seed(db):
    sql = (ROOT / 'backend/migrations/017_popula_farmacia_teste (Opcional).sql').read_text(encoding='utf-8')
    # DELIMITER é comando do cliente mysql, não do servidor.
    before, routine = sql.split('DELIMITER $$', 1)
    execute_sql(db, before)
    for statement in routine.split('DELIMITER ;', 1)[0].split('$$'):
        if statement.strip():
            execute_sql(db, statement)


def main():
    name = 'farmacontrol_seed_test_' + uuid.uuid4().hex
    db = connection()
    created = False
    try:
        with db.cursor() as cur:
            cur.execute(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
            created = True
        db.select_db(name)
        schema = (ROOT / 'backend/schema.sql').read_text(encoding='utf-8')
        # Exclui CREATE DATABASE, USE e roles globais; só objetos no banco temporário.
        execute_sql(db, schema[schema.index('CREATE TABLE IF NOT EXISTS perfis'):])
        # Preservação de dados anteriores e IDs não sequenciais na carga.
        with db.cursor() as cur:
            cur.execute("INSERT INTO produtos (id,nome,preco_custo,preco_venda) VALUES (900,'Produto anterior',1,2)")
            cur.execute("INSERT INTO clientes (id,nome,sobrenome) VALUES (800,'Cliente','Anterior')")
        db.commit()
        run_seed(db)
        tables = ['usuarios','fornecedores','clientes','produtos','estoque','compras','itens_compra',
                  'vendas','itens_venda','financeiro_transacoes','movimentacoes_estoque','receitas','receitas_itens']
        with db.cursor() as cur:
            counts = {}
            for table in tables:
                cur.execute(f'SELECT COUNT(*) AS n FROM {table}')
                counts[table] = cur.fetchone()['n']
            assert counts['usuarios'] == 28 and counts['produtos'] == 201
            assert counts['estoque'] == 600 and counts['vendas'] == 6000 and counts['itens_venda'] == 12000
            checks = [
                "SELECT COUNT(*) n FROM estoque e WHERE quantidade <> (SELECT SUM(CASE tipo_movimentacao WHEN 'entrada' THEN quantidade WHEN 'saida' THEN -quantidade ELSE 0 END) FROM movimentacoes_estoque WHERE estoque_id=e.id)",
                "SELECT COUNT(*) n FROM vendas v WHERE valor_total <> (SELECT SUM(quantidade*preco_unitario) FROM itens_venda WHERE venda_id=v.id)",
                "SELECT COUNT(*) n FROM compras c WHERE valor_total <> (SELECT SUM(quantidade*preco_unitario) FROM itens_compra WHERE compra_id=c.id)",
                "SELECT COUNT(*) n FROM financeiro_transacoes f JOIN vendas v ON v.id=f.venda_id WHERE f.valor<>v.valor_total OR f.status<>CASE v.status WHEN 'concluida' THEN 'pago' WHEN 'cancelada' THEN 'cancelado' ELSE 'pendente' END",
                "SELECT COUNT(*) n FROM financeiro_transacoes f JOIN compras c ON c.id=f.compra_id WHERE f.valor<>c.valor_total OR f.status<>CASE c.status WHEN 'recebido' THEN 'pago' ELSE c.status END",
                "SELECT COUNT(*) n FROM movimentacoes_estoque m JOIN estoque e ON e.id=m.estoque_id JOIN produtos p ON p.id=e.produto_id WHERE m.observacao LIKE 'SEED017 Venda%' AND (m.data_movimentacao < e.criado_em OR (p.exige_validade=1 AND m.data_movimentacao>e.data_validade))",
                "SELECT COUNT(*) n FROM estoque e JOIN produtos p ON p.id=e.produto_id WHERE (p.exige_validade=1 AND e.data_validade IS NULL) OR (p.exige_validade=0 AND e.data_validade IS NOT NULL)",
            ]
            for query in checks:
                cur.execute(query)
                assert cur.fetchone()['n'] == 0, query
            cur.execute("SELECT nome FROM produtos WHERE id=900")
            assert cur.fetchone()['nome'] == 'Produto anterior'
        run_seed(db)
        with db.cursor() as cur:
            for table, count in counts.items():
                cur.execute(f'SELECT COUNT(*) AS n FROM {table}')
                assert cur.fetchone()['n'] == count, table
            # Conflito depois de inserir o marcador: tudo deve ser revertido.
            cur.execute("DELETE FROM configuracoes_sistema WHERE chave='seed.farmacia.017'")
        db.commit()
        import pymysql
        try:
            run_seed(db)
        except pymysql.IntegrityError:
            pass
        else:
            raise AssertionError('Conflito de unicidade deveria abortar a carga')
        with db.cursor() as cur:
            cur.execute("SELECT COUNT(*) n FROM configuracoes_sistema WHERE chave='seed.farmacia.017'")
            assert cur.fetchone()['n'] == 0
            for table, count in counts.items():
                cur.execute(f'SELECT COUNT(*) AS n FROM {table}')
                assert cur.fetchone()['n'] == count, table
        print('OK: carga, estoque, totais, financeiro, datas, preservação, reaplicação e rollback.')
        print(counts)
    finally:
        if created:
            assert re.fullmatch(r'farmacontrol_seed_test_[0-9a-f]{32}', name)
            with db.cursor() as cur:
                cur.execute(f'DROP DATABASE `{name}`')
            print('Banco temporário removido; banco da aplicação não alterado.')
        db.close()


if __name__ == '__main__':
    main()
