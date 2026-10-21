# FarmaControl

Sistema de gestão farmacêutica com backend **Flask + MySQL/MariaDB** e frontend **HTML, CSS e JavaScript**.

Documentação revisada em **19/10/2026**. A aplicação reúne catálogo, estoque por lote, compras, vendas de balcão, financeiro, usuários e histórico de atividades em uma interface web. O Flask serve tanto a API quanto as páginas; não é necessário instalar um servidor Node para usá-la.

## Funcionalidades

| Módulo | Recursos |
| --- | --- |
| Dashboard | Indicadores, gráficos e alertas operacionais |
| Vendas / PDV | Pesquisa, comparação, carrinho, seleção de lotes e conclusão com baixa e financeiro |
| Estoque | Medicamentos e outros produtos, categorias, lotes, validade e movimentações |
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
- Servidor MySQL compatível com o schema e com as instruções de roles. Uso de MariaDB exige conferir diferenças de SQL na versão instalada.
- Navegador moderno e acesso aos recursos externos usados pela interface, como Chart.js e Google Fonts.
- Git para versionar/publicar; Node 22+ e Chrome apenas para as verificações que os utilizam.

Não há instalador automático do banco, conta administrativa criada automaticamente, integração de pagamento ou emissão fiscal nesta versão.

## Estrutura atual

- `backend/app.py`: API, autenticação por cookie, autorização e entrega dos arquivos estáticos.
- `backend/schema.sql` e `backend/migrations/`: definição e evolução do banco.
- `frontend/src/pages/acesso/, convite/, redefinir-senha/, termos/ e privacidade/`: login, cadastro e documentos legais.
- `frontend/src/pages/sistema/`: dashboard, vendas, estoque, vencimentos, compras, financeiro, relatórios, usuários, log e configurações.
- `frontend/src/utils/`: preferências, ciclo de vida das telas e menu com navegação nativa.
- `frontend/src/styles/`: estilos compartilhados de contraste, transições e responsividade.
- `tests/` e `scripts/`: regressões isoladas e verificações de código/navegador.
- `docs/`: guias operacionais, referência da API, banco e relatórios históricos.

## Executar localmente

Para mudar de máquina preservando os dados, siga o [guia de transferência](docs/TRANSFERENCIA.md).

Validado com Python 3.12 e um banco MySQL/MariaDB já preparado. Pela raiz:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
if (-not (Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }
```

Preencha `backend/.env` e, em uma instalação nova, execute `backend/schema.sql` no MySQL Workbench. O schema cria a base `farmacontrol`; use esse nome em `DB_NAME`. Depois inicie:

```powershell
.\.venv\Scripts\python.exe backend/app.py
```

Configure `backend/.env` a partir de `backend/.env.example`, com `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` e `SECRET_KEY`. Para receber e-mails de cadastro/análise, preencha também as credenciais SMTP da Brevo e um remetente verificado. Consulte [backend/README.md](backend/README.md) para as demais opções. O ponto de entrada é [a tela de acesso local](http://localhost:5000/pages/acesso/acesso.html).

Os SQLs não são executados pelos comandos Python. Para uma base existente, revise as migrações necessárias antes de aplicá-las. Scripts marcados como opcionais incluem cargas de demonstração e limpeza de dados; não execute todos automaticamente. Para transferir dados existentes, siga o guia de transferência.

### Primeiro acesso

O cadastro público cria uma conta pendente; só contas aprovadas entram no sistema. Em uma base vazia, cadastre a conta responsável e peça ao administrador do banco para conferir sua identidade e aprovar essa conta inicial. A aplicação não implementa um assistente de primeiro administrador. Depois disso, use os fluxos administrativos de aprovação e convite.

As migrações opcionais 014 e 017 criam usuários com credenciais públicas para testes. Use-as somente em uma base de demonstração, conforme [documentação do banco](docs/database_schema_design.md). Elas não são necessárias para uma instalação operacional.

### Iniciar e encerrar no Windows

Após a configuração, `Iniciar-FarmaControl.bat` usa `.venv/Scripts/python.exe` e abre o navegador após dois segundos. Mantenha a janela do servidor aberta. Encerre com `Ctrl+C` ou com `Encerrar-FarmaControl.bat`, que procura processos Python iniciados com o caminho deste projeto.

O servidor local escuta em `127.0.0.1:5000`. O `.env` distribuído nesta preparação está sem credenciais: preencha os dados da sua instalação. Gere uma chave persistente com:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

Copie o resultado apenas para `SECRET_KEY` no `.env` privado. Sem uma chave válida, o modo de desenvolvimento usa uma temporária e as sessões expiram ao reiniciar.

## Verificar

Para atualizar uma base existente após a remoção da Previsão IA, execute
[`021_remove_previsao_ia.sql`](backend/migrations/021_remove_previsao_ia.sql)
no banco do FarmaControl, após as migrações anteriores. O script remove somente
as permissões do módulo e pode ser executado novamente. Instalações novas já
utilizam o [`schema.sql`](backend/schema.sql) atualizado.

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
node scripts/check_frontend.cjs
node --test tests/frontend.test.cjs tests/log.test.cjs tests/vendas.test.cjs
```

Node é usado apenas nas verificações, não na aplicação. Use Node 22 ou superior. Os testes Python bloqueiam conexões reais ao MySQL. As verificações opcionais de navegador, como `node scripts/check_navigation.cjs`, exigem Chrome; configure `CHROME_PATH` se necessário. Scripts de integração MySQL em `scripts/` têm requisitos próprios descritos na documentação do backend.

## Publicar no GitHub

O arquivo `backend/.env.example` contém apenas valores de exemplo. O `.env` local, ambientes virtuais, caches, logs e backups ficam fora do versionamento pelo `.gitignore`. Não inclua exportações do banco com dados reais.

Com Git instalado, crie um repositório vazio no GitHub e execute na raiz (substitua a URL pela do seu repositório):

```powershell
git init -b main
git add .
git status --short
git diff --cached --stat
git check-ignore backend/.env
git commit -m "Prepara FarmaControl para versionamento"
git remote add origin https://github.com/SEU_USUARIO/FarmaControl.git
git push -u origin main
```

Revise a lista de arquivos antes do commit. `git check-ignore` deve mostrar `backend/.env`; somente o exemplo deve ser publicado. O envio ao GitHub versiona o projeto, mas não coloca a aplicação em funcionamento na internet.

O guia [GitHub](docs/GITHUB.md) detalha os arquivos incluídos, a revisão do índice e o tratamento de arquivos privados já rastreados.

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

Explore o **[Atlas EER do banco](docs/database_eer.md)**: 24 tabelas organizadas em sete áreas, diagramas de relacionamentos e dicionário de colunas com PK/FK, tipos e nulabilidade.

Acesse o [índice completo](docs/README.md), o [guia de desenvolvimento](docs/DESENVOLVIMENTO.md) e a [referência da API](docs/API.md). Para propor uma mudança, descreva o problema, o comportamento esperado, testes executados e eventual migração de banco.

Os relatórios datados são registros históricos. Na preparação de 19/10/2026 passaram 120 testes Python e 17 JavaScript; integração real com MySQL, navegador e infraestrutura publicada não foi revalidada nessa etapa.
