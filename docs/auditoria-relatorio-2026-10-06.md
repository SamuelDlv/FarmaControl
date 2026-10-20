# Relatório de auditoria e refatoração — 06/10/2026

> **Registro histórico.** Revisão documental em 19/10/2026: os resultados e complementos abaixo pertencem às datas em que foram registrados. A matriz de permissões já é aplicada no código atual, o frontend deixou a SPA e `frame_analysis.js` foi removido. Caminhos de backups/evidências locais podem não existir após a limpeza. Use o [índice atual](README.md) para instalação, arquitetura e validação; não interprete números antigos como uma nova execução de testes.

A varredura mapeou a estrutura, dependências, 80 rotas declaradas, 20 tabelas do schema principal, migrações, telas e integrações. Foram aplicadas correções compatíveis e uma refatoração gradual da infraestrutura compartilhada. A autorização efetiva continua usando as regras fixas; a correção das rotas raiz de compras e fornecedores foi expressamente autorizada.

## Melhorias aplicadas

| Área | Problema e correção |
|---|---|
| Autorização | `/compras` e `/fornecedores` não eram reconhecidas pelo teste de prefixo. Agora a coleção e os itens aceitam os mesmos cinco perfis previstos, sem liberar nomes parecidos nem outros perfis. |
| Financeiro | A data enviada pelo cliente era interpolada diretamente no SQL. Passou a ser parâmetro; ausência de data continua usando NOW() do banco. |
| Financeiro | Valores não numéricos lançavam exceção antes do tratamento. Valores inválidos, NaN e infinito retornam erro JSON 400 com a mensagem existente. |
| Estoque | Fornecedor recebido como inteiro passava pela validação e falhava no `.isdigit()`. Inteiros e strings numéricas agora seguem o mesmo fluxo. |
| Estáticos | Dois handlers repetiam validação, leitura, MIME e cache. Um helper compartilha essa lógica, preservando URLs, respostas e cache; a validação da raiz usa caminhos completos. |
| Relatório de estoque | Removida consulta de vencimentos cujo resultado era atribuído e nunca utilizado. Mantidos campos, valores e cálculo de giro da resposta. |
| Ciclo de vida | Oito cópias do registro/limpeza de temporizadores foram substituídas por `page-lifecycle.js`, mantendo os nomes legados. Timers concluídos deixam o registro. |
| Eventos | Listeners de telas registrados em document/window agora são descartados ao sair. O botão persistente de recolher sidebar recebe somente um listener. |
| Modais | A limpeza da SPA passou a preservar os modais da nova `.main`, removendo apenas os externos da tela antiga. |
| CSS na navegação | A folha da tela inicial é descartada após o primeiro swap. Folhas novas mantêm a ordem do documento, antes dos overrides globais, independentemente da ordem da rede. A responsividade compartilhada fica carregada uma vez. |
| Falha de recurso | O timeout/rejeição de recurso aciona o fallback de carregamento completo existente, em vez de seguir silenciosamente sem a folha esperada. |
| Dashboard | O indicador inicial fora de `.main` é removido na navegação; ele não reaparece como texto sem estilo após descarte do CSS. |
| Requisições | O wrapper fetch adiciona credenciais/CSRF somente à origem da API. Recursos externos preservam as opções originais do chamador. |
| Documentação | READMEs passam a descrever Flask/MySQL, cookie/CSRF, diretórios e rotas reais. Documentação do banco confrontada com SQL local; guia de estudo identificado como material histórico. |
| Comentários | Responsabilidades e integração das telas, runtime, SQL parametrizado, limites de autorização e regras legadas foram documentados. Corrigidas afirmações obsoletas sobre pool, localStorage, timeout e giro de estoque. |

## Duplicações, conflitos e otimizações

- Eliminadas oito definições repetidas de infraestrutura de timers e a duplicação dos dois handlers de estáticos.
- Removidos import sem uso (`send_from_directory`), variáveis locais sem uso no shell e a consulta de relatório sem efeito na resposta.
- Evitado acúmulo de listeners, timers pendentes de telas antigas, CSS inicial e reinserção da folha responsiva compartilhada.
- O inventário textual detectou **513 blocos CSS presentes em mais de um arquivo**. Isso é uma lista de candidatos, não prova de redundância: o mesmo texto pode estar em media queries/ordens diferentes. Os CSSs não foram consolidados automaticamente, preservando a cascata e a identidade visual.
- Nomes de funções repetidos entre scripts foram inventariados. Alguns pertencem a escopos locais, outros são globais consumidos por handlers inline; não foram renomeados em massa.
- `frame_analysis.js`, favicons em caminhos distintos, APIs sem consumidor visível na UI e todas as migrações foram preservados. Ausência de import estático não prova desuso.

