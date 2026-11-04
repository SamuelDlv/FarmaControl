# Migracoes do banco

Os arquivos SQL desta pasta devem acompanhar o codigo no GitHub. Publicar o repositorio nao executa as migracoes automaticamente.

## Correcao da devolucao ao fornecedor

Antes de iniciar a API atualizada, selecione o banco do FarmaControl no cliente SQL (por exemplo, phpMyAdmin) e execute:

1. `022_finalidade_movimentacao.sql`, somente se as colunas `finalidade` e `motivo` ainda nao existirem.
2. `023_fornecedor_devolucao.sql`, para acrescentar a referencia historica do fornecedor.

O SQL 023 usa a sintaxe do MariaDB utilizado pelo XAMPP. Para aplicar com verificacao das colunas existentes, tambem esta versionado o utilitario `scripts/migrate_devolucao.py`; execute na raiz do projeto:

```powershell
.\.venv\Scripts\python.exe -B scripts/migrate_devolucao.py --apply
```

O utilitario usa a configuracao local de `backend/.env` e aplica os campos ausentes das migracoes 022 e 023. Nao publique o arquivo `.env` nem credenciais no GitHub.

As migracoes preservam saldos e registros anteriores. O fornecedor de devolucoes antigas permanece nulo; nao e inferido do cadastro atual. Depois da migracao, reinicie a API.

Para banco novo, `backend/schema.sql` ja inclui esses campos. Nao reaplique a migracao 022 nesse caso.

Nao execute todos os arquivos desta pasta indiscriminadamente: existem scripts opcionais de limpeza e de dados de teste.
