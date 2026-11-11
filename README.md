# FarmaControl

Sistema de gestão farmacêutica com backend **Flask + MySQL/MariaDB** e frontend **HTML, CSS e JavaScript**.

Documentação revisada em **09/11/2026**. A aplicação reúne catálogo, estoque por lote, compras, vendas de balcão, financeiro, usuários e histórico de atividades em uma interface web. O Flask serve tanto a API quanto as páginas; não é necessário instalar um servidor Node para usá-la.

## Funcionalidades

| Módulo | Recursos |
| --- | --- |
| Dashboard | Indicadores, gráficos e alertas operacionais |
| Vendas / PDV | Pesquisa, comparação, carrinho, seleção de lotes e conclusão com baixa e financeiro |
| Estoque | Medicamentos e outros produtos, categorias, lotes, validade, movimentações, descarte e devolução ao fornecedor |
| Vencimentos | Consulta de lotes e acompanhamento de validade |
| Compras | Pedidos, fornecedores, itens e recebimento em estoque |
| Financeiro | Categorias, transações, indicadores e fluxo |
| Relatórios | Consultas de estoque, compras e vencimentos |
| Usuários | Cadastros pendentes, convites, perfis e permissões de módulos |
| Log | Consulta filtrada das atividades e detalhes de operações |
| Configurações | Dados da farmácia, aparência clara, regras de estoque e notificações |

Existem sete perfis: proprietário, gerente/administrador, farmacêutico, atendente, compras, TI/suporte e visualizador. A matriz de módulos é consultada no banco; PDV e log têm regras fixas adicionais, e visualizador não pode gravar. Veja [autorização no backend](backend/README.md).

## Requisitos

- Python 3.12, versão usada na validação local, com `venv` e `pip`.
- Servidor MySQL 8 ou MariaDB 10.4+ (como o distribuído no XAMPP). Workbench e phpMyAdmin são clientes para administrar esse servidor.
- Navegador moderno e acesso aos recursos externos usados pela interface, como Chart.js e Google Fonts.
- Git para versionar/publicar; Node 22+ e Chrome apenas para as verificações que os utilizam.

Não há instalador automático do banco, conta administrativa criada automaticamente, integração de pagamento ou emissão fiscal nesta versão.

## Estrutura atual

- `backend/app.py`: entrada local e WSGI da API.
- `backend/farmacontrol/`: inicialização, infraestrutura em `core/`, regras compartilhadas em `services/` e rotas por área em `routes/`.
- `backend/schema.sql` e `backend/migrations/`: definição e evolução do banco.
- `frontend/src/pages/acesso/, convite/, redefinir-senha/, termos/ e privacidade/`: login, cadastro e documentos legais.
- `frontend/src/pages/sistema/`: dashboard, vendas, estoque, vencimentos, compras, financeiro, relatórios, usuários, log e configurações.
- `frontend/src/utils/`: preferências, ciclo de vida das telas e menu com navegação nativa.
- `frontend/src/styles/`: estilos compartilhados de contraste, transições e responsividade.
- `tests/` e `scripts/`: regressões isoladas e verificações de código/navegador.
- `docs/`: guias operacionais, referência da API, banco e relatórios históricos.

## Executar localmente

### Instalador de dependências (Windows)

Depois de clonar ou extrair o projeto completo, execute
[`dist/installer/Instalar Dependencias FarmaControl.exe`](dist/installer/Instalar Dependencias FarmaControl.exe).
O instalador sugere a raiz do projeto dois níveis acima do executável;
confirme ou selecione a pasta que contém `backend/app.py` e
`backend/requirements.txt`. Não o execute diretamente dentro do ZIP.

Ele procura Python 3.12 e, se não encontrar, baixa Python 3.12.10 de 64 bits
do site oficial e instala para o usuário atual. Depois cria `.venv`, instala
`backend/requirements.txt`, executa `pip check` e verifica o carregamento das
bibliotecas. Uma falha impede a conclusão e os detalhes ficam em
`instalacao-dependencias.log`, na raiz selecionada. É necessário acesso à internet
para os downloads. A instalação automática do Python destina-se a Windows x64.

A pasta `.venv` guarda o Python do ambiente e as bibliotecas isoladas do projeto;
não deve ser versionada nem copiada para outra máquina. O banco MySQL e
`backend/.env` precisam ser configurados separadamente. O arquivo-fonte `.iss`
do instalador é mantido apenas localmente e não integra o repositório público.

### Instalação manual

Para mudar de máquina preservando os dados, siga o [guia de transferência](docs/transferencia.md).

