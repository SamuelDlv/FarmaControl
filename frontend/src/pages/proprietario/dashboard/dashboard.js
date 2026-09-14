/* ══════════════════════════════════════════════════════════════════════
 * FARMAControl — DASHBOARD DO PROPRIETÁRIO
 * ══════════════════════════════════════════════════════════════════════
 *
 * Página principal do sistema. Exibe:
 * - KPIs: Total em estoque, críticos, vencendo, saídas/entradas hoje
 * - Gráfico de barras: Saídas dos últimos 7 dias
 * - Tabela: Produtos críticos (baixo estoque ou vencendo)
 * - Ranking: Top 5 produtos mais dispensados
 * - Alertas: Painel lateral com avisos urgentes
 *
 * Dados são carregados da API: GET /dashboard/stats
 * ══════════════════════════════════════════════════════════════════════ */

/* ── Ciclo de vida SPA: coleta timers desta página para descarte ao sair */
if (!window.__fcTimers) { window.__fcTimers = []; window.addEventListener('fc-page-unload', () => {
  window.__fcTimers.forEach(id => { clearInterval(id); clearTimeout(id); });
  window.__fcTimers = [];
  window.dispatchEvent(new Event('fc-page-unloaded'));
}); }
var __fcSetInterval = (fn, ms) => { const i = setInterval(fn, ms); window.__fcTimers.push(i); return i; };
var __fcSetTimeout  = (fn, ms) => { const i = setTimeout(fn, ms); window.__fcTimers.push(i); return i; };
// Guard de sessão e dados do usuário agora são gerenciados globalmente pelo global-settings.js e sidebar-init.js

'use strict';

var API_BASE = window.FarmaControlSettings ? window.FarmaControlSettings.API_BASE : 'http://localhost:5000';
var EASE = t => t < 0.5 ? 2*t*t : -1+(4-2*t)*t;

