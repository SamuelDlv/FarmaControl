# Mapeamento anterior à refatoração — 06/10/2026

> **Registro histórico.** Revisado documentalmente em 19/10/2026, com o conteúdo original preservado abaixo. A aplicação atual usa navegação por documentos completos, matriz de permissões efetiva, 24 tabelas e módulos adicionais. Para o estado atual, consulte o [índice](README.md), a [API](API.md) e o [banco](database_schema_design.md). Backups locais citados abaixo foram destinados à limpeza e não são entregáveis do repositório.

Levantamento local antes da primeira alteração. Nenhuma conexão com banco foi aberta.
Não há diretório .git nesta cópia. Originais: .audit-backup/2026-10-06/original.zip (sem .env).

## Estrutura e dependências

- Backend: Python 3.10+, Flask, Flask-Cors, PyMySQL, python-dotenv, bcrypt e Werkzeug. Versões em backend/requirements.txt.
- Banco: MySQL/MariaDB; conexão por requisição em flask.g, sem pool. Transações explícitas com commit/rollback.
- Frontend: HTML/CSS/JavaScript clássico; sem npm/bundler/framework. Nove telas compartilhadas por perfil, autenticação e páginas legais.
- Integrações externas visuais: Google Fonts e Chart.js via CDN.
- Sessão: cookie Flask assinado HttpOnly + CSRF; sessionStorage guarda apresentação e token. localStorage guarda preferências.
- global-settings.js: paleta, preferências, usuário, notificações e wrapper fetch. sidebar-init.js: navegação SPA, cache e menu.
- Scripts das telas reexecutam na navegação; eventos fc-page-unload, fc-page-unloaded e fc-page-ready coordenam ciclo de vida.

## Fluxos e integração

| Tela/fluxo | APIs e comportamento |
|---|---|
| Autenticação | /auth/register cria pendente e aceite; /auth/login valida senha/status e devolve CSRF; /auth/logout limpa sessão |
| Usuários | /admin/usuarios, /admin/pendentes, /admin/analisar-cadastro, /admin/logs; /admin/perfis/permissoes persiste matriz ainda não aplicada ao acesso |
| Dashboard | /dashboard/stats; /estoque para seleção; /movimentacoes-estoque para saídas |
| Estoque | /estoque, /estoque/<id>/historico, /categorias-produto, /fornecedores, /movimentacoes-estoque; produto e lote separados |
| Vencimentos | /estoque e /produtos; baixas por /movimentacoes-estoque e entrada em /estoque |
| Compras | /compras, /fornecedores, /produtos, /relatorios/compras; recebimento soma lote e registra entrada na mesma transação |
| Financeiro | /financeiro/stats, /fluxo, /categorias, /transacoes; compra/venda não cria transação financeira automaticamente |
| Relatórios | /relatorios/estoque, /vencimentos e /compras, consultas de movimentos e exportação no cliente |
| Configurações | /configuracoes (persistência global) e /configuracoes/visual (preferências públicas do login) |
| APIs sem tela própria | /clientes, /vendas, /receitas, /alertas preservadas; ausência de chamadas na UI não prova desuso externo |

## Banco de dados

Schema principal: 20 tabelas: perfis, perfil_permissoes, usuarios, analises_cadastro, log_acessos, clientes, categorias_produto, fornecedores, produtos, estoque, movimentacoes_estoque, compras, itens_compra, vendas, itens_venda, receitas, receitas_itens, configuracoes_sistema, financeiro_categorias, financeiro_transacoes.
Relações: perfis → usuários; produtos → estoque → movimentações; fornecedores → compras → itens; clientes → vendas/receitas; categorias financeiras → transações.
Complementos: migração 004 cria alertas; aceites_legais é criado no cadastro; 003 permite validade nula; 005 repete estrutura financeira e contém carga de demonstração.
As migrações 002 têm numeração duplicada e finalidades distintas. Nenhuma foi executada ou renomeada.

## Rotas preservadas

