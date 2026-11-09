# Backend — FarmaControl

API Flask com PyMySQL e banco MySQL/MariaDB. As rotas estão separadas por área em `farmacontrol/routes/`, com entrada em `app.py`; não há prefixo `/api`, JWT, Prisma ou servidor Node nesta implementação.

Revisado em **09/11/2026**. Consulte também o [índice da documentação](../docs/README.md) e a [referência de endpoints](../docs/API.md).

## Organização interna

| Arquivo | Responsabilidade |
| --- | --- |
| `app.py` | Entrada local e WSGI (`app:app`) |
| `farmacontrol/__init__.py` | `create_app()`: configuração e registro de rotas e middlewares |
| `farmacontrol/core/` | Conexão por requisição, permissões, credenciais, respostas HTTP e caminhos |
| `farmacontrol/core/runtime_config.py` | Validação de ambiente, sessão, origens e limites HTTP |
| `farmacontrol/core/security.py` | Vínculo da sessão com a credencial e limitador de autenticação |
| `farmacontrol/core/local_server.py` | Servidor local e encerramento cooperativo por instância no Windows |
| `farmacontrol/middleware.py` | Validação de entrada, autorização, CSRF, cabeçalhos, auditoria de consultas e agendamento |
| `farmacontrol/routes/` | Rotas por área: autenticação, administração, clientes, catálogo, fornecedores, estoque, compras, vendas, receitas, alertas, configurações, dashboard, relatórios e financeiro; saúde e frontend |
| `farmacontrol/services/audit.py` | Eventos de auditoria e detalhes permitidos |
| `farmacontrol/services/product_rules.py` | Normalização e validação do catálogo |
| `farmacontrol/services/contact_rules.py` | Formato e limites dos contatos e documentos de fornecedores |
| `farmacontrol/services/reporting.py` | Funções compartilhadas de relatórios |
| `farmacontrol/services/system_settings.py` | Preferências, validação e alertas |
| `farmacontrol/services/email.py` | Templates e envio transacional pela Brevo |
| `farmacontrol/services/settings_notifications.py` | Resumos por e-mail avaliados durante o uso |
| `schema.sql` / `migrations/` | Instalação nova e evolução de bases existentes |

Cada módulo de rotas expõe `register_routes(app)`, preservando as URLs, os métodos HTTP e os nomes dos endpoints. Os handlers usam o contexto Flask atual; a conexão permanece em `g` e é encerrada ao terminar o contexto. O limitador de autenticação pertence à instância da aplicação (`app.extensions`).

Para adicionar uma área, crie um módulo em `farmacontrol/routes/` e registre-o em `create_app()`. Regras reutilizáveis ficam em `services/`; infraestrutura HTTP e segurança ficam em `core/`. Testes e scripts importam a responsabilidade diretamente do módulo correspondente. Os comentários no código identificam entradas, dependências SQL e limites de transação; consulte o [guia de manutenção](../docs/COMENTARIOS_MANUTENCAO.md).

## Configuração

No Windows x64, o executável `dist/installer/Instalar Dependencias FarmaControl.exe`
prepara `.venv` na raiz do projeto e instala `backend/requirements.txt`. Se Python
3.12 não for localizado, baixa e instala Python 3.12.10 para o usuário atual.
Execute-o na pasta original após extrair o projeto; consulte o [README](../README.md).
A configuração do banco e de `backend/.env` continua sendo feita separadamente.

`python backend/app.py` carrega `backend/.env` independentemente do diretório de trabalho. O servidor local escuta apenas em `127.0.0.1:5000`, com debug desligado por padrão. `farmacontrol/core/runtime_config.py` valida a configuração antes de iniciar a aplicação.

