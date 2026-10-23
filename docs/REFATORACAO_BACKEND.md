# Mapa da refatoração do backend

Atualizado em **23/10/2026**. Todos os caminhos são relativos à raiz do projeto.

`backend/app.py` passa a ser apenas a entrada local e WSGI. A composição da aplicação fica em `backend/farmacontrol/__init__.py`, as rotas em `routes/`, a infraestrutura em `core/` e as regras compartilhadas em `services/`. Os hooks HTTP ficam em `middleware.py`.

O comando `python backend/app.py`, a entrada WSGI `app:app`, as URLs, os métodos HTTP e os nomes dos endpoints permanecem compatíveis. Os imports internos usados por testes e scripts foram atualizados. O `.env` continua em `backend/.env` e o frontend em `frontend/src/`.

## Inventário completo

A lista abaixo cobre 58 arquivos nos caminhos atuais. Sete deles foram movidos da raiz de `backend/`; seus caminhos anteriores são removidos no mesmo commit. Arquivos novos de `__init__.py` definem os pacotes Python.

### Entrada e composição

| Caminho atual | Alteração |
| --- | --- |
| [backend/app.py](../backend/app.py) | Alterado |
| [backend/farmacontrol/__init__.py](../backend/farmacontrol/__init__.py) | Criado |
| [backend/farmacontrol/middleware.py](../backend/farmacontrol/middleware.py) | Criado |

### Infraestrutura e segurança

| Caminho atual | Alteração |
| --- | --- |
| [backend/farmacontrol/core/__init__.py](../backend/farmacontrol/core/__init__.py) | Criado |
| [backend/farmacontrol/core/access.py](../backend/farmacontrol/core/access.py) | Criado |
| [backend/farmacontrol/core/credentials.py](../backend/farmacontrol/core/credentials.py) | Criado |
| [backend/farmacontrol/core/database.py](../backend/farmacontrol/core/database.py) | Criado |
| [backend/farmacontrol/core/paths.py](../backend/farmacontrol/core/paths.py) | Criado |
| [backend/farmacontrol/core/responses.py](../backend/farmacontrol/core/responses.py) | Criado |
| [backend/farmacontrol/core/runtime_config.py](../backend/farmacontrol/core/runtime_config.py) | Movido de `backend/runtime_config.py` |
| [backend/farmacontrol/core/security.py](../backend/farmacontrol/core/security.py) | Movido de `backend/security.py` |

### Rotas por área

| Caminho atual | Alteração |
| --- | --- |
| [backend/farmacontrol/routes/__init__.py](../backend/farmacontrol/routes/__init__.py) | Criado |
| [backend/farmacontrol/routes/admin.py](../backend/farmacontrol/routes/admin.py) | Criado |
| [backend/farmacontrol/routes/alertas.py](../backend/farmacontrol/routes/alertas.py) | Criado |
| [backend/farmacontrol/routes/auth.py](../backend/farmacontrol/routes/auth.py) | Criado |
| [backend/farmacontrol/routes/catalogo.py](../backend/farmacontrol/routes/catalogo.py) | Criado |
| [backend/farmacontrol/routes/clientes.py](../backend/farmacontrol/routes/clientes.py) | Criado |
| [backend/farmacontrol/routes/compras.py](../backend/farmacontrol/routes/compras.py) | Criado |
| [backend/farmacontrol/routes/configuracoes.py](../backend/farmacontrol/routes/configuracoes.py) | Criado |
| [backend/farmacontrol/routes/dashboard.py](../backend/farmacontrol/routes/dashboard.py) | Criado |
| [backend/farmacontrol/routes/estoque.py](../backend/farmacontrol/routes/estoque.py) | Criado |
| [backend/farmacontrol/routes/financeiro.py](../backend/farmacontrol/routes/financeiro.py) | Criado |
| [backend/farmacontrol/routes/fornecedores.py](../backend/farmacontrol/routes/fornecedores.py) | Criado |
| [backend/farmacontrol/routes/frontend.py](../backend/farmacontrol/routes/frontend.py) | Criado |
| [backend/farmacontrol/routes/health.py](../backend/farmacontrol/routes/health.py) | Criado |
| [backend/farmacontrol/routes/receitas.py](../backend/farmacontrol/routes/receitas.py) | Criado |
| [backend/farmacontrol/routes/relatorios.py](../backend/farmacontrol/routes/relatorios.py) | Criado |
| [backend/farmacontrol/routes/vendas.py](../backend/farmacontrol/routes/vendas.py) | Criado |