var _dashboardKpis = {};

  /* loadDashboardStats(): Carrega todos os dados do dashboard da API (KPIs, produtos críticos, ranking, movimentações). Atualiza o DOM com os valores reais do banco. */
  async function loadDashboardStats() {
  if (!document.getElementById('kpi-vendas-hoje') && !document.querySelector('.kpi-grid')) return;
  /* Token de página — se mudou durante o await, silenciosamente aborta */
  const token = window.__fcPageToken;
  try {
    const res = await fetch(`${API_BASE}/dashboard/stats`);
    if (window.__fcPageToken !== token) return; /* navegação mudou de página */
    const result = await res.json();
    if (result.ok) {
      const { kpis, movimentacoes_semana, top_produtos, produtos_criticos } = result;
      _dashboardKpis = kpis;

      // Renderiza Tabela de Produtos Críticos
      const tbody = document.getElementById('table-body');
      if (tbody && produtos_criticos) {
        tbody.innerHTML = produtos_criticos.map(p => {
          const statusLabel = p.status_classe === 'crit' ? 'Crítico' : 'Baixo';
          const validade = p.data_validade ? new Date(p.data_validade).toLocaleDateString('pt-BR', { month: '2-digit', year: 'numeric' }) : '—';
          return `
            <tr data-status="${p.status_classe}">
              <td><span class="prod-name">${p.nome}</span></td>
              <td>${p.categoria}</td>
              <td><span class="lot-pill">${p.lote}</span></td>
              <td class="r">${p.quantidade}</td>
              <td class="r">${p.estoque_minimo}</td>
              <td>${validade}</td>
              <td><span class="status-badge ${p.status_classe}">${statusLabel}</span></td>
              <td class="c"><button class="row-btn" onclick="window.location.href='../estoque/estoque.html'">Repor</button></td>
            </tr>`;
        }).join('');

        // Atualiza o contador de itens críticos no cabeçalho da tabela
        const badge = document.querySelector('.card-head-l .badge');
        if (badge) badge.textContent = `${produtos_criticos.length} itens`;
      }

      // Mapeamento de texto do card → chave do KPI
      const kpiTextMap = [
        { text: 'Total em Estoque',    key: 'total_itens'        },
        { text: 'Estoque Crítico',     key: 'estoque_critico'    },
        { text: 'Vencem em 30 dias',   key: 'vencendo_30'        },
        { text: 'Saídas Hoje',         key: 'saidas_hoje'        },
        { text: 'Entradas Hoje',       key: 'entradas_hoje'      },
        { text: 'Compras Pendentes',   key: 'compras_pendentes'  },
        { text: 'Fornecedores Ativos', key: 'fornecedores_ativos'},
        { text: 'Valor em Estoque',    key: 'valor_estoque'      },
      ];

      document.querySelectorAll('.kpi-value[data-target]').forEach(el => {
        const card = el.closest('.kpi-card');
        if (!card) return;
        const cardText = card.textContent;
        for (const { text, key } of kpiTextMap) {
          if (cardText.includes(text) && kpis[key] !== undefined) {
            el.dataset.target = kpis[key];
            break;
          }
        }
      });

      // Reinicializa os contadores com os novos valores
      initCounters();

      // Renderiza Ranking de Produtos (Top Dispensados)
      const rankList = document.getElementById('rank-list');
      if (rankList && top_produtos) {
        const maxSaidas = top_produtos.length > 0 ? Math.max(...top_produtos.map(p => p.total_saidas)) : 1;
        rankList.innerHTML = top_produtos.map((p, i) => {
          const pct = (p.total_saidas / maxSaidas) * 100;
          return `
            <li class="rank-item">
              <span class="rank-pos">${i + 1}</span>
              <div class="rank-info">
                <span class="rank-name">${p.produto_nome}</span>
                <div class="rank-bar-wrap"><div class="rank-bar" style="width:${pct}%"></div></div>
              </div>
              <span class="rank-val">${p.total_saidas}</span>
            </li>`;
        }).join('');
      }

      // Renderiza Alertas Ativos (Painel Lateral)
      const palerts = document.getElementById('palerts');
      if (palerts && produtos_criticos) {
        palerts.innerHTML = produtos_criticos.slice(0, 5).map(p => {
          const icon = p.status_classe === 'crit' ? 
            `<svg viewBox="0 0 14 14" fill="none"><path d="M7 1.5L13.5 12.5H.5L7 1.5Z" stroke="currentColor" stroke-width="1.1" stroke-linejoin="round"/><path d="M7 6v2.5M7 10v.5" stroke="currentColor" stroke-width="1.1" stroke-linecap="round"/></svg>` :
            `<svg viewBox="0 0 14 14" fill="none"><circle cx="7" cy="7" r="5.5" stroke="currentColor" stroke-width="1.1"/><path d="M7 4.5v3M7 9v.5" stroke="currentColor" stroke-width="1.1" stroke-linecap="round"/></svg>`;
          
          return `
            <div class="palert ${p.status_classe}">
              <div class="palert-icon ${p.status_classe}">${icon}</div>
              <div class="palert-body">
                <p class="palert-title">${p.nome} — ${p.status_classe === 'crit' ? 'crítico' : 'baixo'}</p>
                <p class="palert-desc">${p.quantidade} unidades restantes · mín: ${p.estoque_minimo}</p>
              </div>
              <span class="palert-time">agora</span>
            </div>`;
        }).join('');
        
        // Atualiza badge de alertas no painel
        const alertBadge = document.querySelector('.panel-hd .badge.red');
        if (alertBadge) alertBadge.textContent = produtos_criticos.length;
      }

      // Guarda os dados para os modais de detalhe
      _dashboardData = { produtos_criticos, top_produtos, movimentacoes_semana, kpis };

      // Renderiza Gráfico de Saídas (7 dias)
      const barsGroup = document.getElementById('bars-group');
      if (barsGroup && movimentacoes_semana) {
        const maxVal = Math.max(...movimentacoes_semana.map(m => m.total), 10);
        barsGroup.innerHTML = movimentacoes_semana.map(m => {
          const pct = (m.total / maxVal) * 100;
          const date = new Date(m.dia);
          const label = date.toLocaleDateString('pt-BR', { weekday: 'short' }).replace('.', '');
          const isToday = new Date().toDateString() === date.toDateString();
          return `
            <div class="bar-col ${isToday ? 'today' : ''}">
              <div class="bar-tip">${label} · ${m.total}</div>
              <div class="bar-fill" style="--pct:${pct}%"></div>
              <span class="bar-label">${isToday ? 'Hoje' : label}</span>
            </div>`;
        }).join('');
      }

      // Reaplica o filtro ativo após nova carga de dados
      applyCriticalFilter();

      // Atualiza badges de alerta na sidebar
      const totalAlertas = (kpis.estoque_critico || 0) + (kpis.vencendo_30 || 0) + (kpis.vencidos || 0);
      document.querySelectorAll('.nav-badge, .sb-badge').forEach(b => {
        b.textContent = totalAlertas;
        b.style.display = totalAlertas > 0 ? '' : 'none';
      });

    } else {
      try {
        const errorData = await res.clone().json().catch(() => ({}));
        console.error('Erro na API:', errorData);
        throw new Error(errorData.mensagem || 'Resposta da API não foi ok');
      } catch (parseErr) {
        throw new Error(parseErr instanceof Error ? parseErr.message : 'Resposta da API não foi ok');
      }
    }
  } catch (err) {
    console.error('Erro de conexão ou processamento:', err);
    toast('Erro ao conectar com o servidor. Verifique se o backend está rodando.', 'error');
    throw err;
  }
}


  /* initCounters(): Anima os números dos KPIs de 0 até o valor final (efeito de contagem crescente). Usa IntersectionObserver para iniciar quando visível. */
  function initCounters() {
  document.querySelectorAll('.kpi-value[data-target]').forEach(el => {
    const target = +el.dataset.target; 
    let done = false;
    const obs = new IntersectionObserver(([e]) => { 
      if (e.isIntersecting && !done) { 
        done = true; 
        obs.disconnect(); 
        const t0 = performance.now(); 
        (function s(now) { 
          const p = Math.min((now-t0)/900,1); 
          el.textContent = Math.round(EASE(p)*target).toLocaleString('pt-BR'); 
          if(p<1) requestAnimationFrame(s); 
        })(t0); 
      } 
    }, {threshold:0.1});
    obs.observe(el);
  });
}