| Variável | Uso / padrão atual |
|---|---|
| DB_HOST / DB_PORT | Host e porta; localhost / 3306 |
| DB_USER / DB_PASSWORD / DB_NAME | Usuário, senha e base; root / vazio / farmacontrol |
| APP_ENV | development (padrão), test ou production |
| APP_DEBUG | false; true permitido somente fora de produção |
| SECRET_KEY | Chave aleatória com pelo menos 32 caracteres; obrigatória em produção |
| SESSION_HOURS | Duração, em horas, da sessão quando “Lembrar acesso” estiver marcado; 8 |
| COOKIE_SECURE | false no desenvolvimento; true por padrão e obrigatório em produção |
| ALLOWED_ORIGINS | Vazio desabilita CORS (aplicação na mesma origem); aceita lista de origens HTTP(S) explícitas, sem caminho, * ou null; produção exige HTTPS |
| BCRYPT_ROUNDS | Custo de hash de senha; 12 |
| BREVO_SMTP_HOST / BREVO_SMTP_PORT | Servidor SMTP; smtp-relay.brevo.com / 587 |
| BREVO_SMTP_LOGIN / BREVO_SMTP_PASSWORD | Credenciais privadas SMTP |
| BREVO_SENDER_EMAIL / BREVO_SENDER_NAME | Remetente verificado / nome exibido; FarmaControl |
| APP_PUBLIC_URL | Base dos links de convite e recuperação; http://localhost:5000 |

`SESSION_HOURS` aceita valores de 1 a 168. Booleanos validados por `runtime_config.py` aceitam `true` ou `false`. `FLASK_DEBUG` não substitui `APP_DEBUG`. O arquivo `.env.example` é o ponto de partida; não copie credenciais para ele.

Dependências diretas e transitivas estão fixadas em `requirements.txt`, alinhadas ao ambiente validado em Python 3.12. Instale-as em um virtualenv e execute `python -m pip check` e a suíte de testes usando esse mesmo interpretador. A conexão é criada sob demanda, guardada em `flask.g` durante a requisição e fechada no teardown. Não há pool de conexões.

Em desenvolvimento, chave ausente, curta ou igual ao exemplo antigo é substituída por uma chave aleatória em memória, com aviso no log: as sessões expiram ao reiniciar. Para uma chave persistente, gere o valor com `python -c "import secrets; print(secrets.token_hex(32))"` e configure-o fora do repositório.

Em produção, use `APP_ENV=production`, uma chave persistente válida e HTTPS. Debug ligado, cookie inseguro e origens inválidas impedem a inicialização. O início direto com `python backend/app.py` é exclusivamente local; em produção carregue `app:app` a partir de `backend` em um servidor WSGI apropriado ao ambiente, atrás do terminador HTTPS. O frontend usa a origem em que foi servido.

## Contratos e segurança

- Login cria cookie assinado HttpOnly e devolve `csrf_token`. O perfil é revalidado no banco a cada requisição protegida.
- Mutações protegidas exigem `X-CSRF-Token`; o logout também valida o token de uma sessão ativa.
- `proteger_api` consulta `perfil_permissoes` no banco e associa a rota a um módulo com `modulo_da_rota`. A função legada `roles_permitidos` não descreve sozinha a autorização efetiva atual.
- Respostas usam `ok`, `mensagem` e, quando aplicável, `campo`; métodos e caminhos atuais estão na [referência da API](../docs/API.md).
- `/pages/sistema/...` e `/pages/proprietario/...` servem as mesmas telas; o segundo caminho mantém compatibilidade com links existentes.
- HTMLs internos exigem sessão válida e permissão antes da leitura do arquivo, incluindo o alias legado e a rota genérica. Sem sessão, há redirecionamento 302 ao login; sem permissão, 403; falha de validação no banco, 503.
- HTMLs internos e respostas de bloqueio usam `Cache-Control: no-store`. HTML público/CSS/JS usam `no-cache`; outros estáticos usam cache de 300 segundos.

### Autorização efetiva