### Serviços compartilhados

| Caminho atual | Alteração |
| --- | --- |
| [backend/farmacontrol/services/__init__.py](../backend/farmacontrol/services/__init__.py) | Criado |
| [backend/farmacontrol/services/audit.py](../backend/farmacontrol/services/audit.py) | Movido de `backend/audit.py` |
| [backend/farmacontrol/services/email.py](../backend/farmacontrol/services/email.py) | Criado |
| [backend/farmacontrol/services/product_rules.py](../backend/farmacontrol/services/product_rules.py) | Movido de `backend/product_rules.py` |
| [backend/farmacontrol/services/reporting.py](../backend/farmacontrol/services/reporting.py) | Movido de `backend/reporting.py` |
| [backend/farmacontrol/services/settings_notifications.py](../backend/farmacontrol/services/settings_notifications.py) | Movido de `backend/settings_notifications.py` |
| [backend/farmacontrol/services/system_settings.py](../backend/farmacontrol/services/system_settings.py) | Movido de `backend/system_settings.py` |

### Testes

| Caminho atual | Alteração |
| --- | --- |
| [tests/test_app_structure.py](../tests/test_app_structure.py) | Criado |
| [tests/test_audit.py](../tests/test_audit.py) | Alterado |
| [tests/test_backend.py](../tests/test_backend.py) | Alterado |
| [tests/test_catalogo.py](../tests/test_catalogo.py) | Alterado |
| [tests/test_page_access.py](../tests/test_page_access.py) | Alterado |
| [tests/test_pdv.py](../tests/test_pdv.py) | Alterado |
| [tests/test_runtime_config.py](../tests/test_runtime_config.py) | Alterado |
| [tests/test_security.py](../tests/test_security.py) | Alterado |
| [tests/test_system_settings.py](../tests/test_system_settings.py) | Alterado |

### Scripts

| Caminho atual | Alteração |
| --- | --- |
| [scripts/audit_static.py](../scripts/audit_static.py) | Alterado |
| [scripts/check_catalogo_mysql.py](../scripts/check_catalogo_mysql.py) | Alterado |
| [scripts/check_volume_data.py](../scripts/check_volume_data.py) | Alterado |

### Documentação

| Caminho atual | Alteração |
| --- | --- |
| [README.md](../README.md) | Alterado |
| [backend/README.md](../backend/README.md) | Alterado |
| [docs/API.md](../docs/API.md) | Alterado |
| [docs/DESENVOLVIMENTO.md](../docs/DESENVOLVIMENTO.md) | Alterado |
| [docs/GITHUB.md](../docs/GITHUB.md) | Alterado |
| [docs/README.md](../docs/README.md) | Alterado |
| [docs/REFATORACAO_BACKEND.md](../docs/REFATORACAO_BACKEND.md) | Criado |
| [docs/pdv.md](../docs/pdv.md) | Alterado |
| [docs/postman/README.md](../docs/postman/README.md) | Alterado |
| [docs/seguranca-relatorio-2026-10-15.md](../docs/seguranca-relatorio-2026-10-15.md) | Alterado |
| [frontend/src/pages/README-authentication.md](../frontend/src/pages/README-authentication.md) | Alterado |

## Validação

- 137 testes Python aprovados, com banco simulado.
- Compilação Python de `backend/`, `tests/` e `scripts/` sem erros.
- Contratos das rotas comparados com o snapshot existente.
- 112 funções extraídas comparadas estruturalmente com o original.
- Auditoria estática sem imports de backend não utilizados, assets ausentes ou IDs HTML duplicados.

Não foram executados testes de integração com banco real ou envio SMTP. O backup local da extração está em `.audit-backup/modularization/` e não integra a publicação.

