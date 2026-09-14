/* ══════════════════════════════════════════════════════════════════════
 * FARMAControl — PREVISÃO DE DEMANDA POR IA (PROPRIETÁRIO)
 * ══════════════════════════════════════════════════════════════════════
 *
 * Previsão inteligente de demanda de medicamentos:
 * - Gráfico de forecast: Histórico + previsão futura com curva de tendência
 * - KPIs: Demanda estimada, nível de confiança da previsão
 * - Tabela de produtos com previsão de demanda
 * - Histórico de compras relacionado
 * - Filtros por curva de crescimento e categoria
 *
 * Dados são carregados da API: GET /previsao/*
 * ══════════════════════════════════════════════════════════════════════ */

/* ── Ciclo de vida SPA: coleta timers desta página para descarte ao sair */
if (!window.__fcTimers) { window.__fcTimers = []; window.addEventListener('fc-page-unload', () => {
  window.__fcTimers.forEach(id => { clearInterval(id); clearTimeout(id); });
  window.__fcTimers = [];
  window.dispatchEvent(new Event('fc-page-unloaded'));
}); }
var __fcSetInterval = (fn, ms) => { const i = setInterval(fn, ms); window.__fcTimers.push(i); return i; };
var __fcSetTimeout  = (fn, ms) => { const i = setTimeout(fn, ms); window.__fcTimers.push(i); return i; };
'use strict';

/* ══════════════════════════════════════════════════════════════════════
   PREVISÃO IA — FarmaControl · previsao.js
   Padronizado com dashboard.js:
   - initSidebar() com overlay, colapso, mobile drawer, localStorage
   - toast() idêntico ao da dashboard
   - Todas as funcionalidades originais preservadas
   ══════════════════════════════════════════════════════════════════════ */

var API_BASE = window.FarmaControlSettings ? window.FarmaControlSettings.API_BASE : 'http://localhost:5000';
var EASE = t => t < 0.5 ? 2*t*t : -1+(4-2*t)*t;

var forecastChart = null;



/* ══ TOAST — sistema global do global-settings.js ══ */
var toast = window.FarmaControlSettings ? window.FarmaControlSettings.showToast : (() => console.warn('Toast indisponível'));

/* ══ DATA NO TOPBAR ══ */
function initDate() {
  const el = document.getElementById('date-text');
  if (el) {
    el.textContent = new Date().toLocaleDateString('pt-BR', {
      weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
    });
  }
}