| Regra | Comportamento |
| --- | --- |
| Conta | Deve existir e estar aprovada; perfil e credencial são revalidados no banco |
| Matriz | Módulo precisa estar concedido ao perfil em `perfil_permissoes` |
| Visualizador | Toda mutação protegida é recusada, mesmo com módulo concedido |
| Vendas, clientes e receitas | Acesso fixo de proprietário, admin, farmacêutico, atendente e TI |
| `/admin/logs` | Acesso fixo de proprietário, admin e TI |
| Mutação autenticada | Exige `X-CSRF-Token` igual ao da sessão |
| `/configuracoes/visual` | Leitura pública das preferências visuais permitidas |

A maior parte das rotas administrativas corresponde ao módulo `usuarios`. As permissões atuais devem ser conferidas no banco e no handler específico; nomes de perfis ou opções ocultas no menu não substituem autorização no servidor. Alterar a matriz pode retirar acesso inclusive de perfis administrativos.

### Controles HTTP e sessão

A sessão usa cookie assinado, HttpOnly e SameSite=Lax. Um HMAC vincula o cookie à senha atual, invalidando sessões após troca de credencial. A chave de assinatura deve persistir entre reinícios e ser a mesma nos processos da instalação.

Corpos de requisição têm limite de 1 MiB. Mutações de autenticação compartilham limite de 5 requisições por IP em uma janela fixa de 300 segundos, por processo. O contador inclui login, logout e demais mutações de autenticação, bem-sucedidas ou não. Erros de credenciais informam `tentativas_restantes` e `aguarde_segundos`; ao esgotar o limite, há também `Retry-After`, e solicitações seguintes retornam 429. Há validação de `Origin` quando presente, JSON e tipos de campos; senhas novas exigem ao menos oito caracteres e no máximo 72 bytes UTF-8. APIs protegidas e autenticação recebem `no-store`. Cabeçalhos contra enquadramento e interpretação indevida de conteúdo são adicionados pelo servidor; HSTS depende do modo de produção.

`validar_sessao()` é compartilhada pelas APIs e pela entrega dos HTMLs internos, revalidando situação, perfil e vínculo com a senha no banco. A proteção dos arquivos considera seu caminho físico em `frontend/src/pages/sistema`. Novas páginas internas devem permanecer nessa pasta e carregar a guarda visual descrita no [frontend](../frontend/README.md).

O IP vem de `request.remote_addr`; encaminhamento por proxy precisa ser configurado deliberadamente. O limitador em memória não é compartilhado entre workers. O código não fornece implantação pronta nem agendador distribuído.

## Banco e testes

O controle de versões do banco está documentado em
[migrations/README.md](migrations/README.md). `python scripts/migrate.py status`
consulta o histórico sem gravar; adoção da baseline e aplicação são comandos
explícitos. O [CI](../docs/CI.md) verifica migrações em bases descartáveis.

O catálogo aceita medicamentos e outros produtos no mesmo estoque, compras e vendas. O campo `tipo_produto` distingue `medicamento` de `outro`; categorias organizam alimentos (incluindo bebidas), higiene, cosméticos, saúde sexual, itens infantis, suplementos, acessórios e primeiros socorros. Categorias não determinam o tipo: um creme pode ser medicamento ou cosmético conforme seu cadastro.

Instalações novas usam `schema.sql`, seguido da conferência e do registro da baseline descritos no [guia de migrações](migrations/README.md). Em bases antigas ainda sem o catálogo multicategoria, revise e aplique `migrations/012_catalogo_multicategoria.sql` **antes** de iniciar a API atualizada. Nessas bases, confira também `migrations/019_reorganiza_categorias_produto.sql`: transfere Bebidas para Alimentos e substitui a categoria combinada por Acessórios, criando Primeiros socorros separadamente. Os produtos da categoria combinada ficam em Acessórios e podem ser reclassificados pelo cadastro. O utilitário `python scripts/migrate_catalogo.py --apply` prepara as alterações de 012/019 no banco local e pode ser reaplicado; mantém IDs, lotes, histórico e a classificação dos produtos antigos como medicamentos. Não reaplique SQLs do legado em bases cuja baseline já foi revisada e registrada. O utilitário não corrige automaticamente validades antigas (inclusive datas fictícias cadastradas pela versão anterior).