| Método | Caminho | Função |
|---|---|---|
| GET | /health | health |
| POST | /auth/register | register |
| POST | /auth/login | login |
| POST | /auth/logout | logout |
| GET | /admin/usuarios | listar_usuarios |
| GET | /admin/logs | listar_logs |
| GET | /admin/pendentes | listar_pendentes |
| GET | /admin/perfis/permissoes | listar_permissoes_perfis |
| PUT | /admin/perfis/permissoes | atualizar_permissoes_perfis |
| PUT | /admin/usuarios/<int:usuario_id> | editar_usuario |
| DELETE | /admin/usuarios/<int:usuario_id> | excluir_usuario |
| POST | /admin/analisar-cadastro | analisar_cadastro |
| GET | /clientes | get_clientes |
| GET | /clientes/<int:cliente_id> | get_cliente |
| POST | /clientes | create_cliente |
| PUT | /clientes/<int:cliente_id> | update_cliente |
| DELETE | /clientes/<int:cliente_id> | delete_cliente |
| GET | /categorias-produto | get_categorias_produto |
| GET | /categorias-produto/<int:categoria_id> | get_categoria_produto |
| POST | /categorias-produto | create_categoria_produto |
| PUT | /categorias-produto/<int:categoria_id> | update_categoria_produto |
| DELETE | /categorias-produto/<int:categoria_id> | delete_categoria_produto |
| GET | /produtos | get_produtos |
| GET | /produtos/<int:produto_id> | get_produto |
| POST | /produtos | create_produto |
| PUT | /produtos/<int:produto_id> | update_produto |
| DELETE | /produtos/<int:produto_id> | delete_produto |
| GET | /fornecedores | get_fornecedores |
| GET | /fornecedores/<int:fornecedor_id> | get_fornecedor |
| POST | /fornecedores | create_fornecedor |
| PUT | /fornecedores/<int:fornecedor_id> | update_fornecedor |
| DELETE | /fornecedores/<int:fornecedor_id> | delete_fornecedor |
| GET | /estoque | get_estoque |
| GET | /estoque/<int:estoque_id> | get_item_estoque |
| POST | /estoque | create_item_estoque |
| PUT | /estoque/<int:estoque_id> | update_item_estoque |
| DELETE | /estoque/<int:estoque_id> | delete_item_estoque |
| GET | /estoque/<int:estoque_id>/historico | get_historico_estoque |
| GET | /movimentacoes-estoque | get_movimentacoes_estoque |
| GET | /movimentacoes-estoque/<int:movimentacao_id> | get_movimentacao_estoque |
| POST | /movimentacoes-estoque | create_movimentacao_estoque |
| GET | /compras | get_compras |
| GET | /compras/<int:compra_id> | get_compra |
| POST | /compras | create_compra |
| PUT | /compras/<int:compra_id> | update_compra |
| DELETE | /compras/<int:compra_id> | delete_compra |
| GET | /vendas | get_vendas |
| GET | /vendas/<int:venda_id> | get_venda |
| POST | /vendas | create_venda |
| PUT | /vendas/<int:venda_id> | update_venda |
| DELETE | /vendas/<int:venda_id> | delete_venda |
| GET | /receitas | get_receitas |
| GET | /receitas/<int:receita_id> | get_receita |
| POST | /receitas | create_receita |
| PUT | /receitas/<int:receita_id> | update_receita |
| DELETE | /receitas/<int:receita_id> | delete_receita |
| GET | /alertas | get_alertas |
| GET | /alertas/<int:alerta_id> | get_alerta |
| POST | /alertas | create_alerta |
| PUT | /alertas/<int:alerta_id> | update_alerta |
| DELETE | /alertas/<int:alerta_id> | delete_alerta |
| GET | /configuracoes/visual | get_configuracoes_visuais |
| GET | /configuracoes | get_configuracoes |
| GET | /configuracoes/<string:chave> | get_configuracao |
| POST | /configuracoes | create_configuracao |
| PUT | /configuracoes/<string:chave> | update_configuracao |
| DELETE | /configuracoes/<string:chave> | delete_configuracao |
| GET | /dashboard/stats | get_dashboard_stats |
| GET | /relatorios/estoque | relatorio_estoque |
| GET | /relatorios/vencimentos | relatorio_vencimentos |
| GET | /relatorios/compras | relatorio_compras |
| GET | /pages/sistema/<path:filename> | serve_sistema_page |
| GET | /pages/proprietario/<path:filename> | serve_sistema_page |
| GET | /<path:filename> | serve_frontend_asset |
| GET | /financeiro/stats | financeiro_stats |
| GET | /financeiro/fluxo | financeiro_fluxo |
| GET | /financeiro/categorias | financeiro_categorias |
| GET | /financeiro/transacoes | financeiro_transacoes |
| POST | /financeiro/transacoes | create_financeiro_transacao |

## Inventário dos arquivos de código

