# Referência da API

Revisada em **23/10/2026** a partir dos registros de rotas em `backend/farmacontrol/routes/`. Os caminhos não possuem prefixo `/api`. Em desenvolvimento a origem é `http://localhost:5000`; o frontend usa a mesma origem da página.

## Convenções

Requisições JSON usam `Content-Type: application/json`. A autenticação usa cookie de sessão; não existe bearer token/JWT. Mutações protegidas também enviam `X-CSRF-Token`, recebido no login ou aceite do convite. Não envie esse token a origens externas.

Respostas de sucesso incluem `ok: true` e os dados definidos pelo handler. Erros usam `ok: false`, `mensagem` e, quando pertinente, `campo`. Não há um envelope único `data` nem paginação universal: cada endpoint define seus campos e parâmetros.

```json
{"ok": false, "mensagem": "Informe um e-mail válido.", "campo": "email"}
```

| Código | Uso comum |
| --- | --- |
| 200 / 201 | Consulta/ação concluída ou registro criado |
| 400 | Validação de entrada |
| 401 | Sessão ausente ou conta sem acesso |
| 403 | Permissão, CSRF ou origem recusada |
| 404 | Recurso não encontrado |
| 409 | Conflito de cadastro, preço ou saldo |
| 410 | Token expirado/consumido ou configuração aposentada |
| 413 | Corpo acima de 1 MiB |
| 429 | Limite das mutações de autenticação |
| 500 / 503 | Falha de processamento ou dependência indisponível |

Os códigos exatos dependem da rota; interprete também a mensagem. Uma falha de entrega SMTP de convite pode ocorrer depois da gravação, e perda de resposta de venda não prova que houve rollback.

## Autenticação

Exemplo de corpo para login, com dados fictícios:

```json
{
  "email": "pessoa@example.invalid",
  "password": "senha-definida-no-cadastro",
  "remember": false
}
```

`remember` precisa ser booleano. Cadastro público exige nome, sobrenome, e-mail, perfil, senha e os dois aceites booleanos. Para aceite de convite, envie também `convite_token`; identidade e perfil serão resolvidos pelo convite no servidor.

Recuperação recebe `email`; redefinição recebe `token` e `password`. A [documentação de autenticação](../frontend/src/pages/README-authentication.md) detalha os estados e a expiração.

## Autorização

As mutações de `/auth/` compartilham 5 solicitações por IP/processo em uma janela fixa de 300 segundos, incluindo sucessos e logout. Erros de credenciais (401) retornam `tentativas_restantes` e `aguarde_segundos`. Quando restam zero tentativas, a resposta informa o tempo até a janela expirar e o cabeçalho `Retry-After`; novas solicitações recebem 429. O frontend exibe esse tempo em contagem regressiva.

O acesso direto aos HTMLs internos em `/pages/sistema/` e no alias `/pages/proprietario/` também exige sessão e permissão. Sem sessão válida, a resposta é 302 para `/pages/acesso/acesso.html`; sem permissão, 403; indisponibilidade na validação, 503. Essas respostas e o HTML interno usam `Cache-Control: no-store`. A rota genérica de arquivos aplica a mesma proteção pelo destino físico. APIs continuam usando 401 para sessão inválida, sem redirecionamento HTTP.

O middleware consulta o usuário e a matriz de módulos em cada requisição protegida. `/configuracoes/visual` é leitura pública. O conjunto de rotas de vendas/clientes/receitas usa perfis comerciais fixos; log é reservado a proprietário, admin e TI. Visualizador nunca pode executar mutações protegidas.

Mapeamento principal: `/admin/` → usuários; `/financeiro/` → financeiro; `/relatorios/` → relatórios; compras/fornecedores → compras; alertas → vencimentos; estoque/movimentações/produtos/categorias → estoque; dashboard → dashboard; configurações → configurações. Detalhes em [backend](../backend/README.md).

## Contratos operacionais principais

### Catálogo e estoque

`/produtos` usa campos como `tipo_produto`, `exige_validade`, `estoque_minimo` e `fornecedor_id`, além dos dados comerciais. `/estoque` recebe campos do lote e os equivalentes de cadastro com prefixo `produto_`; `produto_id` permite usar um cadastro existente. PUT de produto é parcial e preserva campos omitidos conforme o handler.

Medicamentos e outros produtos possuem regras diferentes; consulte [banco](database_schema_design.md). Não interprete uma categoria como autorização para omitir validade ou marcar receita.

### Recebimento de compras

Na atualização da compra para recebida, `itens_recebimento` informa `id`, `lote_recebido` e `data_validade_recebida` para os itens. O servidor recusa IDs duplicados ou de outra compra e desfaz a transação em erro. O contrato completo de campos adicionais permanece no handler `update_compra`.