Na raiz do projeto, com as dependências Python instaladas:

```powershell
python scripts/migrate_catalogo.py          # inspeção sem alterações
python scripts/migrate_catalogo.py --apply  # apenas o banco local de backend/.env
python -m unittest discover -s tests
python scripts/check_catalogo_mysql.py      # banco temporário; exige CREATE/DROP DATABASE
```

`exige_validade` inicia habilitado, inclusive para alimentos e bebidas; somente outros produtos podem desabilitá-lo. Uma data preenchida continua participando de vencimentos mesmo com a exigência desligada. Medicamentos mantêm princípio ativo e indicação de receita. Outros produtos não armazenam princípio ativo nem podem exigir receita. Não há validação clínica ou nova integração regulatória.

No estoque, o seletor **Cadastro** permite criar um produto ou adicionar lote de um cadastro existente. Campos do produto são compartilhados entre lotes. Lote não informado usa `SEM-LOTE` em cadastro, compras e vendas; diferentes validades do mesmo produto devem ser registradas com lotes distintos. A validade obrigatória é conferida também ao receber compras. Produtos sem vencimento usam `NULL`, nunca uma data artificial.

Pedidos pendentes podem ser criados antes de conhecer lote e validade. Na confirmação de recebimento, a tela solicita esses dados por item; a API recebe `itens_recebimento` com `id` do item da compra, `lote_recebido` e `data_validade_recebida`. IDs de outra compra ou duplicados são rejeitados, e um erro de validação desfaz todo o recebimento.

As APIs `/produtos` aceitam `tipo_produto`, `exige_validade`, `estoque_minimo`, `fornecedor_id` e os campos comerciais existentes. A edição é parcial e preserva campos omitidos. `/estoque` recebe os equivalentes com prefixo `produto_` (por exemplo, `produto_tipo` e `produto_exige_validade`), além de `estoque_minimo`. Enviar `produto_id` no cadastro de lote usa as regras já salvas no catálogo.

O schema e as migrações são fontes locais de definição, não um retrato confirmado do banco instalado. Consulte [as divergências conhecidas](../docs/database_schema_design.md) antes de executar SQL. A migração `007_alertas_aceites_configuracoes.sql` consolida os campos de resolução de alertas e as tabelas antes garantidas pela aplicação; a `008_convites_cadastro.sql` habilita convites administrativos com aceite legal pelo destinatário. Aplique-as em um ambiente revisado antes de atualizar o serviço.

### Carga massiva de teste (opcional)

O arquivo [`017_popula_farmacia_teste (Opcional).sql`](migrations/017_popula_farmacia_teste%20%28Opcional%29.sql)
simula 180 dias de uma farmácia: 28 usuários com diferentes perfis e estados de
cadastro, 20 fornecedores, 500 clientes, 200 produtos, 600 lotes, 800 compras,
6.000 vendas, 12.000 itens de venda, financeiro, movimentações, receitas fictícias,
alertas de vencimento/estoque baixo e logs. Inclui produtos sem validade,
lotes vencidos, pedidos pendentes/cancelados e quatro formas de pagamento.

Prepare uma base **de teste** pelo schema atual, ou confira as migrações
necessárias de uma base antiga (inclusive 012 e 016). Não reaplique essas
migrações sobre o schema novo. Abra a carga no MySQL Workbench, selecione
o banco de teste e execute o arquivo completo. Também é possível abrir o cliente na raiz do projeto:

```text
mysql -u root -p --default-character-set=utf8mb4 farmacontrol
SOURCE backend/migrations/017_popula_farmacia_teste (Opcional).sql;
```