/* Filtro reativo: mantém o filtro ativo e re-renderiza quando os dados mudam */
var _activeFilter = 'all';

  /* initFilter(): Configura os botões de filtro da tabela (Todos, Críticos, Baixos). Ao clicar, filtra as linhas da tabela. */
  function initFilter() {
  const tableBody = document.getElementById('table-body');
  if (!tableBody) return;

  document.querySelectorAll('.ftab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.ftab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      _activeFilter = tab.dataset.filter;
      applyCriticalFilter();
    });
  });
}

  /* applyCriticalFilter(): Aplica o filtro ativo na tabela de produtos críticos. Mostra/oculta linhas conforme o filtro selecionado. */
  function applyCriticalFilter() {
  const tableBody = document.getElementById('table-body');
  if (!tableBody) return;
  const cnt = document.getElementById('filter-count');
  const rows = [...tableBody.querySelectorAll('tr')];
  let v = 0;
  rows.forEach(r => {
    const ok = _activeFilter === 'all' || r.dataset.status === _activeFilter;
    r.style.display = ok ? '' : 'none';
    if (ok) v++;
  });
  if (cnt) cnt.textContent = `Exibindo ${v} de ${rows.length} itens`;
  // Sincroniza o botão "Ver todos" com o estado do filtro
  const verTodos = [...document.querySelectorAll('.card-link, .panel-link')].find(b => b.textContent.trim() === 'Ver todos →');
  if (verTodos && _activeFilter !== 'all' && v < rows.length) {
    verTodos.textContent = 'Ver todos →';
  }
}

