# Frontend — FarmaControl

HTML, CSS e JavaScript clássico servidos pelo Flask em `frontend/src`. Cada tela do sistema tem seus próprios arquivos `.html`, `.css` e `.js`. As chamadas à API permanecem nos scripts de página; não existe camada `services/` nesta versão.

Revisado em **09/11/2026**. São dez telas do sistema: dashboard, vendas, estoque, vencimentos, compras, financeiro, relatórios, usuários, log e configurações. Telas públicas tratam acesso, convites, recuperação e documentos legais. Veja o [índice](../docs/README.md) e o [fluxo de autenticação](src/pages/README-authentication.md).

## Responsabilidades e ordem de carga

Antes de entregar o HTML interno, o Flask valida sessão e permissão. `utils/auth-guard.js` deve ser o primeiro script no `<head>` de todas as telas do sistema: mantém a página oculta durante a carga, oculta ao sair e força revalidação no servidor ao restaurar do cache do histórico. O wrapper fetch chama essa guarda quando a API da mesma origem retorna 401; respostas 403 não encerram a sessão.

- No `<head>`, `utils/auth-guard.js` vem primeiro nas telas internas; `utils/sidebar-init.js` prepara a visibilidade e o estado inicial do menu antes da pintura. Links abrem documentos completos pelo navegador.
- O HTML aplica a paleta inicial e declara seus estilos. `styles/system-shell.css` compartilha estrutura, sidebar, badges e interação; CSS local, contraste, transições e regras responsivas se complementam pela cascata. Preserve a ordem de cada documento.
- `utils/global-settings.js` aplica preferências, dados do usuário e mensagens compartilhadas. Seu wrapper fetch adiciona credenciais/CSRF apenas à origem da API.
- `utils/page-lifecycle.js` disponibiliza os wrappers de timers, listeners e descarte antes dos scripts de tela que os utilizam. `utils/date-chip.js` usa esses wrappers para atualizar a data dos cabeçalhos.
- `utils/input-rules.js`, incluído com `defer`, prepara restrições de edição e atende também campos criados dinamicamente.
- O script local da tela inicializa dados e ações depois dos utilitários necessários. Funções usadas por `onclick` continuam globais por compatibilidade.

O login usa `global-settings.js` e `acesso.js` em carregamento completo. A API usa a mesma origem HTTP(S) da página; a entrada local é `/pages/acesso/acesso.html`, servida pelo Flask. Um servidor de frontend separado precisa encaminhar os caminhos de API ao backend; abrir HTML diretamente como arquivo não é o fluxo suportado.

## Navegação e ciclo de vida

- Cada tela possui seu próprio contexto JavaScript. Funções globais homônimas de telas diferentes não coexistem.
- Links nativos e `fcNavigate(href)` usam o histórico normal do navegador, incluindo Voltar/Avançar e nova aba; não há watchdog nem troca manual de HTML/CSS/scripts.
- `pagehide` dispara `fc-page-unload`: cancela leituras pendentes da API, descarta temporizadores e listeners registrados por `fcPageListen(target, evento, callback, opções)`.
- `fc-page-unloaded`: notifica a conclusão dessa limpeza.
- `DOMContentLoaded` inicializa cada documento uma única vez. Restaurações do bfcache recarregam a tela para reabrir recursos descartados e buscar dados atuais.
- Listeners em elementos da tela desaparecem com o DOM. Listeners em `window`/`document` devem usar `fcPageListen` para não se acumularem.
- CSS e scripts seguem a ordem declarada no HTML. Cor de destaque, densidade, animações e estado recolhido da sidebar são persistidos.
- Cancelar uma leitura não desfaz uma gravação. Mutações e logout com `keepalive` não recebem o sinal de cancelamento das leituras.

Preferências visuais ficam em localStorage; dados de apresentação e CSRF em sessionStorage. A autorização efetiva é do backend. A matriz de módulos concedidos ao perfil orienta a navegação; vendas e log têm restrições próprias. Manipular o armazenamento do navegador não concede acesso às APIs.

A aparência é exclusivamente clara. Cores de destaque, densidade, animações e sidebar continuam configuráveis. As chaves aposentadas `tema`/`tema_efetivo` são removidas dos caches antigos sem apagar as outras preferências; não existem paletas de superfícies alternativas nem seletores para modo escuro. Tons de acento, overlays e a sidebar colorida fazem parte da aparência atual.

Para comparar mudanças de CSS, execute `node scripts/check_theme.cjs baseline` antes da edição e `node scripts/check_theme.cjs verify` depois. O verificador compara 144 cenários com estilos computados e captura estoque desktop/mobile em `.audit-backup/theme-cleanup/`. A preferência escura do sistema operacional é simulada para verificar que a aparência da aplicação permanece clara.

## Verificação

```powershell
node scripts/check_frontend.cjs
node --test tests/*.test.cjs
node scripts/check_navigation.cjs
```

