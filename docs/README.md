# Documentação do FarmaControl

Referência revisada em **09/11/2026**, a partir do código e dos SQLs presentes nesta cópia. A revisão documental não executa migrações nem confirma a estrutura de um banco instalado.

## Por onde começar

| Objetivo | Documento |
| --- | --- |
| Instalar e conhecer os módulos | [README principal](../README.md) |
| Instalar Python e dependências no Windows | [Instalador de dependências](../README.md#instalador-de-dependências-windows) |
| Configurar API, ambiente e permissões | [Backend](../backend/README.md) |
| Localizar os arquivos da estrutura modular do backend | [Mapa da refatoração](REFATORACAO_BACKEND.md) |
| Entender páginas, estilos e navegação | [Frontend](../frontend/README.md) |
| Consultar login, convites e recuperação | [Autenticação](../frontend/src/pages/README-authentication.md) |
| Entender tabelas e migrações | [Banco de dados](database_schema_design.md) |
| Visualizar tabelas, chaves e relacionamentos | [Atlas EER e dicionário de dados](database_eer.md) |
| Consultar endpoints | [Referência da API](API.md) |
| Operar vendas de balcão | [Vendas e PDV](pdv.md) |
| Desenvolver e executar verificações | [Desenvolvimento](DESENVOLVIMENTO.md) |
| Entender os comentários e acompanhar um fluxo no código | [Manutenção e transferência do código](COMENTARIOS_MANUTENCAO.md) |
| Consultar verificações automáticas e testes de integração | [CI e reprodução local](CI.md) |
| Conferir baseline e aplicar migrações novas | [Migrações do banco](../backend/migrations/README.md) |
| Criar uma migração controlada | [Convenção de migrações](../backend/migrations/managed/README.md) |
| Registrar devolução ao fornecedor | [Devolução](devolucao-fornecedor.md) |
| Configurar e diagnosticar MySQL/MariaDB no XAMPP | [MySQL e XAMPP](MYSQL_XAMPP.md) |
| Consultar a API pelo Postman | [Collection e instruções](postman/README.md) |
| Transferir arquivos e banco | [Transferência](TRANSFERENCIA.md) |
| Preparar commits e publicar código | [GitHub](GITHUB.md) |

## Fontes de verdade

O comportamento HTTP está em `backend/farmacontrol/routes/` e `backend/farmacontrol/middleware.py`, com entrada em `backend/app.py`; as variáveis validadas estão em `backend/farmacontrol/core/runtime_config.py`; tabelas, índices e relacionamentos estão em `backend/schema.sql` e nas migrações. O schema descreve uma instalação nova, enquanto as migrações registram alterações para bases anteriores.

Documentação não substitui esses contratos. Ao alterar uma rota, configuração, regra de acesso ou estrutura de dados, atualize o documento correspondente e os testes afetados no mesmo conjunto de mudanças.

## Relatórios históricos

- [Mapeamento de 06/10](auditoria-mapeamento-2026-10-06.md).
- [Auditoria e refatoração de 06/10](auditoria-relatorio-2026-10-06.md).
- [Revisão de segurança de 15/10](seguranca-relatorio-2026-10-15.md).

Esses documentos preservam os resultados e limitações das respectivas revisões. Contagens antigas, caminhos de evidências locais e descrições da antiga SPA não representam necessariamente a versão atual. A consulta de vulnerabilidades de 15/10 não foi repetida nesta atualização documental.

## Validação de referência em 09/11/2026

- 195 testes Python e 25 testes JavaScript aprovados.
- Sintaxe de 55 scripts frontend e dependências Python verificadas.
- Auditoria sem assets ausentes, IDs HTML duplicados ou imports de backend não utilizados.
- [GitHub Actions do commit 710e9dc](https://github.com/SamuelDlv/FarmaControl/actions/runs/42654607638): cinco jobs aprovados, cobrindo unitários/auditoria, encerramento Windows, schema MySQL 8.0.46, schema MariaDB 10.4 e integração MySQL/navegador.

As contagens descrevem essa revisão, não uma garantia sobre versões futuras.
Confira a execução associada ao commit instalado. O CI usa bases descartáveis;
não confirma o estado da base operacional, entrega SMTP real ou compilação do
instalador. Veja os detalhes e limites em [CI](CI.md) e no [registro de manutenção](COMENTARIOS_MANUTENCAO.md).

Os resultados de 19/10 (120 testes Python, 17 JavaScript e 53 scripts) são
históricos. Para preparar outra máquina, crie uma nova `.venv`; não copie
ambientes virtuais da instalação anterior.