- backend/app.py: 3565 linhas.
- backend/migrations/002_adiciona_perfil_visualizador.sql: 5 linhas.
- backend/migrations/002_fix_query_get_compras.sql: 8 linhas.
- backend/migrations/003_estoque_data_validade_nullable.sql: 15 linhas.
- backend/migrations/004_tabela_alertas.sql: 14 linhas.
- backend/migrations/005_tabela_financeiro.sql: 81 linhas.
- backend/migrations/20261005_perfil_permissoes.sql: 29 linhas.
- backend/schema.sql: 346 linhas.
- frontend/src/frame_analysis.js: 48 linhas.
- frontend/src/pages/auth/auth.css: 1810 linhas.
- frontend/src/pages/auth/auth.html: 446 linhas.
- frontend/src/pages/auth/auth.js: 501 linhas.
- frontend/src/pages/auth/legal.css: 35 linhas.
- frontend/src/pages/auth/privacidade.html: 3 linhas.
- frontend/src/pages/auth/termos.html: 3 linhas.
- frontend/src/pages/sistema/compras/compras.css: 1681 linhas.
- frontend/src/pages/sistema/compras/compras.html: 581 linhas.
- frontend/src/pages/sistema/compras/compras.js: 934 linhas.
- frontend/src/pages/sistema/configuracoes/configuracoes.css: 1448 linhas.
- frontend/src/pages/sistema/configuracoes/configuracoes.html: 761 linhas.
- frontend/src/pages/sistema/configuracoes/configuracoes.js: 356 linhas.
- frontend/src/pages/sistema/dashboard/dashboard.css: 1412 linhas.
- frontend/src/pages/sistema/dashboard/dashboard.html: 406 linhas.
- frontend/src/pages/sistema/dashboard/dashboard.js: 590 linhas.
- frontend/src/pages/sistema/estoque/estoque.css: 1388 linhas.
- frontend/src/pages/sistema/estoque/estoque.html: 745 linhas.
- frontend/src/pages/sistema/estoque/estoque.js: 1028 linhas.
- frontend/src/pages/sistema/financeiro/financeiro.css: 1638 linhas.
- frontend/src/pages/sistema/financeiro/financeiro.html: 380 linhas.
- frontend/src/pages/sistema/financeiro/financeiro.js: 519 linhas.
- frontend/src/pages/sistema/relatorios/relatorios.css: 1649 linhas.
- frontend/src/pages/sistema/relatorios/relatorios.html: 569 linhas.
- frontend/src/pages/sistema/relatorios/relatorios.js: 722 linhas.
- frontend/src/pages/sistema/usuarios/usuarios.css: 1620 linhas.
- frontend/src/pages/sistema/usuarios/usuarios.html: 909 linhas.
- frontend/src/pages/sistema/usuarios/usuarios.js: 836 linhas.
- frontend/src/pages/sistema/vencimentos/vencimentos.css: 1554 linhas.
- frontend/src/pages/sistema/vencimentos/vencimentos.html: 614 linhas.
- frontend/src/pages/sistema/vencimentos/vencimentos.js: 836 linhas.
- frontend/src/styles/light-theme-contrast.css: 199 linhas.
- frontend/src/styles/owner-responsive.css: 164 linhas.
- frontend/src/styles/page-transitions.css: 59 linhas.
- frontend/src/utils/global-settings.js: 468 linhas.
- frontend/src/utils/sidebar-init.js: 632 linhas.

## Achados e limites

- README descreve Node/Prisma/PostgreSQL inexistentes; autenticação documenta rota de aprovação incorreta.
- /compras e /fornecedores raiz ficam fora do teste de prefixo. Usuário autorizou corrigir mantendo os perfis previstos.
- Matriz editável no banco diverge de backend/menu; ativação exige decisão de produto e ficou fora desta refatoração.
- Oito scripts repetem temporizadores; botão persistente de recolher acumula listeners a cada navegação.
- Remoção ampla de .modal-overlay também apaga modais recém-inseridos em .main.
- CSS inicial permanece durante navegação e novas folhas são inseridas na ordem da rede.
- Financeiro interpola data no SQL; valor não numérico lança erro antes do tratamento; autor usa primeiro usuário do banco.
- Estoque valida fornecedor numérico mas depois chama isdigit diretamente nele.
- Handlers de arquivos estáticos duplicados; import send_from_directory sem uso.
- Não há testes existentes. Git/Node fora do PATH. Validação isolada sem conexão ao banco.
- CSS tem sobreposições intencionais: consolidar apenas com equivalência verificável.
- frame_analysis.js é utilitário manual, preservado. Favicons duplicados podem atender caminhos distintos.
- Exclusão de estoque apaga histórico; ajustes negativos são recusados antes de seu ramo; falta bloqueio de linhas nas movimentações. Mudar estas regras requer decisão.
- Nota histórica de 06/10: havia código de tema alternativo sem uso. Em 08/10, os resíduos foram removidos e a aparência clara foi preservada; ver item 11 do relatório.
