# Transferir o FarmaControl para outra máquina

Revisado em **19/10/2026**. Para instalação sem dados anteriores, use o [README](../README.md). Para trazer o código por Git, veja [GitHub](GITHUB.md). Este guia trata da preservação de uma instalação existente.

Este roteiro mantém o sistema em localhost e considera Windows no destino.
O projeto usa Python, Flask e um servidor MySQL separado. Não é necessário
instalar Node para usar o sistema. Use Python 3.12, versão validada neste projeto,
e a mesma versão do servidor de banco da máquina de origem. Não troque entre
MySQL e MariaDB durante a transferência: o SQL de roles e outros recursos pode
exigir adaptações.

## 1. Levar os arquivos e os dados

Copie a pasta do projeto, incluindo `backend`, `frontend` e os arquivos `.bat`.
Não copie `.venv`, `.venv-audit`, `__pycache__`, `.audit-backup` e logs: o ambiente
Python precisa ser recriado na outra máquina.

O banco não fica dentro desta pasta. Para manter usuários, senhas de acesso ao
sistema, estoque, vendas e configurações, exporte a base atual completa, com
estrutura e dados. Pare o uso do sistema durante o backup final e mantenha a
máquina original até validar a restauração.

No MySQL Workbench, use **Server → Data Export**, selecione a base configurada
em `DB_NAME` e exporte estrutura e dados em um arquivo SQL, incluindo rotinas,
eventos e triggers caso existam. No destino, use **Server → Data Import** para
restaurar em uma base vazia. Confira o resultado da importação antes de iniciar.
Consulte `SELECT VERSION();` nas duas máquinas para comparar os servidores.

As contas técnicas de conexão do MySQL e suas permissões precisam ser
configuradas no servidor de destino; elas são diferentes dos usuários de login
do FarmaControl. Ajuste o `.env` para a conta do banco no destino.

Ao restaurar o banco existente, não execute `schema.sql` ou todas as migrações
por cima automaticamente. Há scripts opcionais que apagam dados e outros que
inserem demonstrações. `schema.sql` serve para uma instalação nova, sem os dados
antigos. Uma restauração mantém a estrutura que existia na origem; não aplica
migrações que estavam pendentes.

## 2. Preparar o Python

No Windows x64, você pode executar `dist/installer/Instalar Dependencias FarmaControl.exe`
na cópia extraída do projeto. Preserve essa posição dentro da pasta: o instalador
localiza a raiz automaticamente, instala Python 3.12.10 se não localizar Python
3.12 e prepara `.venv` com as dependências. É necessário acesso à internet.
O instalador não transfere o banco nem configura `.env`. Para preparação manual:

Instale Python 3.12 com suporte a `venv` e `pip`. Abra o PowerShell dentro da
pasta copiada e execute:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

O primeiro comando deve indicar Python 3.12. Se você tiver várias versões,
use `py -3.12 -m venv .venv` para selecionar a correta. A instalação das
dependências requer acesso ao índice de pacotes ou arquivos de instalação locais.

O `requirements.txt` contém as versões fixadas na revisão de 15/10/2026, novamente verificadas com `pip check` em 19/10.
Não é preciso atualizar todas as versões apenas para transferir a aplicação.
Se a conexão no destino informar que `cryptography` é necessário para
`sha256_password` ou `caching_sha2_password`, instale o extra de autenticação
fornecido pela mesma versão de PyMySQL e confira novamente:

```powershell
.\.venv\Scripts\python.exe -m pip install "PyMySQL[rsa]==1.2.0"
.\.venv\Scripts\python.exe -m pip check
```

Esse extra não está instalado no ambiente local validado. Sua necessidade
depende da autenticação configurada no servidor de destino.

## 3. Configurar o ambiente

Se não levou o arquivo privado `backend/.env`, crie-o a partir do exemplo.
O comando abaixo preserva um arquivo que já exista:

