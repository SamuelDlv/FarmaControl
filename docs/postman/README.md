# FarmaControl no Postman

Consolidado em **11/11/2026**; conteúdo revisado em **09/11/2026**, comparando a Collection com os contratos de rotas do projeto.

Importe `FarmaControl.postman_collection.json` pelo botão **Import** do Postman. O arquivo usa Collection v2.1 e contém todas as 43 rotas GET e 21 POST registradas em `backend/farmacontrol/routes/`, incluindo três rotas de arquivos do frontend. PUT e DELETE não fazem parte desta Collection. A modularização preserva as URLs e os métodos da Collection.

## Configuração e login

1. Inicie o banco e o backend conforme o [README do backend](../../backend/README.md), com schema e migrações conferidos.
2. Abra a Collection e, em **Variables**, configure `base_url` (padrão `http://localhost:5000`), `email` e `password` de uma conta aprovada.
3. Envie **POST /auth/login**, na pasta **Autenticacao**. O Postman armazena o cookie de sessão; o script da requisição salva `csrf_token` automaticamente.
4. Execute as requisições desejadas com **Send**. Os POST protegidos já enviam `X-CSRF-Token`.

Mantenha o cookie jar habilitado e use o mesmo host durante a sessão: `localhost` e `127.0.0.1` não compartilham cookies. Não há Bearer token. Se a sessão expirar ou for invalidada, faça login novamente. Reiniciar com uma chave de sessão temporária invalida os cookies anteriores; uma chave persistente preserva a assinatura entre reinícios. Um 403 pode indicar falta de permissão do perfil ou token CSRF inválido.

Não defina no ambiente variáveis com os mesmos nomes dos IDs e de `csrf_token`: elas têm precedência sobre as variáveis da Collection atualizadas pelos scripts. As credenciais estão vazias no arquivo entregue; preencha-as localmente.

## Cadastro e consultas

Os IDs iniciais (`1`) são exemplos. Substitua-os por IDs das consultas GET ou crie registros nesta ordem:

1. POST de categoria e fornecedor: ajuste `fornecedor_cnpj` para um valor de teste ainda não cadastrado.
2. POST de produto, usando os IDs salvos de categoria e fornecedor.
3. POST de estoque, usando o ID salvo do produto e um `lote` ainda não cadastrado para ele.
4. POST de cliente, se for usar vendas com cliente ou receitas.
5. Compras, movimentações, vendas e receitas conforme o cenário desejado.

POSTs que retornam `id` salvam a variável correspondente automaticamente. As requisições GET de detalhe reutilizam esses IDs. Consultas de lista não selecionam registros automaticamente. Filtros disponíveis estão na aba **Params**, inicialmente desmarcados; habilite e preencha os desejados.

Para o PDV, consulte **GET /vendas/catalogo** e ajuste as variáveis `estoque_id` e `preco_venda` ao lote e preço atuais. A variável `preco_venda` preenche o campo JSON `preco_unitario`; o servidor confere o preço e o saldo sob bloqueio. **POST /vendas/balcao** conclui a venda e altera estoque e financeiro. Os exemplos de **POST /compras** e **POST /vendas** usam status pendente.

Para transações financeiras, obtenha `financeiro_categoria_id` em **GET /financeiro/categorias**, escolhendo uma categoria do mesmo tipo do corpo (o exemplo usa `despesa`). Atualize datas conforme necessário; `data_prescricao` é um exemplo fixo e `data_validade` precisa ser adequada ao lote.

## Fluxos alternativos de autenticação

- Cadastro público: preencha `cadastro_email` e `nova_senha`; a conta fica pendente de aprovação. Revise os aceites de termos e privacidade antes de enviar.
- Análise administrativa: `usuario_id` é o ID da conta que será analisada, obtido em GET de usuários/pendentes.
- Convite: preencha `convite_email`; o envio depende do SMTP. Copie o token do link recebido para `convite_token`. Para aceitar, acrescente `"convite_token": "{{convite_token}}"` ao corpo de **POST /auth/register**; o servidor resolve identidade e perfil pelo convite, e o script salva o CSRF retornado.
- Recuperação: copie o token do e-mail para `reset_token` e preencha `nova_senha` antes da redefinição. Atualize `password` e faça login novamente.
- Logout: execute ao terminar; encerra a sessão e limpa o CSRF salvo.

