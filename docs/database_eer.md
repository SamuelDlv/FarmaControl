# Atlas EER do FarmaControl

**24 tabelas · 30 chaves estrangeiras · 7 áreas**

Referência visual conferida com o EER fornecido e gerada a partir do [schema SQL](../backend/schema.sql). Descreve a instalação nova; não representa uma inspeção do banco em execução. Consulte o [guia do banco](database_schema_design.md) para instalação e migrações.

## Como ler

- **PK**: chave primária; **FK**: chave estrangeira declarada no SQL.
- `||`: exatamente um; `o|` / `|o`: zero ou um; `o{`: zero ou muitos.
- Linha contínua: FK faz parte da PK do filho. Linha tracejada: relação não identificadora.
- Os diagramas mostram chaves. Tipos completos, demais colunas e índices aparecem no dicionário de cada área.
- Tabelas de apoio reaparecem apenas com sua PK. Os nomes nas linhas são as colunas FK do filho.

O GitHub renderiza os blocos Mermaid. Localmente, use a pré-visualização Markdown com suporte a Mermaid; as tabelas do dicionário também podem ser lidas sem esse suporte.

## Navegação

| Área | Tabelas |
| --- | --- |
| [Acesso e permissões](#acesso) | [`perfis`](#tabela-perfis), [`perfil_permissoes`](#tabela-perfil_permissoes), [`usuarios`](#tabela-usuarios) |
| [Cadastro e consentimento](#cadastro) | [`convites_cadastro`](#tabela-convites_cadastro), [`analises_cadastro`](#tabela-analises_cadastro), [`aceites_legais`](#tabela-aceites_legais) |
| [Catálogo e estoque](#estoque) | [`categorias_produto`](#tabela-categorias_produto), [`fornecedores`](#tabela-fornecedores), [`produtos`](#tabela-produtos), [`estoque`](#tabela-estoque), [`movimentacoes_estoque`](#tabela-movimentacoes_estoque) |
| [Compras](#compras) | [`compras`](#tabela-compras), [`itens_compra`](#tabela-itens_compra) |
| [Vendas e prescrições](#vendas) | [`clientes`](#tabela-clientes), [`vendas`](#tabela-vendas), [`itens_venda`](#tabela-itens_venda), [`receitas`](#tabela-receitas), [`receitas_itens`](#tabela-receitas_itens) |
| [Financeiro](#financeiro) | [`financeiro_categorias`](#tabela-financeiro_categorias), [`financeiro_transacoes`](#tabela-financeiro_transacoes) |
| [Operação e auditoria](#operacao) | [`alertas`](#tabela-alertas), [`log_acessos`](#tabela-log_acessos), [`log_atividades`](#tabela-log_atividades), [`configuracoes_sistema`](#tabela-configuracoes_sistema) |

## Referências que não são FKs

| Campo | Leitura correta |
| --- | --- |
| `log_atividades.usuario_id` | Sem FK; a identidade é preservada por snapshot em `usuario_nome` e `perfil`. |
| `alertas.referencia_id` | Referência interpretada pela aplicação; não existe uma FK de destino fixo. |
| `itens_venda.lote_vendido` / `itens_compra.lote_recebido` | Textos de lote; não possuem FK direta para `estoque`. |
| `configuracoes_sistema` | Tabela independente, identificada pela chave textual `chave`. |

Não há especialização/herança declarada entre tabelas. `tipo_produto` é um discriminador na própria tabela `produtos`.

<a id="acesso"></a>

## Acesso e permissões

```mermaid
erDiagram
    perfis {
        TINYINT id PK "obrigatorio"
    }
    perfil_permissoes {
        TINYINT perfil_id PK, FK "obrigatorio"
        VARCHAR modulo PK "obrigatorio"
    }
    usuarios {
        INT id PK "obrigatorio"
        TINYINT perfil_id FK "obrigatorio"
    }
    perfis ||--o{ perfil_permissoes : "perfil_id"
    perfis ||..o{ usuarios : "perfil_id"
```

**Dicionário da área** — expanda uma tabela para consultar suas colunas.

<a id="tabela-perfis"></a>

<details>
<summary><strong>perfis</strong> · 5 colunas</summary>

| Coluna | Tipo SQL | Chave | Aceita NULL | Definição adicional |
| --- | --- | --- | --- | --- |
| `id` | `TINYINT UNSIGNED` | PK | Não | `AUTO_INCREMENT` |
| `slug` | `VARCHAR(30)` | UNIQUE | Não | — |
| `nome` | `VARCHAR(80)` | — | Não | — |
| `descricao` | `VARCHAR(255)` | — | Não | — |
| `criado_em` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP` |

</details>

<a id="tabela-perfil_permissoes"></a>

<details>
<summary><strong>perfil_permissoes</strong> · 3 colunas</summary>

| Coluna | Tipo SQL | Chave | Aceita NULL | Definição adicional |
| --- | --- | --- | --- | --- |
| `perfil_id` | `TINYINT UNSIGNED` | PK; FK → `perfis.id` | Não | — |
| `modulo` | `VARCHAR(40)` | PK | Não | — |
| `permitido` | `TINYINT(1)` | — | Não | `DEFAULT 0` |

| FK | Destino | ON DELETE | ON UPDATE |
| --- | --- | --- | --- |
| `perfil_id` | [`perfis.id`](#tabela-perfis) | `CASCADE` | `CASCADE` |

</details>

<a id="tabela-usuarios"></a>

<details>
<summary><strong>usuarios</strong> · 12 colunas</summary>

| Coluna | Tipo SQL | Chave | Aceita NULL | Definição adicional |
| --- | --- | --- | --- | --- |
| `id` | `INT UNSIGNED` | PK | Não | `AUTO_INCREMENT` |
| `nome` | `VARCHAR(80)` | — | Não | — |
| `sobrenome` | `VARCHAR(80)` | — | Não | — |
| `email` | `VARCHAR(180)` | UNIQUE | Não | — |
| `senha_hash` | `VARCHAR(255)` | — | Não | — |
| `perfil_id` | `TINYINT UNSIGNED` | FK → `perfis.id` | Não | — |
| `status` | `ENUM('pendente','aprovado','rejeitado')` | — | Não | `DEFAULT 'pendente'` |
| `ultimo_login` | `DATETIME` | — | Sim | — |
| `token_reset` | `VARCHAR(255)` | — | Sim | — |
| `token_expira_em` | `DATETIME` | — | Sim | — |
| `criado_em` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP` |
| `atualizado_em` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP` |

**Índices adicionais / unicidade composta**

- `INDEX idx_email (email)`
- `INDEX idx_status (status)`

| FK | Destino | ON DELETE | ON UPDATE |
| --- | --- | --- | --- |
| `perfil_id` | [`perfis.id`](#tabela-perfis) | `RESTRICT` | `CASCADE` |

</details>

<a id="cadastro"></a>

## Cadastro e consentimento

```mermaid
erDiagram
    convites_cadastro {
        INT id PK "obrigatorio"
        TINYINT perfil_id FK "obrigatorio"
        INT convidado_por_usuario_id FK "obrigatorio"
        INT aceito_usuario_id FK "opcional"
    }
    analises_cadastro {
        INT id PK "obrigatorio"
        INT usuario_id FK "obrigatorio"
        INT analisado_por FK "opcional"
    }
    aceites_legais {
        INT id PK "obrigatorio"
        INT usuario_id FK "obrigatorio"
    }
    perfis {
        TINYINT id PK "obrigatorio"
    }
    usuarios {
        INT id PK "obrigatorio"
    }
    perfis ||..o{ convites_cadastro : "perfil_id"
    usuarios ||..o{ convites_cadastro : "convidado_por_usuario_id"
    usuarios |o..o{ convites_cadastro : "aceito_usuario_id"
    usuarios ||..o{ analises_cadastro : "usuario_id"
    usuarios |o..o{ analises_cadastro : "analisado_por"
    usuarios ||..o{ aceites_legais : "usuario_id"
```

**Dicionário da área** — expanda uma tabela para consultar suas colunas.

<a id="tabela-convites_cadastro"></a>

<details>
<summary><strong>convites_cadastro</strong> · 12 colunas</summary>

| Coluna | Tipo SQL | Chave | Aceita NULL | Definição adicional |
| --- | --- | --- | --- | --- |
| `id` | `INT UNSIGNED` | PK | Não | `AUTO_INCREMENT` |
| `nome` | `VARCHAR(80)` | — | Não | — |
| `sobrenome` | `VARCHAR(80)` | — | Não | — |
| `email` | `VARCHAR(180)` | — | Não | — |
| `perfil_id` | `TINYINT UNSIGNED` | FK → `perfis.id` | Não | — |
| `convidado_por_usuario_id` | `INT UNSIGNED` | FK → `usuarios.id` | Não | — |
| `token_hash` | `CHAR(64)` | UNIQUE | Não | — |
| `status` | `ENUM('pendente','aceito','recusado','expirado')` | — | Não | `DEFAULT 'pendente'` |
| `expira_em` | `DATETIME` | — | Não | — |
| `respondido_em` | `DATETIME` | — | Sim | — |
| `aceito_usuario_id` | `INT UNSIGNED` | FK → `usuarios.id` | Sim | — |
| `criado_em` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP` |

**Índices adicionais / unicidade composta**

- `INDEX idx_convites_email_status (email, status)`

| FK | Destino | ON DELETE | ON UPDATE |
| --- | --- | --- | --- |
| `perfil_id` | [`perfis.id`](#tabela-perfis) | `RESTRICT` | `CASCADE` |
| `convidado_por_usuario_id` | [`usuarios.id`](#tabela-usuarios) | `RESTRICT` | `CASCADE` |
| `aceito_usuario_id` | [`usuarios.id`](#tabela-usuarios) | `SET NULL` | `CASCADE` |

</details>

<a id="tabela-analises_cadastro"></a>

<details>
<summary><strong>analises_cadastro</strong> · 6 colunas</summary>

| Coluna | Tipo SQL | Chave | Aceita NULL | Definição adicional |
| --- | --- | --- | --- | --- |
| `id` | `INT UNSIGNED` | PK | Não | `AUTO_INCREMENT` |
| `usuario_id` | `INT UNSIGNED` | FK → `usuarios.id` | Não | — |
| `analisado_por` | `INT UNSIGNED` | FK → `usuarios.id` | Sim | — |
| `decisao` | `ENUM('aprovado','rejeitado')` | — | Não | — |
| `motivo` | `VARCHAR(500)` | — | Sim | — |
| `analisado_em` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP` |

| FK | Destino | ON DELETE | ON UPDATE |
| --- | --- | --- | --- |
| `usuario_id` | [`usuarios.id`](#tabela-usuarios) | `CASCADE` | `CASCADE` |
| `analisado_por` | [`usuarios.id`](#tabela-usuarios) | `SET NULL` | `CASCADE` |

</details>

<a id="tabela-aceites_legais"></a>

<details>
<summary><strong>aceites_legais</strong> · 6 colunas</summary>

| Coluna | Tipo SQL | Chave | Aceita NULL | Definição adicional |
| --- | --- | --- | --- | --- |
| `id` | `INT UNSIGNED` | PK | Não | `AUTO_INCREMENT` |
| `usuario_id` | `INT UNSIGNED` | FK → `usuarios.id` | Não | — |
| `termos_versao` | `VARCHAR(32)` | — | Não | — |
| `privacidade_versao` | `VARCHAR(32)` | — | Não | — |
| `aceito_em` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP` |
| `ip` | `VARCHAR(64)` | — | Sim | — |

**Índices adicionais / unicidade composta**

- `INDEX idx_aceites_legais_usuario (usuario_id)`

| FK | Destino | ON DELETE | ON UPDATE |
| --- | --- | --- | --- |
| `usuario_id` | [`usuarios.id`](#tabela-usuarios) | `RESTRICT` | `CASCADE` |

</details>

<a id="estoque"></a>

## Catálogo e estoque

```mermaid
erDiagram
    categorias_produto {
        TINYINT id PK "obrigatorio"
    }
    fornecedores {
        INT id PK "obrigatorio"
    }
    produtos {
        INT id PK "obrigatorio"
        TINYINT categoria_id FK "opcional"
        INT fornecedor_id FK "opcional"
    }
    estoque {
        INT id PK "obrigatorio"
        INT produto_id FK "obrigatorio"
    }
    movimentacoes_estoque {
        BIGINT id PK "obrigatorio"
        INT estoque_id FK "obrigatorio"
        INT usuario_id FK "obrigatorio"
    }
    usuarios {
        INT id PK "obrigatorio"
    }
    categorias_produto |o..o{ produtos : "categoria_id"
    fornecedores |o..o{ produtos : "fornecedor_id"
    produtos ||..o{ estoque : "produto_id"
    estoque ||..o{ movimentacoes_estoque : "estoque_id"
    usuarios ||..o{ movimentacoes_estoque : "usuario_id"
```

**Dicionário da área** — expanda uma tabela para consultar suas colunas.

<a id="tabela-categorias_produto"></a>

<details>
<summary><strong>categorias_produto</strong> · 5 colunas</summary>

| Coluna | Tipo SQL | Chave | Aceita NULL | Definição adicional |
| --- | --- | --- | --- | --- |
| `id` | `TINYINT UNSIGNED` | PK | Não | `AUTO_INCREMENT` |
| `nome` | `VARCHAR(100)` | UNIQUE | Não | — |
| `descricao` | `VARCHAR(255)` | — | Sim | — |
| `criado_em` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP` |
| `atualizado_em` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP` |

</details>

<a id="tabela-fornecedores"></a>

<details>
<summary><strong>fornecedores</strong> · 11 colunas</summary>

| Coluna | Tipo SQL | Chave | Aceita NULL | Definição adicional |
| --- | --- | --- | --- | --- |
| `id` | `INT UNSIGNED` | PK | Não | `AUTO_INCREMENT` |
| `nome_fantasia` | `VARCHAR(150)` | — | Não | — |
| `razao_social` | `VARCHAR(255)` | UNIQUE | Não | — |
| `cnpj` | `VARCHAR(18)` | UNIQUE | Não | — |
| `contato_nome` | `VARCHAR(100)` | — | Sim | — |
| `contato_telefone` | `VARCHAR(20)` | — | Sim | — |
| `contato_email` | `VARCHAR(180)` | — | Sim | — |
| `endereco` | `VARCHAR(255)` | — | Sim | — |
| `ativo` | `BOOLEAN` | — | Não | `DEFAULT TRUE` |
| `criado_em` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP` |
| `atualizado_em` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP` |

</details>

<a id="tabela-produtos"></a>

<details>
<summary><strong>produtos</strong> · 17 colunas</summary>

| Coluna | Tipo SQL | Chave | Aceita NULL | Definição adicional |
| --- | --- | --- | --- | --- |
| `id` | `INT UNSIGNED` | PK | Não | `AUTO_INCREMENT` |
| `nome` | `VARCHAR(255)` | — | Não | — |
| `tipo_produto` | `ENUM('medicamento', 'outro')` | — | Não | `DEFAULT 'medicamento'` |
| `exige_validade` | `BOOLEAN` | — | Não | `DEFAULT TRUE` |
| `nome_generico` | `VARCHAR(255)` | — | Sim | — |
| `descricao` | `TEXT` | — | Sim | — |
| `fabricante` | `VARCHAR(150)` | — | Sim | — |
| `preco_custo` | `DECIMAL(10, 2)` | — | Não | — |
| `preco_venda` | `DECIMAL(10, 2)` | — | Não | — |
| `codigo_barras` | `VARCHAR(50)` | UNIQUE | Sim | — |
| `categoria_id` | `TINYINT UNSIGNED` | FK → `categorias_produto.id` | Sim | — |
| `requer_receita` | `BOOLEAN` | — | Não | `DEFAULT FALSE` |
| `ativo` | `BOOLEAN` | — | Não | `DEFAULT TRUE` |
| `estoque_minimo` | `INT UNSIGNED` | — | Não | `DEFAULT 10` |
| `fornecedor_id` | `INT UNSIGNED` | FK → `fornecedores.id` | Sim | — |
| `criado_em` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP` |
| `atualizado_em` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP` |

| FK | Destino | ON DELETE | ON UPDATE |
| --- | --- | --- | --- |
| `categoria_id` | [`categorias_produto.id`](#tabela-categorias_produto) | `SET NULL` | `CASCADE` |
| `fornecedor_id` | [`fornecedores.id`](#tabela-fornecedores) | `SET NULL` | `CASCADE` |

</details>

<a id="tabela-estoque"></a>

<details>
<summary><strong>estoque</strong> · 8 colunas</summary>

| Coluna | Tipo SQL | Chave | Aceita NULL | Definição adicional |
| --- | --- | --- | --- | --- |
| `id` | `INT UNSIGNED` | PK | Não | `AUTO_INCREMENT` |
| `produto_id` | `INT UNSIGNED` | FK → `produtos.id` | Não | — |
| `lote` | `VARCHAR(50)` | — | Não | — |
| `quantidade` | `INT UNSIGNED` | — | Não | — |
| `data_validade` | `DATE` | — | Sim | — |
| `localizacao` | `VARCHAR(100)` | — | Sim | — |
| `criado_em` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP` |
| `atualizado_em` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP` |

**Índices adicionais / unicidade composta**

- `UNIQUE KEY uk_produto_lote (produto_id, lote)`

| FK | Destino | ON DELETE | ON UPDATE |
| --- | --- | --- | --- |
| `produto_id` | [`produtos.id`](#tabela-produtos) | `RESTRICT` | `CASCADE` |

</details>

<a id="tabela-movimentacoes_estoque"></a>

<details>
<summary><strong>movimentacoes_estoque</strong> · 7 colunas</summary>

| Coluna | Tipo SQL | Chave | Aceita NULL | Definição adicional |
| --- | --- | --- | --- | --- |
| `id` | `BIGINT UNSIGNED` | PK | Não | `AUTO_INCREMENT` |
| `estoque_id` | `INT UNSIGNED` | FK → `estoque.id` | Não | — |
| `usuario_id` | `INT UNSIGNED` | FK → `usuarios.id` | Não | — |
| `tipo_movimentacao` | `ENUM('entrada', 'saida', 'ajuste', 'transferencia')` | — | Não | — |
| `quantidade` | `INT` | — | Não | — |
| `observacao` | `VARCHAR(255)` | — | Sim | — |
| `data_movimentacao` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP` |

| FK | Destino | ON DELETE | ON UPDATE |
| --- | --- | --- | --- |
| `estoque_id` | [`estoque.id`](#tabela-estoque) | `RESTRICT` | `CASCADE` |
| `usuario_id` | [`usuarios.id`](#tabela-usuarios) | `RESTRICT` | `CASCADE` |

</details>

<a id="compras"></a>

## Compras

```mermaid
erDiagram
    compras {
        INT id PK "obrigatorio"
        INT fornecedor_id FK "obrigatorio"
        INT usuario_id FK "obrigatorio"
    }
    itens_compra {
        INT id PK "obrigatorio"
        INT compra_id FK "obrigatorio"
        INT produto_id FK "obrigatorio"
    }
    fornecedores {
        INT id PK "obrigatorio"
    }
    produtos {
        INT id PK "obrigatorio"
    }
    usuarios {
        INT id PK "obrigatorio"
    }
    fornecedores ||..o{ compras : "fornecedor_id"
    usuarios ||..o{ compras : "usuario_id"
    compras ||..o{ itens_compra : "compra_id"
    produtos ||..o{ itens_compra : "produto_id"
```

**Dicionário da área** — expanda uma tabela para consultar suas colunas.

<a id="tabela-compras"></a>

<details>
<summary><strong>compras</strong> · 9 colunas</summary>

| Coluna | Tipo SQL | Chave | Aceita NULL | Definição adicional |
| --- | --- | --- | --- | --- |
| `id` | `INT UNSIGNED` | PK | Não | `AUTO_INCREMENT` |
| `fornecedor_id` | `INT UNSIGNED` | FK → `fornecedores.id` | Não | — |
| `usuario_id` | `INT UNSIGNED` | FK → `usuarios.id` | Não | — |
| `data_pedido` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP` |
| `data_recebimento` | `DATETIME` | — | Sim | — |
| `valor_total` | `DECIMAL(10, 2)` | — | Não | — |
| `status` | `ENUM('pendente', 'recebido', 'cancelado')` | — | Não | `DEFAULT 'pendente'` |
| `criado_em` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP` |
| `atualizado_em` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP` |

| FK | Destino | ON DELETE | ON UPDATE |
| --- | --- | --- | --- |
| `fornecedor_id` | [`fornecedores.id`](#tabela-fornecedores) | `RESTRICT` | `CASCADE` |
| `usuario_id` | [`usuarios.id`](#tabela-usuarios) | `RESTRICT` | `CASCADE` |

</details>

<a id="tabela-itens_compra"></a>

<details>
<summary><strong>itens_compra</strong> · 7 colunas</summary>

| Coluna | Tipo SQL | Chave | Aceita NULL | Definição adicional |
| --- | --- | --- | --- | --- |
| `id` | `INT UNSIGNED` | PK | Não | `AUTO_INCREMENT` |
| `compra_id` | `INT UNSIGNED` | FK → `compras.id` | Não | — |
| `produto_id` | `INT UNSIGNED` | FK → `produtos.id` | Não | — |
| `quantidade` | `INT UNSIGNED` | — | Não | — |
| `preco_unitario` | `DECIMAL(10, 2)` | — | Não | — |
| `lote_recebido` | `VARCHAR(50)` | — | Sim | — |
| `data_validade_recebida` | `DATE` | — | Sim | — |

| FK | Destino | ON DELETE | ON UPDATE |
| --- | --- | --- | --- |
| `compra_id` | [`compras.id`](#tabela-compras) | `CASCADE` | `CASCADE` |
| `produto_id` | [`produtos.id`](#tabela-produtos) | `RESTRICT` | `CASCADE` |

</details>

<a id="vendas"></a>

## Vendas e prescrições

```mermaid
erDiagram
    clientes {
        INT id PK "obrigatorio"
    }
    vendas {
        INT id PK "obrigatorio"
        INT cliente_id FK "opcional"
        INT usuario_id FK "obrigatorio"
    }
    itens_venda {
        INT id PK "obrigatorio"
        INT venda_id FK "obrigatorio"
        INT produto_id FK "obrigatorio"
    }
    receitas {
        INT id PK "obrigatorio"
        INT cliente_id FK "obrigatorio"
    }
    receitas_itens {
        INT id PK "obrigatorio"
        INT receita_id FK "obrigatorio"
        INT produto_id FK "obrigatorio"
    }
    produtos {
        INT id PK "obrigatorio"
    }
    usuarios {
        INT id PK "obrigatorio"
    }
    clientes |o..o{ vendas : "cliente_id"
    usuarios ||..o{ vendas : "usuario_id"
    vendas ||..o{ itens_venda : "venda_id"
    produtos ||..o{ itens_venda : "produto_id"
    clientes ||..o{ receitas : "cliente_id"
    receitas ||..o{ receitas_itens : "receita_id"
    produtos ||..o{ receitas_itens : "produto_id"
```

**Dicionário da área** — expanda uma tabela para consultar suas colunas.

<a id="tabela-clientes"></a>

<details>
<summary><strong>clientes</strong> · 10 colunas</summary>

| Coluna | Tipo SQL | Chave | Aceita NULL | Definição adicional |
| --- | --- | --- | --- | --- |
| `id` | `INT UNSIGNED` | PK | Não | `AUTO_INCREMENT` |
| `nome` | `VARCHAR(80)` | — | Não | — |
| `sobrenome` | `VARCHAR(80)` | — | Não | — |
| `cpf` | `VARCHAR(14)` | UNIQUE | Sim | — |
| `telefone` | `VARCHAR(20)` | — | Sim | — |
| `email` | `VARCHAR(180)` | UNIQUE | Sim | — |
| `endereco` | `VARCHAR(255)` | — | Sim | — |
| `data_nascimento` | `DATE` | — | Sim | — |
| `criado_em` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP` |
| `atualizado_em` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP` |

</details>

<a id="tabela-vendas"></a>

<details>
<summary><strong>vendas</strong> · 9 colunas</summary>

| Coluna | Tipo SQL | Chave | Aceita NULL | Definição adicional |
| --- | --- | --- | --- | --- |
| `id` | `INT UNSIGNED` | PK | Não | `AUTO_INCREMENT` |
| `cliente_id` | `INT UNSIGNED` | FK → `clientes.id` | Sim | — |
| `usuario_id` | `INT UNSIGNED` | FK → `usuarios.id` | Não | — |
| `data_venda` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP` |
| `valor_total` | `DECIMAL(10, 2)` | — | Não | — |
| `tipo_pagamento` | `ENUM('dinheiro', 'cartao_credito', 'cartao_debito', 'pix')` | — | Não | — |
| `status` | `ENUM('concluida', 'cancelada', 'pendente')` | — | Não | `DEFAULT 'pendente'` |
| `criado_em` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP` |
| `atualizado_em` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP` |

| FK | Destino | ON DELETE | ON UPDATE |
| --- | --- | --- | --- |
| `cliente_id` | [`clientes.id`](#tabela-clientes) | `SET NULL` | `CASCADE` |
| `usuario_id` | [`usuarios.id`](#tabela-usuarios) | `RESTRICT` | `CASCADE` |

</details>

<a id="tabela-itens_venda"></a>

<details>
<summary><strong>itens_venda</strong> · 7 colunas</summary>

| Coluna | Tipo SQL | Chave | Aceita NULL | Definição adicional |
| --- | --- | --- | --- | --- |
| `id` | `INT UNSIGNED` | PK | Não | `AUTO_INCREMENT` |
| `venda_id` | `INT UNSIGNED` | FK → `vendas.id` | Não | — |
| `produto_id` | `INT UNSIGNED` | FK → `produtos.id` | Não | — |
| `quantidade` | `INT UNSIGNED` | — | Não | — |
| `preco_unitario` | `DECIMAL(10, 2)` | — | Não | — |
| `desconto` | `DECIMAL(5, 2)` | — | Não | `DEFAULT 0.00` |
| `lote_vendido` | `VARCHAR(50)` | — | Sim | — |

| FK | Destino | ON DELETE | ON UPDATE |
| --- | --- | --- | --- |
| `venda_id` | [`vendas.id`](#tabela-vendas) | `CASCADE` | `CASCADE` |
| `produto_id` | [`produtos.id`](#tabela-produtos) | `RESTRICT` | `CASCADE` |

</details>

<a id="tabela-receitas"></a>

<details>
<summary><strong>receitas</strong> · 10 colunas</summary>

| Coluna | Tipo SQL | Chave | Aceita NULL | Definição adicional |
| --- | --- | --- | --- | --- |
| `id` | `INT UNSIGNED` | PK | Não | `AUTO_INCREMENT` |
| `cliente_id` | `INT UNSIGNED` | FK → `clientes.id` | Não | — |
| `medico_nome` | `VARCHAR(150)` | — | Não | — |
| `crm` | `VARCHAR(20)` | — | Não | — |
| `data_prescricao` | `DATE` | — | Não | — |
| `data_validade` | `DATE` | — | Sim | — |
| `observacoes` | `TEXT` | — | Sim | — |
| `arquivo_receita_url` | `VARCHAR(255)` | — | Sim | — |
| `criado_em` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP` |
| `atualizado_em` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP` |

| FK | Destino | ON DELETE | ON UPDATE |
| --- | --- | --- | --- |
| `cliente_id` | [`clientes.id`](#tabela-clientes) | `RESTRICT` | `CASCADE` |

</details>

<a id="tabela-receitas_itens"></a>

<details>
<summary><strong>receitas_itens</strong> · 6 colunas</summary>

| Coluna | Tipo SQL | Chave | Aceita NULL | Definição adicional |
| --- | --- | --- | --- | --- |
| `id` | `INT UNSIGNED` | PK | Não | `AUTO_INCREMENT` |
| `receita_id` | `INT UNSIGNED` | FK → `receitas.id` | Não | — |
| `produto_id` | `INT UNSIGNED` | FK → `produtos.id` | Não | — |
| `quantidade` | `INT UNSIGNED` | — | Não | — |
| `dosagem` | `VARCHAR(100)` | — | Sim | — |
| `instrucoes_uso` | `TEXT` | — | Sim | — |

| FK | Destino | ON DELETE | ON UPDATE |
| --- | --- | --- | --- |
| `receita_id` | [`receitas.id`](#tabela-receitas) | `CASCADE` | `CASCADE` |
| `produto_id` | [`produtos.id`](#tabela-produtos) | `RESTRICT` | `CASCADE` |

</details>

<a id="financeiro"></a>

## Financeiro

```mermaid
erDiagram
    financeiro_categorias {
        INT id PK "obrigatorio"
    }
    financeiro_transacoes {
        INT id PK "obrigatorio"
        INT categoria_id FK "obrigatorio"
        INT usuario_id FK "obrigatorio"
        INT venda_id FK "opcional"
        INT compra_id FK "opcional"
    }
    compras {
        INT id PK "obrigatorio"
    }
    usuarios {
        INT id PK "obrigatorio"
    }
    vendas {
        INT id PK "obrigatorio"
    }
    financeiro_categorias ||..o{ financeiro_transacoes : "categoria_id"
    usuarios ||..o{ financeiro_transacoes : "usuario_id"
    vendas |o..o{ financeiro_transacoes : "venda_id"
    compras |o..o{ financeiro_transacoes : "compra_id"
```

**Dicionário da área** — expanda uma tabela para consultar suas colunas.

<a id="tabela-financeiro_categorias"></a>

<details>
<summary><strong>financeiro_categorias</strong> · 5 colunas</summary>

| Coluna | Tipo SQL | Chave | Aceita NULL | Definição adicional |
| --- | --- | --- | --- | --- |
| `id` | `INT UNSIGNED` | PK | Não | `AUTO_INCREMENT` |
| `nome` | `VARCHAR(80)` | — | Não | — |
| `tipo` | `ENUM('receita', 'despesa')` | — | Não | — |
| `slug` | `VARCHAR(40)` | UNIQUE | Não | — |
| `criado_em` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP` |

</details>

<a id="tabela-financeiro_transacoes"></a>

<details>
<summary><strong>financeiro_transacoes</strong> · 12 colunas</summary>

| Coluna | Tipo SQL | Chave | Aceita NULL | Definição adicional |
| --- | --- | --- | --- | --- |
| `id` | `INT UNSIGNED` | PK | Não | `AUTO_INCREMENT` |
| `categoria_id` | `INT UNSIGNED` | FK → `financeiro_categorias.id` | Não | — |
| `usuario_id` | `INT UNSIGNED` | FK → `usuarios.id` | Não | — |
| `venda_id` | `INT UNSIGNED` | FK → `vendas.id` | Sim | — |
| `compra_id` | `INT UNSIGNED` | FK → `compras.id` | Sim | — |
| `descricao` | `VARCHAR(255)` | — | Não | — |
| `valor` | `DECIMAL(12, 2)` | — | Não | — |
| `data_transacao` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP` |
| `status` | `ENUM('pago', 'pendente', 'cancelado')` | — | Não | `DEFAULT 'pago'` |
| `metodo_pagamento` | `ENUM('dinheiro', 'cartao_credito', 'cartao_debito', 'pix', 'boleto', 'transferencia')` | — | Não | — |
| `criado_em` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP` |
| `atualizado_em` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP` |

**Índices adicionais / unicidade composta**

- `INDEX idx_data (data_transacao)`

| FK | Destino | ON DELETE | ON UPDATE |
| --- | --- | --- | --- |
| `categoria_id` | [`financeiro_categorias.id`](#tabela-financeiro_categorias) | `RESTRICT` | `CASCADE` |
| `usuario_id` | [`usuarios.id`](#tabela-usuarios) | `RESTRICT` | `CASCADE` |
| `venda_id` | [`vendas.id`](#tabela-vendas) | `SET NULL` | `CASCADE` |
| `compra_id` | [`compras.id`](#tabela-compras) | `SET NULL` | `CASCADE` |

</details>

<a id="operacao"></a>

## Operação e auditoria

```mermaid
erDiagram
    alertas {
        INT id PK "obrigatorio"
        INT resolvido_por_usuario_id FK "opcional"
    }
    log_acessos {
        BIGINT id PK "obrigatorio"
        INT usuario_id FK "obrigatorio"
    }
    log_atividades {
        BIGINT id PK "obrigatorio"
    }
    configuracoes_sistema {
        VARCHAR chave PK "obrigatorio"
    }
    usuarios {
        INT id PK "obrigatorio"
    }
    usuarios |o..o{ alertas : "resolvido_por_usuario_id"
    usuarios ||..o{ log_acessos : "usuario_id"
```

**Dicionário da área** — expanda uma tabela para consultar suas colunas.

<a id="tabela-alertas"></a>

<details>
<summary><strong>alertas</strong> · 9 colunas</summary>

| Coluna | Tipo SQL | Chave | Aceita NULL | Definição adicional |
| --- | --- | --- | --- | --- |
| `id` | `INT UNSIGNED` | PK | Não | `AUTO_INCREMENT` |
| `tipo_alerta` | `VARCHAR(30)` | — | Não | — |
| `referencia_id` | `INT` | — | Sim | — |
| `mensagem` | `TEXT` | — | Não | — |
| `status` | `VARCHAR(20)` | — | Não | `DEFAULT 'ativo'` |
| `resolvido_em` | `DATETIME` | — | Sim | — |
| `resolvido_por_usuario_id` | `INT UNSIGNED` | FK → `usuarios.id` | Sim | — |
| `criado_em` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP` |
| `atualizado_em` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP` |

**Índices adicionais / unicidade composta**

- `INDEX idx_alertas_tipo (tipo_alerta)`
- `INDEX idx_alertas_status (status)`
- `INDEX idx_alertas_resolvido_por (resolvido_por_usuario_id)`

| FK | Destino | ON DELETE | ON UPDATE |
| --- | --- | --- | --- |
| `resolvido_por_usuario_id` | [`usuarios.id`](#tabela-usuarios) | `SET NULL` | `CASCADE` |

</details>

<a id="tabela-log_acessos"></a>

<details>
<summary><strong>log_acessos</strong> · 7 colunas</summary>

| Coluna | Tipo SQL | Chave | Aceita NULL | Definição adicional |
| --- | --- | --- | --- | --- |
| `id` | `BIGINT UNSIGNED` | PK | Não | `AUTO_INCREMENT` |
| `usuario_id` | `INT UNSIGNED` | FK → `usuarios.id` | Não | — |
| `ip` | `VARCHAR(45)` | — | Sim | — |
| `user_agent` | `VARCHAR(500)` | — | Sim | — |
| `sucesso` | `TINYINT(1)` | — | Não | `DEFAULT 1` |
| `motivo_falha` | `VARCHAR(200)` | — | Sim | — |
| `criado_em` | `DATETIME` | — | Não | `DEFAULT CURRENT_TIMESTAMP` |

| FK | Destino | ON DELETE | ON UPDATE |
| --- | --- | --- | --- |
| `usuario_id` | [`usuarios.id`](#tabela-usuarios) | `CASCADE` | `CASCADE` |

</details>

<a id="tabela-log_atividades"></a>

<details>
<summary><strong>log_atividades</strong> · 8 colunas</summary>

| Coluna | Tipo SQL | Chave | Aceita NULL | Definição adicional |
| --- | --- | --- | --- | --- |
| `id` | `BIGINT UNSIGNED` | PK | Não | `AUTO_INCREMENT` |
| `usuario_id` | `INT` | — | Sim | — |
| `usuario_nome` | `VARCHAR(255)` | — | Não | — |
| `perfil` | `VARCHAR(40)` | — | Não | — |
| `acao` | `VARCHAR(255)` | — | Não | — |
| `detalhes` | `MEDIUMTEXT` | — | Não | — |
| `status_http` | `SMALLINT UNSIGNED` | — | Não | — |
| `criado_em` | `DATETIME` | — | Não | `DEFAULT (UTC_TIMESTAMP())` |

**Índices adicionais / unicidade composta**

- `INDEX idx_log_usuario (usuario_id, id)`

</details>

<a id="tabela-configuracoes_sistema"></a>

<details>
<summary><strong>configuracoes_sistema</strong> · 5 colunas</summary>

| Coluna | Tipo SQL | Chave | Aceita NULL | Definição adicional |
| --- | --- | --- | --- | --- |
| `chave` | `VARCHAR(120)` | PK | Não | — |
| `valor` | `TEXT` | — | Sim | — |
| `descricao` | `VARCHAR(255)` | — | Sim | — |
| `criado_em` | `TIMESTAMP` | — | Sim | `DEFAULT CURRENT_TIMESTAMP` |
| `atualizado_em` | `TIMESTAMP` | — | Sim | `DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP` |

</details>

## Atualização desta referência

O gerador [`scripts/database_docs.py`](../scripts/database_docs.py) lê apenas o schema e emite este Markdown. Depois de mudar o SQL, gere novamente, confira os diagramas e atualize a documentação. As relações mostradas são somente as FKs declaradas; regras transacionais da aplicação não criam novas FKs.
