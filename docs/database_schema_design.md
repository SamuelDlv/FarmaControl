# Design do Esquema do Banco de Dados - FarmaControl

Este documento detalha o esquema do banco de dados para o sistema FarmaControl, projetado para gerenciar todas as operações de uma farmácia de forma otimizada e profissional. O esquema foi unificado para incluir autenticação, gestão de clientes, produtos, estoque, fornecedores, compras, vendas, receitas, alertas e configurações do sistema.

## Visão Geral

O banco de dados `farmacontrol` é composto por 18 tabelas interconectadas, garantindo integridade referencial e eficiência na recuperação de dados. A estrutura foi pensada para suportar um fluxo de trabalho completo de farmácia, desde o cadastro de usuários e produtos até o controle de vendas e estoque.

## Tabelas

### 1. `perfis`
Armazena os diferentes perfis de acesso (roles) dentro do sistema.

| Coluna | Tipo | Restrições | Descrição |
| :----- | :--- | :--------- | :-------- |
| `id` | INT | PRIMARY KEY, AUTO_INCREMENT | Identificador único do perfil. |
| `slug` | VARCHAR(50) | UNIQUE, NOT NULL | Identificador textual único do perfil (ex: 'admin', 'farmaceutico'). |
| `nome` | VARCHAR(100) | NOT NULL | Nome amigável do perfil (ex: 'Administrador', 'Farmacêutico'). |
| `descricao` | TEXT | | Descrição detalhada do perfil. |

### 2. `usuarios`
Armazena as informações dos usuários do sistema, incluindo dados de autenticação.

| Coluna | Tipo | Restrições | Descrição |
| :----- | :--- | :--------- | :-------- |
| `id` | INT | PRIMARY KEY, AUTO_INCREMENT | Identificador único do usuário. |
| `nome` | VARCHAR(100) | NOT NULL | Primeiro nome do usuário. |
| `sobrenome` | VARCHAR(100) | NOT NULL | Sobrenome do usuário. |
| `email` | VARCHAR(255) | UNIQUE, NOT NULL | Endereço de e-mail do usuário (usado para login). |
| `senha_hash` | VARCHAR(255) | NOT NULL | Hash da senha do usuário (bcrypt). |
| `perfil_id` | INT | NOT NULL, FOREIGN KEY (`perfis.id`) | Perfil de acesso do usuário. |
| `status` | ENUM | NOT NULL, DEFAULT 'pendente' | Status do cadastro ('pendente', 'aprovado', 'rejeitado'). |
| `criado_em` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Data e hora de criação do registro. |
| `ultimo_login` | DATETIME | | Data e hora do último login bem-sucedido. |

### 3. `log_acessos`
Registra todas as tentativas de login no sistema para fins de auditoria e segurança.

| Coluna | Tipo | Restrições | Descrição |
| :----- | :--- | :--------- | :-------- |
| `id` | INT | PRIMARY KEY, AUTO_INCREMENT | Identificador único do log. |
| `usuario_id` | INT | NOT NULL, FOREIGN KEY (`usuarios.id`) | Usuário que tentou o acesso. |
| `ip` | VARCHAR(45) | NOT NULL | Endereço IP de origem da tentativa. |
| `user_agent` | VARCHAR(500) | | User-Agent do navegador/cliente. |
| `sucesso` | BOOLEAN | NOT NULL | Indica se o login foi bem-sucedido (1) ou falhou (0). |
| `motivo_falha` | VARCHAR(255) | | Motivo da falha, se houver. |
| `data_acesso` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Data e hora da tentativa de acesso. |

### 4. `analises_cadastro`
Registra as decisões de aprovação ou rejeição de cadastros de usuários.