Use a Collection como catálogo de requisições individuais. Executar tudo no Runner mistura fluxos alternativos de cadastro, recuperação, recusa de convite e logout, além de gravar dados e enviar e-mails. Repetir cadastros pode gerar conflitos por campos únicos. Os testes de resposta esperam sucesso (200/201 e `ok: true`); respostas de validação aparecem como testes falhos para facilitar a identificação.

O JSON, os corpos após substituição das variáveis e a cobertura GET/POST foram conferidos estaticamente. As requisições não foram enviadas a uma instância com banco e credenciais reais.

## Devolução, migrações e limites da validação

`POST /movimentacoes-estoque` também atende descarte e devolução. Para testar
devolução, ajuste o corpo com `tipo_movimentacao: "saida"`,
`finalidade: "devolucao_fornecedor"`, `estoque_id`, quantidade inteira positiva
e `motivo`. Não envie `estoque_destino_id`. O fornecedor vem do produto no
servidor; se informado, precisa corresponder ao cadastro. O contrato completo
está em [devolução ao fornecedor](../operacao.md#devolucao).

Essas baixas administrativas podem retirar lote vencido; isso não libera vendas
de lotes vencidos. Revise a preparação 022/023 e a baseline no
[guia de migrações](../../backend/migrations/README.md) antes do teste.

A conferência documental de 09/11 preservou os 64 exemplos (43 GET e 21 POST).
O [CI de referência](https://github.com/SamuelDlv/FarmaControl/actions/runs/42654607638)
passou com testes de API e integração MySQL/navegador; ele não executa esta
Collection no Postman. O roteiro manual completo está [neste guia](#roteiro).
PUT e DELETE estão descritos na [referência da API](../api.md).

<a id="roteiro"></a>

## Roteiro manual de execução

Use este roteiro com [FarmaControl.postman_collection.json](FarmaControl.postman_collection.json). Ele cobre os 64 GET e POST da Collection. Execute cada requisição com **Send** e confira a resposta antes de continuar.

O fluxo principal pressupõe uma conta já aprovada. Cadastro, convite e recuperação de senha são cenários separados, descritos ao final. Não execute a Collection inteira de uma vez no Runner.

### 1. Preparar as variáveis

Com o banco configurado e o backend iniciado, abra **Collection → Variables** e preencha:

| Variável | O que colocar |
| --- | --- |
| `base_url` | `http://localhost:5000`, ou o endereço da sua instância, sem barra final e sem `/api` |
| `email` e `password` | Credenciais de uma conta aprovada com acesso aos módulos que deseja testar |
| `fornecedor_cnpj` | CNPJ de teste ainda não cadastrado |
| `lote` | Identificador de lote de teste, por exemplo `POSTMAN-001` |
| `data_validade` | Data adequada ao lote, no formato `YYYY-MM-DD` |
| `data_prescricao` | Data da prescrição de teste, no formato `YYYY-MM-DD` |
| `chave` | Chave nova para o teste de configuração, por exemplo `postman_teste_001` |

Os IDs com valor inicial `1` são apenas exemplos. Os POST de criação que retornam `id` atualizam a variável correspondente automaticamente. GET de lista não escolhe um registro: se usar dados já existentes, copie o ID desejado manualmente para a variável.

Mantenha o cookie jar habilitado. Use sempre o mesmo host e evite variáveis de ambiente com os mesmos nomes dos IDs e de `csrf_token`, pois elas sobrepõem as variáveis da Collection.

### 2. Iniciar a sessão

| Ordem | Requisição | O que conferir |
| --- | --- | --- |
| 1 | `GET /health` | Disponibilidade do serviço; resolva erros antes de avançar |
| 2 | `GET /configuracoes/visual` | Preferências visuais públicas |
| 3 | `POST /auth/login` | Use `email` e `password`; sucesso salva cookie e `csrf_token` |
| 4 | `GET /admin/perfis/permissoes` | Matriz de permissões, se sua conta tiver acesso |
| 5 | `GET /admin/usuarios` | Usuários cadastrados, se autorizado |
| 6 | `GET /admin/pendentes` | Cadastros pendentes; não é necessário aprová-los para seguir com sua conta atual |

Se não tiver uma conta aprovada, consulte o cenário de cadastro na seção 8. As consultas administrativas podem retornar 403 para perfis sem acesso; isso não significa que os demais módulos também estejam indisponíveis.

### 3. Criar os cadastros básicos

Execute os POST com os exemplos da Collection, ajustando os dados que desejar. Os GET seguintes permitem conferir cada criação.

| Ordem | Requisição | Dependência ou resultado |
| --- | --- | --- |
| 7 | `POST /categorias-produto` | Salva `categoria_id` |
| 8 | `GET /categorias-produto` | Lista as categorias |
| 9 | `GET /categorias-produto/{{categoria_id}}` | Confirma a categoria criada |
| 10 | `POST /fornecedores` | CNPJ e razão social devem estar disponíveis; salva `fornecedor_id` |
| 11 | `GET /fornecedores` | Lista os fornecedores |
| 12 | `GET /fornecedores/{{fornecedor_id}}` | Confirma o fornecedor criado |
| 13 | `POST /produtos` | Usa `categoria_id` e `fornecedor_id`; salva `produto_id` |
| 14 | `GET /produtos` | Lista o catálogo |
| 15 | `GET /produtos/{{produto_id}}` | Confirma preços e regras do produto |
| 16 | `POST /clientes` | Salva `cliente_id` |
| 17 | `GET /clientes` | Lista os clientes |
| 18 | `GET /clientes/{{cliente_id}}` | Confirma o cliente criado |

O produto do exemplo é do tipo `outro` e não exige receita. Para testar medicamento, ajuste o corpo conforme as regras do catálogo; medicamentos devem exigir validade. O cliente é usado mais adiante em vendas e receitas.

### 4. Criar estoque, movimentação e compra

| Ordem | Requisição | Dependência ou resultado |
| --- | --- | --- |
| 19 | `GET /estoque/parametros` | Consulte as regras de estoque |
| 20 | `POST /estoque` | Usa `produto_id`, `lote` e validade; salva `estoque_id`. A combinação produto/lote deve ser nova |
| 21 | `GET /estoque` | Lista os lotes |
| 22 | `GET /estoque/{{estoque_id}}` | Confirma o lote e a quantidade inicial |
| 23 | `POST /movimentacoes-estoque` | O exemplo adiciona 5 unidades ao `estoque_id`; salva `movimentacao_id` |
| 24 | `GET /movimentacoes-estoque` | Lista as movimentações |
| 25 | `GET /movimentacoes-estoque/{{movimentacao_id}}` | Confirma a movimentação criada |
| 26 | `GET /estoque/{{estoque_id}}/historico` | Confirma o histórico do lote; repita o GET de detalhe para conferir o saldo |
| 27 | `POST /compras` | Usa fornecedor e produto já criados; salva `compra_id` |
| 28 | `GET /compras` | Lista as compras |
| 29 | `GET /compras/{{compra_id}}` | Confirma a compra e seus itens |

O exemplo de compra usa `status: "pendente"`, portanto não aumenta o estoque. Para testar recebimento na criação, use `status: "recebido"` com lote e validade adequados. Atualizar uma compra existente exige PUT, que não está nesta Collection.

### 5. Criar receita e testar vendas

| Ordem | Requisição | Dependência ou resultado |
| --- | --- | --- |
| 30 | `POST /receitas` | Usa `cliente_id` e `produto_id`; revise os dados fictícios e as datas. Salva `receita_id` |
| 31 | `GET /receitas` | Lista as receitas |
| 32 | `GET /receitas/{{receita_id}}` | Confirma o registro |
| 33 | `POST /vendas` | O exemplo cria venda pendente com cliente e produto; salva `venda_id` |
| 34 | `GET /vendas/{{venda_id}}` | Confira a venda pendente antes de testar o PDV |
| 35 | `GET /vendas/catalogo` | Escolha um lote disponível e confira seu preço; atualize `estoque_id` e `preco_venda` |
| 36 | `POST /vendas/balcao` | Cria outra venda, concluída, e altera estoque e financeiro; sobrescreve `venda_id` com o ID desta venda |
| 37 | `GET /vendas/{{venda_id}}` | Agora consulta a venda concluída pelo PDV |
| 38 | `GET /vendas` | Confira as duas vendas criadas |

**POST /vendas/balcao não conclui a venda pendente do passo 33: ele cria uma venda nova.** Se quiser testar apenas o PDV, pule os passos 33 e 34.

No PDV, o preço informado precisa ser igual ao preço atual do catálogo e o lote deve ter saldo e estar válido. Para produtos que exigem receita, o corpo precisa de `receita_conferida: true` após a conferência; apenas cadastrar uma receita no passo 30 não substitui essa confirmação. Repita o GET de estoque e de histórico para observar a saída.

### 6. Financeiro, alertas e configurações

| Ordem | Requisição | Dependência ou resultado |
| --- | --- | --- |
| 39 | `GET /financeiro/categorias` | Copie o ID de uma categoria do tipo `despesa` para `financeiro_categoria_id`, conforme o corpo do exemplo |
| 40 | `POST /financeiro/transacoes` | Cria uma despesa independente da venda; não use para lançar novamente a receita já gerada pelo PDV |
| 41 | `GET /financeiro/transacoes` | Confira a transação criada; o POST não salva um ID porque a resposta não o fornece |
| 42 | `GET /financeiro/stats` | Consulte os indicadores financeiros |
| 43 | `GET /financeiro/fluxo` | Consulte o fluxo financeiro |
| 44 | `POST /alertas` | Cria alerta manual de teste; salva `alerta_id` |
| 45 | `GET /alertas` | Lista os alertas |
| 46 | `GET /alertas/{{alerta_id}}` | Confirma o alerta criado |
| 47 | `POST /configuracoes` | Cria a `chave` nova definida nas variáveis; repetir a mesma chave pode retornar 409 |
| 48 | `GET /configuracoes/{{chave}}` | Confirma o registro criado |
| 49 | `GET /configuracoes` | Consulta as configurações expostas pelo sistema |

Uma chave de teste não passa a controlar uma funcionalidade apenas por ser criada. Não use `tema` ou `tema_efetivo`: essas chaves foram aposentadas. Em transações financeiras, `data_transacao` vazia usa a data do banco; para informar uma data, use `YYYY-MM-DD`.

### 7. Conferir resultados e encerrar

| Ordem | Requisição | O que conferir |
| --- | --- | --- |
| 50 | `GET /dashboard/stats` | Indicadores após os lançamentos |
| 51 | `GET /relatorios/estoque` | Relatório de estoque |
| 52 | `GET /relatorios/vencimentos` | Relatório de vencimentos |
| 53 | `GET /relatorios/compras` | Relatório de compras |
| 54 | `GET /admin/logs` | Eventos registrados, se sua conta tiver permissão |
| 55 | `GET /pages/sistema/{{pagina}}` | Arquivo da tela; `pagina` vem preenchida com `dashboard/dashboard.html` |
| 56 | `GET /pages/proprietario/{{pagina}}` | Caminho compatível para a mesma tela |
| 57 | `GET /{{arquivo}}` | Arquivo estático; o exemplo usa `utils/sidebar-init.js` |
| 58 | `POST /auth/logout` | Encerra a sessão e limpa o CSRF salvo |

Os três GET de frontend retornam arquivos, não JSON. Relatórios e consultas com filtros podem não mostrar registros fora do período selecionado; revise **Params**. Os parâmetros opcionais vêm desmarcados na Collection.

Se quiser testar os cenários seguintes, faça login novamente quando houver ações protegidas.

### 8. Cenário separado: cadastrar e aprovar uma conta

1. Preencha `cadastro_email` com um e-mail ainda não usado e `nova_senha` com a senha escolhida (mínimo de 8 caracteres e máximo de 72 bytes UTF-8).
2. Execute **POST /auth/register**. Revise nome, sobrenome, perfil e os dois aceites no corpo. O cadastro público fica pendente.
3. Configure `email` e `password` de uma conta existente com permissão administrativa e execute **POST /auth/login**.
4. Execute **GET /admin/pendentes**. Localize o cadastro novo e copie seu ID para `usuario_id`.
5. Execute **POST /admin/analisar-cadastro** com `decisao: "aprovado"`. Para testar rejeição em outro cenário, use `"rejeitado"` e informe o motivo.
6. Execute **GET /admin/usuarios** para conferir o status.
7. Execute **POST /auth/logout**.
8. Troque `email` e `password` pelas credenciais do novo cadastro e execute **POST /auth/login**.

O cadastro público não cria automaticamente o administrador necessário para aprová-lo. Se não existir uma conta aprovada com essa permissão, será necessário preparar o acesso administrativo conforme a instalação do projeto. O envio de notificações depende da configuração SMTP.

### 9. Cenário separado: convidar uma pessoa

1. Faça **POST /auth/login** com uma conta autorizada a convidar.
2. Preencha `convite_email` com o destinatário e execute **POST /admin/convites**. Revise nome, sobrenome e perfil no corpo.
3. Obtenha o token no link do e-mail recebido e coloque-o em `convite_token`. A resposta da criação não fornece esse token.
4. Execute **GET /auth/convites/{{convite_token}}** para consultar o convite.
5. Escolha apenas um dos dois desfechos abaixo para esse token.

#### Aceitar

1. Encerre a sessão administrativa com **POST /auth/logout**.
2. Preencha `nova_senha` e adicione `"convite_token": "{{convite_token}}"` ao JSON de **POST /auth/register**, mantendo os aceites conforme a decisão do convidado.
3. Execute **POST /auth/register**. O servidor usa os dados de identidade e perfil do convite; o acesso é liberado e a sessão criada. O script salva o CSRF retornado.
4. Remova `convite_token` do corpo antes de voltar a testar cadastro público.

#### Recusar

1. Execute **POST /auth/convites/{{convite_token}}/recusar**.
2. O convite é consumido e não cria uma conta. Para testar aceitação depois, gere outro convite e use o novo token.

Convites expirados, aceitos ou recusados não podem ser reutilizados. Aceitar o convite muda a sessão para a conta convidada; faça novo login administrativo se precisar voltar às ações administrativas.

### 10. Cenário separado: recuperar a senha

1. Encerre uma sessão ativa com **POST /auth/logout** antes deste teste.
2. Configure `email` com a conta de teste e execute **POST /auth/recuperar-senha**.
3. Abra o e-mail e copie o token do link para `reset_token`. A resposta é genérica e não confirma se a conta existe; o envio depende de uma conta aprovada e SMTP configurado.
4. Preencha `nova_senha` e execute **POST /auth/redefinir-senha**.
5. Atualize `password` com a nova senha e execute **POST /auth/login**.

O token de recuperação é de uso único e expira. A redefinição invalida sessões vinculadas à senha anterior.

### Se uma etapa falhar

| Resposta | Próximo passo |
| --- | --- |
| 400 | Leia `mensagem` e `campo`; confira tipos, campos obrigatórios e datas |
| 401 | Faça login com uma conta aprovada |
| 403 | Confira permissões, cookie e CSRF; renove a sessão se necessário |
| 404 | Confira o ID ou caminho usado |
| 409 | Confira campos únicos, lote, preço e saldo, conforme a mensagem |
| 410 | Confira token expirado/consumido ou chave de configuração aposentada |
| 429 | Aguarde o prazo indicado antes de repetir ações de autenticação |
| 500/503 | Confira backend, banco, migrações e dependências nos logs |

Os testes da Collection esperam 200/201 e `ok: true` nas respostas da API. Falhas esperadas, como token expirado ou acesso recusado, aparecem como testes falhos. As requisições POST gravam dados; confirme o resultado antes de repetir uma operação cuja resposta se perdeu.