/* ══ TOAST — sistema global do global-settings.js ══ */
var toast = window.FarmaControlSettings ? window.FarmaControlSettings.showToast : (() => console.warn('Toast indisponível'));

  /* initEvents(): Configura todos os event listeners da página: botão atualizar, exportar CSV, modal de movimentação, botões "Ver todos/relatório/análise". */
  function initEvents() {
  // Botão Atualizar — recarrega dados reais do banco
  document.getElementById('btn-refresh')?.addEventListener('click', async () => {
    const svg = document.querySelector('#btn-refresh svg');
    if (svg) {
      svg.style.transition = 'transform 0.6s';
      svg.style.transform  = 'rotate(360deg)';
      setTimeout(() => { svg.style.transition = 'none'; svg.style.transform = 'rotate(0deg)'; }, 650);
    }
    try {
      await loadDashboardStats();
      initCounters();
      toast('Dados atualizados com sucesso.', 'success');
    } catch (err) {
      toast('Erro ao atualizar dados.', 'error');
    }
  });

  // Botão Exportar
  document.querySelectorAll('.ghost-btn').forEach(btn => {
    if (btn.textContent.includes('Exportar')) {
      btn.addEventListener('click', () => {
        handleExport();
      });
    }
  });

  // Botão Registrar Movimentação
  const btnMov = document.getElementById('btn-movimentacao');
  if (btnMov) {
    btnMov.onclick = (e) => {
      e.preventDefault();
      openMovModal();
    };
  }

  // Mudança de tipo no modal
  const selectTipo = document.getElementById('mov-tipo');
  if (selectTipo) {
    selectTipo.onchange = updateModalStyle;
  }

  // Botões da tabela
  document.querySelectorAll('.row-btn').forEach(btn => btn.addEventListener('click', e => {
    const name = e.target.closest('tr')?.querySelector('.prod-name')?.textContent || 'produto';
    toast(btn.textContent === 'Repor' ? `Reposição criada: ${name}` : `Abrindo ficha: ${name}`, btn.textContent === 'Repor' ? 'success' : 'info');
  }));

  // Botão Notificações

  // Botões de link abrem modal de visualização
  document.querySelectorAll('.card-link, .panel-link').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const text = btn.textContent.trim();
      handleViewLink(text, btn);
    });
  });
}

  /* handleViewLink(): Abre modais de visualização para "Ver todos →", "Ver relatório →", "Ver análise →" — apenas visualização, sem interação. */
  function handleViewLink(linkText, btn) {
  if (!window.fcOpenViewModal) return;
  const card = btn.closest('.card, .panel-section');
  const cardTitle = card?.querySelector('.card-title, .panel-title')?.textContent || '';

  if (linkText.includes('Ver todos') && cardTitle.includes('Críticos')) {
    // Modal: Todos os medicamentos críticos
    const rows = [...document.querySelectorAll('#table-body tr')];
    let tableHtml = '<table style="width:100%;font-size:12px;border-collapse:collapse;"><thead><tr style="border-bottom:2px solid var(--ink-12);text-align:left;"><th style="padding:8px 6px;">Produto</th><th style="padding:8px 6px;">Lote</th><th style="padding:8px 6px;text-align:right;">Qtd</th><th style="padding:8px 6px;text-align:right;">Mín</th><th style="padding:8px 6px;">Status</th></tr></thead><tbody>';
    rows.forEach(r => {
      const cells = [...r.querySelectorAll('td')];
      if (cells.length >= 7) {
        const status = cells[6]?.textContent?.trim() || '';
        const statusClass = status.toLowerCase().includes('crit') ? 'color:var(--red);font-weight:600;' : status.toLowerCase().includes('baixo') ? 'color:var(--amber);font-weight:600;' : '';
        tableHtml += `<tr style="border-bottom:1px solid var(--ink-06);"><td style="padding:8px 6px;">${cells[0]?.textContent || ''}</td><td style="padding:8px 6px;">${cells[2]?.textContent || ''}</td><td style="padding:8px 6px;text-align:right;">${cells[3]?.textContent || ''}</td><td style="padding:8px 6px;text-align:right;">${cells[4]?.textContent || ''}</td><td style="padding:8px 6px;${statusClass}">${status}</td></tr>`;
      }
    });
    tableHtml += '</tbody></table>';
    window.fcOpenViewModal('Medicamentos Críticos', `${rows.length} itens no total — visão completa`, tableHtml);
  }
  else if (linkText.includes('Ver relatório')) {
    // Modal: Top dispensados
    const items = [...document.querySelectorAll('#rank-list li')];
    let html = '<div style="display:flex;flex-direction:column;gap:8px;">';
    items.forEach(li => { html += `<div style="padding:10px 12px;background:var(--surface);border:1px solid var(--ink-06);border-radius:8px;font-size:13px;">${li.innerHTML}</div>`; });
    html += '</div>';
    window.fcOpenViewModal('Top Dispensados — Mês', 'Medicamentos mais dispensados no período', html);
  }
  else if (linkText.includes('Ver análise')) {
    // Modal: Previsão IA
    const items = [...document.querySelectorAll('#ia-list li')];
    let html = '<div style="display:flex;flex-direction:column;gap:8px;">';
    items.forEach(li => { html += `<div style="padding:10px 12px;background:var(--surface);border:1px solid var(--ink-06);border-radius:8px;font-size:13px;">${li.innerHTML}</div>`; });
    html += '</div>';
    window.fcOpenViewModal('Previsão de Demanda — IA', 'Análise de itens com maior necessidade de reposição', html);
  }
  else if (linkText.includes('Ver todos') && cardTitle.includes('Alertas')) {
    // Modal: Alertas ativos
    const alerts = [...document.querySelectorAll('#palerts .palert')];
    let html = '<div style="display:flex;flex-direction:column;gap:8px;">';
    alerts.forEach(a => { html += `<div style="padding:10px 12px;background:var(--surface);border:1px solid var(--ink-06);border-radius:8px;font-size:13px;">${a.innerHTML}</div>`; });
    html += '</div>';
    window.fcOpenViewModal('Alertas Ativos', `${alerts.length} alertas no momento`, html);
  }
  else if (linkText.includes('Ver todos') && cardTitle.includes('Vencimentos')) {
    // Modal: Vencimentos próximos
    const items = [...document.querySelectorAll('#exp-list .exp-item')];
    let html = '<div style="display:flex;flex-direction:column;gap:8px;">';
    items.forEach(a => { html += `<div style="padding:10px 12px;background:var(--surface);border:1px solid var(--ink-06);border-radius:8px;font-size:13px;">${a.innerHTML}</div>`; });
    html += '</div>';
    window.fcOpenViewModal('Vencimentos Próximos', 'Itens próximos do vencimento', html);
  }
}

  /* handleExport(): Exporta os dados do dashboard para CSV (produtos críticos com status, quantidades e datas). */
  function handleExport() {
  const k = _dashboardKpis;
  const csv = [
    `Dashboard FarmaControl — Exportado em ${new Date().toLocaleString('pt-BR')}`,
    '',
    'KPI,Valor',
    `Total de Itens em Estoque,${k.total_itens ?? ''}`,
    `Valor Total em Estoque (R$),${k.valor_estoque ?? ''}`,
    `Itens com Estoque Crítico,${k.estoque_critico ?? ''}`,
    `Itens com Estoque Baixo,${k.estoque_baixo ?? ''}`,
    `Lotes Vencidos,${k.vencidos ?? ''}`,
    `Lotes Vencendo em 30 dias,${k.vencendo_30 ?? ''}`,
    `Lotes Vencendo em 60 dias,${k.vencendo_60 ?? ''}`,
    `Saídas Hoje,${k.saidas_hoje ?? ''}`,
    `Entradas Hoje,${k.entradas_hoje ?? ''}`,
    `Compras Pendentes,${k.compras_pendentes ?? ''}`,
    `Fornecedores Ativos,${k.fornecedores_ativos ?? ''}`,
  ].join('\n');

  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  const url  = URL.createObjectURL(blob);
  link.setAttribute('href', url);
  link.setAttribute('download', `dashboard-export-${new Date().toISOString().slice(0,10)}.csv`);
  link.style.visibility = 'hidden';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
  toast('Dados exportados com sucesso!', 'success');
}

