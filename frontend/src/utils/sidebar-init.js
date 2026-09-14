/**
 * FarmaControl — Sidebar Global Initializer + Navegação SPA (v14 — definitiva)
 *
 * ══ ARQUITETURA v14 ══
 *
 * CAUSA RAIZ DO FLASH (confirmada em análise frame a frame a 60fps):
 * O CSS é injetado no <head> como <style data-fc-page>, e o innerHTML swap
 * acontece no MESMO bloco síncrono. Porém o browser NÃO repinta imediatamente
 * após a inserção de <style>. O render pipeline processa o CSS no PRÓXIMO frame.
 * Se o browser pinta entre o swap e a aplicação do CSS → FLASH de conteúdo cru.
 *
 * SOLUÇÃO v14:
 * 1. Injetar CSS no <head> (mesmo que antes)
 * 2. FORÇAR recálculo síncrono de estilos com getComputedStyle() + offsetHeight
 *    — isso força o browser a processar TODAS as mudanças de CSS pendentes
 *    ANTES de continuar
 * 3. SÓ DEPOIS fazer o swap — garantindo que o CSS já está no render tree
 *
 * Além disso: NÃO remover CSS antigos antes de injetar novos. O CSS antigo
 * fica no head até o swap acontecer. Remover CSS cria uma janela onde
 * o head está sem CSS de página — se o browser pintar durante essa janela
 * → flash. Na v14, os CSS antigos são removidos APÓS o swap.
 *
 * Sidebar persistente: swap apenas do .main, sidebar permanece no DOM.
 * Scripts de página re-executam a cada visita (sem dedup).
 * Timeouts + watchdog contra lockup.
 */