| Coluna | Tipo | Restrições | Descrição |
| :----- | :--- | :--------- | :-------- |
| `id` | INT | PRIMARY KEY, AUTO_INCREMENT | Identificador único da análise. |
| `usuario_id` | INT | NOT NULL, FOREIGN KEY (`usuarios.id`) | Usuário cujo cadastro foi analisado. |
| `analisado_por` | INT | FOREIGN KEY (`usuarios.id`) | Usuário (admin) que realizou a análise. |
| `decisao` | ENUM | NOT NULL | Decisão ('aprovado', 'rejeitado'). |
| `motivo` | TEXT | | Motivo da decisão (especialmente para rejeição). |
| `data_analise` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Data e hora da análise. |

### 5. `clientes`
Armazena informações detalhadas sobre os clientes da farmácia.

| Coluna | Tipo | Restrições | Descrição |
| :----- | :--- | :--------- | :-------- |
| `id` | INT | PRIMARY KEY, AUTO_INCREMENT | Identificador único do cliente. |
| `nome` | VARCHAR(100) | NOT NULL | Primeiro nome do cliente. |
| `sobrenome` | VARCHAR(100) | NOT NULL | Sobrenome do cliente. |
| `cpf` | VARCHAR(14) | UNIQUE | CPF do cliente (com ou sem formatação). |
| `telefone` | VARCHAR(20) | | Telefone de contato. |
| `email` | VARCHAR(255) | UNIQUE | E-mail do cliente. |
| `endereco` | VARCHAR(255) | | Endereço completo do cliente. |
| `data_nascimento` | DATE | | Data de nascimento do cliente. |
| `criado_em` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Data e hora de cadastro do cliente. |
| `atualizado_em` | DATETIME | DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | Data e hora da última atualização. |

### 6. `categorias_produto`
Categoriza os produtos para melhor organização e busca.

| Coluna | Tipo | Restrições | Descrição |
| :----- | :--- | :--------- | :-------- |
| `id` | INT | PRIMARY KEY, AUTO_INCREMENT | Identificador único da categoria. |
| `nome` | VARCHAR(100) | UNIQUE, NOT NULL | Nome da categoria (ex: 'Analgésicos', 'Vitaminas'). |
| `descricao` | TEXT | | Descrição da categoria. |

### 7. `produtos`
Armazena informações sobre todos os produtos disponíveis na farmácia.

| Coluna | Tipo | Restrições | Descrição |
| :----- | :--- | :--------- | :-------- |
| `id` | INT | PRIMARY KEY, AUTO_INCREMENT | Identificador único do produto. |
| `nome` | VARCHAR(255) | NOT NULL | Nome comercial do produto. |
| `nome_generico` | VARCHAR(255) | | Nome genérico do produto, se aplicável. |
| `descricao` | TEXT | | Descrição detalhada do produto. |
| `fabricante` | VARCHAR(100) | | Fabricante do produto. |
| `preco_custo` | DECIMAL(10, 2) | NOT NULL | Preço de custo do produto. |
| `preco_venda` | DECIMAL(10, 2) | NOT NULL | Preço de venda sugerido. |
| `codigo_barras` | VARCHAR(50) | UNIQUE | Código de barras EAN/UPC. |
| `categoria_id` | INT | FOREIGN KEY (`categorias_produto.id`) | Categoria do produto. |
| `requer_receita` | BOOLEAN | NOT NULL, DEFAULT FALSE | Indica se o produto requer receita médica. |
| `ativo` | BOOLEAN | NOT NULL, DEFAULT TRUE | Indica se o produto está ativo para venda. |
| `estoque_minimo` | INT | NOT NULL, DEFAULT 10 | Quantidade mínima para alerta de reposição. |
| `fornecedor_id` | INT | FOREIGN KEY (`fornecedores.id`) | Fornecedor preferencial do produto. |
| `criado_em` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Data e hora de cadastro do produto. |
| `atualizado_em` | DATETIME | DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | Data e hora da última atualização. |

### 8. `fornecedores`
Armazena informações sobre os fornecedores dos produtos.

