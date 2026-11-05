# Migrações do banco

Publicar no GitHub não executa migrações na instalação. Use uma conta com permissão
de alteração de schema, faça backup e valide a restauração antes de mudanças em dados reais.
Os comandos abaixo partem da raiz e usam `backend/.env`; variáveis de ambiente
`DB_*` têm precedência. Os utilitários aceitam somente servidor local.

## Consultar a situação

```powershell
python scripts/migrate.py status
```

Esse comando é somente leitura. Lista a baseline, as migrações controladas aplicadas
e as pendentes. Detecta arquivos alterados/removidos, versões duplicadas e execuções
interrompidas. Sem histórico, informa `baseline: false`; não tenta adivinhar quais
SQLs antigos foram executados.

## Adotar o controle em uma base existente

1. Revise o histórico de implantação até 023, incluindo alterações de dados,
   permissões, tipos e índices. Os arquivos antigos permanecem com seus nomes:
   os dois prefixos `002` e o arquivo datado são legado e não são executados pelo runner.
2. Para descarte/devolução, inspecione com `python scripts/migrate_devolucao.py`.
   Se as colunas estiverem ausentes, aplique a preparação idempotente com
   `python scripts/migrate_devolucao.py --apply`.
3. Depois da revisão, registre o ponto de partida:

```powershell
python scripts/migrate.py baseline --legacy-reviewed
python scripts/migrate.py status
```

`baseline` verifica a presença das tabelas e colunas do contrato congelado
`baseline_023.json`, cria `schema_migrations` e registra a versão 23. Repetir esse
comando não duplica o registro. A verificação estrutural não atesta tipos, índices
nem transformações de dados: `--legacy-reviewed` confirma a revisão feita pelo
responsável. Uma base incompleta é recusada. Não use o comando para ocultar
migrações antigas que ainda precisam ser aplicadas.

Em instalação nova, execute `backend/schema.sql`, confira a instalação e registre
a mesma baseline. O schema já inclui os campos de 022/023; não reaplique 022.

## Próximas alterações

Crie SQLs em `backend/migrations/managed/` com número único e crescente, começando
por `024_descricao.sql`. Consulte a [convenção](managed/README.md). Então execute:

```powershell
python scripts/migrate.py status
python scripts/migrate.py apply
```

O runner executa apenas SQLs dessa pasta. Registra nome, versão, checksum SHA-256,
estado e datas. Um bloqueio MySQL por banco impede dois runners simultâneos.
Arquivos já aplicados são imutáveis; correções recebem outra versão. Finais de
linha LF e CRLF produzem o mesmo checksum. O contrato de baseline também é imutável.
Não há migração 024 nesta entrega: o recurso novo é o controle de versões.

## Falhas e recuperação

O MySQL pode confirmar DDL implicitamente. Se um SQL falhar no meio, tabelas ou
colunas anteriores ao erro podem já existir. O runner registra `failed`; uma
interrupção abrupta pode deixar `running`. Novas aplicações são bloqueadas.

O responsável deve revisar o SQL e o estado real do banco, restaurar o backup ou
concluir as etapas restantes sob manutenção. Só depois de confirmar que o efeito
completo da versão foi obtido, pode corrigir seu registro para `state='applied'`
e preencher `applied_at` em `schema_migrations`, mantendo nome e checksum originais.
Documente a recuperação. Não apague o registro nem reexecute o arquivo inteiro
sem conferir efeitos parciais. O runner não oferece rollback automático de DDL.

## Legado e scripts opcionais

Os SQLs históricos continuam disponíveis para instalações antigas e revisão manual.
Não execute a pasta inteira: 013 limpa dados; 014 e 017 criam dados/usuários de teste;
015 configura roles técnicas globais. Eles não participam da execução automática.

O SQL 023 é compatível com MySQL e consulta `information_schema` antes de adicionar
`fornecedor_id`. O utilitário de devolução aplica apenas os campos ausentes de
022/023, preservando saldos e referências históricas. Fornecedores de devoluções
antigas permanecem nulos.

## Validação

`python scripts/check_migrations_mysql.py` valida baseline, reaplicação, checksum,
concorrência e falha parcial de DDL em base temporária, removida ao terminar.
O CI executa esse teste no MySQL 8.0.46; MariaDB não está coberto por essa matriz.