## Validações executadas

| Verificação | Resultado |
|---|---|
| Python / imports | 3 arquivos Python compilados em memória; app importado com conexão real bloqueada. |
| Regressões do backend | **31 testes aprovados**, com subcasos de perfis/métodos. Cobrem sessão, CSRF, revogação, login, aceites, rollback, estáticos, parâmetros SQL, valores inválidos, fornecedor, relatório, retenção de histórico, filtros, ajuste de estoque, migrações sem DDL em runtime, SMTP TLS, convite administrativo e exclusão de conta sem histórico operacional. |
| Contrato de rotas | As **80 rotas declaradas** mantêm método, caminho e nome de endpoint. Alias `/pages/proprietario/` preservado. |
| Sintaxe JavaScript | **35 scripts**, incluindo inline, analisados pelo runtime JavaScript. |
| Runtime frontend | **8 testes aprovados**: limpeza de timers/listeners, inicialização única, CSRF, Request/headers e opções de origem externa. |
| HTML / referências | **12 arquivos HTML**, sem recursos locais ausentes e sem IDs duplicados detectados. |
| Navegador | **18 carregamentos diretos** (9 telas × desktop/celular) comparados ao snapshot, sem diferenças nas propriedades computadas verificadas. |
| Navegação SPA | **12 navegações**, comparando estilos com carregamento direto, modais, ausência de CSS antigo e funcionamento único do botão de recolher. |
| Menu móvel | Abertura e fechamento por Escape aprovados; captura inspecionada após a correção do indicador residual. |
| Exceções do navegador | Nenhuma exceção JavaScript registrada nos cenários executados. |

Os testes de regressão reproduziram as falhas de autorização, fornecedor numérico, data SQL e valor financeiro antes das correções.

### Limites das validações

O navegador usou APIs simuladas com listas vazias e substitutos para fontes/Chart.js, sem consultar a instância real. A comparação cobre propriedades computadas de componentes, não cada pixel ou todos os estados, conteúdos e cores possíveis. Não foram validados CRUDs completos com dados reais, execução de SQL pelo MySQL, concorrência, filtros com históricos extensos ou o Chart.js externo.

Ambiente usado: Python 3.12.10 e Node 24.21.0 incluído no VS Code. Pacotes instalados: Flask 3.1.0, Flask-Cors 5.0.0, PyMySQL 1.2.0, python-dotenv 1.0.1, Werkzeug 3.1.8 e bcrypt 5.0.0. **Essas versões diferem de requirements.txt**; os pins existentes foram preservados e não houve instalação/atualização. Falta repetir a suíte em ambiente descartável criado a partir dos requisitos declarados.

## Pontos que exigem decisão ou trabalho futuro