/* ══ DADOS DO GRÁFICO — histórico real de saídas dos últimos 30 dias ══ */
async function getChartData(productId) {
  const token = window.__fcPageToken;
  const labels = [], history = [], forecast = [], upper = [], lower = [];
  const res = await fetch(`${API_BASE}/movimentacoes-estoque?tipo=saida&produto_id=${encodeURIComponent(productId)}`);
  if (window.__fcPageToken !== token) return { labels, history, forecast, upper, lower };
  let historico = [];
  if (res.ok) {
    const data = await res.json();
    if (data.ok) historico = data.movimentacoes || data.estoque || [];
  }

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const buckets = new Array(30).fill(0);

  for (const m of historico) {
    const d = new Date(m.data_movimentacao || m.data || '');
    if (!isNaN(d)) {
      d.setHours(0, 0, 0, 0);
      const idx = Math.round((today - d) / 86400000);
      if (idx >= 0 && idx < 30) buckets[29 - idx] += m.quantidade || 0;
    }
  }

  const consumoDia = buckets.reduce((a, b) => a + b, 0) / 30;

  /* Histórico (30 dias) */
  for (let i = 30; i > 0; i--) {
    const d = new Date();
    d.setDate(today.getDate() - i);
    labels.push(d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' }));
    history.push(buckets[30 - i]);
    forecast.push(null);
    upper.push(null);
    lower.push(null);
  }

  /* Hoje */
  labels.push('Hoje');
  history.push(buckets[29]);
  forecast.push(buckets[29]);
  upper.push(buckets[29]);
  lower.push(buckets[29]);

  /* Previsão (30 dias) baseada na média diária real */
  for (let i = 1; i <= 30; i++) {
    const d = new Date();
    d.setDate(today.getDate() + i);
    labels.push(d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' }));
    const val = Math.round(consumoDia * i);
    history.push(null);
    forecast.push(val);
    upper.push(Math.round(val * (1 + 0.15 * (i / 30))));
    lower.push(Math.round(val * (1 - 0.15 * (i / 30))));
  }

  return { labels, history, forecast, upper, lower };
}

/* ══ GRÁFICO ══ */
async function initChart(productId) {
  const token = window.__fcPageToken;
  const ctx = document.getElementById('forecastChart');
  if (!ctx) return;
  let data;
  try {
    data = await getChartData(productId);
    if (window.__fcPageToken !== token) return;
  } catch (err) {
    console.error('Erro ao carregar dados do gráfico:', err);
    data = { labels: [], history: [], forecast: [], upper: [], lower: [] };
  }

  // Lê variáveis CSS dinâmicas para cores do gráfico
  const cssVars = getComputedStyle(document.documentElement);
  const chartSage    = cssVars.getPropertyValue('--sage').trim()    || '#4a7c59';
  const chartSagePale = cssVars.getPropertyValue('--sage-pale').trim() || 'rgba(74,124,89,0.1)';
  const chartInk35   = cssVars.getPropertyValue('--ink-35').trim()  || 'rgba(13,21,16,0.35)';
  const chartInk12   = cssVars.getPropertyValue('--ink-12').trim()  || 'rgba(13,21,16,0.12)';
  // Cor de previsão: usa blue fixo pois é uma cor semântica distinta da cor de destaque
  const chartBlue    = '#2e6da4';
  const chartBluePale = 'rgba(46,109,164,0.1)';

  const chartConfig = {
    type: 'line',
    data: {
      labels: data.labels,
      datasets: [
        {
          label: 'Histórico Real',
          data: data.history,
          borderColor: chartSage,
          backgroundColor: 'transparent',
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.3
        },
        {
          label: 'Previsão IA',
          data: data.forecast,
          borderColor: chartBlue,
          borderDash: [5, 5],
          backgroundColor: 'transparent',
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.3
        },
        {
          label: 'Intervalo de Confiança',
          data: data.upper,
          borderColor: 'transparent',
          backgroundColor: chartBluePale,
          fill: '+1',
          pointRadius: 0,
          tension: 0.3
        },
        {
          label: 'Limite Inferior',
          data: data.lower,
          borderColor: 'transparent',
          backgroundColor: chartBluePale,
          fill: false,
          pointRadius: 0,
          tension: 0.3
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { mode: 'index', intersect: false }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            maxTicksLimit: 10,
            font: { family: 'Outfit', size: 11 },
            color: chartInk35
          }
        },
        y: {
          grid: { color: chartInk12 },
          ticks: {
            font: { family: 'DM Mono', size: 11 },
            color: chartInk35
          }
        }
      }
    }
  };

  if (forecastChart) forecastChart.destroy();
  forecastChart = new Chart(ctx, chartConfig);
}

/* ══ TABELA DE REPOSIÇÃO ══ */
var allProducts = [];

  /* fetchProductsForForecast(): Busca a lista de produtos disponíveis para previsão. */
  async function fetchProductsForForecast() {
  const token = window.__fcPageToken;
  try {
    const res = await fetch(`${API_BASE}/previsao/reposicao`);
    if (window.__fcPageToken !== token) return;
    const data = await res.json();
    if (!data.ok) {
      console.error('Erro na previsão:', data.mensagem);
      return;
    }
    const lista = data.previsao || [];

    allProducts = lista.map(item => {
      const consumoDia = item.consumo_diario || 0;
      const mediaDia = consumoDia > 0 ? consumoDia : (item.reposicao_urgente ? 0.5 : 1);
      const coverage = consumoDia > 0 ? Math.round(item.estoque_atual / consumoDia) : 999;
      const prev30 = Math.round(mediaDia * 30);
      const sug = Math.max(0, Math.round(mediaDia * 60) - item.estoque_atual);
      const giro = consumoDia * 30 * 10; // estimativa simplificada de giro
      const abc = giro > 5000 ? 'A' : giro > 1000 ? 'B' : 'C';
      const estMin = item.estoque_minimo || 10;
      const status = item.reposicao_urgente
        ? (item.estoque_atual <= estMin * 0.5 ? 'Crítico' : 'Alerta')
        : (coverage <= 15 ? 'Alerta' : 'Estável');
      return {
        id:           item.produto_id,
        name:         item.nome || '—',
        principio:    item.nome_generico || '',
        abc,
        cat:          'Geral',
        stock:        item.estoque_atual,
        min:          estMin,
        prev:         prev30,
        sug,
        coverage:     Math.min(coverage, 999),
        supplier:     '—',
        status,
        lote:         '',
        validade:     '',
      };
    });

    // Atualiza o select do gráfico com os produtos reais (depois de carregar)
    const sel = document.getElementById('product-select');
    if (sel && allProducts.length > 0) {
      sel.innerHTML = allProducts.slice(0, 20).map(p =>
        `<option value="${p.id}">${p.name}</option>`
      ).join('');
      // Se o gráfico ainda aponta para um mock id, usa o primeiro produto real
      if (!allProducts.some(p => String(p.id) === String(sel.value))) {
        sel.value = allProducts[0].id;
        await initChart(sel.value);
      }
    }
    renderTable();
  } catch (err) {
    console.error('Erro ao buscar produtos para previsão:', err);
  }
}

/* (populateProductSelect integrado ao fetchProductsForForecast, que agora carrega os produtos reais) */

function renderTable(filterCurve = '', filterCategory = '', searchText = '') {
  const tableBody = document.getElementById('forecast-table-body');
  if (!tableBody) return;

  const filtered = allProducts.filter(p => {
    if (filterCurve && p.abc !== filterCurve) return false;
    if (filterCategory && p.cat !== filterCategory) return false;
    if (searchText && !p.name.toLowerCase().includes(searchText.toLowerCase())) return false;
    return true;
  });

  tableBody.innerHTML = filtered.map(p => {
    const coveragePct  = Math.min(100, Math.round((p.coverage / 30) * 100));
    const coverageColor = p.coverage <= 7 ? 'var(--red, #c03a3a)' : p.coverage <= 15 ? 'var(--amber, #b87a1a)' : 'var(--sage, #4a7c59)';
    const statusClass  = p.status === 'Crítico' ? 'crit' : p.status === 'Alerta' ? 'warn' : 'ok';
    const statusLabel  = p.status === 'Crítico' ? 'Crítico' : p.status === 'Alerta' ? 'Alerta' : 'Estável';
    const abcClass     = `abc-${p.abc.toLowerCase()}`;
    return `
      <tr data-id="${p.id}">
        <td class="c"><input type="checkbox" class="row-check"></td>
        <td><span class="prod-name">${p.name}</span></td>
        <td><span class="abc-tag ${abcClass}">Curva ${p.abc}</span></td>
        <td class="r">${p.stock} un.</td>
        <td class="r" style="color:var(--ink-35)">${p.min} un.</td>
        <td class="r">${p.prev} un.</td>
        <td>
          <div class="coverage-wrap">
            <span style="font-size:12px; font-weight:600; color:${coverageColor}; white-space:nowrap; min-width:28px;">${p.coverage}d</span>
            <div class="coverage-bar"><div class="coverage-fill" style="width:${coveragePct}%; background:${coverageColor};"></div></div>
          </div>
        </td>
        <td class="r"><strong style="color:${p.sug > 0 ? 'var(--sage)' : 'var(--ink-35)'}">+${p.sug} un.</strong></td>
        <td style="color:var(--ink-60); font-size:12px;">${p.supplier}</td>
        <td><span class="status-badge ${statusClass}">${statusLabel}</span></td>
      </tr>`;
  }).join('');

  /* Atualiza KPIs */
  updateForecastKPIs(filtered);

  /* Atualiza contador */
  const countEl = document.getElementById('table-count');
  if (countEl) countEl.textContent = `Exibindo ${filtered.length} itens`;

  const badgeEl = document.getElementById('sug-badge');
  if (badgeEl) badgeEl.textContent = `${filtered.length} itens`;

  /* Renderiza Painéis Laterais */
  renderSidePanels(filtered);

  /* Seleção de linhas — re-registra listeners a cada render */
  const checks     = tableBody.querySelectorAll('.row-check');
  const checkAll   = document.getElementById('check-all');
  const countSpan  = document.getElementById('selected-count');

  const updateCount = () => {
    const n = tableBody.querySelectorAll('.row-check:checked').length;
    if (countSpan) countSpan.textContent = n;
  };

  if (checkAll) {
    /* Remove listener antigo clonando o nó */
    const newCheckAll = checkAll.cloneNode(true);
    checkAll.parentNode.replaceChild(newCheckAll, checkAll);
    newCheckAll.addEventListener('change', () => {
      checks.forEach(c => {
        c.checked = newCheckAll.checked;
        c.closest('tr').classList.toggle('row-selected', c.checked);
      });
      updateCount();
    });
  }

  checks.forEach(c => {
    c.addEventListener('change', () => {
      c.closest('tr').classList.toggle('row-selected', c.checked);
      updateCount();
    });
  });
}

/* ══ HISTÓRICO DE PEDIDOS — busca do banco ══ */
var _allOrders = [];

  /* loadHistoricoCompras(): Carrega o histórico de compras relacionadas ao período. */
  async function loadHistoricoCompras() {
  const body    = document.getElementById('history-table-body');
  const countEl = document.getElementById('history-count');
  if (!body) return;
  const token = window.__fcPageToken;

  try {
    const res    = await fetch(`${API_BASE}/compras`);
    if (window.__fcPageToken !== token) return;
    const result = await res.json();
    if (!result.ok) return;

    _allOrders = (result.compras || []).map(c => ({
      id:       `PED-${String(c.id).padStart(4,'0')}`,
      rawId:    c.id,
      date:     c.criado_em ? new Date(c.criado_em).toLocaleDateString('pt-BR') : '—',
      product:  c.fornecedor_nome || '—',
      qty:      c.itens_count || 0,
      supplier: c.fornecedor_nome || '—',
      total:    c.valor_total
        ? 'R$ ' + parseFloat(c.valor_total).toLocaleString('pt-BR', { minimumFractionDigits: 2 })
        : '—',
      delivery: c.data_entrega_prevista
        ? new Date(c.data_entrega_prevista).toLocaleDateString('pt-BR')
        : '—',
      status:   c.status === 'recebido' ? 'entregue'
              : c.status === 'pendente' ? 'pendente'
              : c.status === 'cancelado' ? 'cancelado'
              : 'transito',
      user:     c.usuario_nome || '—',
    }));

    renderHistory();
  } catch (err) {
    console.error('Erro ao carregar histórico de compras:', err);
  }
}

  /* renderHistory(): Renderiza o histórico de compras com filtros de status. */
  function renderHistory(filterStatus = '') {
  const body    = document.getElementById('history-table-body');
  const countEl = document.getElementById('history-count');
  if (!body) return;

  const filtered = filterStatus
    ? _allOrders.filter(o => o.status === filterStatus)
    : _allOrders;

  const statusLabel = { entregue: 'Entregue', transito: 'Em trânsito', pendente: 'Pendente', cancelado: 'Cancelado' };

  if (filtered.length === 0) {
    body.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:24px;color:rgba(13,21,16,0.4)">Nenhum pedido encontrado.</td></tr>';
    if (countEl) countEl.textContent = 'Exibindo 0 registros';
    return;
  }

  body.innerHTML = filtered.map(o => `
    <tr>
      <td style="font-size:12px; font-weight:600; color:var(--ink-60);">${o.id}</td>
      <td>${o.date}</td>
      <td><span class="prod-name">${o.product}</span></td>
      <td class="r">${o.qty} it.</td>
      <td style="font-size:12px; color:var(--ink-60);">${o.supplier}</td>
      <td class="r" style="font-weight:600;">${o.total}</td>
      <td>${o.delivery}</td>
      <td><span class="status-dot ${o.status}">${statusLabel[o.status] || o.status}</span></td>
      <td style="font-size:12px; color:var(--ink-60);">${o.user}</td>
    </tr>`).join('');

  if (countEl) countEl.textContent = `Exibindo ${filtered.length} registros`;
}

/* ══ EXPORTAR CSV ══ */
function exportTableCSV() {
  const rows = [
    ['Produto', 'Curva', 'Estoque Atual', 'Mín. Config.', 'Prev. (30d)', 'Cobertura (dias)', 'Sugestão (un.)', 'Fornecedor', 'Status']
  ];
  allProducts.forEach(p => {
    rows.push([p.name, `Curva ${p.abc}`, p.stock, p.min, p.prev, p.coverage, p.sug, p.supplier, p.status]);
  });
  const csv = rows.map(r => r.join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = `sugestoes-reposicao-${Date.now()}.csv`;
  link.style.display = 'none';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  toast('CSV exportado com sucesso!', 'success');
}

  /* exportHistoryCSV(): Exporta o histórico de compras para arquivo CSV. */
  function exportHistoryCSV() {
  const rows = [
    ['Nº Pedido', 'Data', 'Fornecedor', 'Itens', 'Valor Total', 'Prev. Entrega', 'Status', 'Usuário']
  ];
  _allOrders.forEach(o => {
    rows.push([o.id, o.date, o.supplier, o.qty, o.total, o.delivery, o.status, o.user]);
  });
  const csv = '\uFEFF' + rows.map(r => r.join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = `historico-pedidos-${new Date().toISOString().slice(0,10)}.csv`;
  link.style.display = 'none';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(link.href);
  toast('Histórico exportado com sucesso!', 'success');
}

/* ══ INICIALIZAÇÃO DA UI ══ */
function initUI() {
  /* Filtros de período */
  document.querySelectorAll('#filter-period .ftab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#filter-period .ftab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      toast(`Período ajustado para ${btn.dataset.val} dias.`, 'info');
    });
  });

  /* Troca de produto no gráfico */
  document.getElementById('product-select')?.addEventListener('change', e => {
    initChart(e.target.value);
    toast(`Gráfico atualizado: ${e.target.options[e.target.selectedIndex].text}`, 'info');
  });

  /* Filtros da tabela */
  const applyTableFilters = () => {
    const curve = document.getElementById('filter-curve')?.value || '';
    const cat   = document.getElementById('filter-category')?.value || '';
    const txt   = document.getElementById('search-table')?.value || '';
    renderTable(curve, cat, txt);
  };

  document.getElementById('filter-curve')?.addEventListener('change', applyTableFilters);
  document.getElementById('filter-category')?.addEventListener('change', applyTableFilters);
  document.getElementById('search-table')?.addEventListener('input', applyTableFilters);

  /* Limpar filtros */
  document.getElementById('btn-clear-filters')?.addEventListener('click', () => {
    const curve = document.getElementById('filter-curve');
    const cat   = document.getElementById('filter-category');
    const txt   = document.getElementById('search-table');
    if (curve) curve.value = '';
    if (cat)   cat.value   = '';
    if (txt)   txt.value   = '';
    document.querySelectorAll('#filter-period .ftab').forEach((b, i) => b.classList.toggle('active', i === 0));
    renderTable();
    toast('Filtros limpos.', 'info');
  });

  /* Filtro de histórico */
  document.getElementById('filter-history-status')?.addEventListener('change', e => renderHistory(e.target.value));

  /* Aprovação em lote */
  document.getElementById('btn-batch-approve')?.addEventListener('click', () => {
    const count = document.querySelectorAll('#forecast-table-body .row-check:checked').length;
    if (count > 0) {
      toast(`${count} pedido(s) de reposição gerado(s) com sucesso!`, 'success');
      /* Desmarca todas */
      document.querySelectorAll('#forecast-table-body .row-check').forEach(c => {
        c.checked = false;
        c.closest('tr').classList.remove('row-selected');
      });
      const checkAll = document.getElementById('check-all');
      if (checkAll) checkAll.checked = false;
      const countSpan = document.getElementById('selected-count');
      if (countSpan) countSpan.textContent = '0';
    } else {
      toast('Selecione ao menos um produto para reposição.', 'error');
    }
  });

  document.getElementById('btn-batch-reject')?.addEventListener('click', () => {
    const count = document.querySelectorAll('#forecast-table-body .row-check:checked').length;
    if (count > 0) {
      toast(`${count} sugestão(ões) rejeitada(s).`, 'info');
      document.querySelectorAll('#forecast-table-body .row-check').forEach(c => {
        c.checked = false;
        c.closest('tr').classList.remove('row-selected');
      });
      const checkAll = document.getElementById('check-all');
      if (checkAll) checkAll.checked = false;
      const countSpan = document.getElementById('selected-count');
      if (countSpan) countSpan.textContent = '0';
    } else {
      toast('Selecione ao menos um produto.', 'error');
    }
  });

  /* Exportar CSV */
  document.getElementById('btn-export-table')?.addEventListener('click', exportTableCSV);
  document.getElementById('btn-export-history')?.addEventListener('click', exportHistoryCSV);

  /* Botões Atualizar (topbar e page-header) — recarrega dados reais */
  const handleRefresh = async () => {
    await Promise.all([fetchProductsForForecast(), loadHistoricoCompras()]);
    toast('Dados atualizados com sucesso.', 'success');
  };
  document.getElementById('btn-refresh')?.addEventListener('click', handleRefresh);

  /* Botão Exportar topbar */
  document.getElementById('btn-export-prev')?.addEventListener('click', exportTableCSV);
  document.getElementById('btn-export')?.addEventListener('click', exportTableCSV);

  /* Botão Notificações */

  /* Botões "Ver todos" são indicadores visuais — sem ação */
}

  /* updateForecastKPIs(): Atualiza os KPIs de previsão (demanda estimada, confiança). */
  function updateForecastKPIs(data) {
  const sugCount = data.filter(p => p.sug > 0).length;
  const curvaA   = data.filter(p => p.abc === 'A').length;
  const rupturas = data.filter(p => p.status === 'Crítico').length;

  const sugEl = document.getElementById('sug-count');
  if (sugEl) sugEl.textContent = sugCount;

  const curvaAEl = document.getElementById('kpi-curva-a');
  if (curvaAEl) curvaAEl.textContent = curvaA;

  const rupturasEl = document.getElementById('kpi-rupturas');
  if (rupturasEl) rupturasEl.textContent = rupturas;

  // Atualiza badges da sidebar
  const criticos = allProducts.filter(p => p.status === 'Crítico').length;
  const alertas  = allProducts.filter(p => p.status === 'Alerta').length;
  const vencendo = allProducts.filter(p => {
    if (!p.validade) return false;
    const d = new Date(p.validade);
    const diff = (d - new Date()) / 86400000;
    return diff > 0 && diff <= 30;
  }).length;

  const stockBadge = document.querySelector('.sb-item[href*="estoque"] .sb-badge');
  if (stockBadge) {
    const count = criticos + alertas;
    stockBadge.textContent = count;
    stockBadge.style.display = count > 0 ? '' : 'none';
  }

  const expiryBadge = document.querySelector('.sb-item[href*="vencimentos"] .sb-badge');
  if (expiryBadge) {
    expiryBadge.textContent = vencendo;
    expiryBadge.style.display = vencendo > 0 ? '' : 'none';
  }
}

  /* renderSidePanels(): Renderiza os painéis laterais com informações complementares. */
  function renderSidePanels(data) {
  // Alertas de Cobertura Crítica
  const insufList = document.getElementById('insuf-list');
  if (insufList) {
    const criticos = data.filter(p => p.coverage <= 15).slice(0, 4);
    if (criticos.length === 0) {
      insufList.innerHTML = '<div style="padding:20px;text-align:center;color:var(--ink-35);font-size:12px;">Nenhum alerta crítico.</div>';
    } else {
      insufList.innerHTML = criticos.map(p => `
        <div class="palert ${p.coverage <= 7 ? 'crit' : 'warn'}">
          <div class="palert-icon ${p.coverage <= 7 ? 'crit' : 'warn'}">
            <svg viewBox="0 0 14 14" fill="none"><path d="M7 1.5L13.5 12.5H.5L7 1.5Z" stroke="currentColor" stroke-width="1.1" stroke-linejoin="round"/><path d="M7 6v2.5M7 10v.5" stroke="currentColor" stroke-width="1.1" stroke-linecap="round"/></svg>
          </div>
          <div class="palert-body">
            <p class="palert-title">${p.name}</p>
            <p class="palert-desc">Cobertura: ${p.coverage} dias · mín: ${p.min}u</p>
          </div>
          <span class="palert-time">${p.coverage}d</span>
        </div>
      `).join('');
    }
  }

  // Previsão Resumida (IA List)
  const iaList = document.getElementById('ia-forecast-list');
  if (iaList) {
    const topGiro = data.sort((a, b) => b.prev - a.prev).slice(0, 4);
    if (topGiro.length === 0) {
      iaList.innerHTML = '<div style="padding:20px;text-align:center;color:var(--ink-35);font-size:12px;">Sem dados de previsão.</div>';
    } else {
      iaList.innerHTML = topGiro.map(p => {
        const trend = p.abc === 'A' ? 'high' : p.abc === 'B' ? 'mid' : 'low';
        const icon = trend === 'high' ? '<svg viewBox="0 0 14 14" fill="none"><path d="M7 2v10M3 6l4-4 4 4" stroke="currentColor" stroke-width="1.25" stroke-linecap="round" stroke-linejoin="round"/></svg>'
                   : trend === 'mid' ? '<svg viewBox="0 0 14 14" fill="none"><path d="M2 7h10" stroke="currentColor" stroke-width="1.25" stroke-linecap="round"/></svg>'
                   : '<svg viewBox="0 0 14 14" fill="none"><path d="M7 2v10M3 8l4 4 4-4" stroke="currentColor" stroke-width="1.25" stroke-linecap="round" stroke-linejoin="round"/></svg>';
        return `
          <li class="ia-item ${trend}">
            <div class="ia-ico ${trend === 'mid' ? 'mid' : trend === 'low' ? 'low' : ''}">${icon}</div>
            <div class="ia-body"><p class="ia-prod">${p.name}</p><p class="ia-reason">Curva ${p.abc} · Giro: ${p.prev}u/mês</p></div>
            <div class="ia-forecast"><span class="ia-pct">${p.abc === 'A' ? '+12%' : 'Estável'}</span><span class="ia-lbl">demanda</span></div>
          </li>
        `;
      }).join('');
    }
  }
}