(function () {
  'use strict';

  /* ══ ESTADO GLOBAL DE NAVEGAÇÃO SPA ══ */
  let spaNavigating = false;
  let pendingNav = null;
  /* Token de página — incrementa a cada navegação SPA.
   * Scripts de página podem capturar o token no início e verificar
   * se ainda é válido antes de renderizar dados assíncronos.
   * Isso previne que operações pendentes de uma página antiga
   * tentem acessar DOM elements que já foram removidos. */
  let __fcPageToken = 0;
  const GLOBAL_SCRIPTS = ['global-settings.js', 'sidebar-init.js'];
  const GLOBAL_STYLES = [
    'light-theme-contrast.css',
    'page-transitions.css',
  ];
  const pageCache = new Map();
  const cssTextCache = new Map();

  /* ══ TIMEOUTS DE SEGURANÇA ══ */
  const RESOURCE_TIMEOUT = 4000;
  const NAV_WATCHDOG = 8000;

  /* ══ LISTENERS GLOBAIS — EXECUTADOS APENAS UMA VEZ ══ */
  let globalClickAttached = false;
  let globalResizeAttached = false;
  let globalKeyAttached = false;
  let globalLogoutAttached = false;

  /* ══ WITH TIMEOUT ══ */
  /* ══ withTimeout(): Cria um "timeout" para requisições fetch.
   * Se a resposta demorar mais de "ms" milissegundos, aborta e retorna erro.
   * Usado para evitar que o SPA fique travado se o servidor não responder. */
  function withTimeout(promise, ms) {
    return new Promise(resolve => {
      const timer = setTimeout(() => {
        console.warn('[FC-SPA] Timeout: forçando continuação');
        resolve();
      }, ms);
      promise.then(val => { clearTimeout(timer); resolve(val); })
             .catch(() => { clearTimeout(timer); resolve(); });
    });
  }

  /* ══ RESOLVE URL RELATIVA ══ */
  /* ══ resolveUrl(): Converte um caminho relativo (ex: "dashboard.css")
   * em URL absoluta, considerando o caminho base da página atual. */
  function resolveUrl(attr, baseHref) {
    if (!attr) return null;
    if (/^https?:|^\/\//.test(attr)) return attr;
    return new URL(attr, baseHref).href;
  }

  function stylesAbsoluteHref(hrefAttr) {
    const m = hrefAttr.match(/([\w.-]*\/)?styles\//);
    return m ? '/' + hrefAttr.split('/styles/')[1] : null;
  }

  /* ══ fetchCssText(): Busca o conteúdo CSS de um arquivo via fetch.
   * Retorna o texto CSS para ser injetado via <style> inline. */
  function fetchCssText(resolved) {
    let cached = cssTextCache.get(resolved);
    if (cached) return Promise.resolve(cached);
    return fetch(resolved)
      .then(res => res.ok ? res.text() : Promise.reject(new Error('HTTP ' + res.status)))
      .catch(() => {
        const abs = stylesAbsoluteHref(resolved);
        if (!abs) throw new Error('CSS sem variante absoluta: ' + resolved);
        return fetch(abs)
          .then(res => res.ok ? res.text() : Promise.reject(new Error('HTTP ' + res.status)));
      })
      .then(text => {
        cssTextCache.set(resolved, text);
        return text;
      });
  }

  /* ══ FORÇAR RECALCULO SÍNCRONO DE ESTILOS ══
   * Força o browser a processar TODAS as mudanças de CSS pendentes
   * (incluindo <style> tags recém-inseridos) ANTES de continuar.
   * Sem isso, o browser pode pintar com CSS não-processado → FLASH.
   */
  /* ══ forceStyleRecalc(): Força o navegador a recalcular os estilos CSS.
   * Usa getComputedStyle() para garantir que as mudanças são aplicadas
   * imediatamente antes da transição de página. */
  function forceStyleRecalc() {
    try {
      if (document && document.body && document.documentElement) {
        void document.body.offsetHeight;
        void getComputedStyle(document.documentElement).getPropertyValue('--sage');
        void getComputedStyle(document.body).getPropertyValue('background');
      }
    } catch(e) { /* ignora — não bloqueia navegação */ }
  }

  /* ══ NAVEGAÇÃO SPA v14 ══ */
  /* ══ spaLoadPage(): Função PRINCIPAL do SPA.
   * Carrega uma nova página sem recarregar o navegador (navigation).
   * Faz: 1) Busca o HTML via fetch, 2) Remove CSS/JS da página antiga,
   * 3) Injeta CSS/JS da página nova, 4) Atualiza a sidebar ativa,
   * 5) Aplica configurações de tema, 6) Atualiza URL no histórico.
   * É chamada quando o usuário clica em qualquer item da sidebar. */
  async function spaLoadPage(href) {
    if (spaNavigating) {
      pendingNav = href;
      return;
    }
    /* Incrementa o token — invalida operações pendentes da página anterior */
    __fcPageToken++;
    if (typeof window !== 'undefined') {
      window.__fcPageToken = __fcPageToken;
    }
    spaNavigating = true;

    /* Watchdog */
    const watchdog = setTimeout(() => {
      console.warn('[FC-SPA] Watchdog: resetando');
      spaNavigating = false;
      const next = pendingNav;
      pendingNav = null;
      if (next) spaLoadPage(next);
    }, NAV_WATCHDOG);

    const app = document.querySelector('.app');
    if (!app) { clearTimeout(watchdog); spaNavigating = false; window.location.href = href; return; }

    const currentMain = app.querySelector(':scope > .main');
    const currentSidebar = app.querySelector(':scope > .sidebar');
    const canPersistSidebar = !!(currentMain && currentSidebar);

    try {
      const baseHref = new URL(href, window.location.href).href;

      /* ── 1. FETCH HTML ── */
      let html = pageCache.get(href);
      if (!html) {
        const res = await withTimeout(fetch(href), RESOURCE_TIMEOUT);
        if (!res || !res.ok) throw new Error('HTTP ' + res.status + ' para ' + href);
        html = await res.text();
        pageCache.set(href, html);
      }
      const doc = new DOMParser().parseFromString(html, 'text/html');

      /* ── 2. TÍTULO ── */
      const newTitle = doc.querySelector('title');
      if (newTitle) document.title = newTitle.textContent;

      /* ── 3. RESETAR OVERFLOW ── */
      document.body.style.overflow = '';

      /* ── 4. EXTRAIR SCRIPTS DO DOC PARSEADO ── */
      const extractedScripts = [];
      doc.body.querySelectorAll('script').forEach(s => {
        extractedScripts.push({ src: s.getAttribute('src'), text: s.textContent });
        s.remove();
      });

      /* ── 4.5. APLICAR TEMA ANTES DE INJETAR CSS — GARANTIR CORES CORRETAS ──
       * O applySettings() regenera o <style> com valores DIRETOS (não var())
       * e seta as CSS vars no root. Fazemos isso ANTES da injeção de CSS
       * da página nova para que, quando o browser parse o CSS da página
       * (que pode ter fallbacks var(--sage, #4a7c59)), as vars já estejam
       * corretas e o <style> global já tenha os valores resolvidos. */
      if (window.FarmaControlSettings) {
        const saved = window.FarmaControlSettings.readLocal
          ? window.FarmaControlSettings.readLocal()
          : null;
        window.FarmaControlSettings.apply(saved || {});
        window.FarmaControlSettings.applyUser();
      }

      /* ── 5. INJETAR CSS DA PÁGINA NOVA — SEM REMOVER OS ANTIGOS ── */
      const cssPromises = [];
      doc.head.querySelectorAll('link[rel="stylesheet"]').forEach(link => {
        const hrefAttr = link.getAttribute('href');
        if (!hrefAttr) return;
        const baseName = hrefAttr.split('/').pop().split('?')[0];
        if (GLOBAL_STYLES.some(g => baseName === g)) return;
        if (/googleapis\.com|gstatic\.com/.test(hrefAttr)) return;
        const resolved = resolveUrl(hrefAttr, baseHref);
        if (!resolved) return;
        cssPromises.push(fetchCssText(resolved).then(text => {
          const ns = document.createElement('style');
          ns.textContent = text;
          ns.setAttribute('data-fc-page', href);
          document.head.appendChild(ns);
        }).catch(() => {
          const ns = document.createElement('style');
          ns.setAttribute('data-fc-page', href);
          document.head.appendChild(ns);
        }));
      });
      /* Injetar <style> inline do HTML parseado */
      doc.head.querySelectorAll('style').forEach(style => {
        if (style.id === 'fc-body-lock') return;
        if (!style.textContent.trim()) return;
        const ns = document.createElement('style');
        ns.textContent = style.textContent;
        ns.setAttribute('data-fc-page', href);
        document.head.appendChild(ns);
      });
      if (cssPromises.length) await withTimeout(Promise.all(cssPromises), RESOURCE_TIMEOUT);

      /* ── 6. FORÇAR RECALCULO SÍNCRONO ANTES DO SWAP ── */
      /* Este é o ponto crítico da v14: garantir que o CSS está processado
         pelo browser ANTES de trocar o DOM. */
      forceStyleRecalc();

      /* Avisar página anterior */
      window.dispatchEvent(new Event('fc-page-unload'));

      /* ── 8. SWAP ── */
      const newMain = canPersistSidebar ? doc.body.querySelector('.main') : null;
      if (newMain) {
        currentMain.replaceWith(newMain);
        /* ── 8b. SWAP DE MODAIS FORA DO .main ──
         * O DOMParser aninha os modais dentro de .app (pois .app nunca fecha explicitamente).
         * Por isso, buscamos TODOS os .modal-overlay fora de .main e os trocamos.
         * Modais dentro de .main já são trocados pelo replaceWith acima. */
        /* Encontrar TODOS os modais no doc parseado que estão fora de .main */
        const allParsedModals = doc.body.querySelectorAll('.modal-overlay');
        const newModals = [];
        allParsedModals.forEach(m => {
          /* Verificar se o modal está dentro de .main */
          if (m.closest('.main')) return; /* Está dentro do .main, não precisa trocar separadamente */
          newModals.push(m);
        });
        /* Sempre remover modais antigos fora do .main (que já foi substituído) */
        document.querySelectorAll('.modal-overlay').forEach(m => m.remove());
        if (newModals.length > 0) {
          /* Adiciona os novos modais após o .main */
          const frag = document.createDocumentFragment();
          newModals.forEach(m => frag.appendChild(m.cloneNode(true)));
          newMain.after(frag);
        }
      } else {
        document.body.innerHTML = doc.body.innerHTML;
      }

      /* ── 9. REMOVER CSS DE PÁGINAS ANTERIORES (após swap) ── */
      document.head.querySelectorAll('style[data-fc-page]').forEach(el => {
        if (el.getAttribute('data-fc-page') !== href) el.remove();
      });
      document.head.querySelectorAll('script[data-fc-page-src]').forEach(el => el.remove());

      /* ── 10. FORÇAR RECALCULO APÓS SWAP ── */
      forceStyleRecalc();

      /* ── 11. CARREGAR BIBLIOTECAS EXTERNAS ── */
      const externalPromises = [];
      const currentScripts = new Set(
        [...document.querySelectorAll('script[src]')].map(s => s.src)
      );
      doc.head.querySelectorAll('script[src]').forEach(s => {
        const src = resolveUrl(s.getAttribute('src'), baseHref);
        if (!src || currentScripts.has(src)) return;
        externalPromises.push(
          withTimeout(new Promise(resolve => {
            const ns = document.createElement('script');
            ns.async = false;
            ns.src = src;
            ns.onload = () => resolve();
            ns.onerror = () => {
              console.error('[FC-SPA] Falha biblioteca:', src);
              resolve();
            };
            document.head.appendChild(ns);
          }), RESOURCE_TIMEOUT)
        );
      });
      if (externalPromises.length) await withTimeout(Promise.all(externalPromises), RESOURCE_TIMEOUT);

      /* ── 12. EXECUTAR SCRIPTS DA PÁGINA ── */
      const pageScriptPromises = [];
      extractedScripts.forEach(({ src, text }) => {
        if (src) {
          const srcName = src.split('/').pop().split('?')[0];
          if (GLOBAL_SCRIPTS.includes(srcName)) return;
          const resolved = resolveUrl(src, baseHref);
          if (!resolved) return;
          pageScriptPromises.push(
            withTimeout(new Promise(resolve => {
              const ns = document.createElement('script');
              ns.async = false;
              ns.src = resolved;
              ns.setAttribute('data-fc-page-src', href);
              ns.onload = () => resolve();
              ns.onerror = () => {
                console.error('[FC-SPA] Falha script:', resolved);
                resolve();
              };
              document.head.appendChild(ns);
            }), RESOURCE_TIMEOUT)
          );
        } else if (text && text.trim()) {
          const ns = document.createElement('script');
          ns.textContent = text;
          ns.setAttribute('data-fc-page-src', href);
          document.head.appendChild(ns);
        }
      });
      if (pageScriptPromises.length) await withTimeout(Promise.all(pageScriptPromises), RESOURCE_TIMEOUT);

      /* ── 13. EVENTOS DE INICIALIZAÇÃO ── */
      window.dispatchEvent(new Event('fc-page-ready'));
      document.dispatchEvent(new Event('DOMContentLoaded'));

      /* ── 14. SIDEBAR / LOGOUT / HISTÓRICO ── */
      initSidebar();
      initLogout();
      initSpaHistory();

      /* ── 15. FINALIZAR ── */
      clearTimeout(watchdog);
      document.body.scrollTop = 0;
      window.scrollTo(0, 0);
      spaNavigating = false;
      const next = pendingNav;
      pendingNav = null;
      if (next) spaLoadPage(next);
    } catch (err) {
      console.error('[FC-SPA] Erro navegando para', href, err);
      clearTimeout(watchdog);
      spaNavigating = false;
      window.location.href = href;
    }
  }
  /* Exposição global para navegação programática de páginas */
  window.fcNavigate = (href) => {
    window.history.replaceState({ href }, '', href);
    spaLoadPage(href);
  };

  /* ══ HISTÓRICO DO BROWSER ══ */
  /* ══ initSpaHistory(): Configura o histórico do navegador (pushState/popstate).
   * Permite que os botões Voltar/Avançar do navegador funcionem
   * corretamente dentro do SPA sem recarregar a página. */
  function initSpaHistory() {
    window.onpopstate = (e) => {
      const target = (e.state && e.state.href) || window.location.pathname;
      if (target !== window.location.pathname) {
        spaLoadPage(target);
        window.history.replaceState({ href: target }, '', target);
      }
    };
  }

  /* ══ initSidebar(): Inicializa a sidebar interativa.
   * Configura: clique nos itens (navegação SPA), toggle mobile,
   * botão de recolher, badges de alerta e estado ativo do item. */
  function initSidebar() {
    const sb = document.getElementById('sidebar');
    const overlay = document.getElementById('sb-overlay');
    const btnCollapse = document.getElementById('btn-collapse');
    const btnMobileMenu = document.getElementById('btn-mobile-menu');

    if (!sb) return;

    const isMobile = () => window.innerWidth <= 860;
    const closeMobile = () => {
      const sbCur = document.getElementById('sidebar');
      if (!sbCur) return;
      sbCur.classList.remove('mobile-open');
      document.getElementById('sb-overlay')?.classList.remove('visible');
      document.body.style.overflow = '';
    };

    if (!isMobile() && localStorage.getItem('fc_sb') === '1') {
      sb.classList.add('collapsed');
    }

    if (btnCollapse) {
      btnCollapse.addEventListener('click', () => {
        const sbCur = document.getElementById('sidebar');
        if (!sbCur || isMobile()) return;
        sbCur.classList.toggle('collapsed');
        localStorage.setItem('fc_sb', sbCur.classList.contains('collapsed') ? '1' : '0');
      });
    }

    btnMobileMenu?.addEventListener('click', () => {
      const sbCur = document.getElementById('sidebar');
      if (!sbCur) return;
      const ov = document.getElementById('sb-overlay');
      if (sbCur.classList.contains('mobile-open')) {
        sbCur.classList.remove('mobile-open');
        ov?.classList.remove('visible');
        document.body.style.overflow = '';
      } else {
        sbCur.classList.add('mobile-open');
        ov?.classList.add('visible');
        document.body.style.overflow = 'hidden';
      }
    });

    if (!globalClickAttached) {
      globalClickAttached = true;
      document.addEventListener('click', (e) => {
        const sbCur = document.getElementById('sidebar');
        if (!sbCur) return;
        const isMobCur = () => window.innerWidth <= 860;
        if (
          isMobCur() &&
          sbCur.classList.contains('mobile-open') &&
          !sbCur.contains(e.target) &&
          e.target !== document.getElementById('btn-mobile-menu') &&
          e.target !== document.getElementById('sb-overlay')
        ) {
          sbCur.classList.remove('mobile-open');
          document.getElementById('sb-overlay')?.classList.remove('visible');
          document.body.style.overflow = '';
        }
      });
    }

    if (!globalResizeAttached) {
      globalResizeAttached = true;
      window.addEventListener('resize', () => {
        const sbCur = document.getElementById('sidebar');
        if (!sbCur) return;
        if (window.innerWidth > 860) {
          sbCur.classList.remove('mobile-open');
          document.getElementById('sb-overlay')?.classList.remove('visible');
          document.body.style.overflow = '';
        } else {
          sbCur.classList.remove('collapsed');
        }
      });
    }

    const currentPath = window.location.pathname;
    document.querySelectorAll('.sb-item').forEach((item) => {
      item.classList.remove('active');
      const href = item.getAttribute('href');
      if (href && currentPath.includes(href.split('/').pop())) {
        item.classList.add('active');
      }
    });

    document.querySelectorAll('.sb-item:not([data-attached])').forEach((item) => {
      item.setAttribute('data-attached', '1');
      item.addEventListener('click', (e) => {
        if (isMobile()) closeMobile();
        const href = item.getAttribute('href');
        if (!href) return;
        const isSamePage = item.classList.contains('active');
        e.preventDefault();
        if (isSamePage) return;
        item.classList.add('sb-clicked');
        setTimeout(() => item.classList.remove('sb-clicked'), 200);
        window.history.replaceState({ href }, '', href);
        spaLoadPage(href);
      });
    });
  }

  /* ══ initLogout(): Configura o botão de logout em TODAS as páginas.
   * Quando clicado: limpa a sessão (localStorage), remove cookies
   * e redireciona para a página de login (auth.html). */
  function initLogout() {
    if (globalLogoutAttached) return;
    globalLogoutAttached = true;
    document.addEventListener('click', (e) => {
      const logoutBtn = e.target.closest('[data-logout]') || e.target.closest('#btn-logout');
      if (!logoutBtn) return;
      e.preventDefault();
      e.stopPropagation();
      sessionStorage.removeItem('farmacontrol_usuario');
      sessionStorage.removeItem('farmacontrol_perfil');
      sessionStorage.removeItem('farmacontrol_token');
      const logoutUrl = logoutBtn.getAttribute('data-logout') || logoutBtn.getAttribute('href') || '../../auth/auth.html';
      window.location.href = logoutUrl;
    });
  }

  /* ══ INICIALIZAÇÃO GLOBAL (executa uma vez) ══ */
  /* ══ init(): Inicialização automática do SPA.
   * Executada ao carregar o script. Configura: sidebar, histórico,
   * logout e aplica as configurações de tema do usuário. */
  function init() {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => {
        initSidebar();
        initLogout();
        initSpaHistory();
      });
    } else {
      initSidebar();
      initLogout();
      initSpaHistory();
    }
  }

  init();
})();