1. **Permissões editáveis (implementado em 06/10):** middleware consulta `perfil_permissoes` para perfis editáveis e o login fornece a mesma lista ao menu. A migração 006 completa os módulos Financeiro e Vendas em instalações existentes. Usuários precisam entrar novamente para o menu refletir uma alteração já salva.
2. **Cadastro administrativo e aceite (implementado em 07/10):** a tela Usuários cria convite, não uma conta. O e-mail enviado permite aceitar ou recusar; ao aceitar, a pessoa abre uma tela exclusiva, define a própria senha e marca os dois aceites. Por ter sido convidada por administrador autenticado, a conta é criada já aprovada e entra diretamente no sistema. O modal administrativo confirma o envio. A migração 008 cria a tabela de convites, que armazena apenas o hash do token e expira em sete dias.
3. **Autoria de operações (implementado em 06/10):** estoque, movimentações, compras, vendas e financeiro atribuem autoria a `g.usuario_id`, derivado da sessão. O campo `usuario_id` enviado pelo cliente deixou de fazer parte desses contratos; atualizações preservam o autor original e atribuem movimentações decorrentes à sessão que as executou.
4. **Histórico e concorrência (implementado em 06/10):** lotes com movimentações não podem mais ser excluídos, preservando a trilha de auditoria. Ajustes agora aceitam deltas positivos ou negativos, sem permitir saldo abaixo de zero; transferências exigem lote destino do mesmo produto e registram os dois lados. Leituras que antecedem alteração de saldo usam `FOR UPDATE`; compras recebidas e vendas concluídas não podem regredir de status — devoluções devem ser registradas como operação de estoque.
5. **Filtros de movimentações (implementado em 06/10):** `/movimentacoes-estoque` aplica `produto_id`, `tipo` e `periodo_dias`, com limite configurável e validado (até 5.000).
6. **Alertas e schema (implementado em 06/10):** a migração 007 cria `aceites_legais` e `configuracoes_sistema` e complementa instalações existentes de `alertas` com `resolvido_em`/`resolvido_por_usuario_id`, índice e chave estrangeira. O DDL foi removido dos fluxos de cadastro e configurações. A resolução de alerta usa o usuário autenticado, não um ID enviado pelo cliente. Notificações de cadastro e análise usam SMTP TLS da Brevo quando as credenciais de ambiente existem; falhas de envio não revertem a transação. Aplique e revise a migração em ambiente isolado antes de atualizar a instância.
7. **Financeiro (implementado em 08/10):** o filtro de tipo agora restringe `financeiro_categorias` após o `LEFT JOIN`, preservando categorias sem movimentações somente do tipo solicitado. As leituras não disfarçam falhas de banco como resultados vazios: schema ausente responde 503 e falha de consulta responde 500 com `ok: false`; a tela exibe o estado de erro. Os parâmetros de período, tipo e limite também são validados/limitados.
8. **Renderização de dados (implementado em 08/10):** a tela Financeiro escapa qualquer valor textual vindo da API antes de interpolá-lo em `innerHTML`, tanto em texto quanto no atributo `value` de opções. O toast compartilhado passou a inserir sua mensagem com `textContent`. A revisão foi aplicada aos pontos que processam dados financeiros; outras telas ainda devem seguir o mesmo padrão antes de novas interpolações de dados externos.
9. **Configuração e dependências (implementado em 08/10):** `runtime_config.py` valida ambiente, chave, debug, cookies, sessão e origens. Debug fica desligado e o servidor local escuta somente em loopback; produção exige chave persistente de pelo menos 32 caracteres, cookies seguros, HTTPS nas origens CORS e servidor WSGI. Não há segredo fixo de fallback: desenvolvimento sem chave válida usa chave aleatória temporária, com aviso e expiração das sessões ao reiniciar. CORS é desabilitado por padrão, sem expansão de `*` ou aceitação de `null`; a API usa a origem da página. Dependências diretas e transitivas foram alinhadas às versões instaladas e verificadas em `.venv-audit`, criado a partir de `requirements.txt`: `pip check` passou e os 39 testes Python passaram. `.env` e credenciais existentes não foram alterados.
10. **Navegação e estado (implementado em 08/10):** o mecanismo de troca manual de HTML/CSS/scripts foi substituído por navegação nativa entre documentos completos. Assim, funções homônimas de telas diferentes não compartilham o contexto, não há watchdog e Voltar/Avançar usa o histórico real do navegador. Tema e estado da sidebar permanecem persistidos. Leituras da API recebem sinal de cancelamento da tela, combinado com eventual sinal do chamador; `pagehide` cancela leituras e descarta listeners/timers. Restaurações do bfcache recarregam a tela para obter dados atuais. A navegação passa a recarregar cada documento; formulários não enviados não são persistidos pela aplicação. Validação: 11 testes frontend; Chrome isolado com 18 aberturas desktop/mobile, 12 trocas de tela, histórico real, envio de transação simulado, modais, resposta lenta cancelada e navegação rápida. Nenhuma exceção no navegador; APIs/CDNs simuladas, sem CRUD em banco real.
11. **CSS/temas (implementado em 08/10):** removidos os seletores condicionais, superfícies e geradores de paleta remanescentes do tema escuro. A aparência é exclusivamente clara, com cores de destaque e densidades preservadas. Chaves legadas de seleção de tema são descartadas dos caches locais e deixam de ser expostas/aceitas pela API; a migração opcional 011 limpa somente essas chaves em instalações existentes (não executada). Foram extraídas 36 regras idênticas de estrutura, sidebar, badges e interação para `styles/system-shell.css`, carregado antes dos estilos locais nas nove telas. As variações de cada página e suas media queries foram preservadas. Comparação antes/depois: 144 cenários de estilos computados, em 1440/860/390 px, com sidebar expandida/recolhida/móvel, modais, toasts, seis paletas e uma cor personalizada, três densidades e preferência do sistema operacional por modo escuro; nenhuma diferença ou exceção. Testes: 41 backend e 13 frontend passaram. APIs e fontes simuladas, sem validação de banco real ou de todos os conteúdos possíveis.