A conta do banco precisa poder criar/remover procedures e ler/gravar as tabelas.
O script usa o banco selecionado, preserva registros anteriores e reverte a carga
em caso de erro. A chave `seed.farmacia.017` impede duplicação em reexecuções;
não remova esse marcador para tentar repetir a carga. A chamada ao fim do arquivo
permite ajustar produtos e vendas **antes da primeira execução**.

Login de proprietário: `usuario001@farmacia.example.invalid`.
Senha de todos os usuários fictícios: `FarmaciaTeste@2026`.
As contas vão até `usuario028`; as duas últimas são pendente e rejeitada.
Esta carga contém credenciais públicas e dados exclusivamente fictícios: use
somente em desenvolvimento/teste. Não envia e-mails ou solicita pagamentos.

Validação isolada (exige CREATE/DROP DATABASE; não popula a base da aplicação):

```powershell
python scripts/check_seed_mysql.py
```

### Roles técnicas do MySQL

As roles técnicas são destinadas somente à equipe de TI e são diferentes dos perfis funcionais da aplicação (`proprietario`, `farmaceutico`, `atendente` etc.), que continuam nas tabelas `perfis` e `perfil_permissoes`. O `schema.sql` cria somente o banco da aplicação. Para provisionar roles, execute opcionalmente `setup/technical_roles.sql` com uma conta administrativa, após a importação e em um servidor saudável. A migração histórica `015_roles_tecnicas_mysql.sql` permanece imutável; não é um passo obrigatório de instalação no XAMPP. Consulte [MySQL/MariaDB e XAMPP](../docs/MYSQL_XAMPP.md).