```powershell
if (-not (Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

Use o valor gerado como `SECRET_KEY` e ajuste `DB_HOST`, `DB_PORT`, `DB_USER`,
`DB_PASSWORD` e `DB_NAME` para o banco restaurado. Para execução local, mantenha:

```dotenv
APP_ENV=development
APP_DEBUG=false
COOKIE_SECURE=false
APP_PUBLIC_URL=http://localhost:5000
ALLOWED_ORIGINS=
```

Se precisar dos e-mails, configure também os campos `BREVO_*`. O `.env` contém
senhas: transfira-o por um meio privado, sem incluí-lo em um repositório público.
Uma nova `SECRET_KEY` encerra as sessões antigas, mas não altera as senhas de login.

## 4. Iniciar e conferir

Execute `Iniciar-FarmaControl.bat`. Ele prioriza a `.venv` deste projeto e, se ela
não existir, tenta o launcher `py -3` e depois o Python do PATH. O inicializador
mostra os erros no terminal e abre o navegador após dois segundos.
Mantenha a janela aberta durante o uso. Também é possível iniciar manualmente:

```powershell
.\.venv\Scripts\python.exe backend/app.py
```

Acesse http://localhost:5000/pages/acesso/acesso.html. Entre com uma conta já
existente e confira estoque, vendas, usuários e configurações da base restaurada.
Abrir a tela de login, sozinho, não comprova que o banco está conectado.

Para executar as regressões isoladas:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests
```

Na preparação de 19/10/2026 passaram 120 testes Python e `pip check`. Esses testes simulam
o banco; a restauração e o login no destino ainda precisam ser conferidos.

O servidor escuta em `127.0.0.1:5000`: continuará acessível apenas na própria
máquina. Links de convite com `localhost` também só funcionam nela. Acesso por
outros computadores ou publicação na internet exige uma configuração separada.

## 5. Conferência após restaurar

| Área | Conferir |
| --- | --- |
| Ambiente | `.venv` nova, dependências completas e `.env` privado do destino |
| Banco | Base correta, contagens esperadas, tabelas, índices e rotinas |
| Conta | Login de usuário aprovado e módulos concedidos |
| Catálogo | Produtos, lotes, saldo e validade preservados |
| Compras e vendas | Histórico e vínculos com itens/financeiro |
| Auditoria | Consulta de eventos e detalhe de ações novas |
| Configurações | Dados da farmácia, limites e preferências |
| E-mail | Remetente, credenciais e URL acessível nos links |

Faça qualquer operação de teste primeiro em uma cópia descartável. Na instalação operacional restaurada, evite criar vendas ou movimentações apenas para testar sem um procedimento de conferência e compensação.

## 6. Atualização de código durante a transferência

Restaurar uma base e atualizar o código são operações diferentes. Registre a versão de origem e compare as migrações necessárias antes de iniciar código mais novo. Consulte [banco de dados](database_schema_design.md); não execute cargas opcionais sobre os dados restaurados.

Preserve a cópia original e o backup até concluir a conferência. Se precisar voltar, pare o serviço do destino e restaure um conjunto compatível de código, configuração e banco. Evite manter duas instalações recebendo gravações independentes sobre cópias divergentes dos mesmos dados.

## 7. Problemas comuns

| Sintoma | Ação de diagnóstico |
| --- | --- |
| `.bat` não encontra Python | Crie `.venv` na raiz; o iniciador não usa mais `.venv-audit` |
| Erro de conexão | Confira serviço MySQL, porta, usuário, senha e host autorizado |
| Erro de role/SQL | Compare versões de MySQL/MariaDB e privilégios de instalação |
| Tabela/coluna ausente | Compare estrutura restaurada e migrações exigidas pelo código |
| Sessão expira ao reiniciar | Configure `SECRET_KEY` persistente |
| Login falha após troca de chave | Faça login novamente; cookies anteriores ficam inválidos |
| Convites não chegam | Confira SMTP, remetente e a resposta da API |
| Link abre no computador errado | Ajuste `APP_PUBLIC_URL`; localhost aponta para o dispositivo que abre o link |

Os backups e credenciais são arquivos privados. GitHub transporta código versionado, não substitui backup operacional do banco.