| Coluna | Tipo | Restrições | Descrição |
| :----- | :--- | :--------- | :-------- |
| `id` | INT | PRIMARY KEY, AUTO_INCREMENT | Identificador único do fornecedor. |
| `nome_fantasia` | VARCHAR(255) | NOT NULL | Nome fantasia do fornecedor. |
| `razao_social` | VARCHAR(255) | UNIQUE, NOT NULL | Razão social do fornecedor. |
| `cnpj` | VARCHAR(18) | UNIQUE, NOT NULL | CNPJ do fornecedor. |
| `contato_nome` | VARCHAR(100) | | Nome do contato principal. |
| `contato_telefone` | VARCHAR(20) | | Telefone do contato. |
| `contato_email` | VARCHAR(255) | | E-mail do contato. |
| `endereco` | VARCHAR(255) | | Endereço completo do fornecedor. |
| `ativo` | BOOLEAN | NOT NULL, DEFAULT TRUE | Indica se o fornecedor está ativo. |
| `criado_em` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Data e hora de cadastro do fornecedor. |
| `atualizado_em` | DATETIME | DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | Data e hora da última atualização. |

### 9. `estoque`
Controla o estoque de cada produto, incluindo lotes e datas de validade.

| Coluna | Tipo | Restrições | Descrição |
| :----- | :--- | :--------- | :-------- |
| `id` | INT | PRIMARY KEY, AUTO_INCREMENT | Identificador único do item de estoque. |
| `produto_id` | INT | NOT NULL, FOREIGN KEY (`produtos.id`) | Produto em estoque. |
| `lote` | VARCHAR(50) | NOT NULL | Número do lote do produto. |
| `quantidade` | INT | NOT NULL | Quantidade atual em estoque. |
| `data_validade` | DATE | NOT NULL | Data de validade do lote. |
| `localizacao` | VARCHAR(100) | | Localização física no estoque (ex: 'Prateleira A1'). |
| `criado_em` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Data e hora de registro no estoque. |
| `atualizado_em` | DATETIME | DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | Data e hora da última atualização. |
| `uk_produto_lote` | UNIQUE (`produto_id`, `lote`) | | Garante que um produto tenha apenas um registro por lote. |

### 10. `movimentacoes_estoque`
Registra todas as entradas e saídas de produtos do estoque.

| Coluna | Tipo | Restrições | Descrição |
| :----- | :--- | :--------- | :-------- |
| `id` | INT | PRIMARY KEY, AUTO_INCREMENT | Identificador único da movimentação. |
| `estoque_id` | INT | NOT NULL, FOREIGN KEY (`estoque.id`) | Item de estoque movimentado. |
| `usuario_id` | INT | NOT NULL, FOREIGN KEY (`usuarios.id`) | Usuário que realizou a movimentação. |
| `tipo_movimentacao` | ENUM | NOT NULL | Tipo de movimentação ('entrada', 'saida', 'ajuste', 'transferencia'). |
| `quantidade` | INT | NOT NULL | Quantidade movimentada. |
| `data_movimentacao` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Data e hora da movimentação. |
| `observacao` | TEXT | | Observações adicionais sobre a movimentação. |

### 11. `compras`
Registra as ordens de compra de produtos da farmácia com fornecedores.

| Coluna | Tipo | Restrições | Descrição |
| :----- | :--- | :--------- | :-------- |
| `id` | INT | PRIMARY KEY, AUTO_INCREMENT | Identificador único da compra. |
| `fornecedor_id` | INT | NOT NULL, FOREIGN KEY (`fornecedores.id`) | Fornecedor da compra. |
| `usuario_id` | INT | NOT NULL, FOREIGN KEY (`usuarios.id`) | Usuário que registrou a compra. |
| `data_compra` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Data e hora da realização da compra. |
| `valor_total` | DECIMAL(10, 2) | NOT NULL | Valor total da compra. |
| `status` | ENUM | NOT NULL, DEFAULT 'pendente' | Status da compra ('pendente', 'recebido', 'cancelado'). |
| `data_recebimento` | DATETIME | | Data e hora do recebimento dos produtos. |
| `observacoes` | TEXT | | Observações sobre a compra. |