Executar pela raiz do projeto. `scripts/check_navigation.cjs` usa Chrome sem janela, perfil separado e servidor local com APIs/CDNs simuladas. Verifica 18 aberturas desktop/mobile, 12 trocas de tela, histórico real, envio de modal, leituras lentas, navegações rápidas, menu e estilos computados. Evidências ficam em `.audit-backup/navigation/`; não comprovam integração com o banco nem renderização real do Chart.js externo. `check_browser.cjs` é o verificador histórico da antiga SPA, mantido para reprodução do snapshot de 06/10.

Em 09/11/2026, os 25 testes JavaScript e a sintaxe de 55 scripts frontend
passaram. O [CI de referência](https://github.com/SamuelDlv/FarmaControl/actions/runs/42654607638)
também aprovou a integração de devolução com MySQL e navegador. Os cenários
simulados acima continuam tendo seus próprios limites; esse CI não valida todos
os layouts nem garante disponibilidade de CDNs ou entrega SMTP.

## Alterar uma tela

Mantenha `../../../utils/auth-guard.js` no início do `<head>` das páginas internas, antes dos demais scripts e do conteúdo. A proteção real depende da entrega autenticada pelo Flask; a guarda visual não substitui a validação no servidor.

Consulte o [guia dos comentários para manutenção](../docs/DESENVOLVIMENTO.md#manutencao). Edite o trio HTML/CSS/JS da página em `src/pages/sistema/`. Confira os caminhos dos assets, o tratamento de erro da API, carregamento vazio e ações de gravação. Use o wrapper de `global-settings.js` para preservar cookies e CSRF, e os registros de `page-lifecycle.js` para recursos que precisam de descarte.

Mantenha o menu compatível com permissões devolvidas pelo servidor. Para conteúdo vindo de usuários ou da API, prefira inserção textual e preserve as rotinas de escape existentes. Verifique desktop e mobile quando alterar layout, modal, tabela ou sidebar.

O Flask insere `fc-session-context` (JSON inerte) no HTML interno, com perfil,
módulos e capacidades de escrita revalidados, página inicial permitida e token
CSRF da sessão. O HTML usa `no-store`; não copie esse contexto para logs ou
artefatos publicados. Menu e transporte priorizam esse contexto sobre caches
antigos, inclusive ao abrir outra aba. Controles com `data-fc-write="estoque"`
(ou outro módulo) ficam ocultos sem capacidade de escrita; `data-fc-read`
controla atalhos que consultam outro módulo. A API valida novamente toda ação.
Preferências visuais usam `/configuracoes/visual` quando o perfil não tem acesso
ao módulo administrativo de configurações.

## Recursos e limites

Chart.js e fontes podem depender de serviços externos conforme os HTMLs. Não existe garantia de funcionamento visual completo offline. O backend serve os arquivos de `frontend/src`; os favicons existentes em mais de um caminho foram preservados por compatibilidade.

`frame_analysis.js` era uma ferramenta manual da antiga transição e foi removido na preparação do repositório. A navegação atual carrega documentos completos; alterações não devem reintroduzir um motor SPA presumindo que ele ainda existe.

As configurações globais são persistidas no banco. Cache visual local ajuda a primeira pintura, mas não substitui a resposta da API nem representa confirmação de salvamento.

## Restrições dos campos

`utils/input-rules.js` restringe a edição por eventos delegados, incluindo campos dinâmicos. Quantidades aceitam inteiros não negativos; preços aceitam centavos (na digitação, use o separador decimal do navegador; na colagem, ponto ou vírgula). Sinais negativos, expoentes e letras são bloqueados nos campos numéricos, inclusive na colagem e ao arrastar texto.

CNPJ aceita 14 dígitos, preserva zeros iniciais e aceita colagem da máscara convencional. Telefones aceitam números e pontuação telefônica; e-mails não aceitam espaços. Os limites de texto seguem os tamanhos existentes no schema. Nomes comerciais, códigos, lotes, endereços e observações continuam aceitando letras e números. O backend também valida o formato dos contatos de fornecedores e das configurações. Não há alteração estrutural nem migração de banco nesta mudança.

Regressão de edição em Chrome isolado, com APIs simuladas: `node scripts/check_navigation.cjs --input-rules`. Evidências textuais ficam em `.audit-backup/navigation/browser-input-rules.json`.

## Saídas administrativas e confirmação de vendas

Descarte e devolução ao fornecedor são saídas estruturadas com motivo e
autorização no backend; podem retirar lotes vencidos sem liberar sua venda.
Consulte [devolução](../docs/OPERACAO.md#devolucao) para o contrato e a preparação
do banco. A interface não deve inferir autorização a partir de observações livres.

No PDV, o carrinho agrupa quantidades por produto e o envio as distribui por lote.
Preço, saldo e receita são revalidados pelo servidor. Se a resposta se perder,
a tela bloqueia repetição automática até conferência do histórico; atualizar o
documento não representa cancelamento de uma venda já confirmada.
