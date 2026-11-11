# Referência da API

Consolidada em **11/11/2026**, com inventário de rotas revisado em **23/10/2026** a partir dos registros de rotas em `backend/farmacontrol/routes/`. Os caminhos não possuem prefixo `/api`. Em desenvolvimento a origem é `http://localhost:5000`; o frontend usa a mesma origem da página.

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

A política de 11/11/2026 separa 5 falhas por conta em 300 segundos, 100 mutações de autenticação por IP/processo em 300 segundos e 5 solicitações por operação/IP para cadastro, recuperação, redefinição e recusa. Logout fica fora dessas cotas e preserva origem, CSRF e auditoria. Respostas de bloqueio incluem `limite_escopo`, `tentativas_restantes`, `aguarde_segundos` e `Retry-After`. Consulte [segurança e permissões](seguranca.md).

O acesso direto aos HTMLs internos em `/pages/sistema/` e no alias `/pages/proprietario/` também exige sessão e permissão. Sem sessão válida, a resposta é 302 para `/pages/acesso/acesso.html`; sem permissão, 403; indisponibilidade na validação, 503. Essas respostas e o HTML interno usam `Cache-Control: no-store`. A rota genérica de arquivos aplica a mesma proteção pelo destino físico. APIs continuam usando 401 para sessão inválida, sem redirecionamento HTTP.

O middleware consulta o usuário e a matriz de módulos em cada requisição protegida. `/configuracoes/visual` é leitura pública. O conjunto de rotas de vendas/clientes/receitas usa perfis comerciais fixos; log é reservado a proprietário, admin e TI. Visualizador nunca pode executar mutações protegidas.

Mapeamento principal: `/admin/` → usuários; `/financeiro/` → financeiro; `/relatorios/` → relatórios; compras/fornecedores → compras; alertas → vencimentos; estoque/movimentações/produtos/categorias → estoque; dashboard → dashboard; configurações → configurações. Detalhes em [backend](../backend/README.md).

## Contratos operacionais principais

### Catálogo e estoque

`/produtos` usa campos como `tipo_produto`, `exige_validade`, `estoque_minimo` e `fornecedor_id`, além dos dados comerciais. `/estoque` recebe campos do lote e os equivalentes de cadastro com prefixo `produto_`; `produto_id` permite usar um cadastro existente. PUT de produto é parcial e preserva campos omitidos conforme o handler.

Medicamentos e outros produtos possuem regras diferentes; consulte [banco](banco-de-dados.md). Não interprete uma categoria como autorização para omitir validade ou marcar receita.

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