### PDV

Exemplo de estrutura para `POST /vendas/balcao`; IDs e preço devem corresponder ao catálogo real da instalação:

```json
{
  "tipo_pagamento": "pix",
  "receita_conferida": false,
  "itens": [
    {"estoque_id": 123, "quantidade": 2, "preco_unitario": "19.90"}
  ]
}
```

O servidor admite de 1 a 100 lotes distintos e compara o preço enviado ao preço atual do banco. Recalcula o total e confirma os efeitos numa transação. Sucesso retorna `id` e `valor_total` com status 201. Receita exigida depende de confirmação booleana `true`. Formas aceitas: dinheiro, pix, cartão de crédito e débito com os slugs documentados em [PDV](pdv.md).

### Permissões

`PUT /admin/perfis/permissoes` recebe um objeto `perfis`, mapeando slugs de perfil para listas de módulos. Para cada perfil enviado, a lista substitui as permissões existentes; não é apenas uma adição. Módulos desconhecidos são recusados. Alterar essa matriz pode retirar o acesso do próprio perfil administrador.

### Configurações

`PUT /configuracoes` recebe `configuracoes` com as chaves editáveis. `backend/farmacontrol/services/system_settings.py` define tipos e limites. As antigas chaves `tema` e `tema_efetivo` não são configurações ativas e sua leitura/gravação individual retorna 410. Opções de idioma/moeda não realizam tradução ou conversão financeira.

### Histórico

`GET /admin/logs` aceita `limit` até 100, `antes` para paginação por ID, `usuario_id`, `data_inicio`, `data_fim`, `busca`, `atividade` e `incluir_usuarios=1`. Datas usam `YYYY-MM-DD`, incluem o dia no horário de Brasília e não podem ser futuras. `atividade` distingue alterações/acessos de consultas. Não há rota pública para alterar ou excluir eventos do log.

## Inventário de endpoints

A tabela abaixo foi extraída estaticamente dos decoradores do arquivo atual; não exige importar a aplicação nem conectar ao banco. Lista métodos explícitos e GET das rotas estáticas, sem expandir HEAD/OPTIONS automáticos do Flask. Os links apontam ao arquivo de implementação, evitando números de linha que envelhecem a cada edição.


Total: **88 declarações de rota** nos [módulos de rotas](../backend/farmacontrol/routes/), registrados por [create_app()](../backend/farmacontrol/__init__.py). URLs, métodos e nomes dos endpoints foram preservados na modularização.

