/**
 * Menu compartilhado. Cada tela carrega em seu próprio documento/contexto JS.
 * O navegador controla o histórico, CSS, scripts e o cancelamento da navegação.
 */
(function () {
  'use strict';
  const collapseButtons = new WeakSet();
  const initializedSidebars = new WeakSet();
  // O script roda no head: evita pintar o menu parcial antes de restaurar o estado.
  document.documentElement.classList.add('fc-sidebar-pending');

  /* Compatibilidade para sessões antigas sem a lista de permissões do login.
     Mantém os padrões do schema; a lista persistida sempre tem prioridade. */
  const ROLE_MODULES = Object.freeze({
    proprietario: [
      'dashboard',
      'estoque',
      'vencimentos',
      'compras',
      'financeiro',
      'relatorios',
      'usuarios',
      'configuracoes'
    ],
    admin: [
      'dashboard',
      'estoque',
      'vencimentos',
      'compras',
      'financeiro',
      'relatorios',
      'usuarios',
      'configuracoes'
    ],
    farmaceutico: ['dashboard', 'estoque', 'vencimentos', 'compras', 'relatorios'],
    atendente: ['dashboard', 'estoque'],
    compras: ['dashboard', 'estoque', 'vencimentos', 'compras', 'relatorios'],
    ti: [
      'dashboard',
      'estoque',
      'vencimentos',
      'compras',
      'financeiro',
      'relatorios',
      'usuarios',
      'configuracoes'
    ],
    visualizador: ['dashboard', 'estoque', 'vencimentos', 'relatorios']
  });

  function getCurrentUser() {
    try {
      return JSON.parse(sessionStorage.getItem('farmacontrol_usuario') || 'null');
    } catch (_) {
      return null;
    }
  }

  function getModuleFromUrl(url) {
    try {
      const path = new URL(url, window.location.href).pathname.toLowerCase();
      const match = path.match(
        /\/(?:sistema|proprietario)\/(dashboard|vendas|estoque|vencimentos|compras|financeiro|relatorios|usuarios|log|configuracoes)\//
      );
      return match ? match[1] : 'dashboard';
    } catch (_) {
      return 'dashboard';
    }
  }

  function hasModuleAccess(module) {
    const user = getCurrentUser();
    /* Mantém a abertura local para desenvolvimento quando não há sessão. */
    if (!user?.perfil) return module !== 'log';
    if (module === 'log') return ['proprietario', 'admin', 'ti'].includes(user.perfil);
    if (module === 'vendas')
      return ['proprietario', 'admin', 'farmaceutico', 'atendente', 'ti'].includes(user.perfil);
    // A mesma matriz persistida que protege a API vem no login para os sete
    // perfis. O fallback só atende sessões antigas sem esse campo.
    if (Array.isArray(user.permissoes)) return user.permissoes.includes(module);
    return (ROLE_MODULES[user.perfil] || ['dashboard']).includes(module);
  }

  function applyModuleAccess() {
    const user = getCurrentUser();
    if (!user?.perfil) return true;
    const currentModule = getModuleFromUrl(window.location.href);
    if (!hasModuleAccess(currentModule)) {
      window.location.replace('../dashboard/dashboard.html');
      return false;
    }
    document.querySelectorAll('.sb-item[href]').forEach(item => {
      const href = item.getAttribute('href') || '';
      /* Normaliza links legados após a pasta compartilhada ser renomeada. */
      const normalizedHref = href.replace('/proprietario/', '/sistema/');
      if (normalizedHref !== href) item.setAttribute('href', normalizedHref);
      const allowed = hasModuleAccess(getModuleFromUrl(normalizedHref));
      item.hidden = !allowed;
      item.setAttribute('aria-hidden', String(!allowed));
    });
    // Oculta tambem os titulos sem nenhum modulo visivel abaixo deles.
    document.querySelectorAll('.sb-group-label').forEach(label => {
      let node = label.nextElementSibling;
      let hasVisibleItem = false;
      while (node && !node.classList.contains('sb-group-label')) {
        if (
          node.matches('.sb-item:not([hidden])') ||
          node.querySelector?.('.sb-item:not([hidden])')
        ) {
          hasVisibleItem = true;
          break;
        }
        node = node.nextElementSibling;
      }
      label.hidden = !hasVisibleItem;
    });
    return true;
  }

  /* ══ LISTENERS GLOBAIS — EXECUTADOS APENAS UMA VEZ ══ */
  let globalResizeAttached = false;
  let globalKeyAttached = false;
  let globalLogoutAttached = false;
  let globalMobileMenuAttached = false;

  /* Controle móvel delegado: os botões de menu são criados por cada documento, portanto não podem depender de listeners presos a uma página. */
  function isMobileViewport() {
    return window.innerWidth <= 860;
  }

  function setMobileSidebar(open) {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sb-overlay');
    const button = document.getElementById('btn-mobile-menu');
    if (!sidebar || !isMobileViewport()) return;

    sidebar.classList.toggle('mobile-open', open);
    overlay?.classList.toggle('visible', open);
    button?.setAttribute('aria-expanded', String(open));
    document.body.style.overflow = open ? 'hidden' : '';
  }

  window.fcNavigate = href => {
    const target = new URL(href, window.location.href);
    if (target.origin !== window.location.origin || !/^https?:$/.test(target.protocol)) return;
    if (!hasModuleAccess(getModuleFromUrl(target.href))) {
      window.FarmaControlSettings?.showToast?.(
        'Você não tem permissão para acessar esta área.',
        'error'
      );
      return;
    }
    if (target.href !== window.location.href) window.location.assign(target.href);
  };

  /* ══ initSidebar(): Inicializa a sidebar interativa.
   * Configura: clique nos itens (navegação entre telas), toggle mobile,
   * botão de recolher, badges de alerta e estado ativo do item. */
  function initSidebar() {
    const sb = document.getElementById('sidebar');
    if (!sb || initializedSidebars.has(sb)) return;
    const dashboard = sb?.querySelector('a[href*="/dashboard/"]');
    if (dashboard && !sb.querySelector('a[href*="/vendas/"]')) {
      const link = document.createElement('a');
      link.href = '../vendas/vendas.html';
      link.className = 'sb-item';
      link.dataset.tooltip = 'Vendas / PDV';
      link.innerHTML =
        '<span class="sb-icon"><svg viewBox="0 0 16 16" fill="none"><path d="M2 2h2l2 8h7l1-6H5M6 13h1m5 0h1" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg></span><span class="sb-label">Vendas / PDV</span>';
      dashboard.after(link);
    }
    const btnCollapse = document.getElementById('btn-collapse');

    if (!sb || !applyModuleAccess()) return;

    const isMobile = isMobileViewport;
    const closeMobile = () => setMobileSidebar(false);

    // Restaura o estado antes da primeira pintura, sem animar a navegação.
    const previousTransition = sb.style.transition;
    sb.style.setProperty('transition', 'none', 'important');
    try {
      const saved = localStorage.getItem('fc_sb');
      const settings = Object.assign(
        {},
        JSON.parse(localStorage.getItem('farmacontrol_configuracoes') || '{}'),
        JSON.parse(sessionStorage.getItem('farmacontrol_visual_bootstrap') || '{}')
      );
      document.body.classList.toggle('fc-density-compact', settings.densidade_interface === 'compacta');
      document.body.classList.toggle('fc-density-spaced', settings.densidade_interface === 'espacada');
      document.body.classList.toggle('fc-no-animations', String(settings.animacoes_interface) === 'false');
      sb.classList.toggle(
        'collapsed',
        !isMobile() &&
          (saved === '1' ||
            (saved === null && String(settings.sidebar_recolhida_padrao) === 'true'))
      );
    } catch (_) {
      /* O menu continua disponível sem armazenamento. */
    }
    void sb.offsetWidth;
    if (previousTransition) sb.style.transition = previousTransition;
    else sb.style.removeProperty('transition');
    initializedSidebars.add(sb);

    if (btnCollapse && !collapseButtons.has(btnCollapse)) {
      collapseButtons.add(btnCollapse);
      btnCollapse.addEventListener('click', event => {
        const sbCur = document.getElementById('sidebar');
        if (!sbCur) return;
        if (isMobile()) {
          event.preventDefault();
          event.stopPropagation();
          closeMobile();
          return;
        }
        sbCur.classList.toggle('collapsed');
        localStorage.setItem('fc_sb', sbCur.classList.contains('collapsed') ? '1' : '0');
      });
    }

    if (!globalMobileMenuAttached) {
      globalMobileMenuAttached = true;
      document.addEventListener(
        'click',
        event => {
          const target = event.target instanceof Element ? event.target : null;
          const menuButton = target?.closest('#btn-mobile-menu');
          if (menuButton) {
            event.preventDefault();
            event.stopPropagation();
            const sidebar = document.getElementById('sidebar');
            setMobileSidebar(!sidebar?.classList.contains('mobile-open'));
            return;
          }

          if (target?.closest('#sb-overlay')) setMobileSidebar(false);
        },
        true
      );
    }

    if (!globalKeyAttached) {
      globalKeyAttached = true;
      document.addEventListener('keydown', event => {
        if (event.key === 'Escape') setMobileSidebar(false);
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
    document.querySelectorAll('.sb-item').forEach(item => {
      item.classList.remove('active');
      const href = item.getAttribute('href');
      if (href && currentPath.includes(href.split('/').pop())) {
        item.classList.add('active');
      }
    });

    document.querySelectorAll('.sb-item:not([data-attached])').forEach(item => {
      item.setAttribute('data-attached', '1');
      item.addEventListener('click', e => {
        if (isMobile()) closeMobile();
        const href = item.getAttribute('href');
        if (!href) return;
        if (!hasModuleAccess(getModuleFromUrl(href))) {
          e.preventDefault();
          window.FarmaControlSettings?.showToast?.(
            'Você não tem permissão para acessar esta área.',
            'error'
          );
        }
        // Links nativos preservam Voltar/Avançar, Ctrl+clique e abrir em nova aba.
      });
    });
    // Mantem a posicao do menu ao navegar em janelas de pouca altura.
    const nav = sb.querySelector('.sb-nav');
    if (nav) {
      try { nav.scrollTop = Number(sessionStorage.getItem('fc_sb_scroll')) || 0; } catch (_) {}
      window.addEventListener('pagehide', () => {
        try { sessionStorage.setItem('fc_sb_scroll', String(nav.scrollTop)); } catch (_) {}
      });
    }
    document.documentElement.classList.remove('fc-sidebar-pending');
  }

  /* ══ initLogout(): Configura o botão de logout em TODAS as páginas.
   * Quando clicado: limpa dados da aba (sessionStorage), invalida o cookie via API
   * e redireciona para a página de login (auth.html). */
  function initLogout() {
    if (globalLogoutAttached) return;
    globalLogoutAttached = true;
    document.addEventListener('click', async e => {
      const logoutBtn = e.target.closest('[data-logout]') || e.target.closest('#btn-logout');
      if (!logoutBtn) return;
      e.preventDefault();
      e.stopPropagation();
      const apiBase = window.FarmaControlSettings?.API_BASE || 'http://localhost:5000';
      // keepalive permite invalidar o cookie mesmo quando a navegacao comeca em seguida.
      try {
        const response = await fetch(`${apiBase}/auth/logout`, { method: 'POST', keepalive: true });
        if (!response.ok) throw new Error('Não foi possível encerrar a sessão. Tente novamente.');
      } catch (_) {
        window.FarmaControlSettings?.showToast?.(
          'Não foi possível encerrar a sessão. Tente novamente.',
          'error'
        );
        return;
      }
      sessionStorage.removeItem('farmacontrol_usuario');
      sessionStorage.removeItem('farmacontrol_perfil');
      sessionStorage.removeItem('farmacontrol_token');
      sessionStorage.removeItem('farmacontrol_csrf');
      sessionStorage.setItem('farmacontrol_skip_login_boot', 'true');
      const logoutUrl =
        logoutBtn.getAttribute('data-logout') ||
        logoutBtn.getAttribute('href') ||
        '../../acesso/acesso.html';
      window.location.href = logoutUrl;
    });
  }

  function init() {
    initSidebar();
    initLogout();
  }
  // Chamado pelo HTML assim que a barra termina de ser lida pelo parser.
  window.fcInitSidebar = init;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();

/* ══ MODAL DE VISUALIZAÇÃO GLOBAL (read-only) ══ */
window.fcOpenViewModal = function (title, subtitle, contentHtml) {
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