Validado com Python 3.12 e um banco MySQL/MariaDB já preparado. Pela raiz:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
if (-not (Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }
```

Preencha `backend/.env` e, em uma instalação nova, execute `backend/schema.sql` no MySQL Workbench ou importe-o pelo phpMyAdmin do XAMPP. O schema cria a base `farmacontrol`; use esse nome em `DB_NAME`. Confira a estrutura e registre a baseline conforme o [guia de migrações](backend/migrations/README.md). O schema atual já inclui 022/023; não reaplique migrações antigas sobre uma instalação nova. As roles técnicas são opcionais e ficam em `backend/setup/technical_roles.sql`, para execução separada pela TI. Depois inicie:

```powershell
.\.venv\Scripts\python.exe backend/app.py
```

Configure `backend/.env` a partir de `backend/.env.example`, com `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` e `SECRET_KEY`. Para receber e-mails de cadastro/análise, preencha também as credenciais SMTP da Brevo e um remetente verificado. Consulte [backend/README.md](backend/README.md) para as demais opções. O ponto de entrada é [a tela de acesso local](http://localhost:5000/pages/acesso/acesso.html).

Iniciar o backend não aplica SQL nem atualiza o banco. Os utilitários de migração têm comandos explícitos de inspeção e aplicação. Para uma base existente, revise o legado até 023 e adote o controle de versões conforme o [guia](backend/migrations/README.md); versões novas ficam em `backend/migrations/managed/`. Scripts opcionais incluem cargas de demonstração e limpeza de dados; não execute a pasta inteira. Para transferir dados existentes, siga o guia de transferência.

### Primeiro acesso

O cadastro público cria uma conta pendente; só contas aprovadas entram no sistema. Em uma base vazia, cadastre a conta responsável e peça ao administrador do banco para conferir sua identidade e aprovar essa conta inicial. A aplicação não implementa um assistente de primeiro administrador. Depois disso, use os fluxos administrativos de aprovação e convite.

As migrações opcionais 014 e 017 criam usuários com credenciais públicas para testes. Use-as somente em uma base de demonstração, conforme [documentação do banco](docs/banco-de-dados.md). Elas não são necessárias para uma instalação operacional.

### Iniciar e encerrar no Windows

Após a configuração, `Iniciar-FarmaControl.bat` usa `.venv/Scripts/python.exe` e abre o navegador após dois segundos. Mantenha a janela do servidor aberta. Encerre com `Ctrl+C` ou com `Encerrar-FarmaControl.bat`: o servidor para de receber requisições e aguarda as que já estão em andamento, incluindo o fechamento das conexões do banco. O BAT sinaliza somente a instância desta pasta na sessão Windows, sem finalizar processos à força nem parar MySQL/MariaDB ou Apache. Se demorar mais de 30 segundos, informa que não confirmou o término; confira a janela do servidor.

Após atualizar de uma versão antiga, encerre uma vez com `Ctrl+C` e reinicie pelo iniciador para habilitar o novo sinal de encerramento. O modo local mantém `APP_DEBUG` para diagnóstico, sem recarga automática. Para usar XAMPP, inicie o MySQL pelo painel antes da aplicação; pare o banco pelo próprio painel somente depois de encerrar o FarmaControl. Apache é necessário para o phpMyAdmin, mas não para servir o FarmaControl. Veja [compatibilidade e diagnóstico do banco](docs/banco-de-dados.md#mysql-xampp).

O servidor local escuta em `127.0.0.1:5000`. O repositório distribui `backend/.env.example`; crie o `.env` privado com os dados da sua instalação. Gere uma chave persistente com:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

Copie o resultado apenas para `SECRET_KEY` no `.env` privado. Sem uma chave válida, o modo de desenvolvimento usa uma temporária e as sessões expiram ao reiniciar.

## Verificar

As verificações agora rodam automaticamente no GitHub em pushes para `main` e
pull requests, incluindo MySQL e navegador em ambiente descartável. Consulte
[CI e reprodução local](docs/desenvolvimento.md#ci). O controle de migrações permite consultar
pendências com `python scripts/migrate.py status`; consulte a
[adoção da baseline e aplicação](backend/migrations/README.md) antes de gravar.

Para atualizar uma base existente após a remoção da Previsão IA, execute
[`021_remove_previsao_ia.sql`](backend/migrations/021_remove_previsao_ia.sql)
no banco do FarmaControl, após as migrações anteriores. O script remove somente
as permissões do módulo e pode ser executado novamente. Instalações novas já
utilizam o [`schema.sql`](backend/schema.sql) atualizado.

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
node scripts/check_frontend.cjs
node --test tests/*.test.cjs
.\.venv\Scripts\python.exe -B scripts/audit_static.py
```

Node é usado apenas nas verificações, não na aplicação. Use Node 22 ou superior. A suíte unitária Python usa conexões simuladas para os contratos de banco; os testes de servidor local também exercitam HTTP e encerramento no Windows. As verificações opcionais de navegador, como `node scripts/check_navigation.cjs`, exigem Chrome; configure `CHROME_PATH` se necessário. Scripts de integração MySQL em `scripts/` têm requisitos próprios descritos na documentação do backend.

## Publicar no GitHub

O arquivo `backend/.env.example` contém apenas valores de exemplo. O `.env` local, ambientes virtuais, caches, logs e backups ficam fora do versionamento pelo `.gitignore`. Não inclua exportações do banco com dados reais.

O repositório do projeto é [SamuelDlv/FarmaControl](https://github.com/SamuelDlv/FarmaControl), branch `main`. Para obter uma cópia de trabalho com histórico Git:

```powershell
git clone https://github.com/SamuelDlv/FarmaControl.git
cd FarmaControl
```

Em uma cópia já clonada, confira mudanças locais antes de atualizar. Para publicar,
selecione somente os arquivos revisados (o exemplo abaixo inclui o README principal):

```powershell
git status --short
git pull --ff-only origin main
# Faça as alterações e execute as verificações pertinentes.
git add README.md
git diff --cached --stat
git diff --cached
git check-ignore backend/.env
git commit -m "Atualiza a documentação do projeto"
git push origin main
```

Uma pasta extraída de ZIP não contém o histórico Git; prefira clonar e transportar
as alterações revisadas, preservando arquivos locais e a configuração privada.

Revise a lista de arquivos antes do commit. `git check-ignore` deve mostrar `backend/.env`; somente o exemplo deve ser publicado. O envio ao GitHub versiona o projeto, mas não coloca a aplicação em funcionamento na internet.

O guia [GitHub](docs/desenvolvimento.md#publicacao) detalha os arquivos incluídos, a revisão do índice e o tratamento de arquivos privados já rastreados.

## Operação e limites atuais

O banco é separado dos arquivos do projeto. Backup de código não preserva estoque, usuários ou vendas; exporte e valide a restauração do banco quando precisar proteger ou transferir dados.

SMTP é necessário para entrega de convites e recuperação por e-mail. Resumos automáticos dependem do acesso ao dashboard; não existe agendador independente. Preferências de idioma, moeda e custeio não implementam tradução, conversão monetária ou recálculo histórico.

O PDV registra o pagamento confirmado pelo operador, mas não cobra automaticamente nem emite documento fiscal. O carrinho existe apenas na página e não oferece idempotência persistente. A Previsão IA foi removida.

Para disponibilização na internet, configure separadamente WSGI, HTTPS, banco, credenciais e operação do serviço. `python backend/app.py` é o iniciador local e recusa execução em produção. Veja [backend](backend/README.md).

## Licença

Copyright (c) 2026 [SamuelDlv](https://github.com/SamuelDlv). Todos os direitos reservados.

O FarmaControl permite **uso, estudo, cópia, modificação e redistribuição para fins não comerciais**, sem autorização individual, desde que sejam preservados os créditos e a [licença](LICENSE) e identificadas as alterações.

**Uso comercial exige autorização prévia, expressa e por escrito de SamuelDlv**, incluindo venda, serviços pagos, monetização e uso interno na operação de farmácias ou empresas. Redistribuição sob outros termos, remoção de créditos ou uso da identidade do projeto para sugerir aprovação do titular também exigem autorização. Consulte o arquivo `LICENSE` para as condições completas, exceções e forma de contato.

## Documentação e colaboração

As páginas internas exigem sessão e permissão no servidor antes da entrega do HTML. Acesso direto sem login redireciona à tela de acesso, e a guarda visual revalida páginas restauradas pelo histórico. A política de autenticação distingue 5 falhas por conta e 100 requisições por IP/processo em 5 minutos; cadastro e recuperação têm cotas por operação. Logout permanece disponível com as cotas esgotadas. Veja [limites e permissões](docs/seguranca.md). Veja os detalhes e limites no [fluxo de autenticação](frontend/src/pages/README-authentication.md).

Explore o **[Atlas EER do banco](docs/diagrama-do-banco.md)**: 24 tabelas organizadas em sete áreas, diagramas de relacionamentos e dicionário de colunas com PK/FK, tipos e nulabilidade.

Acesse o [índice completo](docs/README.md), o [guia de desenvolvimento](docs/desenvolvimento.md), a [referência da API](docs/api.md) e o [guia dos comentários para manutenção](docs/desenvolvimento.md#manutencao). Para propor uma mudança, descreva o problema, o comportamento esperado, testes executados e eventual migração de banco.

Na revisão de 09/11/2026, passaram **195 testes Python**, **25 testes JavaScript**,
a sintaxe de **55 scripts frontend**, `pip check` e a auditoria estática. O
[CI do commit 710e9dc](https://github.com/SamuelDlv/FarmaControl/actions/runs/42654607638)
também aprovou os cinco jobs: unitários/auditoria, encerramento Windows, schema
MySQL 8.0.46, schema MariaDB 10.4 e integração MySQL/navegador. Esses resultados
pertencem à execução indicada; confira o Actions de cada atualização.

Os relatórios datados preservam resultados históricos. Entrega SMTP real,
compilação do instalador e uma instalação operacional específica não foram
validadas por essa execução.
