# Desenvolvimento e validação

Revisado em 19/10/2026. Todos os comandos abaixo partem da raiz do projeto.

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
node --test tests/frontend.test.cjs tests/log.test.cjs tests/vendas.test.cjs
```

| Arquivo | Cobertura principal |
| --- | --- |
| `tests/test_backend.py` | Contratos HTTP, sessão, perfis, operações e respostas |
| `tests/test_catalogo.py` | Medicamentos, outros produtos, categorias e validade |
| `tests/test_pdv.py` | Validação de vendas, cálculo e rollback |
| `tests/test_audit.py` | Registro e consulta de atividades |
| `tests/test_runtime_config.py` | Ambiente, cookies, origens e chave de sessão |
| `tests/test_security.py` | Revogação, tokens, limite de acesso e entradas inválidas |
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

Os utilitários `migrate_catalogo.py` e `migrate_audit.py` permitem inspeção e aplicação explícita com `--apply`. Antes de aplicar, confira o banco configurado, faça backup e leia o SQL. Veja [banco de dados](database_schema_design.md).

## Organização de mudanças

1. Localize o fluxo da tela e a rota usada por ela.
2. Confira o módulo de autorização, validação de dados e limites transacionais.
3. Altere o menor conjunto de arquivos que atende ao comportamento desejado.
4. Para estrutura de banco, mantenha o schema novo e a migração de atualização coerentes.
5. Execute a suíte pertinente e documente o comportamento e as limitações verificadas.

No frontend, mantenha a ordem dos estilos e use os utilitários compartilhados. No backend, parametrize valores SQL e confirme mutações e auditoria na mesma transação quando esse for o contrato do fluxo. Não crie tabelas como efeito de uma requisição comum.

## Diagnóstico

| Sintoma | Conferência |
| --- | --- |
| Módulo Python ausente | Use o Python da `.venv` e reinstale `requirements.txt` |
| Falha na inicialização | Leia a validação de `APP_ENV`, chave, cookies e origens |
| Erro de conexão MySQL | Confira serviço, host, porta, banco, usuário e privilégios |
| Login retorna 401 | Verifique conta aprovada, sessão e alteração recente de senha/chave |
| Operação retorna 403 | Confira permissões do módulo e envio de CSRF |
| Autenticação retorna 429 | Respeite `Retry-After`; o limitador é por IP/processo |
| Convite retorna 503 | O convite pode ter sido salvo; confira SMTP antes de reenviar |
| Tabela ou coluna ausente | Compare a base instalada com as migrações necessárias |
| Aparência incorreta | Confira assets, ordem de CSS, cache e recursos externos |

Logs podem conter informações operacionais; mantenha-os fora do repositório. Não trate mensagens de erros simulados da suíte como falha se o resultado final dos testes for `OK`.

## Registro de validação

Em 19/10/2026, antes da remoção do ambiente de auditoria: 120 testes Python aprovados e `pip check` sem inconsistências. Os 17 testes JavaScript passaram usando o runtime Node do VS Code com isolamento de processo desativado, pois o ambiente bloqueou a criação de subprocessos. O comando padrão acima é destinado a uma instalação normal do Node. A última verificação de sintaxe examinou 53 scripts.

Esta revisão de documentação não repete esses testes nem constitui validação de produção. A conferência documental inclui caminhos relativos, inventário de rotas, tabelas e consistência com o código local.
