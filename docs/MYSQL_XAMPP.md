# MySQL, MariaDB e XAMPP

O Workbench é um cliente de administração. O XAMPP normalmente distribui MariaDB
com o nome “MySQL” no painel; confira a versão real com:

```sql
SELECT VERSION(), @@version_comment, @@port, @@datadir;
```

O schema base usa InnoDB e `utf8mb4_unicode_ci`, disponíveis em MySQL 8 e
MariaDB 10.4+. A matriz de CI verifica a importação completa nos dois motores.
Não copie a pasta de dados entre MySQL e MariaDB: transfira o banco da aplicação
por exportação/importação SQL, conforme [TRANSFERENCIA.md](TRANSFERENCIA.md).

## Instalação nova

1. Inicie o servidor escolhido. Se MySQL instalado e XAMPP coexistirem, use portas
   diferentes ou execute somente um deles na mesma porta.
2. Importe `backend/schema.sql` pelo Workbench ou phpMyAdmin. É um schema para
   instalação nova, não uma rotina de reparo ou de atualização de dados existentes.
3. Configure `backend/.env` para essa instância: `DB_HOST`, `DB_PORT`, `DB_NAME`,
   `DB_USER` e `DB_PASSWORD`. Não presuma que senha e porta são iguais nos dois PCs.
4. Inicie o FarmaControl. O Apache é necessário somente para acessar o phpMyAdmin;
   o FarmaControl serve suas próprias páginas em `127.0.0.1:5000`.

As tabelas `perfis` e `perfil_permissoes` fazem parte do schema e continuam
controlando o acesso funcional. As roles técnicas `fc_*` são opcionais: a TI pode
executar `backend/setup/technical_roles.sql` separadamente, com privilégios
administrativos. O schema base não executa `CREATE ROLE`, `GRANT`, reparos ou
alterações nas tabelas internas `mysql.*`. As migrações históricas não foram alteradas.

## Erro 1034 na tabela mysql.db

A imagem mostra falha no `GRANT`, com índice incorreto na tabela `db`.
`mysql.db` pertence ao sistema de privilégios do servidor, não às tabelas do
FarmaControl. Separar as roles evita que a importação dependa desse provisionamento,
mas não recupera um servidor já corrompido. Não há reparo automático na aplicação.

Se o problema reaparecer, preserve backup antes de manutenção, registre a versão
e consulte o log de erro. `CHECK TABLE mysql.db` permite diagnosticar essa tabela;
`REPAIR TABLE` só se aplica aos motores que o suportam, como Aria/MyISAM, e não
é reparo de InnoDB. Não transforme reparos repetidos em etapa normal de importação.
Não exclua `ibdata1`, arquivos de redo/Aria ou substitua a pasta `data` como tentativa
genérica: isso pode destruir dados ou agravar a recuperação.

## Encerramento

Encerre primeiro o FarmaControl com `Ctrl+C` ou `Encerrar-FarmaControl.bat` e
aguarde a confirmação. O servidor local interrompe a aceitação de requisições e
aguarda os handlers ativos terminarem, com commit/rollback conforme a rota e
fechamento das conexões pelo Flask. Só depois pare o MySQL no painel do XAMPP,
se desejar. O BAT não para o banco, Apache ou outros processos.

O sinal de controle é um evento nativo da sessão Windows, identificado pelo
caminho absoluto do projeto. Não há endpoint HTTP de desligamento, senha gravada
em arquivo ou finalização forçada como alternativa. Após atualizar uma versão
antiga já aberta, use `Ctrl+C` uma vez e reinicie pelo iniciador. Se o BAT não
confirmar o encerramento em 30 segundos, confira a janela do servidor; ele pode
estar aguardando uma requisição demorada. Não desligue o banco nesse intervalo.

## “MySQL shutdown unexpectedly” no painel

A mensagem do painel é genérica e não identifica a causa. O BAT anterior encontrado
no repositório encerrava somente o Python do projeto à força; não continha comando
para encerrar `mysqld`. Portanto, as imagens não comprovam que o BAT derrubou o banco.

Abra **Logs** ao lado de MySQL no XAMPP e preserve o trecho do momento da falha
(normalmente `mysql/data/mysql_error.log`, ou o destino configurado em `my.ini`).
Verifique ali se há erro de porta em uso, privilégios, Aria, InnoDB ou recuperação.
Confira também se outro serviço MySQL está usando a mesma porta. A causa específica
da segunda imagem depende desse log; não pode ser confirmada somente pelo painel.

Referências oficiais:

- [Erro 1034](https://mariadb.com/docs/server/reference/error-codes/mariadb-error-codes-1000-to-1099/e1034)
- [REPAIR TABLE e motores suportados](https://mariadb.com/docs/server/reference/sql-statements/table-statements/repair-table)
- [SET DEFAULT ROLE no MariaDB](https://mariadb.com/docs/server/reference/sql-statements/account-management-sql-statements/set-default-role)
- [Diagnóstico de quedas do MySQL](https://dev.mysql.com/doc/refman/8.4/en/crashing.html)