O servidor admite de 1 a 100 lotes distintos e compara o preço enviado ao preço atual do banco. Recalcula o total e confirma os efeitos numa transação. Sucesso retorna `id` e `valor_total` com status 201. Receita exigida depende de confirmação booleana `true`. Formas aceitas: dinheiro, pix, cartão de crédito e débito com os slugs documentados em [PDV](operacao.md#pdv).

### Permissões

`PUT /admin/perfis/permissoes` recebe um objeto `perfis`, mapeando slugs de perfil para listas de módulos. Para cada perfil enviado, a lista substitui as permissões existentes; não é apenas uma adição. Módulos desconhecidos são recusados. Alterar essa matriz pode retirar o acesso do próprio perfil administrador.

### Configurações

`PUT /configuracoes` recebe `configuracoes` com as chaves editáveis. `backend/farmacontrol/services/system_settings.py` define tipos e limites. As antigas chaves `tema` e `tema_efetivo` não são configurações ativas e sua leitura/gravação individual retorna 410. Opções de idioma/moeda não realizam tradução ou conversão financeira.

### Histórico

`GET /admin/logs` aceita `limit` até 100, `antes` para paginação por ID, `usuario_id`, `data_inicio`, `data_fim`, `busca`, `atividade` e `incluir_usuarios=1`. Datas usam `YYYY-MM-DD`, incluem o dia no horário de Brasília e não podem ser futuras. `atividade` distingue alterações/acessos de consultas. Não há rota pública para alterar ou excluir eventos do log.

## Inventário de endpoints

A tabela abaixo foi extraída estaticamente dos decoradores do arquivo atual; não exige importar a aplicação nem conectar ao banco. Lista métodos explícitos e GET das rotas estáticas, sem expandir HEAD/OPTIONS automáticos do Flask. Os links apontam ao arquivo de implementação, evitando números de linha que envelhecem a cada edição.

Total: **88 declarações de rota** nos [módulos de rotas](../backend/farmacontrol/routes), registrados por [create_app()](../backend/farmacontrol/__init__.py). URLs, métodos e nomes dos endpoints foram preservados na modularização.

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

<a id="pesquisas"></a>

## Pesquisas e listagens — 04/11/2026

Auditoria e refatoração incremental de 04/11/2026. Escopo: API, sem alterações visuais, de permissões ou de banco.

### Divergências e decisões (antes da implementação)

| Divergência | Classificação | Decisão |
| --- | --- | --- |
| Logs usam keyset por ID; movimentações usam offset e total | Diferença justificada | Preservar navegação de histórico e paginação/exportação dos relatórios |
| Logs usam LOCATE em três campos; movimentos usam LIKE no produto | Diferença justificada | Preservar campos e operadores; documentar curingas |
| Conversão de produto_id/periodo_dias inválidos elimina filtros; limite/offset inválidos voltam ao padrão | Inconsistência que precisa de correção | Parsing explícito; 400 com campo, sem executar a consulta de domínio |
| Busca de movimentos sem tamanho máximo | Inconsistência que precisa de correção | Limite de 120 caracteres, como logs |
| Limites numéricos de logs/financeiro são ajustados à faixa, movimentos rejeitam fora da faixa | Diferença de contrato preservada na transição | Helper compartilhado com política explícita; não mudar chamadas válidas |
| Transações financeiras não desempataram registros na mesma data | Inconsistência que precisa de correção | Acrescentar ID decrescente |
| Limite financeiro malformado assume padrão | Inconsistência que precisa de correção | 400 para vazio/não inteiro; manter ajuste numérico legado |
| Metadados de paginação incompletos | Oportunidade de melhoria | Campos aditivos; preservar chaves antigas e cálculo opcional de total |
| Clientes/fornecedores/produtos/estoque/compras retornam listas completas | Oportunidade de melhoria sem urgência comprovada | Não truncar listas usadas para filtros, seletores e exportação; futura migração precisa adaptar consumidores |
| Agregados financeiros aceitam days inválido e usam fallback | Oportunidade de melhoria | Preservar nesta etapa e documentar |
| Outras listas sem desempate ou ordem SQL | Oportunidade de melhoria | Inventariar; evitar reescrita global |

### Inventário dos GET de listagem, pesquisa e agregação

Todas as respostas abaixo incluem `ok`. Sem parâmetros significa que não há filtro por query string implementado; não significa acesso público. O middleware continua validando sessão, conta, módulo e regras específicas de PDV/log.

| Endpoint | Parâmetros/filtros atuais | Resposta principal | Ordem/volume atuais e consumidor |
| --- | --- | --- | --- |
| /movimentacoes-estoque | produto_id, tipo, periodo_dias, periodo, busca, limite, offset | movimentacoes; total quando offset informado | data_movimentacao DESC, id DESC; relatórios paginam e exportam em lotes |
| /admin/logs | limit, antes, usuario_id, data_inicio, data_fim, busca, atividade, incluir_usuarios | logs, proximo, filtros; usuarios opcional | id DESC; tela de log usa cursor e filtros no servidor |
| /financeiro/transacoes | days, limit | transacoes | data_transacao DESC, id DESC; lista limitada na tela financeira, sem navegação por páginas |
| /clientes | nenhum | clientes | Sem ORDER BY/limite; API de cadastro, sem busca textual de servidor |
| /fornecedores | nenhum | fornecedores | Sem ORDER BY/limite; compras e estoque carregam a lista para seleção e filtro local |
| /categorias-produto | nenhum | categorias | Sem ORDER BY/limite; listas auxiliares/seletores |
| /produtos | nenhum | produtos | Sem ORDER BY/limite; estoque, vencimentos e relatórios usam catálogo completo |
| /estoque | nenhum | estoque | Validades não nulas primeiro, validade ASC; listas e filtros locais em estoque/vencimentos/dashboard/relatórios |
| /estoque/<id>/historico | ID no caminho | historico | data_movimentacao DESC, LIMIT 50; sem cursor/offset; desempate futuro |
| /estoque/parametros | nenhum | parametros | Configuração finita usada por estoque |
| /compras | nenhum | compras com itens | criado_em DESC; filtro/paginação locais; consulta adicional de itens por IDs |
| /vendas | nenhum | vendas | Sem ORDER BY/limite; API de listagem, distinta do catálogo PDV |
| /vendas/catalogo | nenhum; somente produtos ativos no SQL | produtos por lote | nome e validade; PDV filtra termos, tipo e disponibilidade localmente |
| /receitas | nenhum | receitas | Sem ORDER BY/limite; API de cadastro |
| /alertas | nenhum | alertas | Sem ORDER BY/limite; listagem de alertas |
| /admin/usuarios | nenhum | usuarios | nome ASC; pesquisa/filtros da tela de usuários locais |
| /admin/pendentes | status pendente fixo no SQL | pendentes | criado_em ASC; análise administrativa |
| /admin/perfis/permissoes | nenhum | perfis, modulos | Ordem fixa dos perfis e módulo; conjunto pequeno |
| /financeiro/stats | days: 7/30/90, padrão/fallback 30 | saldo, receitas, despesas, ticket_medio, deltas, spark | Agregados; spark ordenado por dia; sem paginação |
| /financeiro/fluxo | days: 7/30/90, padrão/fallback 7; start_date/end_date juntos | labels, dias, receitas, despesas, periodo | Calendário ASC; datas explícitas substituem days |
| /financeiro/categorias | days: 7/30/90, padrão/fallback 30; tipo receita/despesa opcional | categorias | valor DESC; agregação por categoria |
| /relatorios/estoque | periodo: month/quarter/year, padrão month | kpis, resumo, por_categoria, top_produtos, evolucao, periodo | Categorias por quantidade DESC; top 10 por quantidade/nome; evolução por mês |
| /relatorios/vencimentos | nenhum | kpis | Contagens por faixa de validade; sem paginação |
| /relatorios/compras | periodo: month/quarter/year, padrão month | kpis, fornecedores, categorias, evolucao | Fornecedores por valor DESC/ID, categorias por valor DESC, evolução por mês |
| /dashboard/stats | nenhum | KPIs, séries e listas auxiliares | Agregações e ordens fixas por série; top produtos limitado a 5 |
| /configuracoes | nenhum | configuracoes | Lista de configurações, com email_disponivel; sem paginação |
| /configuracoes/visual | allowlist fixa de chaves visuais | configuracoes | Lista finita pública usada antes do login |

GET de detalhe por ID em clientes, fornecedores, categorias, produtos, estoque, movimentações, compras, vendas, receitas e alertas retornam um registro, não páginas. GET de configuração por chave, convite por token, health e páginas/assets não são operações de pesquisa. Nenhuma dessas rotas foi alterada.

A auditoria confrontou handlers, `tests/fixtures/api_routes.json`, testes HTTP e chamadas em `frontend/src/pages/sistema/`. Não introduzir paginação automática em clientes/fornecedores nesta etapa: os seletores de compras/estoque não percorrem páginas. Buscas locais do PDV normalizam termos no JavaScript; isso não equivale à comparação SQL.

### Convenções compartilhadas

Aplicadas aos campos migrados: busca, limite/limit, offset, antes, produto_id e periodo_dias. Os demais filtros preservam suas validações específicas.

`core/query.py` contém apenas parsing de inteiros e texto. Não recebe tabelas, colunas ou SQL do cliente. Rotas continuam usando `core.responses`, SQL próprio e allowlists existentes para tipo/período/atividade. Não foi criada ordenação arbitrária por parâmetro.

- Inteiro ausente: padrão da rota ou ausência do filtro opcional.
- Inteiro presente vazio, decimal, não numérico ou com separadores como `1_000`: HTTP 400, `ok:false`, `mensagem`, `campo`.
- Espaços nas bordas de inteiros e busca são removidos. Espaços internos do texto são preservados para não mudar a semântica das pesquisas.
- Busca ausente/vazia/só espaços não adiciona filtro; até 120 caracteres Unicode após trim. Acima disso: 400 no campo busca.
- Query strings repetidas preservam o primeiro valor, como Werkzeug já fazia.
- Parâmetros desconhecidos continuam ignorados; não foi introduzida rejeição global.
- Campos numéricos sem teto de domínio específico aceitam no máximo 9223372036854775807.
- Uma lista vazia é sucesso 200. Parâmetro inválido é 400. Erro operacional permanece 500 (movimentações/financeiro) ou 503 (logs e indisponibilidade das tabelas financeiras).

### Contratos preservados e adições

#### Movimentações

`produto_id`: inteiro positivo opcional. `periodo_dias`: 1 a 3650 opcional.
`tipo`: entrada/saida/ajuste/transferencia; ausente ou vazio não filtra.
`periodo`: month/quarter/year opcional; vazio/inválido rejeitado.
Período relativo e calendário, quando fornecidos juntos, são combinados por AND.
`limite`: padrão 1000, faixa 1 a 5000, fora da faixa retorna 400.
`offset`: padrão 0, não negativo. Continua sendo posição, não número da página.

Busca apenas `p.nome LIKE %s`, com o valor `%termo%` vinculado.
**Compatibilidade:** `%` e `_` continuam curingas de LIKE; esta API não promete busca literal desses caracteres. Aspas não viram SQL. O comportamento de barra invertida depende do modo SQL do servidor. Nenhum operador foi trocado.

Retorna `movimentacoes`, com `limite` e `offset` adicionados.
Quando o cliente envia offset (inclusive zero), retorna também:
`total` (já existente), `tem_mais` e `proximo_offset` (inteiro ou null).
A contagem usa os mesmos filtros da consulta. Sem offset explícito não executa COUNT e não afirma se existe próxima página.

Exemplo de página vazia:
`{"ok":true,"movimentacoes":[],"limite":20,"offset":0,"total":0,"tem_mais":false,"proximo_offset":null}`

#### Logs

Preserva `limit` (padrão 50), `antes` (padrão 0), `proximo`, filtros e usuarios opcionais.
Limites numéricos são ajustados para 1..100 como antes, inclusive zero/negativos; texto/vazio retorna 400.
`antes` não negativo; consulta `id < antes ORDER BY id DESC LIMIT limit+1`.
A linha extra determina a próxima página; não usa COUNT.
Adiciona `limite` aplicado e `tem_mais`; `proximo` é null no fim.
Datas mantêm AAAA-MM-DD, intervalo válido, sem futuro e conversão Brasília→UTC.
Busca usa LOCATE em acao/detalhes/usuario_nome; `%`, `_` e aspas são literais.
As permissões exclusivas do log permanecem no middleware.

#### Transações financeiras

Preserva `limit` (padrão 50, números ajustados para 1..500).
Valores vazios/não inteiros agora retornam 400 antes da consulta às tabelas.
Preserva days 7/30/90 com fallback 30; esse legado não foi alterado nos agregados.
Acrescenta `limite` à resposta e `t.id DESC` como desempate.
É uma lista dos registros mais recentes, não uma API de páginas: não recebe offset/cursor e não promete total ou próxima página.

### Caixa, acentos e SQL

O schema cria a base com `utf8mb4_unicode_ci`; a migração de logs explicita essa collation. A intenção dessa configuração é comparação sem distinção de caixa e acentos. Bases existentes podem ter collations por coluna diferentes; os handlers não forçam COLLATE nem removem acentos.

Testes unitários confirmam que Unicode e caracteres SQL chegam como parâmetros, não interpolação. Isso não confirma equivalência entre LIKE e LOCATE nem resultados de collation em MySQL/MariaDB. A validação real deve consultar `SHOW FULL COLUMNS` nas colunas pesquisadas e comparar, por exemplo, ação/ACAO/Ação, aspas e curingas em uma base isolada com a mesma versão e sql_mode da implantação.

### Índices e desempenho

Revisão estática: logs têm PK(id) e `idx_log_usuario(usuario_id,id)`; financeiro tem `idx_data(data_transacao)`; movimentos têm PK e vínculos por estoque/usuário. Não foi adicionada migração nem dependência.

Antes de propor novos índices, executar EXPLAIN das consultas efetivas com dados representativos: logs com/sem autor e datas; movimentos com produto, tipo e período; transações por data/ID. Avaliar candidatos em movimentos (data_movimentacao,id) e (estoque_id,data_movimentacao,id), conforme seletividade e custo de gravação. Não afirmar ganho sem medir.

LIKE com curinga inicial e LOCATE podem exigir varredura; índice B-tree comum no nome não resolve automaticamente. OFFSET profundo e COUNT filtrado continuam custosos. O total só é calculado quando solicitado pelo contrato legado. Listas completas e calendário financeiro com intervalo explícito amplo continuam oportunidades de uma próxima etapa coordenada com consumidores.

Ordenação estável evita ambiguidade de empates em dados estáveis. Offset não garante ausência de duplicação/perda se houver inserções/exclusões concorrentes; lista e total também não são prometidos como snapshot atômico. Cursor de logs preserva a estratégia adequada ao histórico.

### Validação

`tests/test_search.py` cobre parsing, vazios, limites, espaços, Unicode, caracteres SQL, filtros combinados, vinculação de parâmetros, metadados, páginas finais/vazias, cursor, autorização e falhas de banco.
Os testes existentes continuam verificando contratos HTTP, datas e consumidores JavaScript. Integração real, EXPLAIN com volume representativo e renderização em navegador não são substituídos por esses testes.

Resultado em 04/11/2026: 186 testes Python (18 novos) e 25 testes JavaScript aprovados; auditoria estática sem assets ausentes, IDs HTML duplicados ou imports de backend não utilizados. Nenhuma migração foi executada.
