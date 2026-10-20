# Autenticação, contas e permissões

Revisado em **19/10/2026**, a partir de `backend/app.py`, `runtime_config.py` e `security.py`. Consulte [backend](../../../backend/README.md) e [API](../../../docs/API.md).

## Páginas públicas

| Página | Finalidade |
| --- | --- |
| `acesso/acesso.html` | Login, cadastro e solicitação de recuperação |
| `convite/convite.html` | Consulta, aceite e recusa de convite |
| `redefinir-senha/redefinir-senha.html` | Nova senha por token |
| `termos/termos.html` | Termos apresentados ao titular |
| `privacidade/privacidade.html` | Política apresentada ao titular |

Cada pasta contém HTML, CSS e JavaScript. `shared/legal.css` compartilha a apresentação dos documentos legais. A entrada local é `http://localhost:5000/pages/acesso/acesso.html`.

## Cadastro público

1. `POST /auth/register` recebe `nome`, `sobrenome`, `email`, `role` e `password`.
2. `accepts_terms` e `accepts_privacy` precisam ser booleanos `true`.
3. O backend valida os campos, resolve o perfil, grava a senha com bcrypt e registra os aceites.
4. Sem convite, a conta fica `pendente`. A equipe com acesso administrativo consulta `/admin/pendentes` e decide por `/admin/analisar-cadastro`.
5. Somente conta aprovada pode entrar.

Nome e sobrenome precisam ter ao menos dois caracteres. Senhas novas precisam ter oito caracteres ou mais e até 72 bytes UTF-8. O backend valida esses limites mesmo que a interface já tenha validado.

O schema não cria automaticamente um administrador com senha. Em uma base vazia, o responsável pelo banco precisa conferir e aprovar a conta inicial com o perfil pretendido. As cargas opcionais de usuários são somente para testes.

## Convite administrativo

`POST /admin/convites` recebe nome, sobrenome, e-mail e perfil; não permite convidar como `proprietario`. O backend expira um convite pendente anterior do mesmo destinatário, salva o hash de um novo token e envia o link por SMTP. A validade é de sete dias.

`GET /auth/convites/<token>` consulta o convite. O aceite usa `POST /auth/register` com `convite_token`, senha e os dois aceites. Nome, e-mail e perfil vêm do convite no banco. O administrador não aceita os documentos em nome da pessoa.

A confirmação cria uma conta aprovada, consome o convite e devolve usuário/CSRF com sessão autenticada. O consumo usa bloqueio e verificação transacional. `POST /auth/convites/<token>/recusar` recusa sem criar conta.

Se SMTP falhar, a rota pode retornar 503 depois de salvar o convite. Corrija a configuração antes de reenviar. A conta só existe depois do aceite; não há envio de senha por e-mail.

## Login e sessão

`POST /auth/login` recebe e-mail, senha e a opção de lembrar acesso da interface. O sucesso define cookie assinado HttpOnly/SameSite=Lax e devolve `usuario` e `csrf_token`.

O frontend guarda apresentação e CSRF em sessionStorage; o cookie autentica as requisições. Editar o armazenamento do navegador não muda a conta no servidor. `/configuracoes/visual` fornece somente preferências visuais públicas.

Com lembrar acesso, a sessão usa `SESSION_HOURS` (oito horas por padrão); sem essa opção, é uma sessão de navegador. Conta bloqueada, senha alterada ou chave de assinatura trocada podem invalidá-la antes. Em desenvolvimento, chave temporária muda no reinício.

`POST /auth/logout` limpa a sessão e exige CSRF quando há sessão ativa. Fechar o navegador não equivale a acionar essa rota ou registrar uma saída explícita.

## Recuperação de senha

`POST /auth/recuperar-senha` recebe e-mail e responde genericamente para não revelar a existência da conta. Para uma conta aprovada, grava o hash de um token válido por uma hora e envia um link baseado em `APP_PUBLIC_URL`.

`POST /auth/redefinir-senha` recebe `token` e `password`, bloqueia a linha durante a validação, atualiza o hash e apaga o token na mesma transação. Token expirado ou consumido é recusado. Sessões antigas deixam de ser aceitas após a mudança da credencial.

Sem SMTP não há entrega do link, mesmo com resposta genérica de sucesso. Uma URL pública com `localhost` só funciona no computador do servidor.

## Autorização e proteção HTTP

O middleware reconsulta status, perfil, credencial e módulos permitidos. A maioria das rotas usa `perfil_permissoes`. Vendas, clientes e receitas usam os perfis comerciais fixos; `/admin/logs` aceita proprietário, admin e TI. Visualizador não pode alterar dados nas APIs protegidas.

Mutações autenticadas enviam `X-CSRF-Token`. O wrapper fetch o adiciona apenas à origem da API. Mutações públicas de autenticação validam `Origin` quando presente e compartilham limite de 20 requisições por IP/processo em 300 segundos.

| Código | Interpretação comum |
| --- | --- |
| 400 | Campos inválidos ou ausentes |
| 401 | Sessão inválida ou conta sem acesso |
| 403 | Permissão, origem ou CSRF recusado |
| 409 | Conflito, como e-mail duplicado |
| 410 | Token expirado ou indisponível |
| 429 | Limite de acesso; respeitar `Retry-After` |
| 503 | Serviço indisponível ou falha de validação de sessão |

## Aceites e testes

`LEGAL_DOCUMENT_VERSION` define a versão dos aceites (`2026-10-05` no código revisado). O registro fica em `aceites_legais`. Mudanças nos textos legais precisam considerar também essa versão e o fluxo de consentimento.

Os testes de backend/segurança usam banco simulado. Na homologação, valide cadastro, aprovação, convite, recuperação, logout e revogação usando contas fictícias e SMTP de teste. A atualização desta documentação não representa validação jurídica dos textos apresentados aos usuários.