var estoqueFull = [];

/* Guarda os dados do dashboard para os modais de detalhe */
var _dashboardData = { produtos_criticos: [], top_produtos: [], movimentacoes_semana: [], kpis: {} };

  /* fetchEstoqueFull(): Busca a lista completa de produtos do estoque para os modais de detalhe. */
  async function fetchEstoqueFull() {
  /* Token de página — se mudou durante o await, silenciosamente aborta */
  const token = window.__fcPageToken;
  try {
    const res = await fetch(`${API_BASE}/estoque`);
    if (window.__fcPageToken !== token) return; /* navegação mudou de página */
    const data = await res.json();
    if (data.ok) {
      estoqueFull = data.estoque;
      // Atualiza o select do modal caso ele esteja aberto
      const select = document.getElementById('mov-estoque-id');
      const modalAberto = document.getElementById('modal-movimentacao')?.classList.contains('open');
      if (select && modalAberto && estoqueFull.length > 0) {
        const valorAtual = select.value;
        select.innerHTML = '<option value="">Selecione um item do estoque...</option>' +
          estoqueFull.map(item => `<option value="${item.id}">${item.produto_nome} - Lote: ${item.lote} (Qtd: ${item.quantidade})</option>`).join('');
        select.value = valorAtual;
      }
    }
  } catch (err) {
    console.error('Erro ao buscar estoque completo:', err);
  }
}

