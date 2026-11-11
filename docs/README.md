# Documentação do FarmaControl

Organizada em **11/11/2026**: **11 Markdown**, sendo oito guias principais, um guia do Postman e dois históricos mensais. Guias são agrupados por assunto; revisões e resultados são consultados por data. A consolidação documental não executa migrações nem confirma o estado de uma instalação.

## Guias por assunto

| Guia | Conteúdo |
| --- | --- |
| [Desenvolvimento](DESENVOLVIMENTO.md) | Ambiente, testes, arquitetura, manutenção, CI e publicação no GitHub |
| [Banco de dados](database_schema_design.md) | Tabelas, migrações, backup, MySQL/MariaDB e diagnóstico do XAMPP |
| [Atlas EER](database_eer.md) | Diagramas por área, chaves e dicionário das 24 tabelas; gerado pelo schema |
| [API](API.md) | Autenticação HTTP, endpoints, contratos, pesquisas e paginação |
| [Segurança](SEGURANCA.md) | Limites de autenticação, logout, sete perfis e permissões |
| [Operação](OPERACAO.md) | PDV, saldo por lote e devolução ao fornecedor |
| [Transferência](TRANSFERENCIA.md) | Mudança de máquina, arquivos, restauração do banco e conferências |
| [Postman](postman/README.md) | Configuração da Collection, variáveis e roteiro completo de execução |

## Histórico por data

| Período | Revisões registradas |
| --- | --- |
| [Novembro de 2026](historico/2026-11.md) | 04/11 pesquisas; 05/11 testes reais; 09/11 comentários e CI; 11/11 autenticação, permissões e consolidação documental |
| [Outubro de 2026](historico/2026-10.md) | 06–08/10 mapeamento e auditoria; 15/10 segurança; 19 e 23/10 validações; 23/10 modularização |

Cada registro conserva a data, o escopo e as limitações da revisão original. Contagens antigas, caminhos locais e descrições da antiga SPA são históricos. Consultas de vulnerabilidades de 15/10 e testes anteriores não foram repetidos pela consolidação.

Para novas revisões, atualize o guia do assunto e registre resultados na seção da data, em `historico/AAAA-MM.md`. Reutilize o arquivo do mês e ordene suas seções cronologicamente; abra outro apenas quando mudar o mês. Use datas ISO no nome dos arquivos e dia/mês/ano no texto. Não crie um Markdown separado para cada revisão.

## Instalação e fontes de verdade

- [README principal](../README.md): módulos, requisitos e instalação.
- [Backend](../backend/README.md): configuração e autorização.
- [Frontend](../frontend/README.md) e [fluxo de autenticação](../frontend/src/pages/README-authentication.md): páginas, navegação, cadastro e recuperação.
- [Migrações](../backend/migrations/README.md) e [convenção de versões novas](../backend/migrations/managed/README.md): baseline e aplicação controlada.

O comportamento HTTP está em `backend/farmacontrol/routes/` e `middleware.py`; as variáveis validadas em `core/runtime_config.py`; a instalação nova em `backend/schema.sql`; e a evolução de bases existentes nas migrações. Atualize os guias e testes afetados junto de cada mudança de contrato. SQLs históricos, versões registradas e checksums permanecem imutáveis.

Screenshots e evidências visuais ficam em `.audit-backup/`, fora do versionamento. Não publique credenciais, `.env`, bases ou dados operacionais. Os JSONs históricos já existentes em `docs/` continuam acessíveis pelos relatórios correspondentes.