| Role | Finalidade | Privilégios no banco `farmacontrol` |
|---|---|---|
| `fc_runtime_rw` | Conta técnica do backend | `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `EXECUTE` |
| `fc_schema_deployer` | Pipeline ou responsável por migrations | Dados, DDL, views, triggers, eventos e rotinas |
| `fc_support_ro` | Suporte e diagnóstico | `SELECT`, `SHOW VIEW` |
| `fc_database_admin` | Administração restrita à TI responsável | Todos os privilégios no banco, com `GRANT OPTION` |

A migração não cria contas, senhas ou atribuições de role. Crie contas individuais, limite o host de origem e associe somente a role necessária. Por exemplo, para a conta do backend:

```sql
CREATE USER 'farmacontrol_app'@'localhost' IDENTIFIED BY '<senha-secreta>';
GRANT 'fc_runtime_rw' TO 'farmacontrol_app'@'localhost';
SET DEFAULT ROLE 'fc_runtime_rw' TO 'farmacontrol_app'@'localhost';
```

O exemplo acima usa a sintaxe MySQL 8. No MariaDB, o último comando é
`SET DEFAULT ROLE fc_runtime_rw FOR 'farmacontrol_app'@'localhost';`.

Não use `fc_database_admin` no backend e não conceda privilégios globais (`*.*`) a essas contas.

Copie `.env.example` para `.env` e preencha os valores locais. Para notificações transacionais, defina `BREVO_SMTP_LOGIN`, `BREVO_SMTP_PASSWORD` e `BREVO_SENDER_EMAIL` (remetente verificado); sem eles, cadastro e análise continuam funcionando e o e-mail é apenas ignorado com log informativo.

A aplicação tem apenas aparência clara. As preferências aposentadas `tema` e `tema_efetivo` não são retornadas nas listagens de configurações; leitura individual e gravação retornam 410. A migração opcional `011_remove_preferencias_tema.sql` remove somente essas duas chaves do banco, preservando cores, densidade e demais configurações. Revise-a antes de aplicar na instância escolhida; o código funciona mesmo que os registros antigos ainda existam.

```powershell
python -B -m unittest discover -s tests -v
```

A suíte cobre sessão, CSRF, perfis, contratos de rotas, estáticos, parâmetro SQL, validação e rollback. Ela não substitui testes de concorrência/transações com MySQL em uma base descartável.
## Histórico de atividades

A tela Sistema → Log é somente para consulta e permite acesso exclusivamente a
Proprietário, Gerente / Administrador e TI / Suporte. Essa regra é fixa na API,
independentemente da matriz editável de módulos.

Em bases existentes, aplique `migrations/016_log_atividades.sql` e
`migrations/020_detalhes_auditoria.sql` antes de iniciar esta versão.
Para ampliar uma tabela de logs já existente no banco local, execute
`python scripts/migrate_audit.py --apply`. A migração 020 preserva os registros
e amplia os detalhes para MEDIUMTEXT, sem truncar listas de itens.
O schema completo já inclui a tabela para instalações novas.
O histórico começa com a ativação desta versão; ações antigas não são reconstruídas.
Alterações e seu registro são confirmados na mesma transação. Consultas autenticadas
também são registradas, exceto a leitura do próprio log. Login e saída explícita
são registrados; fechar o navegador não equivale a clicar em Sair.
Não são armazenados corpos completos de requisições, senhas ou tokens. A identidade
do autor fica preservada mesmo após exclusão de sua conta. Datas são gravadas em UTC
e exibidas no horário de Brasília. A API de consulta é `GET /admin/logs`, com
`limit` (até 100) e `antes` (ID para paginação); não há rota para alterar ou excluir logs.
Os eventos incluem os IDs envolvidos e campos comerciais permitidos por módulo:
fornecedor e razão social, produto, lote, quantidade, valores e forma de pagamento.
Vendas no PDV registram o total calculado pelo servidor e todos os itens validados.
Mudanças de status de vendas/compras incluem o status anterior; permissões indicam
os módulos concedidos a cada perfil. Dados clínicos, contatos privados, senhas e
tokens não são copiados para o histórico. Exclusões preservam o ID do registro.
Os detalhes novos valem para operações futuras; logs antigos continuam consultáveis.

Os filtros opcionais são `usuario_id`, `data_inicio` e `data_fim` (YYYY-MM-DD),
`busca` (até 120 caracteres, busca literal em ação, detalhes e nome do autor) e
`atividade` (`alteracoes` para operações/acessos, `consultas` para GET, vazio para tudo).
A tela prioriza operações/acessos, permite expandir detalhes de cada evento e
apresenta o resultado da operação. Consultas continuam disponíveis no filtro.
As duas datas incluem o dia completo no horário de Brasília e podem ser usadas
separadamente. Datas futuras são rejeitadas com uma mensagem de validação.
`incluir_usuarios=1` retorna todos os usuários cadastrados, inclusive os que ainda
não têm atividades, além dos autores excluídos preservados no histórico.
Depois de atualizar o backend, reinicie o processo local para ativar as mudanças.



## Configurações da farmácia

A tela salva as três seções em `PUT /configuracoes`, em uma única transação com auditoria.
O banco é a fonte dos dados; somente preferências visuais podem vir do cache local.
Após salvar os dados da farmácia, use **Editar** para alterar e **Cancelar edição** para
restaurar os últimos valores gravados. **Recarregar dados** busca os valores do banco.

Os alertas do dashboard respeitam os interruptores de estoque mínimo, vencimentos
(incluindo a antecedência em dias) e compras pendentes há mais de 48 horas. O estoque mínimo padrão é usado no cadastro de novos produtos. Produtos existentes preservam seu mínimo próprio. O controle de lote é
validado no cadastro/recebimento e o bloqueio de vencidos nas saídas e vendas.
Descarte e devolução de lotes vencidos usam saídas administrativas com finalidade e motivo explícitos, conforme a seção abaixo.

Resumos por e-mail usam a configuração SMTP da Brevo já existente no servidor.
São avaliados em segundo plano ao consultar o dashboard, no máximo uma vez por minuto.
O resumo diário é enviado uma vez por dia e o semanal às segundas-feiras; portanto,
dependendem do acesso ao painel nesses dias. Um envio que falha não é marcado como
concluído. O fuso escolhido define o dia dos resumos. Não há envio retroativo.
Não é necessário executar migração para estas alterações.

Idioma, moeda, unidade de medida e método de custeio são preferências armazenadas;
não traduzem a aplicação, convertem quantidades/moedas nem recalculam custos históricos.

Verificações: `python -m unittest discover -s tests -p "test_*.py"`,
`node --test tests/frontend.test.cjs` e `node scripts/check_settings.cjs`.
O último usa Chrome isolado e API simulada, sem gravar no banco real.

### Descarte e devolução ao fornecedor (migrações 022/023)

Em uma base antiga, confira os campos de 022 (`finalidade`, `motivo`) e 023
(`fornecedor_id`) antes de usar as saídas administrativas. O utilitário
`python scripts/migrate_devolucao.py` inspeciona a estrutura e, com `--apply`,
acrescenta somente os campos ausentes no banco local configurado. Instalações
novas já recebem esses campos por `schema.sql`. Consulte o [guia de migrações](migrations/README.md)
antes de aplicar SQL ou registrar a baseline. A preparação não altera saldos nem
reclassifica histórico com base em texto livre.

`POST /movimentacoes-estoque` aceita `finalidade` opcional apenas para `saida`:
`venda`, `descarte` ou `devolucao_fornecedor`. Clientes antigos continuam
funcionando sem finalidade, sujeitos ao bloqueio usual de vencimento.
Descarte e devolução exigem motivo textual não vazio (até 255 caracteres), CSRF, módulo
`estoque` habilitado e perfil administrativo de estoque (`proprietario`,
`admin`, `farmaceutico`, `compras` ou `ti`). Visualizador e atendente não
podem autorizar essas baixas, mesmo com módulo estoque habilitado. A autoria
vem exclusivamente da sessão validada no servidor.

Descarte e devolução ao fornecedor podem baixar lotes vencidos com o bloqueio
comercial ativo. Saídas comuns e vendas preservam suas regras de vencimento.
Devolução não aceita estoque interno de destino: o servidor captura o fornecedor
do cadastro do produto e rejeita um `fornecedor_id` enviado que não corresponda.
Sem fornecedor cadastrado, a referência pode permanecer nula. Transferência
interna continua exigindo lote de destino do mesmo produto.
Quantidade inteira positiva, saldo, bloqueio `FOR UPDATE`, movimentação e
log transacional são preservados. Se a gravação do log falhar, a baixa é
revertida. Histórico, tabela de movimentos e CSV identificam finalidade e
motivo. Os indicadores de dispensação excluem descartes e devoluções
estruturados; registros legados sem finalidade mantêm o tratamento anterior.
O contador de lotes descartados usa a finalidade estruturada, sem inferir
que observações antigas sejam autorizações de descarte.


## Validação de referência

Em 09/11/2026, a suíte geral passou com 195 testes Python e 25 JavaScript, além
da verificação de 55 scripts frontend, auditoria estática e `pip check`. O
[CI de referência](https://github.com/SamuelDlv/FarmaControl/actions/runs/42654607638)
aprovou os cinco jobs, incluindo schema MySQL/MariaDB, integração MySQL/navegador
e encerramento real no Windows. Isso não confirma o estado do banco instalado
nem a entrega de e-mails por um SMTP operacional.

Comandos pela raiz do projeto, no ambiente Python configurado:

```powershell
python -B -m unittest discover -s tests -v
python -m pip check
python -B scripts/audit_static.py
node --test tests/*.test.cjs
node scripts/check_frontend.cjs
```

Os pré-requisitos dos testes adicionais estão em [CI](../docs/CI.md).
