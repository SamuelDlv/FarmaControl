# Desenvolvimento, manutenção e publicação

Consolidado em **11/11/2026**. Reúne ambiente, arquitetura, manutenção, CI e GitHub. Resultados de execuções anteriores ficam no [histórico de outubro](historico/2026-10.md) e [novembro](historico/2026-11.md). Os comandos partem da raiz do projeto.

- [Ambiente e verificações](#ambiente-de-trabalho)
- [Arquitetura do backend](#arquitetura)
- [Manutenção do código](#manutencao)
- [CI e integração](#ci)
- [Publicação no GitHub](#publicacao)

## Ambiente de trabalho

Use Python 3.12 e uma `.venv` instalada a partir de `backend/requirements.txt`. Node 22 ou superior é usado pelas verificações JavaScript; não é necessário para servir a aplicação. Os testes de navegador requerem Chrome. Não há `package.json`, bundler nem etapa npm de build.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

Não copie ambientes virtuais entre máquinas. Configure o `.env` pelo modelo do backend. Utilize dados fictícios em uma base separada ao desenvolver fluxos que alterem estoque, vendas ou contas.

## Verificações sem banco real

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
node scripts/check_frontend.cjs
node --test tests/frontend.test.cjs tests/log.test.cjs tests/vendas.test.cjs tests/logout.test.cjs tests/login-attempts.test.cjs tests/auth-guard.test.cjs
```

| Arquivo | Cobertura principal |
| --- | --- |
| `tests/test_backend.py` | Contratos HTTP, sessão, perfis, operações e respostas |
| `tests/test_app_structure.py` | Criação de aplicações isoladas, caminhos, entrada local/WSGI e agendamento de notificações |
| `tests/test_catalogo.py` | Medicamentos, outros produtos, categorias e validade |
| `tests/test_pdv.py` | Validação de vendas, cálculo e rollback |
| `tests/test_audit.py` | Registro e consulta de atividades |
| `tests/test_runtime_config.py` | Ambiente, cookies, origens e chave de sessão |
| `tests/test_security.py` | Revogação, tokens, limite de acesso e entradas inválidas |
| `tests/test_page_access.py` | HTML protegido, aliases, logout, permissões e falha de validação |
| `tests/auth-guard.test.cjs` | Ocultação, histórico, sessão inválida e abertura como arquivo |
| `tests/logout.test.cjs` | Saída lenta, cliques repetidos e nova tentativa após erro |
| `tests/login-attempts.test.cjs` | Aviso persistente e contagem regressiva do bloqueio |
| `tests/test_system_settings.py` | Preferências, alertas e notificações |
| `tests/frontend.test.cjs` | Ciclo de vida, fetch, CSRF e preferências visuais |
| `tests/log.test.cjs` | Filtros, paginação e detalhes do histórico |
| `tests/vendas.test.cjs` | Catálogo, agrupamento e pesquisa de produtos |

Os testes Python usam dados e conexões simulados. Eles não confirmam SQL em um servidor real, migrações aplicadas, entrega de e-mails ou comportamento de concorrência no MySQL. A verificação de sintaxe JavaScript também não comprova renderização visual.

## Navegador isolado

```powershell
node scripts/check_navigation.cjs
node scripts/check_pdv.cjs
node scripts/check_settings.cjs
```

Esses scripts usam APIs simuladas e perfis separados do navegador. Consulte o início de cada script para pré-requisitos e seleção do executável. Quando suportado, `CHROME_PATH` aponta para a instalação do Chrome. Evidências são gravadas em `.audit-backup/`, fora do Git.

Para comparar estilos antes e depois de uma alteração:

```powershell
node scripts/check_theme.cjs baseline
# Faça a alteração de CSS.
node scripts/check_theme.cjs verify
```

`check_browser.cjs` contém verificações históricas e cenários específicos: revise o cenário antes de usá-lo como critério para a navegação atual. Os scripts de volume são ferramentas adicionais de diagnóstico, não parte obrigatória dos testes unitários.

## Verificações com MySQL

`check_catalogo_mysql.py` e `check_seed_mysql.py` criam bancos temporários e exigem privilégios de criação/remoção de bases. Leia o script, confira a conexão e use um servidor destinado a testes. Nunca confunda esses verificadores com migrações da aplicação.

Os utilitários `migrate_catalogo.py` e `migrate_audit.py` permitem inspeção e aplicação explícita com `--apply`. Antes de aplicar, confira o banco configurado, faça backup e leia o SQL. Veja [banco de dados](banco-de-dados.md).

## Organização de mudanças

1. Localize o fluxo da tela e a rota usada por ela.
2. Confira o módulo de autorização, validação de dados e limites transacionais.
3. Altere o menor conjunto de arquivos que atende ao comportamento desejado.
4. Para estrutura de banco, mantenha o schema novo e a migração de atualização coerentes.
5. Execute a suíte pertinente e documente o comportamento e as limitações verificadas.

No frontend, mantenha a ordem dos estilos e use os utilitários compartilhados. No backend, parametrize valores SQL e confirme mutações e auditoria na mesma transação quando esse for o contrato do fluxo. Não crie tabelas como efeito de uma requisição comum.

As rotas estão em `backend/farmacontrol/routes/`, agrupadas por área e registradas por `create_app()`. Infraestrutura e permissões ficam em `core/`, regras compartilhadas em `services/` e os hooks HTTP em `middleware.py`. Ao simular dependências em testes, aplique o patch no módulo correspondente, por exemplo `farmacontrol.core.database.get_db`; `backend/app.py` contém apenas a entrada da aplicação. Veja o [mapa de arquivos](#arquitetura).

## Diagnóstico

| Sintoma | Conferência |
| --- | --- |
| Módulo Python ausente | Use o Python da `.venv` e reinstale `requirements.txt` |
| Falha na inicialização | Leia a validação de `APP_ENV`, chave, cookies e origens |
| Erro de conexão MySQL | Confira serviço, host, porta, banco, usuário e privilégios |
| Login retorna 401 | Verifique conta aprovada, sessão e alteração recente de senha/chave |
| URL interna volta ao login | Comportamento esperado sem cookie válido; o servidor não entrega o HTML |
| Operação retorna 403 | Confira permissões do módulo e envio de CSRF |
| Autenticação retorna 429 | Respeite `Retry-After`; o limitador é por IP/processo |
| Convite retorna 503 | O convite pode ter sido salvo; confira SMTP antes de reenviar |
| Tabela ou coluna ausente | Compare a base instalada com as migrações necessárias |
| Aparência incorreta | Confira assets, ordem de CSS, cache e recursos externos |

Logs podem conter informações operacionais; mantenha-os fora do repositório. Não trate mensagens de erros simulados da suíte como falha se o resultado final dos testes for `OK`.

<a id="arquitetura"></a>

## Arquitetura do backend

Atualizado em **23/10/2026**. Todos os caminhos são relativos à raiz do projeto.

`backend/app.py` passa a ser apenas a entrada local e WSGI. A composição da aplicação fica em `backend/farmacontrol/__init__.py`, as rotas em `routes/`, a infraestrutura em `core/` e as regras compartilhadas em `services/`. Os hooks HTTP ficam em `middleware.py`.

O comando `python backend/app.py`, a entrada WSGI `app:app`, as URLs, os métodos HTTP e os nomes dos endpoints permanecem compatíveis. Os imports internos usados por testes e scripts foram atualizados. O `.env` continua em `backend/.env` e o frontend em `frontend/src/`.

### Mapa de responsabilidades

| Caminho | Responsabilidade |
| --- | --- |
| `backend/app.py` | Entrada local e WSGI |
| `backend/farmacontrol/__init__.py` | Factory e registro das rotas |
| `backend/farmacontrol/middleware.py` | Hooks HTTP e proteção de requisições |
| `backend/farmacontrol/core/` | Acesso, credenciais, banco, respostas, configuração e segurança |
| `backend/farmacontrol/routes/` | Handlers agrupados por domínio |
| `backend/farmacontrol/services/` | Auditoria, e-mail, produtos, relatórios e configurações compartilhadas |

O inventário dos 58 arquivos da extração e sua validação estão no [registro de 23/10](historico/2026-10.md#refatoracao-2026-10-23).

<a id="manutencao"></a>

## Manutenção do código

### Como acompanhar um fluxo

1. Comece pelo HTML em `frontend/src/pages/`: os comentários identificam a região
   principal, formulários, tabelas e diálogos. Preserve os IDs usados pelo JavaScript.
2. No JavaScript correspondente, leia os comentários das funções de carregamento,
   renderização e envio. Os utilitários em `frontend/src/utils/` compartilham sessão
   visual, transporte HTTP, ciclo de vida, menu e preferências.
3. Localize a URL em `backend/farmacontrol/routes/`. Os comentários apontam as
   chaves lidas do JSON e as tabelas com nomes literais nas consultas diretas. Essa
   lista não inclui dependências indiretas dos serviços chamados pela rota.
4. Confira `middleware.py`, `core/` e `services/` para autorização, validações,
   sessão, conexão, auditoria e regras compartilhadas. Ao alterar uma gravação,
   preserve os limites de transação documentados junto ao código.
5. Leia os testes correspondentes e execute os comandos em `desenvolvimento.md`.

### Cuidados documentados junto ao código

- A sessão visual no navegador não autoriza operações; a API revalida a conta,
  as permissões e o CSRF.
- A conexão de banco pertence ao contexto Flask. A operação e sua auditoria usam
  a mesma transação; threads de notificação abrem contexto e conexão próprios.
- O PDV revalida preço e saldo por lote sob bloqueio. Falha de rede após o envio
  não comprova que a venda foi recusada; a tela bloqueia repetição automática.
- O recebimento de compras movimenta saldo na transição de estado. Descarte e
  devolução preservam motivos, permissões adicionais e histórico.
- Timers e listeners pertencem ao ciclo de vida da tela. Novas rotinas devem usar
  os wrappers compartilhados para permitir descarte.
- A cascata CSS, os breakpoints, os estados de foco e o empilhamento de diálogos
  fazem parte do comportamento visual dos componentes.
- Os BATs e o PowerShell compartilham o protocolo de encerramento cooperativo
  com `core/local_server.py`, identificado pelo caminho da instalação.

As migrações históricas, as versões registradas e `baseline_023.json` são imutáveis, inclusive comentários que alterariam checksums. Consulte o [guia de migrações](../backend/migrations/README.md). Capturas e backups ficam apenas em `.audit-backup/`. O registro da revisão de comentários de 09/11 está no [histórico](historico/2026-11.md#2026-11-09).

<a id="ci"></a>

## CI e reprodução local

O workflow `.github/workflows/ci.yml` roda em pushes para `main`, pull requests e
acionamento manual pelo GitHub Actions. Usa Python 3.12, Node 22 e Ubuntu 24.04.

### Unitários e auditoria

- Instala as dependências fixadas e executa `pip check`.
- Executa todos os testes Python e JavaScript, sem banco real.
- Valida sintaxe dos scripts frontend.
- Falha se a auditoria encontrar assets ausentes, IDs HTML duplicados ou imports
  de backend não utilizados. Repetições de CSS continuam apenas informativas.

### MySQL e navegador

- Inicia MySQL 8.0.46 em um serviço descartável, com credenciais exclusivas do job.
- Instala `requirements-dev.txt` e Chromium pelo Playwright.
- Executa `check_migrations_mysql.py`, `check_catalogo_mysql.py` e
  `check_devolucao_mysql.py --browser`.
- Os testes criam e removem bases aleatórias. Não usam o `.env` privado da instalação.
- Não publica screenshots nem faz deploy ou migração da base operacional.

### Compatibilidade e encerramento

- A matriz de schema importa e reimporta o arquivo completo em MySQL 8.0.46 e
  MariaDB 10.4, com uma conta limitada à base descartável, sem privilégios globais.
- O job Windows executa o BAT real contra os eventos de controle e verifica o
  isolamento entre pastas. Também verifica que uma requisição em andamento termina
  e que o teardown fecha sua conexão antes de concluir o encerramento.
- Esses testes não reproduzem uma instalação XAMPP com arquivos internos corrompidos.

Todos os jobs precisam ficar verdes para a validação ser considerada concluída.
O workflow publica resultados na aba Actions. Exigir esses checks antes de merge
depende de uma regra de proteção da branch; criar o workflow não ativa essa regra.

### Reprodução local

```powershell
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python -B -m unittest discover -s tests -v
node --test tests/*.test.cjs
node scripts/check_frontend.cjs
python -B scripts/audit_static.py
python -B scripts/check_migrations_mysql.py
python -B scripts/check_schema_mysql.py
python -B scripts/check_catalogo_mysql.py
python -B scripts/check_devolucao_mysql.py --browser
```

No Windows, o teste usa o Chrome instalado quando disponível; `CHROME_PATH`
permite escolher outro executável. No CI Linux usa o Chromium instalado pelo
Playwright. Os testes de integração exigem MySQL local e credenciais com permissão
para criar/remover bases temporárias. Variáveis `DB_*` de ambiente prevalecem sobre
`backend/.env`.

Referências: [workflows Python do GitHub](https://docs.github.com/en/actions/tutorials/build-and-test-code/python)
e [instalação de navegadores Playwright](https://playwright.dev/python/docs/browsers).

<a id="publicacao"></a>

## Versionamento e publicação

Revisado em 23/10/2026. Execute os comandos na raiz do projeto, com Git instalado. Publicar o código não hospeda a API Flask nem o banco MySQL.

### Conteúdo do repositório

O instalador compilado é publicado em `dist/installer/Instalar Dependencias FarmaControl.exe`.
Essa é a única exceção de distribuição em `dist/`; mantenha o executável nessa
posição ao copiar ou extrair o projeto. Os arquivos `installer/*.iss` ficam apenas
na máquina de desenvolvimento, conforme a política de publicação deste projeto.

Versione `backend/` sem o `.env`, `frontend/`, `tests/`, `scripts/`, `docs/`, `README.md`, `LICENSE`, os arquivos `.bat`, `.gitignore` e `.gitattributes`. Mantenha `backend/.env.example` como modelo sem credenciais.

O `.gitignore` exclui ambientes virtuais, arquivos `.env` e suas variantes privadas, caches, logs, resultados de auditoria, backups e arquivos locais de banco. Arquivos SQL de schema e migrações são código do projeto e devem permanecer versionados. Exportações de dados reais não devem ser colocadas entre as migrações.

O `.gitattributes` normaliza arquivos de texto e preserva CRLF nos scripts `.bat`. Favicons e documentos binários são tratados como binários.

### Primeiro envio

Crie no GitHub um repositório vazio, sem README ou licença gerados automaticamente. Use a URL dele no comando `remote add`:

```powershell
git init -b main
git add .
git status --short
git diff --cached --stat
git diff --cached -- backend/.env.example .gitignore
git check-ignore backend/.env
git ls-files -- backend/.env
```

O penúltimo comando deve listar o `.env`; o último não deve retornar nenhum arquivo. Revise os arquivos preparados antes de continuar:

```powershell
git commit -m "Prepara FarmaControl para versionamento"
git remote add origin https://github.com/SEU_USUARIO/FarmaControl.git
git push -u origin main
```

Se o Git solicitar identidade, configure `user.name` e `user.email` conforme sua conta antes do commit. Autentique-se pelo mecanismo oferecido pelo Git/GitHub; não coloque tokens na URL salva do repositório.

### Atualizações posteriores

```powershell
git status --short
git diff
git add README.md
# Acrescente somente os caminhos revisados para esta mudança.
git diff --cached
git commit -m "Descreve a mudança realizada"
git push
```

Adapte a lista de caminhos aos arquivos modificados. Para trabalho em equipe, use uma branch e um pull request, descrevendo comportamento, validação e eventuais migrações necessárias.

### Arquivo privado já rastreado

O `.gitignore` não remove arquivos que já entraram no histórico. Se o `.env` aparecer em `git ls-files`, retire-o do índice preservando a cópia local:

```powershell
git rm --cached -- backend/.env
```

Revise e registre essa alteração. Se credenciais reais já foram publicadas, removê-las do arquivo atual não elimina versões antigas: substitua as credenciais expostas e trate o histórico separadamente.

### Copiar para outra máquina

```powershell
git clone https://github.com/SEU_USUARIO/FarmaControl.git
cd FarmaControl
```

Siga o [README](../README.md) para criar o ambiente e o [guia de transferência](transferencia.md) se houver dados a restaurar. O clone não inclui `.env`, dependências instaladas ou banco de dados.

### Estado do repositório

O repositório é [SamuelDlv/FarmaControl](https://github.com/SamuelDlv/FarmaControl), com branch principal `main`. Em 23/10/2026, as correções de logout e limite de autenticação foram publicadas pelo conector GitHub. Esse envio não cria uma pasta `.git` nem configura um remoto no diretório local; os comandos de Git deste guia exigem um clone ou repositório local inicializado.

Arquivos locais de `.audit-backup` e ambientes virtuais permanecem fora do versionamento. Publicar uma atualização no GitHub não reinicia o servidor local: depois de atualizar o código, reinicie o backend para carregar mudanças Python.

A atualização de modularização de 23/10/2026 mantém `backend/app.py` como entrada e distribui a implementação em `backend/farmacontrol/`. O [mapa da refatoração](#arquitetura) lista cada arquivo criado, movido ou alterado. Os módulos antigos na raiz de `backend/` são removidos do repositório junto com a inclusão de seus novos caminhos, no mesmo commit.
