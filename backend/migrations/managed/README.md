# Migrações controladas

Revisado em **09/11/2026**. Esta pasta ainda não contém arquivos SQL; a próxima versão é 024.

Novos SQLs usam `024_descricao_em_snake_case.sql`, `025_...sql` e assim por diante.
O número é único e crescente. Arquivos aplicados não devem ser editados ou removidos.
Uma correção recebe outro número. Não coloque dados de teste, limpeza, `USE`,
`CREATE DATABASE`, roles globais nem comandos do cliente como `DELIMITER` nesta pasta.
Use somente SQL do servidor para a base selecionada. Revise os SQLs antes de publicar.

Ainda não há alterações posteriores à base 023. O controle de versões é criado
pelo comando `python scripts/migrate.py baseline --legacy-reviewed`, depois das
verificações descritas no [guia](../README.md). `apply` executa apenas os SQLs desta
pasta, em ordem, sob bloqueio exclusivo por banco.


## Conferir e aplicar

Execute pela raiz do projeto, no ambiente Python configurado:

```powershell
python scripts/migrate.py status
# Depois da revisão do SQL, do destino e do backup:
python scripts/migrate.py apply
```

O registro de baseline é necessário antes de `apply`. Não modifique uma migração
aplicada para corrigir falhas ou acrescentar comentários; o checksum considera
todo o conteúdo. Uma execução `failed` ou `running` exige inspeção manual antes
de continuar, pois DDL pode ter sido confirmado parcialmente pelo MySQL.

O [CI de referência](https://github.com/SamuelDlv/FarmaControl/actions/runs/42654607638)
validou baseline, checksums, concorrência e falha parcial em MySQL descartável.
Os procedimentos e limites estão no [guia de migrações](../README.md) e em
[CI](../../../docs/CI.md). Esta atualização documental não adiciona migração nem
altera os SQLs ou o contrato congelado da baseline.
