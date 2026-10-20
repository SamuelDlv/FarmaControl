# Frontend — FarmaControl

HTML, CSS e JavaScript clássico servidos pelo Flask em `frontend/src`. Cada tela do sistema tem seus próprios arquivos `.html`, `.css` e `.js`. As chamadas à API permanecem nos scripts de página; não existe camada `services/` nesta versão.

Revisado em **19/10/2026**. São dez telas do sistema: dashboard, vendas, estoque, vencimentos, compras, financeiro, relatórios, usuários, log e configurações. Telas públicas tratam acesso, convites, recuperação e documentos legais. Veja o [índice](../docs/README.md) e o [fluxo de autenticação](src/pages/README-authentication.md).

## Responsabilidades e ordem de carga

1. O HTML aplica a paleta inicial antes da pintura e inclui CSS local, contraste, transições e responsividade.
   `styles/system-shell.css` compartilha estrutura, sidebar, badges e interação. Variações locais e media queries continuam nas páginas; preserve a ordem declarada de estilos de cada HTML ao editar contraste e responsividade.
2. `utils/global-settings.js` aplica preferências, dados do usuário e notificações. Seu wrapper fetch adiciona credenciais/CSRF apenas à origem da API.
3. `utils/page-lifecycle.js` registra temporizadores e listeners das telas; mantém os nomes legados `__fcSetInterval` e `__fcSetTimeout`.
4. `utils/sidebar-init.js` mantém o menu e verifica os módulos visíveis; os links abrem documentos completos pelo navegador.
5. O script local da tela inicializa os dados e as ações. Funções usadas por `onclick` continuam globais por compatibilidade.

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
node --test tests/frontend.test.cjs tests/log.test.cjs tests/vendas.test.cjs
node scripts/check_navigation.cjs
```

Executar pela raiz do projeto. `scripts/check_navigation.cjs` usa Chrome sem janela, perfil separado e servidor local com APIs/CDNs simuladas. Verifica 18 aberturas desktop/mobile, 12 trocas de tela, histórico real, envio de modal, leituras lentas, navegações rápidas, menu e estilos computados. Evidências ficam em `.audit-backup/navigation/`; não comprovam integração com o banco nem renderização real do Chart.js externo. `check_browser.cjs` é o verificador histórico da antiga SPA, mantido para reprodução do snapshot de 06/10.

## Alterar uma tela

Edite o trio HTML/CSS/JS da página em `src/pages/sistema/`. Confira os caminhos dos assets, o tratamento de erro da API, carregamento vazio e ações de gravação. Use o wrapper de `global-settings.js` para preservar cookies e CSRF, e os registros de `page-lifecycle.js` para recursos que precisam de descarte.

Mantenha o menu compatível com permissões devolvidas pelo servidor. Para conteúdo vindo de usuários ou da API, prefira inserção textual e preserve as rotinas de escape existentes. Verifique desktop e mobile quando alterar layout, modal, tabela ou sidebar.

## Recursos e limites

Chart.js e fontes podem depender de serviços externos conforme os HTMLs. Não existe garantia de funcionamento visual completo offline. O backend serve os arquivos de `frontend/src`; os favicons existentes em mais de um caminho foram preservados por compatibilidade.

`frame_analysis.js` era uma ferramenta manual da antiga transição e foi removido na preparação do repositório. A navegação atual carrega documentos completos; alterações não devem reintroduzir um motor SPA presumindo que ele ainda existe.

As configurações globais são persistidas no banco. Cache visual local ajuda a primeira pintura, mas não substitui a resposta da API nem representa confirmação de salvamento.