### 12. `itens_compra`
Detalha os produtos incluídos em cada ordem de compra.

| Coluna | Tipo | Restrições | Descrição |
| :----- | :--- | :--------- | :-------- |
| `id` | INT | PRIMARY KEY, AUTO_INCREMENT | Identificador único do item da compra. |
| `compra_id` | INT | NOT NULL, FOREIGN KEY (`compras.id`) | Compra à qual o item pertence. |
| `produto_id` | INT | NOT NULL, FOREIGN KEY (`produtos.id`) | Produto comprado. |
| `quantidade` | INT | NOT NULL | Quantidade do produto comprado. |
| `preco_unitario` | DECIMAL(10, 2) | NOT NULL | Preço unitário do produto na compra. |
| `lote_recebido` | VARCHAR(50) | | Lote do produto recebido (se aplicável). |
| `data_validade_recebida` | DATE | | Data de validade do lote recebido. |

### 13. `vendas`
Registra todas as vendas realizadas pela farmácia.

| Coluna | Tipo | Restrições | Descrição |
| :----- | :--- | :--------- | :-------- |
| `id` | INT | PRIMARY KEY, AUTO_INCREMENT | Identificador único da venda. |
| `cliente_id` | INT | FOREIGN KEY (`clientes.id`) | Cliente que realizou a compra (pode ser NULL para vendas avulsas). |
| `usuario_id` | INT | NOT NULL, FOREIGN KEY (`usuarios.id`) | Usuário (atendente/farmacêutico) que registrou a venda. |
| `data_venda` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Data e hora da venda. |
| `valor_total` | DECIMAL(10, 2) | NOT NULL | Valor total da venda. |
| `tipo_pagamento` | ENUM | NOT NULL | Tipo de pagamento ('dinheiro', 'cartao_credito', 'cartao_debito', 'pix'). |
| `status` | ENUM | NOT NULL, DEFAULT 'concluida' | Status da venda ('concluida', 'cancelada', 'pendente'). |
| `observacoes` | TEXT | | Observações sobre a venda. |

### 14. `itens_venda`
Detalha os produtos incluídos em cada venda.

| Coluna | Tipo | Restrições | Descrição |
| :----- | :--- | :--------- | :-------- |
| `id` | INT | PRIMARY KEY, AUTO_INCREMENT | Identificador único do item da venda. |
| `venda_id` | INT | NOT NULL, FOREIGN KEY (`vendas.id`) | Venda à qual o item pertence. |
| `produto_id` | INT | NOT NULL, FOREIGN KEY (`produtos.id`) | Produto vendido. |
| `quantidade` | INT | NOT NULL | Quantidade do produto vendido. |
| `preco_unitario` | DECIMAL(10, 2) | NOT NULL | Preço unitário do produto na venda. |
| `desconto` | DECIMAL(10, 2) | DEFAULT 0.00 | Valor do desconto aplicado ao item. |
| `lote_vendido` | VARCHAR(50) | | Lote do produto que foi vendido. |

### 15. `receitas`
Armazena informações sobre receitas médicas apresentadas pelos clientes.

| Coluna | Tipo | Restrições | Descrição |
| :----- | :--- | :--------- | :-------- |
| `id` | INT | PRIMARY KEY, AUTO_INCREMENT | Identificador único da receita. |
| `cliente_id` | INT | NOT NULL, FOREIGN KEY (`clientes.id`) | Cliente ao qual a receita pertence. |
| `medico_nome` | VARCHAR(255) | NOT NULL | Nome do médico que prescreveu. |
| `crm` | VARCHAR(20) | NOT NULL | CRM do médico. |
| `data_prescricao` | DATE | NOT NULL | Data em que a receita foi prescrita. |
| `data_validade` | DATE | | Data de validade da receita. |
| `observacoes` | TEXT | | Observações adicionais da receita. |
| `arquivo_receita_url` | VARCHAR(255) | | URL para o arquivo digitalizado da receita. |
| `criado_em` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Data e hora de registro da receita. |