/* ══ MODAL DE VISUALIZAÇÃO GLOBAL (read-only) ══ */
window.fcOpenViewModal = function(title, subtitle, contentHtml) {
  // Remove qualquer modal de visualização anterior
  document.querySelectorAll('.fc-view-overlay').forEach(m => m.remove());

  const overlay = document.createElement('div');
  overlay.className = 'fc-view-overlay modal-overlay open';
  overlay.innerHTML = `
    <div class="modal" style="max-width:720px;width:95%;">
      <div class="modal-head">
        <div style="flex:1;min-width:0;">
          <h3 class="modal-title" style="font-size:16px;font-weight:600;">${title}</h3>
          ${subtitle ? `<p style="font-size:12px;color:var(--ink-35);margin-top:2px;">${subtitle}</p>` : ''}
        </div>
        <button class="modal-close" onclick="this.closest('.fc-view-overlay').remove()">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2.5 2.5l9 9M11.5 2.5l-9 9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
        </button>
      </div>
      <div class="modal-body" style="max-height:65vh;overflow-y:auto;padding:20px 22px;">
        ${contentHtml}
      </div>
      <div class="modal-foot">
        <button class="btn-modal-cancel" onclick="this.closest('.fc-view-overlay').remove()">Fechar</button>
      </div>
    </div>
  `;

  document.body.appendChild(overlay);
};