## Evidências e reprodução

Complemento do item 11: `node scripts/check_theme.cjs baseline` registra a referência **antes** de uma alteração visual; `node scripts/check_theme.cjs verify` compara o estado posterior. Evidências de 08/10: `.audit-backup/theme-cleanup/theme-baseline.json`, `theme-verify.json` e capturas de estoque desktop/mobile. Os tons fortes dos botões, overlays e identidade visual da sidebar permanecem porque pertencem à aparência clara atual.

Complemento de 08/10 (itens 9–10): `tests/test_runtime_config.py`, `tests/frontend.test.cjs` e `scripts/check_navigation.cjs`. Execute `.venv-audit\Scripts\python.exe -B -m unittest discover -s tests`, `.venv-audit\Scripts\python.exe -m pip check`, `node --test tests/frontend.test.cjs` e `node scripts/check_navigation.cjs`. Evidência local: `.audit-backup/navigation/browser-navigation.json`. O verificador `check_browser.cjs` descrito abaixo pertence à antiga SPA; os pins mencionados na validação original de 06/10 foram substituídos pelo ambiente reproduzível descrito no item 9. As versões foram alinhadas e testadas, sem alegação de auditoria de vulnerabilidades dos pacotes.

- [Mapeamento prévio](auditoria-mapeamento-2026-10-06.md) e [inventário estático](auditoria-estatica-2026-10-06.json).
- `tests/test_backend.py`, `tests/frontend.test.cjs` e `tests/fixtures/api_routes.json`.
- `scripts/check_frontend.cjs`, `scripts/audit_static.py` e `scripts/check_browser.cjs`.
- Evidências locais: `.audit-backup/2026-10-06/browser-before.json`, `browser-after.json` e `estoque-mobile-after.png`.
- Originais: `.audit-backup/2026-10-06/original.zip`, manifesto SHA-256 e `changes.patch`. Nenhum `.env` foi incluído na cópia.

Não há diretório Git nesta cópia. Não foram realizados deploys, operações externas de escrita, conexão ao banco, execução de migrações ou remoção de arquivos originais. A reversão pode ser revisada por arquivo contra o snapshot.

## Arquivos alterados e adicionados

**30 arquivos existentes alterados:**

- .gitignore
- README.md
- backend/README.md
- backend/app.py
- backend/requirements.txt
- docs/database_schema_design.md
- frontend/README.md
- frontend/src/pages/auth/README.md
- frontend/src/pages/auth/auth.js
- frontend/src/pages/sistema/compras/compras.html
- frontend/src/pages/sistema/compras/compras.js
- frontend/src/pages/sistema/configuracoes/configuracoes.html
- frontend/src/pages/sistema/configuracoes/configuracoes.js
- frontend/src/pages/sistema/dashboard/dashboard.html
- frontend/src/pages/sistema/dashboard/dashboard.js
- frontend/src/pages/sistema/estoque/estoque.html
- frontend/src/pages/sistema/estoque/estoque.js
- frontend/src/pages/sistema/financeiro/financeiro.html
- frontend/src/pages/sistema/financeiro/financeiro.js
- frontend/src/pages/sistema/relatorios/relatorios.html
- frontend/src/pages/sistema/relatorios/relatorios.js
- frontend/src/pages/sistema/usuarios/usuarios.html
- frontend/src/pages/sistema/usuarios/usuarios.js
- frontend/src/pages/sistema/vencimentos/vencimentos.html
- frontend/src/pages/sistema/vencimentos/vencimentos.js
- frontend/src/utils/global-settings.js
- frontend/src/utils/sidebar-init.js

**10 arquivos adicionados:**

- docs/auditoria-estatica-2026-10-06.json
- docs/auditoria-mapeamento-2026-10-06.md
- docs/auditoria-relatorio-2026-10-06.md
- frontend/src/utils/page-lifecycle.js
- scripts/audit_static.py
- scripts/check_browser.cjs
- scripts/check_frontend.cjs
- tests/fixtures/api_routes.json
- tests/frontend.test.cjs
- tests/test_backend.py