// Lógica do Modal de Movimentação
window.openMovModal = function() {
  const modal = document.getElementById('modal-movimentacao');
  if (!modal) return;

  // Carrega o estoque (com fallback para lista já em memória)
  fetchEstoqueFull();

  // Reseta os campos do formulário
  document.getElementById('mov-estoque-id').value = '';
  document.getElementById('mov-quantidade').value = '';
  document.getElementById('mov-obs').value = '';
  document.getElementById('mov-tipo').value = 'entrada';

  // Popula o select com os itens já carregados
  const select = document.getElementById('mov-estoque-id');
  if (select && estoqueFull && estoqueFull.length > 0) {
    select.innerHTML = '<option value="">Selecione um item do estoque...</option>' +
      estoqueFull.map(item => `<option value="${item.id}">${item.produto_nome} - Lote: ${item.lote} (Qtd: ${item.quantidade})</option>`).join('');
  }

  updateModalStyle();
  modal.classList.add('open');
  document.body.style.overflow = 'hidden';
};

  /* getUsuarioId(): Retorna o ID do usuário logado (salvo no localStorage durante o login). */
  function getUsuarioId() {
  try {
    const raw = sessionStorage.getItem('farmacontrol_usuario');
    return raw ? JSON.parse(raw).id : null;
  } catch { return null; }
}

