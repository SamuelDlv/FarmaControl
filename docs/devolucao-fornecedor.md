# Devolucao ao fornecedor

POST /movimentacoes-estoque usa tipo_movimentacao=saida e finalidade=devolucao_fornecedor, com estoque_id, quantidade inteira positiva, motivo obrigatorio (ate 255 caracteres) e observacao opcional. Nao aceita estoque_destino_id.

O fornecedor_id e capturado do produto no servidor; se enviado, precisa coincidir com o cadastro. Produtos sem fornecedor permitem devolucao com referencia nula. O identificador permanece como referencia historica, sem chave estrangeira que o apague junto com o cadastro. Nao se infere o fornecedor de movimentacoes antigas. Produto/lote sao vinculados pelo estoque_id e registrados na auditoria. Nao ha comprovante anexado neste escopo.

Exige perfil administrativo de estoque, permissao persistida e CSRF. Permite baixa administrativa de lote vencido sem alterar as regras de venda. Saldo, movimentacao e auditoria sao gravados na mesma transacao; transferencia interna mantem destino obrigatorio e dois saldos.

Antes de iniciar a versao atualizada: `.\.venv\Scripts\python.exe -B scripts/migrate_devolucao.py --apply`. O utilitario idempotente aplica os campos da migracao 022 se faltarem e acrescenta fornecedor_id (023). Nao modifica saldos nem reclassifica historico. Em outras instalacoes, aplicar 022 e backend/migrations/023_fornecedor_devolucao.sql.

Arquivos alterados: backend/farmacontrol/routes/estoque.py, services/audit.py, backend/schema.sql, migrations/023_fornecedor_devolucao.sql, scripts/migrate_devolucao.py, vencimentos.html/js e testes de descarte/devolucao. Historico e relatorios ja exibem a finalidade de devolucao e excluem essas baixas das vendas.

Validacao: executar `.\.venv\Scripts\python.exe -B -m unittest discover -s tests`.



Distribuicao pelo GitHub: incluir backend/migrations/023_fornecedor_devolucao.sql, backend/migrations/README.md e scripts/migrate_devolucao.py junto das alteracoes de codigo. A ordem de aplicacao esta no README de migracoes. Publicar o codigo nao atualiza o banco automaticamente.