| Método | Caminho | Handler |
| --- | --- | --- |
| `GET` | `/health` | `health` |
| `POST` | `/auth/register` | `register` |
| `POST` | `/auth/recuperar-senha` | `solicitar_recuperacao_senha` |
| `POST` | `/auth/redefinir-senha` | `redefinir_senha` |
| `GET` | `/auth/convites/<string:token>` | `consultar_convite` |
| `POST` | `/auth/convites/<string:token>/recusar` | `recusar_convite` |
| `POST` | `/auth/login` | `login` |
| `POST` | `/auth/logout` | `logout` |
| `GET` | `/admin/usuarios` | `listar_usuarios` |
| `GET` | `/admin/logs` | `listar_logs` |
| `GET` | `/admin/pendentes` | `listar_pendentes` |
| `GET` | `/admin/perfis/permissoes` | `listar_permissoes_perfis` |
| `PUT` | `/admin/perfis/permissoes` | `atualizar_permissoes_perfis` |
| `PUT` | `/admin/usuarios/<int:usuario_id>` | `editar_usuario` |
| `POST` | `/admin/convites` | `criar_convite` |
| `DELETE` | `/admin/usuarios/<int:usuario_id>` | `excluir_usuario` |
| `POST` | `/admin/analisar-cadastro` | `analisar_cadastro` |
| `GET` | `/clientes` | `get_clientes` |
| `GET` | `/clientes/<int:cliente_id>` | `get_cliente` |
| `POST` | `/clientes` | `create_cliente` |
| `PUT` | `/clientes/<int:cliente_id>` | `update_cliente` |
| `DELETE` | `/clientes/<int:cliente_id>` | `delete_cliente` |
| `GET` | `/categorias-produto` | `get_categorias_produto` |
| `GET` | `/categorias-produto/<int:categoria_id>` | `get_categoria_produto` |
| `POST` | `/categorias-produto` | `create_categoria_produto` |
| `PUT` | `/categorias-produto/<int:categoria_id>` | `update_categoria_produto` |
| `DELETE` | `/categorias-produto/<int:categoria_id>` | `delete_categoria_produto` |
| `GET` | `/produtos` | `get_produtos` |
| `GET` | `/produtos/<int:produto_id>` | `get_produto` |
| `POST` | `/produtos` | `create_produto` |
| `PUT` | `/produtos/<int:produto_id>` | `update_produto` |
| `DELETE` | `/produtos/<int:produto_id>` | `delete_produto` |
| `GET` | `/fornecedores` | `get_fornecedores` |
| `GET` | `/fornecedores/<int:fornecedor_id>` | `get_fornecedor` |
| `POST` | `/fornecedores` | `create_fornecedor` |
| `PUT` | `/fornecedores/<int:fornecedor_id>` | `update_fornecedor` |
| `DELETE` | `/fornecedores/<int:fornecedor_id>` | `delete_fornecedor` |
| `GET` | `/estoque` | `get_estoque` |
| `GET` | `/estoque/parametros` | `get_parametros_estoque` |
| `GET` | `/estoque/<int:estoque_id>` | `get_item_estoque` |
| `POST` | `/estoque` | `create_item_estoque` |
| `PUT` | `/estoque/<int:estoque_id>` | `update_item_estoque` |
| `DELETE` | `/estoque/<int:estoque_id>` | `delete_item_estoque` |
| `GET` | `/estoque/<int:estoque_id>/historico` | `get_historico_estoque` |
| `GET` | `/movimentacoes-estoque` | `get_movimentacoes_estoque` |
| `GET` | `/movimentacoes-estoque/<int:movimentacao_id>` | `get_movimentacao_estoque` |
| `POST` | `/movimentacoes-estoque` | `create_movimentacao_estoque` |
| `GET` | `/compras` | `get_compras` |
| `GET` | `/compras/<int:compra_id>` | `get_compra` |
| `POST` | `/compras` | `create_compra` |
| `PUT` | `/compras/<int:compra_id>` | `update_compra` |
| `DELETE` | `/compras/<int:compra_id>` | `delete_compra` |
| `GET` | `/vendas` | `get_vendas` |
| `GET` | `/vendas/catalogo` | `catalogo_pdv` |
| `POST` | `/vendas/balcao` | `concluir_pdv` |
| `GET` | `/vendas/<int:venda_id>` | `get_venda` |
| `POST` | `/vendas` | `create_venda` |
| `PUT` | `/vendas/<int:venda_id>` | `update_venda` |
| `DELETE` | `/vendas/<int:venda_id>` | `delete_venda` |
| `GET` | `/receitas` | `get_receitas` |
| `GET` | `/receitas/<int:receita_id>` | `get_receita` |
| `POST` | `/receitas` | `create_receita` |
| `PUT` | `/receitas/<int:receita_id>` | `update_receita` |
| `DELETE` | `/receitas/<int:receita_id>` | `delete_receita` |
| `GET` | `/alertas` | `get_alertas` |
| `GET` | `/alertas/<int:alerta_id>` | `get_alerta` |
| `POST` | `/alertas` | `create_alerta` |
| `PUT` | `/alertas/<int:alerta_id>` | `update_alerta` |
| `DELETE` | `/alertas/<int:alerta_id>` | `delete_alerta` |
| `GET` | `/configuracoes/visual` | `get_configuracoes_visuais` |
| `GET` | `/configuracoes` | `get_configuracoes` |
| `PUT` | `/configuracoes` | `save_configuracoes` |
| `GET` | `/configuracoes/<string:chave>` | `get_configuracao` |
| `POST` | `/configuracoes` | `create_configuracao` |
| `PUT` | `/configuracoes/<string:chave>` | `update_configuracao` |
| `DELETE` | `/configuracoes/<string:chave>` | `delete_configuracao` |
| `GET` | `/dashboard/stats` | `get_dashboard_stats` |
| `GET` | `/relatorios/estoque` | `relatorio_estoque` |
| `GET` | `/relatorios/vencimentos` | `relatorio_vencimentos` |
| `GET` | `/relatorios/compras` | `relatorio_compras` |
| `GET` | `/pages/sistema/<path:filename>` | `serve_sistema_page` |
| `GET` | `/pages/proprietario/<path:filename>` | `serve_sistema_page` |
| `GET` | `/<path:filename>` | `serve_frontend_asset` |
| `GET` | `/financeiro/stats` | `financeiro_stats` |
| `GET` | `/financeiro/fluxo` | `financeiro_fluxo` |
| `GET` | `/financeiro/categorias` | `financeiro_categorias` |
| `GET` | `/financeiro/transacoes` | `financeiro_transacoes` |
| `POST` | `/financeiro/transacoes` | `create_financeiro_transacao` |
