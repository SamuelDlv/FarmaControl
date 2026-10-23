"""Valida schema, migração reaplicável e fluxos reais num banco temporário isolado."""
import sys
import uuid
import re
from unittest.mock import patch
from migrate_catalogo import ROOT, connection, execute_sql, migrate

sys.path.insert(0, str(ROOT / 'backend'))
import app as api


from farmacontrol.core import database
from farmacontrol.routes import compras
from farmacontrol.routes import estoque
from farmacontrol.routes import vendas
from flask import g


def main():
    name = 'farmacontrol_catalogo_test_' + uuid.uuid4().hex
    assert re.fullmatch(r'farmacontrol_catalogo_test_[0-9a-f]{32}', name)
    db = connection()
    created = False
    try:
        with db.cursor() as cur:
            cur.execute(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
            created = True
        db.select_db(name)
        schema = (ROOT / 'backend/schema.sql').read_text(encoding='utf-8')
        schema = schema.replace('CREATE DATABASE IF NOT EXISTS farmacontrol', f'CREATE DATABASE IF NOT EXISTS `{name}`')
        schema = schema.replace('USE farmacontrol;', f'USE `{name}`;')
        execute_sql(db, schema)
        with db.cursor() as cur:
            cur.execute("SELECT nome FROM categorias_produto")
            names = {row['nome'] for row in cur.fetchall()}
            assert {'Alimentos', 'Acessórios', 'Primeiros socorros'} <= names
            assert not {'Bebidas', 'Acessórios e primeiros socorros'} & names
            # Simula produtos vinculados às duas categorias antigas.
            for category in ('Bebidas', 'Acessórios e primeiros socorros'):
                cur.execute('INSERT INTO categorias_produto (nome) VALUES (%s)', (category,))
                cur.execute('INSERT INTO produtos (nome, categoria_id, preco_custo, preco_venda) VALUES (%s, %s, 2, 4)',
                            ('Legado ' + category, cur.lastrowid))
        db.commit()
        migrate(db)
        migrate(db)
        with db.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM categorias_produto WHERE nome IN ('Bebidas', 'Acessórios e primeiros socorros')")
            assert cur.fetchone()['n'] == 0
            cur.execute("SELECT p.nome, c.nome AS categoria FROM produtos p JOIN categorias_produto c ON c.id = p.categoria_id WHERE p.nome LIKE 'Legado %'")
            assert {row['nome']: row['categoria'] for row in cur.fetchall()} == {
                'Legado Bebidas': 'Alimentos', 'Legado Acessórios e primeiros socorros': 'Acessórios'}
            # Caminho em que só existe a categoria combinada: mantém seu ID.
            cur.execute("UPDATE categorias_produto SET nome = 'Acessórios e primeiros socorros' WHERE nome = 'Acessórios'")
            cur.execute("SELECT id FROM categorias_produto WHERE nome = 'Acessórios e primeiros socorros'")
            old_id = cur.fetchone()['id']
        db.commit()
        execute_sql(db, (ROOT / 'backend/migrations/019_reorganiza_categorias_produto.sql').read_text(encoding='utf-8'))
        with db.cursor() as cur:
            cur.execute("SELECT id FROM categorias_produto WHERE nome = 'Acessórios'")
            assert cur.fetchone()['id'] == old_id
            # Simula schema anterior: valida também o caminho que cria as colunas.
            cur.execute('ALTER TABLE produtos DROP COLUMN tipo_produto, DROP COLUMN exige_validade')
            cur.execute("INSERT INTO produtos (nome, preco_custo, preco_venda) VALUES ('Legado', 2, 4)")
        migrate(db)
        with db.cursor() as cur:
            cur.execute("SELECT tipo_produto, exige_validade FROM produtos WHERE nome = 'Legado'")
            assert cur.fetchone() == {'tipo_produto': 'medicamento', 'exige_validade': 1}
            cur.execute("SHOW COLUMNS FROM usuarios")
            columns = {row['Field'] for row in cur.fetchall()}
            assert 'senha_hash' in columns
            cur.execute("INSERT INTO usuarios (nome, sobrenome, email, senha_hash, perfil_id, status) VALUES ('Teste', 'Catálogo', 'catalogo@example.invalid', 'hash-inutilizavel', 1, 'aprovado')")
            user_id = cur.lastrowid
            cur.execute("INSERT INTO fornecedores (nome_fantasia, razao_social, cnpj) VALUES ('Teste', 'Fornecedor teste', '00000000000000')")
            supplier_id = cur.lastrowid
        db.commit()

        def call(view, payload, *args):
            with api.app.test_request_context(json=payload), patch.object(database, 'get_db', return_value=db):
                g.usuario_id = user_id
                result = view(*args)
                response, status = result if isinstance(result, tuple) else (result, 200)
                body = response.get_json()
                assert status < 300, (status, body)
                return body

        brush = call(estoque.create_item_estoque, {'produto_nome': 'Escova teste', 'produto_tipo': 'outro',
            'produto_exige_validade': False, 'produto_preco_custo': 2, 'produto_preco_venda': 4,
            'produto_codigo_barras': '0012345', 'quantidade': 3, 'estoque_minimo': 0})
        water = call(estoque.create_item_estoque, {'produto_nome': 'Água teste', 'produto_tipo': 'outro',
            'produto_preco_custo': 1, 'produto_preco_venda': 2, 'quantidade': 4,
            'data_validade': '2027-04-01', 'lote': 'AGUA-1'})
        medicine = call(estoque.create_item_estoque, {'produto_nome': 'Medicamento teste',
            'produto_principio': 'Princípio teste', 'produto_requer_receita': True,
            'quantidade': 2, 'data_validade': '2027-05-01', 'lote': 'MED-1'})
        call(compras.create_compra, {'fornecedor_id': supplier_id, 'valor_total': 4, 'status': 'recebido',
            'itens': [{'produto_id': brush['produto_id'], 'quantidade': 2, 'preco_unitario': 2}]})
        call(vendas.create_venda, {'valor_total': 4, 'tipo_pagamento': 'pix', 'status': 'concluida',
            'itens': [{'produto_id': brush['produto_id'], 'quantidade': 1, 'preco_unitario': 4}]})
        pending = call(compras.create_compra, {'fornecedor_id': supplier_id, 'valor_total': 2, 'status': 'pendente',
            'itens': [{'produto_id': water['produto_id'], 'quantidade': 2, 'preco_unitario': 1}]})
        with db.cursor() as cur:
            cur.execute('SELECT id FROM itens_compra WHERE compra_id = %s', (pending['id'],))
            item_id = cur.fetchone()['id']
        call(compras.update_compra, {'status': 'recebido', 'itens_recebimento': [
            {'id': item_id, 'lote_recebido': 'AGUA-2', 'data_validade_recebida': '2027-06-01'}]}, pending['id'])
        call(estoque.update_item_estoque, {'estoque_minimo': 0, 'data_validade': None}, brush['id'])
        with db.cursor() as cur:
            cur.execute('SELECT quantidade, data_validade, lote FROM estoque WHERE id = %s', (brush['id'],))
            assert cur.fetchone() == {'quantidade': 4, 'data_validade': None, 'lote': 'SEM-LOTE'}
            cur.execute('SELECT nome_generico, requer_receita FROM produtos WHERE id = %s', (medicine['produto_id'],))
            assert cur.fetchone() == {'nome_generico': 'Princípio teste', 'requer_receita': 1}
        assert len(call(estoque.get_estoque, {})['estoque']) == 4
        print('OK: schema novo, migração sobre legado, reaplicação, cadastro misto, edição, compras, vendas e estoque.')
    finally:
        if created:
            # Nome aleatório criado exclusivamente por este processo, nunca o banco configurado.
            assert re.fullmatch(r'farmacontrol_catalogo_test_[0-9a-f]{32}', name)
            with db.cursor() as cur:
                cur.execute(f'DROP DATABASE `{name}`')
            print('Banco temporário de testes removido; banco da aplicação não alterado.')
        db.close()


if __name__ == '__main__':
    main()
