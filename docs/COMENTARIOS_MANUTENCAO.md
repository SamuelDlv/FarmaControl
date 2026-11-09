# Comentários para manutenção e transferência

Revisão de 09/11/2026. Foram acrescentadas 2.676 linhas de comentários em 142
arquivos versionados de código, estilos, marcação, testes, scripts e CI. A revisão
documenta a implementação existente; não altera regras de negócio, consultas,
contratos HTTP ou dependências.

## Como acompanhar um fluxo

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
5. Leia os testes correspondentes e execute os comandos em `DESENVOLVIMENTO.md`.

## Cuidados documentados junto ao código

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

## Verificações desta revisão

| Verificação | Resultado |
| --- | --- |
| Suíte Python completa | 195 testes aprovados |
| Suíte JavaScript | 25 testes aprovados |
| Sintaxe dos scripts do frontend | 55 scripts externos e inline validados |
| Auditoria estática | Sem assets ausentes, IDs HTML duplicados ou imports de backend não utilizados |
| Dependências Python | `pip check` sem inconsistências |
| Estrutura Python | AST preservada nos 66 arquivos Python alterados, incluindo docstrings |
| Estrutura JavaScript | Tokens preservados nos 35 arquivos JS/CJS e nos scripts inline |
| HTML e CSS | Marcação e estilos preservados, descontando comentários e espaços de separação |
| Linhas originais | Todas preservadas, em ordem, nos arquivos comentados |

O ambiente bloqueou a criação de subprocessos na execução padrão dos testes
JavaScript; a suíte passou no runtime Node do VS Code com `--test-isolation=none`.
A repetição da suíte Python encontrou restrições de acesso às pastas temporárias
dentro do sandbox; a execução autorizada fora dessa restrição passou integralmente.
Os testes não exigiram alterações no código para contornar essas limitações.

Não foram executados localmente nesta revisão os testes adicionais de integração
com MySQL, envio SMTP, compilação do instalador ou inspeção visual em navegador.
O workflow existente continua responsável pela matriz automatizada de MySQL,
MariaDB, navegador e encerramento Windows; seu resultado deve ser consultado no
GitHub Actions do commit publicado.

## Arquivos preservados e limites

As migrações históricas, as migrações registradas e `baseline_023.json` permanecem
intactos. Mesmo comentários mudariam checksums; a orientação de manutenção desses
arquivos continua em `backend/migrations/README.md`.

O fonte local `installer/FarmaControl-Dependencias.iss` também recebeu comentários,
mas permanece fora da publicação por estar explicitamente ignorado no `.gitignore`.
As 12 linhas acrescentadas nesse arquivo não integram o total versionado acima.
Nenhum executável foi recompilado.

O snapshot e os utilitários usados para conferir a preservação do código ficam
localmente em `.audit-backup/`. Não integram a publicação, assim como `.env`,
credenciais, bases, dados operacionais e screenshots.
