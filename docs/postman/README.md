# FarmaControl no Postman

Importe `FarmaControl.postman_collection.json` pelo botão **Import** do Postman. O arquivo usa Collection v2.1 e contém todas as 43 rotas GET e 21 POST declaradas em `backend/app.py`, incluindo três rotas de arquivos do frontend. PUT e DELETE não fazem parte desta Collection.

## Configuração e login

1. Inicie o banco e o backend conforme `backend/README.md`.
2. Abra a Collection e, em **Variables**, configure `base_url` (padrão `http://localhost:5000`), `email` e `password` de uma conta aprovada.
3. Envie **POST /auth/login**, na pasta **Autenticacao**. O Postman armazena o cookie de sessão; o script da requisição salva `csrf_token` automaticamente.
4. Execute as requisições desejadas com **Send**. Os POST protegidos já enviam `X-CSRF-Token`.

Mantenha o cookie jar habilitado e use o mesmo host durante a sessão: `localhost` e `127.0.0.1` não compartilham cookies. Não há Bearer token. Se a sessão expirar ou o backend reiniciar, faça login novamente. Um 403 pode indicar falta de permissão do perfil ou token CSRF inválido.

Não defina no ambiente variáveis com os mesmos nomes dos IDs e de `csrf_token`: elas têm precedência sobre as variáveis da Collection atualizadas pelos scripts. As credenciais estão vazias no arquivo entregue; preencha-as localmente.

## Cadastro e consultas

Os IDs iniciais (`1`) são exemplos. Substitua-os por IDs das consultas GET ou crie registros nesta ordem:

1. POST de categoria e fornecedor: ajuste `fornecedor_cnpj` para um valor de teste ainda não cadastrado.
2. POST de produto, usando os IDs salvos de categoria e fornecedor.
3. POST de estoque, usando o ID salvo do produto e um `lote` ainda não cadastrado para ele.
4. POST de cliente, se for usar vendas com cliente ou receitas.
5. Compras, movimentações, vendas e receitas conforme o cenário desejado.

POSTs que retornam `id` salvam a variável correspondente automaticamente. As requisições GET de detalhe reutilizam esses IDs. Consultas de lista não selecionam registros automaticamente. Filtros disponíveis estão na aba **Params**, inicialmente desmarcados; habilite e preencha os desejados.

Para o PDV, consulte **GET /vendas/catalogo** e ajuste `estoque_id` e `preco_venda` ao lote e preço atuais. **POST /vendas/balcao** conclui a venda e altera estoque e financeiro. Os exemplos de **POST /compras** e **POST /vendas** usam status pendente.

Para transações financeiras, obtenha `financeiro_categoria_id` em **GET /financeiro/categorias**, escolhendo uma categoria do mesmo tipo do corpo (o exemplo usa `despesa`). Atualize datas conforme necessário; `data_prescricao` é um exemplo fixo e `data_validade` precisa ser adequada ao lote.

## Fluxos alternativos de autenticação

- Cadastro público: preencha `cadastro_email` e `nova_senha`; a conta fica pendente de aprovação. Revise os aceites de termos e privacidade antes de enviar.
- Análise administrativa: `usuario_id` é o ID da conta que será analisada, obtido em GET de usuários/pendentes.
- Convite: preencha `convite_email`; o envio depende do SMTP. Copie o token do link recebido para `convite_token`. Para aceitar, acrescente `"convite_token": "{{convite_token}}"` ao corpo de **POST /auth/register**; o servidor resolve identidade e perfil pelo convite, e o script salva o CSRF retornado.
- Recuperação: copie o token do e-mail para `reset_token` e preencha `nova_senha` antes da redefinição. Atualize `password` e faça login novamente.
- Logout: execute ao terminar; encerra a sessão e limpa o CSRF salvo.

Use a Collection como catálogo de requisições individuais. Executar tudo no Runner mistura fluxos alternativos de cadastro, recuperação, recusa de convite e logout, além de gravar dados e enviar e-mails. Repetir cadastros pode gerar conflitos por campos únicos. Os testes de resposta esperam sucesso (200/201 e `ok: true`); respostas de validação aparecem como testes falhos para facilitar a identificação.

O JSON, os corpos após substituição das variáveis e a cobertura GET/POST foram conferidos estaticamente. As requisições não foram enviadas a uma instância com banco e credenciais reais.