### 16. `receitas_itens`
Detalha os produtos prescritos em cada receita.

| Coluna | Tipo | Restrições | Descrição |
| :----- | :--- | :--------- | :-------- |
| `id` | INT | PRIMARY KEY, AUTO_INCREMENT | Identificador único do item da receita. |
| `receita_id` | INT | NOT NULL, FOREIGN KEY (`receitas.id`) | Receita à qual o item pertence. |
| `produto_id` | INT | NOT NULL, FOREIGN KEY (`produtos.id`) | Produto prescrito. |
| `quantidade` | INT | NOT NULL | Quantidade prescrita. |
| `dosagem` | VARCHAR(100) | | Dosagem do medicamento. |
| `instrucoes_uso` | TEXT | | Instruções de uso do medicamento. |

### 17. `alertas`
Gerencia alertas automáticos do sistema (ex: estoque baixo, produtos vencendo).

| Coluna | Tipo | Restrições | Descrição |
| :----- | :--- | :--------- | :-------- |
| `id` | INT | PRIMARY KEY, AUTO_INCREMENT | Identificador único do alerta. |
| `tipo_alerta` | ENUM | NOT NULL | Tipo de alerta ('vencimento', 'estoque_baixo', 'outros'). |
| `referencia_id` | INT | | ID do item relacionado (ex: `estoque.id` para vencimento/estoque baixo). |
| `mensagem` | TEXT | NOT NULL | Mensagem descritiva do alerta. |
| `status` | ENUM | NOT NULL, DEFAULT 'ativo' | Status do alerta ('ativo', 'resolvido'). |
| `criado_em` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Data e hora de criação do alerta. |
| `resolvido_em` | DATETIME | | Data e hora em que o alerta foi resolvido. |
| `resolvido_por_usuario_id` | INT | FOREIGN KEY (`usuarios.id`) | Usuário que resolveu o alerta. |

### 18. `configuracoes_sistema`
Armazena configurações gerais do sistema que podem ser alteradas dinamicamente.

| Coluna | Tipo | Restrições | Descrição |
| :----- | :--- | :--------- | :-------- |
| `chave` | VARCHAR(100) | PRIMARY KEY | Chave única da configuração (ex: 'estoque_minimo_padrao'). |
| `valor` | TEXT | NOT NULL | Valor da configuração. |
| `descricao` | TEXT | | Descrição da configuração. |
| `atualizado_em` | DATETIME | DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | Data e hora da última atualização. |

## Relacionamentos

Os relacionamentos entre as tabelas são definidos por chaves estrangeiras (FOREIGN KEYs), garantindo a integridade dos dados. Por exemplo:

*   `usuarios.perfil_id` referencia `perfis.id`
*   `log_acessos.usuario_id` referencia `usuarios.id`
*   `analises_cadastro.usuario_id` e `analises_cadastro.analisado_por` referenciam `usuarios.id`
*   `produtos.categoria_id` referencia `categorias_produto.id`
*   `estoque.produto_id` referencia `produtos.id`
*   `movimentacoes_estoque.estoque_id` referencia `estoque.id` e `movimentacoes_estoque.usuario_id` referencia `usuarios.id`
*   `compras.fornecedor_id` referencia `fornecedores.id` e `compras.usuario_id` referencia `usuarios.id`
*   `itens_compra.compra_id` referencia `compras.id` e `itens_compra.produto_id` referencia `produtos.id`
*   `vendas.cliente_id` referencia `clientes.id` e `vendas.usuario_id` referencia `usuarios.id`
*   `itens_venda.venda_id` referencia `vendas.id` e `itens_venda.produto_id` referencia `produtos.id`
*   `receitas.cliente_id` referencia `clientes.id`
*   `receitas_itens.receita_id` referencia `receitas.id` e `receitas_itens.produto_id` referencia `produtos.id`
*   `alertas.resolvido_por_usuario_id` referencia `usuarios.id`

Este esquema fornece uma base robusta e escalável para o desenvolvimento do sistema FarmaControl. 
