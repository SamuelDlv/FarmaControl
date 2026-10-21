"""Emite a documentação EER em UTF-8 a partir do schema, sem acessar o banco.

Uso: python scripts/database_docs.py (Markdown na saída padrão).
Parser restrito ao formato CREATE TABLE utilizado em backend/schema.sql.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GROUPS = [
    ('acesso', 'Acesso e permissões', ['perfis', 'perfil_permissoes', 'usuarios']),
    ('cadastro', 'Cadastro e consentimento', ['convites_cadastro', 'analises_cadastro', 'aceites_legais']),
    ('estoque', 'Catálogo e estoque', ['categorias_produto', 'fornecedores', 'produtos', 'estoque', 'movimentacoes_estoque']),
    ('compras', 'Compras', ['compras', 'itens_compra']),
    ('vendas', 'Vendas e prescrições', ['clientes', 'vendas', 'itens_venda', 'receitas', 'receitas_itens']),
    ('financeiro', 'Financeiro', ['financeiro_categorias', 'financeiro_transacoes']),
    ('operacao', 'Operação e auditoria', ['alertas', 'log_acessos', 'log_atividades', 'configuracoes_sistema']),
]


def split_sql(body):
    """Separa definições sem dividir DECIMAL, ENUM ou chaves compostas."""
    start, depth, quoted = 0, 0, False
    for i, char in enumerate(body):
        if char == "'" and (not i or body[i - 1] != '\\'):
            quoted = not quoted
        if not quoted:
            depth += (char == '(') - (char == ')')
            if char == ',' and depth == 0:
                yield body[start:i].strip()
                start = i + 1
    yield body[start:].strip()


def read_schema():
    sql = (ROOT / 'backend/schema.sql').read_text(encoding='utf-8')
    tables = {}
    for m in re.finditer(r'CREATE TABLE IF NOT EXISTS (\w+)\s*\((.*?)\)\s*(?:ENGINE[^;]*|);', sql, re.S):
        cols, fks, indexes, primary = {}, [], [], []
        for definition in split_sql(m[2]):
            definition = ' '.join(definition.split())
            fk = re.search(r'FOREIGN KEY\s*\((\w+)\)\s*REFERENCES\s+(\w+)\s*\((\w+)\).*?ON DELETE (CASCADE|RESTRICT|SET NULL)', definition)
            if fk:
                fks.append(tuple(fk.groups()))
            elif definition.startswith('PRIMARY KEY'):
                primary.extend(re.search(r'\((.*?)\)', definition)[1].replace(' ', '').split(','))
            elif definition.startswith(('INDEX ', 'UNIQUE KEY ', 'KEY ')):
                indexes.append(definition)
            else:
                col = re.match(r'(\w+)\s+([A-Z]+(?:\([^)]*\))?(?: UNSIGNED)?)(.*)', definition)
                if not col:
                    raise ValueError(f'Definição não reconhecida: {definition}')
                name, kind, attrs = col.groups()
                cols[name] = dict(type=kind, attrs=attrs.strip())
                if 'PRIMARY KEY' in attrs:
                    primary.append(name)
        for col, info in cols.items():
            info['pk'] = col in primary
            info['fk'] = next((f for f in fks if f[0] == col), None)
            info['nullable'] = not info['pk'] and 'NOT NULL' not in info['attrs']
        tables[m[1]] = dict(cols=cols, fks=fks, indexes=indexes)
    expected = [t for _, _, group in GROUPS for t in group]
    assert len(expected) == len(set(expected)) == 24
    assert set(expected) == set(tables), (set(expected) - set(tables), set(tables) - set(expected))
    for table in tables.values():
        for col, parent, target, _ in table['fks']:
            assert col in table['cols'] and target in tables[parent]['cols']
    return tables


def diagram(tables, members):
    parents = sorted({f[1] for t in members for f in tables[t]['fks']} - set(members))
    lines = ['```mermaid', 'erDiagram']
    for t in members + parents:
        lines.append(f'    {t} {{')
        for name, col in tables[t]['cols'].items():
            if t in parents and not col['pk']:
                continue
            # Atributos operacionais ficam no dicionário para evitar caixas enormes.
            if not (col['pk'] or col['fk']):
                continue
            kind = col['type'].split('(')[0].split()[0]
            keys = ', '.join(k for k, present in [('PK', col['pk']), ('FK', bool(col['fk']))] if present)
            note = 'opcional' if col['nullable'] else 'obrigatorio'
            lines.append(f'        {kind} {name} {keys} "{note}"')
        lines.append('    }')
    for child in members:
        for col, parent, _, _ in tables[child]['fks']:
            cardinal = '|o' if tables[child]['cols'][col]['nullable'] else '||'
            identifying = '--' if tables[child]['cols'][col]['pk'] else '..'
            lines.append(f'    {parent} {cardinal}{identifying}o{{ {child} : "{col}"')
    lines.append('```')
    return '\n'.join(lines)


def markdown(tables):
    fk_count = sum(len(t['fks']) for t in tables.values())
    out = ['# Atlas EER do FarmaControl', '',
           f'**24 tabelas · {fk_count} chaves estrangeiras · 7 áreas**', '',
           'Referência visual conferida com o EER fornecido e gerada a partir do [schema SQL](../backend/schema.sql). '
           'Descreve a instalação nova; não representa uma inspeção do banco em execução. '
           'Consulte o [guia do banco](database_schema_design.md) para instalação e migrações.', '',
           '## Como ler', '',
           '- **PK**: chave primária; **FK**: chave estrangeira declarada no SQL.',
           '- `||`: exatamente um; `o|` / `|o`: zero ou um; `o{`: zero ou muitos.',
           '- Linha contínua: FK faz parte da PK do filho. Linha tracejada: relação não identificadora.',
           '- Os diagramas mostram chaves. Tipos completos, demais colunas e índices aparecem no dicionário de cada área.',
           '- Tabelas de apoio reaparecem apenas com sua PK. Os nomes nas linhas são as colunas FK do filho.', '',
           'O GitHub renderiza os blocos Mermaid. Localmente, use a pré-visualização Markdown com suporte a Mermaid; '
           'as tabelas do dicionário também podem ser lidas sem esse suporte.', '',
           '## Navegação', '', '| Área | Tabelas |', '| --- | --- |']
    for slug, title, members in GROUPS:
        links = ', '.join(f'[`{t}`](#tabela-{t})' for t in members)
        out.append(f'| [{title}](#{slug}) | {links} |')
    out += ['', '## Referências que não são FKs', '',
            '| Campo | Leitura correta |', '| --- | --- |',
            '| `log_atividades.usuario_id` | Sem FK; a identidade é preservada por snapshot em `usuario_nome` e `perfil`. |',
            '| `alertas.referencia_id` | Referência interpretada pela aplicação; não existe uma FK de destino fixo. |',
            '| `itens_venda.lote_vendido` / `itens_compra.lote_recebido` | Textos de lote; não possuem FK direta para `estoque`. |',
            '| `configuracoes_sistema` | Tabela independente, identificada pela chave textual `chave`. |', '',
            'Não há especialização/herança declarada entre tabelas. `tipo_produto` é um discriminador na própria tabela `produtos`.', '']
    for slug, title, members in GROUPS:
        out += [f'<a id="{slug}"></a>', '', f'## {title}', '', diagram(tables, members), '',
                '**Dicionário da área** — expanda uma tabela para consultar suas colunas.', '']
        for t in members:
            out += [f'<a id="tabela-{t}"></a>', '', '<details>', f'<summary><strong>{t}</strong> · {len(tables[t]["cols"])} colunas</summary>', '',
                    '| Coluna | Tipo SQL | Chave | Aceita NULL | Definição adicional |', '| --- | --- | --- | --- | --- |']
            for name, col in tables[t]['cols'].items():
                tags = []
                if col['pk']:
                    tags.append('PK')
                if col['fk']:
                    tags.append(f'FK → `{col["fk"][1]}.{col["fk"][2]}`')
                if 'UNIQUE' in col['attrs']:
                    tags.append('UNIQUE')
                attrs = re.sub(r'\b(?:NOT NULL|NULL|PRIMARY KEY|UNIQUE)\b', '', col['attrs']).strip()
                attrs = ' '.join(attrs.split())
                out.append(f'| `{name}` | `{col["type"]}` | {"; ".join(tags) or "—"} | {"Sim" if col["nullable"] else "Não"} | {f"`{attrs}`" if attrs else "—"} |')
            if tables[t]['indexes']:
                out += ['', '**Índices adicionais / unicidade composta**', '']
                out.extend(f'- `{idx}`' for idx in tables[t]['indexes'])
            if tables[t]['fks']:
                out += ['', '| FK | Destino | ON DELETE | ON UPDATE |', '| --- | --- | --- | --- |']
                out.extend(f'| `{col}` | [`{parent}.{target}`](#tabela-{parent}) | `{delete}` | `CASCADE` |' for col, parent, target, delete in tables[t]['fks'])
            out += ['', '</details>', '']
    out += ['## Atualização desta referência', '',
            'O gerador [`scripts/database_docs.py`](../scripts/database_docs.py) lê apenas o schema e emite este Markdown. '
            'Depois de mudar o SQL, gere novamente, confira os diagramas e atualize a documentação. '
            'As relações mostradas são somente as FKs declaradas; regras transacionais da aplicação não criam novas FKs.', '']
    return '\n'.join(out)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    print(markdown(read_schema()), end='')
