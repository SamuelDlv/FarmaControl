# Documentação do FarmaControl

Referência revisada em **19/10/2026**, a partir do código e dos SQLs presentes nesta cópia. A revisão documental não executa migrações nem confirma a estrutura de um banco instalado.

## Por onde começar

| Objetivo | Documento |
| --- | --- |
| Instalar e conhecer os módulos | [README principal](../README.md) |
| Configurar API, ambiente e permissões | [Backend](../backend/README.md) |
| Entender páginas, estilos e navegação | [Frontend](../frontend/README.md) |
| Consultar login, convites e recuperação | [Autenticação](../frontend/src/pages/README-authentication.md) |
| Entender tabelas e migrações | [Banco de dados](database_schema_design.md) |
| Consultar endpoints | [Referência da API](API.md) |
| Operar vendas de balcão | [Vendas e PDV](pdv.md) |
| Desenvolver e executar verificações | [Desenvolvimento](DESENVOLVIMENTO.md) |
| Transferir arquivos e banco | [Transferência](TRANSFERENCIA.md) |
| Preparar commits e publicar código | [GitHub](GITHUB.md) |

## Fontes de verdade

O comportamento HTTP está em `backend/app.py`; as variáveis validadas estão em `backend/runtime_config.py`; tabelas, índices e relacionamentos estão em `backend/schema.sql` e nas migrações. O schema descreve uma instalação nova, enquanto as migrações registram alterações para bases anteriores.

Documentação não substitui esses contratos. Ao alterar uma rota, configuração, regra de acesso ou estrutura de dados, atualize o documento correspondente e os testes afetados no mesmo conjunto de mudanças.

## Relatórios históricos

- [Mapeamento de 06/10](auditoria-mapeamento-2026-10-06.md).
- [Auditoria e refatoração de 06/10](auditoria-relatorio-2026-10-06.md).
- [Revisão de segurança de 15/10](seguranca-relatorio-2026-10-15.md).

Esses documentos preservam os resultados e limitações das respectivas revisões. Contagens antigas, caminhos de evidências locais e descrições da antiga SPA não representam necessariamente a versão atual. A consulta de vulnerabilidades de 15/10 não foi repetida nesta atualização documental.

## Verificação registrada em 19/10

Na preparação desta cópia para GitHub passaram 120 testes Python, 17 testes JavaScript e a verificação de dependências Python. A verificação final de sintaxe cobriu 53 scripts externos e inline. Não foram executados testes de navegador ou integração com MySQL nessa preparação. O ambiente virtual utilizado foi removido parcialmente durante a limpeza e deve ser recriado como `.venv`.
