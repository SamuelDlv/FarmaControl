# Operação: vendas, estoque e devoluções

Consolidado em **11/11/2026**. Consulte [API](API.md), [banco](database_schema_design.md) e [permissões](SEGURANCA.md#permissoes).

- [Vendas e PDV](#pdv)
- [Devolução ao fornecedor](#devolucao)

<a id="pdv"></a>

## Vendas e PDV

Revisado em **23/10/2026**. Página: `frontend/src/pages/sistema/vendas/vendas.html`. Implementação: `catalogo_pdv` e `concluir_pdv` em `backend/farmacontrol/routes/vendas.py`. Consulte também [API](API.md) e [banco](database_schema_design.md).

### Acesso e catálogo

A tela fica entre Dashboard e Estoque. Atendente, Farmacêutico, Gerente / Administrador, Proprietário e TI / Suporte acessam consulta e conclusão; Compras e Visualizador não acessam. A regra é fixa no servidor e no menu, independente da matriz editável dos outros módulos. Não exige migração adicional sobre o schema atual.

Busca por nome, código de barras, fabricante e princípio ativo, filtro por tipo/disponibilidade, ordenação por preço e comparação de até três produtos. O botão Pesquisar ↵ e Enter executam a pesquisa; se o catálogo não carregou, tentam buscá-lo novamente. F2 foca a busca; F8 abre a revisão. Enter não adiciona itens ao carrinho. Preços são por unidade comercial cadastrada, não por comprimido ou dose.

Não há classificação estruturada de genérico/similar/referência no catálogo atual. A busca por mesmo princípio ativo ajuda a localizar opções, mas não certifica intercambialidade; apresentação, dose e forma devem ser conferidas pelo responsável. Produtos marcados com receita exigem confirmação da conferência; isso não constitui validação clínica nem armazenamento da prescrição.

### Conclusão transacional

`GET /vendas/catalogo` fornece dados comerciais e lotes; `POST /vendas/balcao` calcula o total com os preços do banco, rejeita preço alterado, saldo insuficiente, quantidades inválidas e lotes vencidos. A venda, os itens, as saídas, o financeiro e a auditoria são confirmados juntos. As linhas de estoque são bloqueadas em ordem de ID. A interface prioriza lotes pelo vencimento. Os endpoints antigos de vendas não foram substituídos.

O pedido admite de 1 a 100 lotes, sem repetir `estoque_id`. IDs e quantidades precisam ser inteiros; a quantidade por item fica entre 1 e 100.000, além de depender do saldo disponível. As formas aceitas são `dinheiro`, `pix`, `cartao_credito` e `cartao_debito`.

O backend valida novamente o estado do lote e seu preço, mesmo que o catálogo tenha sido carregado recentemente. Uma mudança de estoque ou preço durante o atendimento pode impedir a conclusão. A categoria financeira de vendas precisa estar configurada no banco.

### Operação na tela

1. Pesquise ou filtre os produtos disponíveis.
2. Confira produto, apresentação, preço unitário e lotes.
3. Adicione quantidades ao carrinho e revise os itens.
4. Confira a receita quando exigida e registre essa confirmação.
5. Escolha a forma de pagamento após confirmação do operador.
6. Conclua e confira o resultado antes de iniciar outro atendimento.

### Pagamento e resposta incerta

Pagamento é registrado após confirmação do operador, sem cobrança automática, integração com adquirente ou emissão fiscal. Nesta versão, o carrinho permanece somente na página e avisa antes de sair. Se a resposta de conclusão se perder, a interface bloqueia nova tentativa e orienta conferir o histórico; não há reenvio automático nem chave persistente de idempotência.

### Validação

Execute pela raiz, com as dependências instaladas:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_pdv.py -v
node --test tests/vendas.test.cjs
node scripts/check_frontend.cjs
node scripts/check_pdv.cjs
```

O último comando usa Chrome isolado, catálogo fictício e API simulada; não grava vendas reais. Capturas e resultado ficam em `.audit-backup/pdv/`. Os testes Python verificam validação e rollback com banco simulado; concorrência e SQL real exigem uma base de homologação. Reinicie o backend após atualizar o código.

<a id="devolucao"></a>

## Devolução ao fornecedor

POST /movimentacoes-estoque usa tipo_movimentacao=saida e finalidade=devolucao_fornecedor, com estoque_id, quantidade inteira positiva, motivo obrigatorio (ate 255 caracteres) e observacao opcional. Nao aceita estoque_destino_id.

O fornecedor_id e capturado do produto no servidor; se enviado, precisa coincidir com o cadastro. Produtos sem fornecedor permitem devolucao com referencia nula. O identificador permanece como referencia historica, sem chave estrangeira que o apague junto com o cadastro. Nao se infere o fornecedor de movimentacoes antigas. Produto/lote sao vinculados pelo estoque_id e registrados na auditoria. Nao ha comprovante anexado neste escopo.

Exige perfil administrativo de estoque, permissao persistida e CSRF. Permite baixa administrativa de lote vencido sem alterar as regras de venda. Saldo, movimentacao e auditoria sao gravados na mesma transacao; transferencia interna mantem destino obrigatorio e dois saldos.

Em bases existentes, confira primeiro o [guia de migrações](../backend/migrations/README.md), a baseline e o estado das versões 022/023. O utilitário legado de atualização é: `.\.venv\Scripts\python.exe -B scripts/migrate_devolucao.py --apply`. O utilitario idempotente aplica os campos da migracao 022 se faltarem e acrescenta fornecedor_id (023). Nao modifica saldos nem reclassifica historico. Em outras instalacoes, aplicar 022 e backend/migrations/023_fornecedor_devolucao.sql.

Arquivos alterados: backend/farmacontrol/routes/estoque.py, services/audit.py, backend/schema.sql, migrations/023_fornecedor_devolucao.sql, scripts/migrate_devolucao.py, vencimentos.html/js e testes de descarte/devolucao. Historico e relatorios ja exibem a finalidade de devolucao e excluem essas baixas das vendas.

Validacao: executar `.\.venv\Scripts\python.exe -B -m unittest discover -s tests`.

Distribuicao pelo GitHub: incluir backend/migrations/023_fornecedor_devolucao.sql, backend/migrations/README.md e scripts/migrate_devolucao.py junto das alteracoes de codigo. A ordem de aplicacao esta no README de migracoes. Publicar o codigo nao atualiza o banco automaticamente.