/* ══ INICIALIZAÇÃO ══ */
document.addEventListener('DOMContentLoaded', async () => {
  initDate();
  initUI();
  // Carrega dados reais primeiro; o gráfico é atualizado com produtos reais em seguida
  await Promise.all([fetchProductsForForecast(), loadHistoricoCompras()]);
  // Garante que o gráfico tenha um produto para exibir — mesmo sem dados
  // reais (allProducts vazio), o gráfico mostra o preview (linha em y=0),
  // evitando o canvas em branco que sobra após navegação SPA
  const sel = document.getElementById('product-select');
  if (sel && sel.value) {
    await initChart(sel.value);
  }
});

/* ══ BOTÕES DE VISUALIZAÇÃO (abrem modal read-only) ══ */
function initPrevisaoViewLinks() {
  document.querySelectorAll('.card-link, .panel-link, #btn-view-all-history').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const text = btn.textContent.trim();

      if (text.includes('Ver todos') && !window.fcOpenViewModal) return;

      if (text.includes('Ver todos') && btn.id === 'btn-view-all-history') {
        // Modal: Histórico completo de previsões
        const historyList = btn.closest('.card')?.querySelector('ul') || btn.closest('.card')?.querySelector('[id$="-list"]');
        const items = historyList ? [...historyList.querySelectorAll('li')] : [];
        let html = '<div style="display:flex;flex-direction:column;gap:8px;">';
        items.forEach(li => { html += `<div style="padding:10px 12px;background:var(--surface);border:1px solid var(--ink-06);border-radius:8px;font-size:13px;">${li.innerHTML}</div>`; });
        html += '</div>';
        window.fcOpenViewModal('Histórico de Previsões', `${items.length} registros no total`, html);
      }
      else if (text.includes('Ver todos')) {
        // Modal: Cobertura crítica
        const panelSection = btn.closest('.panel-section');
        const alertItems = panelSection ? [...panelSection.querySelectorAll('.palert, .insuf-item, li')] : [];
        let html = '<div style="display:flex;flex-direction:column;gap:8px;">';
        alertItems.forEach(item => { html += `<div style="padding:10px 12px;background:var(--surface);border:1px solid var(--ink-06);border-radius:8px;font-size:13px;">${item.innerHTML}</div>`; });
        html += '</div>';
        window.fcOpenViewModal('Cobertura Crítica — Visão Completa', `${alertItems.length} itens com cobertura crítica`, html);
      }
    });
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initPrevisaoViewLinks);
} else {
  initPrevisaoViewLinks();
}
