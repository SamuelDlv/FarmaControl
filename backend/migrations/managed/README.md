# Migrações controladas

Novos SQLs usam `024_descricao_em_snake_case.sql`, `025_...sql` e assim por diante.
O número é único e crescente. Arquivos aplicados não devem ser editados ou removidos.
Uma correção recebe outro número. Não coloque dados de teste, limpeza, `USE`,
`CREATE DATABASE`, roles globais nem comandos do cliente como `DELIMITER` nesta pasta.
Use somente SQL do servidor para a base selecionada. Revise os SQLs antes de publicar.

Ainda não há alterações posteriores à base 023. O controle de versões é criado
pelo comando `python scripts/migrate.py baseline --legacy-reviewed`, depois das
verificações descritas no [guia](../README.md). `apply` executa apenas os SQLs desta
pasta, em ordem, sob bloqueio exclusivo por banco.