window.updateModalStyle = function() {
  const tipo = document.getElementById('mov-tipo').value;
  const title = document.getElementById('mov-modal-title');
  const icon = document.getElementById('mov-modal-icon');
  const btnSubmit = document.getElementById('btn-mov-submit');

  if (tipo === 'entrada') {
    title.textContent = 'Registrar Entrada';
    if (icon) icon.style.background = 'var(--sage)';
    if (btnSubmit) btnSubmit.style.background = 'var(--sage)';
  } else {
    title.textContent = 'Registrar Saída';
    if (icon) icon.style.background = 'var(--sage-2)';
    if (btnSubmit) btnSubmit.style.background = 'var(--sage-2)';
  }
};

window.closeMovModal = function() {
  const modal = document.getElementById('modal-movimentacao');
  if (modal) modal.classList.remove('open');
  document.body.style.overflow = '';
};

// Garante que o modal feche ao clicar fora dele
window.addEventListener('click', (e) => {
  const modal = document.getElementById('modal-movimentacao');
  if (e.target === modal) {
    closeMovModal();
  }
});

  /* initClock(): Atualiza o relógio no topo da página a cada segundo. */
  function initClock() {
  const el = document.querySelector('.page-subtitle');
  const dateChip = document.querySelector('.date-chip span');
  
  const t = () => { 
    const n = new Date(); 
    if (el) {
      el.textContent = `Situação do estoque em tempo real · Última atualização: ${String(n.getHours()).padStart(2,'0')}:${String(n.getMinutes()).padStart(2,'0')}:${String(n.getSeconds()).padStart(2,'0')}`; 
    }
    if (dateChip) {
      const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
      dateChip.textContent = n.toLocaleDateString('pt-BR', options);
    }
  };
  t(); 
  __fcSetInterval(t, 1000);
}

// Inicialização segura
  /* initDashboard(): Inicialização automática: carrega dados, configura filtros, eventos e relógio. */
  async function initDashboard() {
  // initSidebar(); // Removido: já inicializado pelo sidebar-init.js
  initFilter(); 
  initClock();
  initEvents();
  try {
    await Promise.all([
      loadDashboardStats(),
      fetchEstoqueFull()
    ]);
  } catch (err) {
    console.error('Erro ao carregar dados do dashboard:', err);
  }
  initCounters(); // Deve ser chamado APÓS loadDashboardStats para evitar piscada
  
  // Bind submit button (remover listener anterior para evitar duplicação)
  const btnSubmit = document.getElementById('btn-mov-submit');
  if (btnSubmit) {
    const novoBtn = btnSubmit.cloneNode(true);
    btnSubmit.parentNode.replaceChild(novoBtn, btnSubmit);
    novoBtn.addEventListener('click', async () => {
    const estoque_id = document.getElementById('mov-estoque-id').value;
    const quantidade = document.getElementById('mov-quantidade').value;
    const type = document.getElementById('mov-tipo').value;
    const observacao = document.getElementById('mov-obs').value;

    if (!estoque_id || !quantidade) {
      toast('Preencha todos os campos obrigatórios', 'error');
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/movimentacoes-estoque`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          estoque_id: parseInt(estoque_id),
          usuario_id: getUsuarioId(),
          tipo_movimentacao: type,
          quantidade: parseInt(quantidade),
          observacao: observacao || (type === 'entrada' ? 'Entrada manual via Dashboard' : 'Saída manual via Dashboard')
        })
      });

      const data = await res.json();
      if (data.ok) {
        toast(type === 'entrada' ? 'Entrada registrada!' : 'Saída registrada!', 'success');
        closeMovModal();
        loadDashboardStats();
      } else {
        toast(data.mensagem || 'Erro ao registrar', 'error');
      }
    } catch (err) {
      toast('Erro de conexão', 'error');
    }
  });
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initDashboard);
} else {
  initDashboard();
}

/* (Atalhos de teclado e gerenciamento da sidebar delegados ao sidebar-init.js) */

/* (Logout delegado ao sidebar-init.js: já limpa a sessão e redireciona corretamente) */
