# Pesquisas e listagens do backend

Auditoria e refatoração incremental de 04/11/2026. Escopo: API, sem alterações visuais, de permissões ou de banco.

## Divergências e decisões (antes da implementação)

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

## Inventário dos GET de listagem, pesquisa e agregação

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

## Convenções compartilhadas

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

## Contratos preservados e adições

### Movimentações

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

### Logs

Preserva `limit` (padrão 50), `antes` (padrão 0), `proximo`, filtros e usuarios opcionais.
Limites numéricos são ajustados para 1..100 como antes, inclusive zero/negativos; texto/vazio retorna 400.
`antes` não negativo; consulta `id < antes ORDER BY id DESC LIMIT limit+1`.
A linha extra determina a próxima página; não usa COUNT.
Adiciona `limite` aplicado e `tem_mais`; `proximo` é null no fim.
Datas mantêm AAAA-MM-DD, intervalo válido, sem futuro e conversão Brasília→UTC.
Busca usa LOCATE em acao/detalhes/usuario_nome; `%`, `_` e aspas são literais.
As permissões exclusivas do log permanecem no middleware.

### Transações financeiras

Preserva `limit` (padrão 50, números ajustados para 1..500).
Valores vazios/não inteiros agora retornam 400 antes da consulta às tabelas.
Preserva days 7/30/90 com fallback 30; esse legado não foi alterado nos agregados.
Acrescenta `limite` à resposta e `t.id DESC` como desempate.
É uma lista dos registros mais recentes, não uma API de páginas: não recebe offset/cursor e não promete total ou próxima página.

## Caixa, acentos e SQL

O schema cria a base com `utf8mb4_unicode_ci`; a migração de logs explicita essa collation. A intenção dessa configuração é comparação sem distinção de caixa e acentos. Bases existentes podem ter collations por coluna diferentes; os handlers não forçam COLLATE nem removem acentos.

Testes unitários confirmam que Unicode e caracteres SQL chegam como parâmetros, não interpolação. Isso não confirma equivalência entre LIKE e LOCATE nem resultados de collation em MySQL/MariaDB. A validação real deve consultar `SHOW FULL COLUMNS` nas colunas pesquisadas e comparar, por exemplo, ação/ACAO/Ação, aspas e curingas em uma base isolada com a mesma versão e sql_mode da implantação.

## Índices e desempenho

Revisão estática: logs têm PK(id) e `idx_log_usuario(usuario_id,id)`; financeiro tem `idx_data(data_transacao)`; movimentos têm PK e vínculos por estoque/usuário. Não foi adicionada migração nem dependência.

Antes de propor novos índices, executar EXPLAIN das consultas efetivas com dados representativos: logs com/sem autor e datas; movimentos com produto, tipo e período; transações por data/ID. Avaliar candidatos em movimentos (data_movimentacao,id) e (estoque_id,data_movimentacao,id), conforme seletividade e custo de gravação. Não afirmar ganho sem medir.

LIKE com curinga inicial e LOCATE podem exigir varredura; índice B-tree comum no nome não resolve automaticamente. OFFSET profundo e COUNT filtrado continuam custosos. O total só é calculado quando solicitado pelo contrato legado. Listas completas e calendário financeiro com intervalo explícito amplo continuam oportunidades de uma próxima etapa coordenada com consumidores.

Ordenação estável evita ambiguidade de empates em dados estáveis. Offset não garante ausência de duplicação/perda se houver inserções/exclusões concorrentes; lista e total também não são prometidos como snapshot atômico. Cursor de logs preserva a estratégia adequada ao histórico.

## Validação

`tests/test_search.py` cobre parsing, vazios, limites, espaços, Unicode, caracteres SQL, filtros combinados, vinculação de parâmetros, metadados, páginas finais/vazias, cursor, autorização e falhas de banco.
Os testes existentes continuam verificando contratos HTTP, datas e consumidores JavaScript. Integração real, EXPLAIN com volume representativo e renderização em navegador não são substituídos por esses testes.


Resultado em 04/11/2026: 186 testes Python (18 novos) e 25 testes JavaScript aprovados; auditoria estática sem assets ausentes, IDs HTML duplicados ou imports de backend não utilizados. Nenhuma migração foi executada.
