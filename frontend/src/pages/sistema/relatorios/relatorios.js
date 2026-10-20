/* ══════════════════════════════════════════════════════════════════════
 * FARMAControl — RELATÓRIOS DE MOVIMENTAÇÃO (PROPRIETÁRIO)
 * ══════════════════════════════════════════════════════════════════════
 *
 * Relatórios detalhados de movimentações de estoque:
 * - KPIs: Total movimentações, entradas, saídas do período
 * - Tabela paginada de movimentações com filtros (data, tipo, categoria)
 * - Gráfico mensal: Entradas vs Saídas por mês
 * - Exportação CSV de movimentações
 *
 * Dados são carregados da API: GET /relatorios/*
 * ══════════════════════════════════════════════════════════════════════ */

/* Timers e listeners globais desta tela são descartados por page-lifecycle.js. */
// Guard de sessão e dados do usuário agora são gerenciados globalmente pelo global-settings.js e sidebar-init.js

'use strict';

var API_BASE =
  (window.FarmaControlSettings && window.FarmaControlSettings.API_BASE) || 'http://localhost:5000';
var EASE = t => (t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t);

/* ══ CARREGAR KPIs DE RELATÓRIOS DO BANCO ══ */
var currentPeriod = 'month';
var reportRequest = 0;
var reportInsightData = { categories: [], topProducts: [] };
function reportEscape(value) {
  return String(value ?? '').replace(
    /[&<>"']/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]
  );
}
async function loadRelatoriosKPIs() {
  const requestId = ++reportRequest;
  try {
    const res = await fetch(`${API_BASE}/relatorios/estoque?periodo=${currentPeriod}`);
    const data = await res.json();
    if (requestId !== reportRequest) return;
    if (!res.ok || !data.ok) throw new Error(data.mensagem || 'Erro ao carregar relatório');
    const keys = ['total_saidas', 'valor_estoque', 'itens_alerta', 'giro_estoque'];
    document.querySelectorAll('.kpi-value[data-target]').forEach((el, i) => {
      el.dataset.target = data.kpis[keys[i]] || 0;
    });
    initCounters();
    const categories = data.por_categoria || [];
    const top = data.top_produtos || [];
    reportInsightData = { categories, topProducts: top };
    renderCategoryInsight(categories);
    renderProductsInsight(top);
    document.getElementById('badge-top-count').textContent = `${top.length} itens`;
    const summary = data.resumo || {};
    const entries = [
      ['Total saídas', summary.saidas],
      ['Total entradas', summary.entradas],
      ['Valor dispensado (custo)', summary.valor_saidas, true],
      ['Valor reposto (custo)', summary.valor_entradas, true],
      ['Lotes zerados (atual)', summary.zerados],
      ['Lotes com descarte', summary.descartados],
      ['Dias com operação', summary.dias_operacao]
    ];
    document.getElementById('summary-list').innerHTML = entries
      .map(
        ([label, value, currency]) =>
          `<div class="summary-row"><span class="summary-label">${label}</span><span class="summary-val">${Number(value || 0).toLocaleString('pt-BR', currency ? { style: 'currency', currency: 'BRL' } : {})}</span></div>`
      )
      .join('');
    const periodLabel = { month: 'Mês atual', quarter: 'Trimestre atual', year: 'Ano atual' }[
      currentPeriod
    ];
    document.getElementById('badge-resumo-periodo').textContent = periodLabel;
    document.getElementById('badge-periodo-cat').textContent = periodLabel;
    const months = data.evolucao || [];
    const now = new Date();
    const start =
      currentPeriod === 'year'
        ? 0
        : currentPeriod === 'quarter'
          ? Math.floor(now.getMonth() / 3) * 3
          : now.getMonth();
    const series = [];
    for (let month = start; month <= now.getMonth(); month++) {
      const key = `${now.getFullYear()}-${String(month + 1).padStart(2, '0')}`;
      const row = months.find(m => m.mes === key) || {};
      series.push({
        label: String(month + 1).padStart(2, '0'),
        monthName: new Date(now.getFullYear(), month, 1).toLocaleDateString('pt-BR', {
          month: 'short'
        }),
        ...row
      });
    }
    monthlyData.saidas = series.map(m => ({ ...m, value: Number(m.saidas || 0) }));
    monthlyData.entradas = series.map(m => ({ ...m, value: Number(m.entradas || 0) }));
    document.getElementById('badge-evolucao').textContent =
      `${Number(summary.saidas || 0).toLocaleString('pt-BR')} saídas`;
    renderMonthlyChart();
  } catch (error) {
    if (requestId !== reportRequest || error.name === 'AbortError') return;
    document.querySelectorAll('.kpi-value').forEach(el => {
      el.textContent = '—';
    });
    document.getElementById('category-chart').innerHTML =
      '<p class="empty-state">Não foi possível carregar as categorias.</p>';
    document.getElementById('rank-list').innerHTML =
      '<li class="empty-state">Não foi possível carregar os produtos.</li>';
    document.getElementById('summary-list').innerHTML =
      '<p class="empty-state">Resumo indisponível. Tente atualizar.</p>';
    document.getElementById('mc-bars').innerHTML =
      '<p class="empty-state">Gráfico indisponível.</p>';
    toast('Não foi possível carregar o relatório. Tente atualizar.', 'error');
  }
}

function reportNumber(value) {
  return Number(value || 0).toLocaleString('pt-BR');
}

function renderCategoryInsight(categories) {
  const chart = document.getElementById('category-chart');
  if (!chart) return;
  const total = categories.reduce((sum, item) => sum + Number(item.qtd_total || 0), 0);
  const top = categories[0];
  const preview = categories.slice(0, 5);
  if (!categories.length) {
    chart.innerHTML = '<p class="empty-state">Nenhuma saída no período.</p>';
    return;
  }
  chart.innerHTML = `<div class="insight-summary"><div><span class="insight-eyebrow">Volume dispensado</span><strong>${reportNumber(total)}</strong><span class="insight-caption">unidades distribuídas em ${categories.length} categorias</span></div><div class="insight-callout"><span>Maior participação</span><strong>${reportNumber(top.qtd_total)}</strong><small>${reportEscape(top.categoria)}</small></div></div><div class="insight-list cat-insight-list">${preview
    .map((c, index) => {
      const qty = Number(c.qtd_total || 0);
      const share = total ? (qty / total) * 100 : 0;
      return `<div class="cat-row"><span class="insight-rank">${String(index + 1).padStart(2, '0')}</span><div class="cat-main"><div class="cat-row-head"><span class="cat-label" title="${reportEscape(c.categoria)}">${reportEscape(c.categoria)}</span><span class="cat-share">${share.toFixed(1).replace('.', ',')}%</span></div><div class="cat-bar-wrap"><div class="cat-bar" style="width:${share}%"></div></div></div><strong class="cat-val">${reportNumber(qty)}</strong></div>`;
    })
    .join(
      ''
    )}</div>${categories.length > preview.length ? `<span class="insight-footer">+ ${categories.length - preview.length} categorias no detalhamento</span>` : ''}`;
}

function renderProductsInsight(products) {
  const list = document.getElementById('rank-list');
  if (!list) return;
  const total = products.reduce((sum, item) => sum + Number(item.quantidade || 0), 0);
  const top = products[0];
  const preview = products.slice(0, 5);
  if (!products.length) {
    list.innerHTML = '<li class="empty-state">Nenhuma saída no período.</li>';
    return;
  }
  list.innerHTML = `<li class="products-leader"><span class="leader-medal">01</span><div class="leader-body"><span class="insight-eyebrow">Produto mais dispensado</span><strong title="${reportEscape(top.nome)}">${reportEscape(top.nome)}</strong><span>${reportNumber(top.quantidade)} unidades · ${total ? ((Number(top.quantidade) / total) * 100).toFixed(1).replace('.', ',') : 0}% do ranking</span></div></li><li class="products-divider"><span>Demais posições</span><span>Unidades</span></li>${preview
    .slice(1)
    .map((p, index) => {
      const qty = Number(p.quantidade || 0);
      const width = top.quantidade ? (qty / Number(top.quantidade)) * 100 : 0;
      return `<li class="rank-item"><span class="rank-pos">${String(index + 2).padStart(2, '0')}</span><div class="rank-info"><span class="rank-name" title="${reportEscape(p.nome)}">${reportEscape(p.nome)}</span><div class="rank-bar-wrap"><div class="rank-bar" style="width:${width}%"></div></div></div><strong class="rank-val">${reportNumber(qty)}</strong></li>`;
    })
    .join(
      ''
    )}${products.length > preview.length ? `<li class="insight-footer">+ ${products.length - preview.length} produtos no ranking completo</li>` : ''}`;
}

/* ══ CARREGAR MOVIMENTAÇÕES DO BANCO ══ */
var allMovs = [];
var movPage = 1;
var MOV_PAGE_SIZE = 10;

/* loadMovimentacoesTable(): Carrega a tabela de movimentações com paginação e filtros. */
var movTotal = 0;
var movRequest = 0;
async function loadMovimentacoesTable() {
  const requestId = ++movRequest;
  try {
    const params = new URLSearchParams({
      periodo: currentPeriod,
      limite: MOV_PAGE_SIZE,
      offset: (movPage - 1) * MOV_PAGE_SIZE
    });
    const type = movFilterActive();
    if (type !== 'all') params.set('tipo', type);
    if (movSearchActive()) params.set('busca', movSearchActive());
    const res = await fetch(`${API_BASE}/movimentacoes-estoque?${params}`);
    const data = await res.json();
    if (requestId !== movRequest) return;
    if (!res.ok || !data.ok) throw new Error(data.mensagem || 'Erro de leitura');
    allMovs = data.movimentacoes || [];
    movTotal = data.total ?? allMovs.length;
    document.getElementById('mov-count').textContent =
      `${movTotal.toLocaleString('pt-BR')} registros`;
    renderMovimentacoesPage();
  } catch (error) {
    if (requestId !== movRequest || error.name === 'AbortError') return;
    document.getElementById('mov-table-body').innerHTML =
      '<tr><td colspan="9">Não foi possível carregar as movimentações.</td></tr>';
    toast('Erro ao carregar movimentações.', 'error');
  }
}

/* movFilterActive(): Verifica se algum filtro está ativo na tabela. */
function movFilterActive() {
  const ftab = document.querySelector('.ftab[data-type].active');
  return ftab ? ftab.dataset.type : 'all';
}

/* movSearchActive(): Verifica se há busca textual ativa. */
function movSearchActive() {
  const input = document.getElementById('table-search');
  return input ? input.value.toLowerCase().trim() : '';
}

/* renderMovimentacoesPage(): Renderiza a página atual da tabela de movimentações. */
function renderMovimentacoesPage() {
  const tbody = document.getElementById('mov-table-body');
  const countEl = document.getElementById('mov-filter-count');
  if (!tbody) return;

  const slice = allMovs;
  if (!slice.length) {
    tbody.innerHTML =
      '<tr><td colspan="9" class="empty-state">Nenhuma movimentação neste período ou filtro.</td></tr>';
    countEl.textContent = 'Exibindo 0 de 0 registros';
    updateMovPagination(0);
    return;
  }
  tbody.innerHTML = slice
    .map(m => {
      const dataBr = m.data_movimentacao
        ? new Date(m.data_movimentacao).toLocaleDateString('pt-BR')
        : '—';
      const tipo = m.tipo_movimentacao || 'saida';
      const pillCls = tipo === 'entrada' ? 'in' : 'out';
      const pillLabel =
        { entrada: 'Entrada', saida: 'Saída', ajuste: 'Ajuste', transferencia: 'Transferência' }[
          tipo
        ] || tipo;
      const valorUnit = Number(m.valor_unitario) || 0;
      const valorTotal = m.quantidade * valorUnit || 0;

      return `<tr data-type="${tipo}">
        <td class="mono">${dataBr}</td>
        <td class="prod-cell"><span class="prod-name">${reportEscape(m.produto_nome || '—')}</span></td>
        <td><span class="cat-tag">${reportEscape(m.categoria || '—')}</span></td>
        <td class="mono">${reportEscape(m.lote || '—')}</td>
        <td class="c"><span class="pill-type ${pillCls}">${pillLabel}</span></td>
        <td class="r fw6">${m.quantidade}</td>
        <td class="r muted">R$ ${valorUnit.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</td>
        <td class="r fw6">R$ ${valorTotal.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</td>
        <td>${reportEscape(m.usuario_nome || '—')}</td>
      </tr>`;
    })
    .join('');

  const start = (movPage - 1) * MOV_PAGE_SIZE + 1;
  const end = Math.min(movPage * MOV_PAGE_SIZE, movTotal);
  if (countEl) countEl.textContent = `Exibindo ${start}–${end} de ${movTotal} registros`;
  updateMovPagination(movTotal);
}

/* updateMovPagination(): Atualiza os controles de paginação conforme total de registros. */
function updateMovPagination(total) {
  const pagination = document.querySelector('.pagination');
  if (!pagination) return;
  const pages = Math.max(1, Math.ceil(total / MOV_PAGE_SIZE));
  pagination.innerHTML = `
    <button class="pag-btn" id="pg-prev" ${movPage <= 1 ? 'disabled' : ''}>Anterior</button>
    <span class="pag-num" style="font-size:11px;color:var(--ink-35);padding:0 6px">Página ${movPage} de ${pages}</span>
    <button class="pag-btn" id="pg-next" ${movPage >= pages ? 'disabled' : ''}>Próximo</button>`;
  document.getElementById('pg-prev')?.addEventListener('click', () => {
    if (movPage > 1) {
      movPage--;
      loadMovimentacoesTable();
    }
  });
  document.getElementById('pg-next')?.addEventListener('click', () => {
    if (movPage < pages) {
      movPage++;
      loadMovimentacoesTable();
    }
  });
}

/* goMovPage1(): Volta para a primeira página da tabela. */
function goMovPage1() {
  movPage = 1;
  loadMovimentacoesTable();
}

/* ══ DATE ══ */

/* ══ COUNTERS ══ */
function initCounters() {
  document.querySelectorAll('.kpi-value[data-target]').forEach(el => {
    const target = +el.dataset.target;
    const isCurrency = el.classList.contains('kpi-currency');
    const isDecimal = el.classList.contains('kpi-decimal');
    let done = false;

    const obs = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting && !done) {
          done = true;
          obs.disconnect();
          const t0 = performance.now();
          (function step(now) {
            const p = Math.min((now - t0) / 900, 1);
            const val = EASE(p) * target;
            if (isCurrency) {
              el.textContent =
                'R$ ' +
                val.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            } else if (isDecimal) {
              el.textContent = val.toLocaleString('pt-BR', {
                minimumFractionDigits: 1,
                maximumFractionDigits: 1
              });
            } else {
              el.textContent = Math.round(val).toLocaleString('pt-BR');
            }
            if (p < 1) requestAnimationFrame(step);
          })(t0);
        }
      },
      { threshold: 0.1 }
    );
    obs.observe(el);
  });
}

/* ══ PERIOD SELECTOR ══ */
function initPeriodSelector() {
  document.querySelectorAll('.period-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const period = btn.dataset.period;
      currentPeriod = period;
      movPage = 1;
      loadRelatoriosKPIs();
      loadMovimentacoesTable();
      const labels = {
        month:
          'Período atual: ' +
          new Date().toLocaleString('pt-BR', { month: 'long', year: 'numeric' }),
        quarter: 'Período atual: trimestre',
        year: 'Período atual: ano'
      };
      const sub = document.getElementById('page-subtitle');
      if (sub) sub.textContent = `Central de análise e exportação de dados · ${labels[period]}`;
    });
  });
}

/* ══ CHART TABS ══ */
var monthlyData = { saidas: [], entradas: [] };
var currentChartMode = 'saidas';

/* initChartTabs(): Configura as abas do gráfico mensal (entradas/saídas/ambos). */
function initChartTabs() {
  document.querySelectorAll('.ftab[data-chart]').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.ftab[data-chart]').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      currentChartMode = tab.dataset.chart;
      renderMonthlyChart();
    });
  });
}

/* ══ GRÁFICO DE EVOLUÇÃO MENSAL (DADOS REAIS) ══ */
/* renderMonthlyChart(): Renderiza o gráfico de barras mensal (entradas vs saídas). */
function renderMonthlyChart() {
  const barsContainer = document.getElementById('mc-bars');
  if (!barsContainer) return;

  const mode = currentChartMode; // saidas | entradas | ambos
  let dataset = [];
  if (mode === 'saidas') dataset = monthlyData.saidas;
  else if (mode === 'entradas') dataset = monthlyData.entradas;
  else {
    // comparar: mescla saídas e entradas
    dataset = monthlyData.saidas.map((m, i) => ({
      ...m,
      saidas: m.value,
      entradas: monthlyData.entradas[i]?.value || 0
    }));
  }

  const maxVal = Math.max(
    ...(mode === 'ambos'
      ? dataset.flatMap(d => [d.saidas, d.entradas])
      : dataset.map(d => d.value)),
    1
  );

  // Rótulos do eixo Y
  const yLabels = document.querySelectorAll('.mc-y-labels span');
  if (yLabels.length === 5) {
    const steps = [
      maxVal,
      Math.round(maxVal * 0.75),
      Math.round(maxVal * 0.5),
      Math.round(maxVal * 0.25),
      0
    ];
    yLabels.forEach((el, i) => {
      el.textContent = steps[i] >= 1000 ? `${(steps[i] / 1000).toFixed(1)}k` : steps[i];
    });
  }

  const currentMonth = String(new Date().getMonth() + 1).padStart(2, '0');
  const hasAnyData =
    mode === 'ambos'
      ? dataset.some(d => d.saidas > 0 || d.entradas > 0)
      : dataset.some(d => d.value > 0);

  if (dataset.length === 0 || !hasAnyData) {
    const label = mode === 'saidas' ? 'saídas' : mode === 'entradas' ? 'entradas' : 'movimentações';
    barsContainer.innerHTML =
      '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--ink-35);font-size:12px">Nenhuma ' +
      label +
      ' registrada no período selecionado</div>';
    return;
  }

  barsContainer.innerHTML = dataset
    .map(d => {
      if (mode === 'ambos') {
        const hSaidas = Math.max((d.saidas / maxVal) * 100, d.saidas > 0 ? 4 : 0);
        const hEntradas = Math.max((d.entradas / maxVal) * 100, d.entradas > 0 ? 4 : 0);
        return `<div class="mc-col${d.label === currentMonth ? ' today' : ''}">
        <div class="mc-bar-group">
          <div class="mc-bar saidas" style="height:${hSaidas}%"><span class="mc-tip">Saídas: ${d.saidas}</span></div>
          <div class="mc-bar entradas" style="height:${hEntradas}%"><span class="mc-tip">Entradas: ${d.entradas}</span></div>
        </div>
        <span class="mc-label">${d.monthName}</span>
      </div>`;
      }
      const h = Math.max((d.value / maxVal) * 100, d.value > 0 ? 4 : 0);
      return `<div class="mc-col${d.label === currentMonth ? ' today' : ''}">
      <div class="mc-bar-group">
        <div class="mc-bar ${mode}" style="height:${h}%"><span class="mc-tip">${mode === 'saidas' ? 'Saídas' : 'Entradas'}: ${d.value}</span></div>
      </div>
      <span class="mc-label">${d.monthName}</span>
    </div>`;
    })
    .join('');
}

/* ══ TABLE FILTER ══ */
function initTableFilter() {
  document.querySelectorAll('.ftab[data-type]').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.ftab[data-type]').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      goMovPage1();
    });
  });

  const searchInput = document.getElementById('table-search');
  let searchTimer;
  searchInput?.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = __fcSetTimeout(goMovPage1, 200);
  });
}

/* ══ TOAST — centralizado no global-settings.js ══ */
function toast(msg, type = 'info') {
  if (window.FarmaControlSettings && typeof window.FarmaControlSettings.showToast === 'function') {
    window.FarmaControlSettings.showToast(
      msg,
      type === 'ok' || type === 'success' ? 'success' : type === 'error' ? 'error' : type
    );
  }
}

/* ══ MODAL NOVO LOTE ══ */
var produtosFull = [];

/* fetchProdutos(): Busca a lista de produtos para os modais. */
async function fetchProdutos() {
  /* Token de página — se mudou durante o await, silenciosamente aborta */
  const token = window.__fcPageToken;
  try {
    const res = await fetch(`${API_BASE}/produtos`);
    if (window.__fcPageToken !== token) return; /* navegação mudou de página */
    const data = await res.json();
    if (data.ok) {
      produtosFull = [...data.produtos].sort((a, b) =>
        String(a.nome || a.produto_nome || '').localeCompare(
          String(b.nome || b.produto_nome || ''),
          'pt-BR',
          { sensitivity: 'base' }
        )
      );
      const select = document.getElementById('lote-produto-id');
      if (select) {
        select.innerHTML =
          '<option value="">Selecione um produto...</option>' +
          produtosFull
            .map(
              p =>
                `<option value="${p.id}">${p.nome}${p.categoria_nome ? ' · ' + p.categoria_nome : ''}</option>`
            )
            .join('');
      }
    }
  } catch (err) {
    console.error('Erro ao buscar produtos:', err);
  }
}

/* openLoteModal(): Abre o modal de registro de movimentação por lote. */
function openLoteModal() {
  document.getElementById('modal-lote').classList.add('open');
  fetchProdutos();
}

/* closeLoteModal(): Fecha o modal de lote. */
function closeLoteModal() {
  document.getElementById('modal-lote').classList.remove('open');
}

/* handleLoteSubmit(): Processa o envio do formulário de movimentação por lote. */
async function handleLoteSubmit() {
  const produto_id = document.getElementById('lote-produto-id').value;
  const lote = document.getElementById('lote-numero').value;
  const quantidade = document.getElementById('lote-quantidade').value;
  const data_validade = document.getElementById('lote-validade').value;
  const preco_compra = document.getElementById('lote-preco').value;

  const produto = produtosFull.find(p => Number(p.id) === Number(produto_id));
  if (!produto_id || !quantidade || (produto?.exige_validade && !data_validade)) {
    toast('Informe produto, quantidade e validade quando exigida pelo cadastro.', 'error');
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/estoque`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        produto_id: parseInt(produto_id),
        lote: lote,
        quantidade: parseInt(quantidade),
        data_validade: data_validade || null,
        preco_compra: parseFloat(preco_compra) || 0
      })
    });

    const data = await res.json();
    if (data.ok) {
      toast('Novo lote cadastrado com sucesso!', 'success');
      closeLoteModal();
      loadRelatoriosKPIs();
      loadMovimentacoesTable();
    } else {
      toast(data.mensagem || 'Erro ao cadastrar lote', 'error');
    }
  } catch (err) {
    toast('Erro de conexão ao cadastrar lote', 'error');
  }
}

/* ══ GERAR RELATÓRIOS (SIDEBAR) ══ */
var CSV_SEP = ';';

/* downloadFile(): Gera e baixa um arquivo CSV com os dados da tabela. */
function downloadFile(filename, rows, headers) {
  const lineSep = '\r\n';
  const lines = [
    headers.map(h => `"${h}"`).join(CSV_SEP),
    ...rows.map(r => r.map(v => `"${String(v ?? '').replace(/"/g, '""')}"`).join(CSV_SEP))
  ];
  const csv = '\uFEFF' + lines.join(lineSep);
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
  try {
    const entries = JSON.parse(sessionStorage.getItem('fc_report_exports') || '[]');
    entries.unshift({ filename, count: rows.length, at: new Date().toISOString() });
    sessionStorage.setItem('fc_report_exports', JSON.stringify(entries.slice(0, 8)));
  } catch (_) {
    /* O download continua disponível sem armazenamento local. */
  }
  renderExportHistory();
}

async function gerarRelatorioEstoque() {
  try {
    const res = await fetch(`${API_BASE}/estoque`).catch(() => ({ ok: false }));
    if (!res.ok) {
      toast('Servidor indisponível. Verifique o backend.', 'error');
      return;
    }
    const data = await res.json();
    if (!data.ok) {
      toast(data.mensagem || 'Erro ao buscar estoque.', 'error');
      return;
    }
    const rows = (data.estoque || []).map(e => [
      e.produto_nome || '—',
      e.lote || '—',
      e.categoria_nome || e.categoria || '—',
      e.quantidade ?? 0,
      e.data_validade ? new Date(e.data_validade).toLocaleDateString('pt-BR') : '—',
      e.fornecedor_nome || '—'
    ]);
    downloadFile('relatorio_estoque_atual.csv', rows, [
      'Produto',
      'Lote',
      'Categoria',
      'Quantidade',
      'Validade',
      'Fornecedor'
    ]);
    toast('Relatório de estoque baixado.', 'ok');
  } catch {
    toast('Erro ao gerar o relatório de estoque.', 'error');
  }
}

async function gerarRelatorioSaidas() {
  try {
    const res = await fetchAllReportMovements();
    if (!res.ok) {
      toast('Servidor indisponível. Verifique o backend.', 'error');
      return;
    }
    const data = await res.json();
    if (!data.ok) {
      toast(data.mensagem || 'Erro ao buscar movimentações.', 'error');
      return;
    }
    const rows = (data.movimentacoes || [])
      .filter(m => (m.tipo_movimentacao || 'saida') === 'saida')
      .map(m => [
        m.data_movimentacao ? new Date(m.data_movimentacao).toLocaleDateString('pt-BR') : '—',
        m.produto_nome || '—',
        m.categoria || '—',
        m.lote || '—',
        m.quantidade ?? 0,
        m.valor_unitario ?? 0,
        ((m.quantidade || 0) * (m.valor_unitario || 0)).toFixed(2).replace('.', ','),
        m.usuario_nome || '—',
        m.observacao || ''
      ]);
    downloadFile('relatorio_saidas_periodo.csv', rows, [
      'Data',
      'Produto',
      'Categoria',
      'Lote',
      'Quantidade',
      'Valor Unitário (R$)',
      'Valor Total (R$)',
      'Usuário',
      'Observação'
    ]);
    toast('Relatório de saídas baixado.', 'ok');
  } catch {
    toast('Erro ao gerar o relatório de saídas.', 'error');
  }
}

async function gerarRelatorioVencimentos() {
  try {
    const res = await fetch(`${API_BASE}/estoque`).catch(() => ({ ok: false }));
    if (!res.ok) {
      toast('Servidor indisponível. Verifique o backend.', 'error');
      return;
    }
    const data = await res.json();
    if (!data.ok) {
      toast(data.mensagem || 'Erro ao buscar estoque.', 'error');
      return;
    }
    const hoje = new Date();
    hoje.setHours(0, 0, 0, 0);
    const rows = (data.estoque || [])
      .filter(e => e.data_validade)
      .map(e => {
        const d = new Date(e.data_validade.slice(0, 10) + 'T00:00:00');
        const diff = Math.ceil((d - hoje) / 86400000);
        let status = 'Regular';
        if (diff < 0) status = 'Vencido';
        else if (diff <= 30) status = 'Crítico';
        else if (diff <= 60) status = 'Atenção';
        return [
          e.produto_nome || '—',
          e.lote || '—',
          e.categoria_nome || e.categoria || '—',
          e.quantidade ?? 0,
          d.toLocaleDateString('pt-BR'),
          `${diff} dias`,
          status
        ];
      })
      .sort(
        (a, b) =>
          new Date(`${a[4].split('/').reverse().join('-')}`) -
          new Date(`${b[4].split('/').reverse().join('-')}`)
      );
    downloadFile('relatorio_vencimentos.csv', rows, [
      'Produto',
      'Lote',
      'Categoria',
      'Quantidade',
      'Validade',
      'Prazo',
      'Status'
    ]);
    toast('Relatório de vencimentos baixado.', 'ok');
  } catch {
    toast('Erro ao gerar o relatório de vencimentos.', 'error');
  }
}

async function gerarRelatorioFinanceiro() {
  try {
    const res = await fetchAllReportMovements();
    if (!res.ok) {
      toast('Servidor indisponível. Verifique o backend.', 'error');
      return;
    }
    const data = await res.json();
    if (!data.ok) {
      toast(data.mensagem || 'Erro ao buscar movimentações.', 'error');
      return;
    }
    const rows = (data.movimentacoes || []).map(m => {
      const tipo = (m.tipo_movimentacao || 'saida') === 'entrada' ? 'Entrada (compra)' : 'Saída';
      const valorTotal = (m.quantidade || 0) * (m.valor_unitario || 0);
      return [
        m.data_movimentacao ? new Date(m.data_movimentacao).toLocaleDateString('pt-BR') : '—',
        tipo,
        m.produto_nome || '—',
        m.lote || '—',
        m.quantidade ?? 0,
        Number(m.valor_unitario ?? 0)
          .toFixed(2)
          .replace('.', ','),
        valorTotal.toFixed(2).replace('.', ',')
      ];
    });
    downloadFile('relatorio_financeiro.csv', rows, [
      'Data',
      'Tipo',
      'Produto',
      'Lote',
      'Quantidade',
      'Valor Unitário (R$)',
      'Valor Total (R$)'
    ]);
    toast('Relatório financeiro baixado.', 'ok');
  } catch {
    toast('Erro ao gerar o relatório financeiro.', 'error');
  }
}

function initGerarRelatorios() {
  const bindDl = (itemId, fn) => {
    const item = document.getElementById(itemId);
    if (!item) return;
    item.addEventListener('click', e => {
      const dl = item.querySelector('.report-dl');
      if (dl && !dl.classList.contains('downloading')) {
        dl.classList.add('downloading');
        setTimeout(() => dl.classList.remove('downloading'), 1200);
      }
      fn(e);
    });
  };
  bindDl('rpt-estoque', gerarRelatorioEstoque);
  bindDl('rpt-saidas', gerarRelatorioSaidas);
  bindDl('rpt-venc', gerarRelatorioVencimentos);
  bindDl('rpt-fin', gerarRelatorioFinanceiro);
}

/* ══ IMPRESSÃO ══ */
function initPrintButton() {
  const btn = document.getElementById('btn-print');
  if (!btn || btn.dataset.printBound === 'true') return;
  btn.dataset.printBound = 'true';
  btn.addEventListener('click', () => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = '';
    window.print();
    document.body.style.overflow = previousOverflow;
  });
}

/* ══ INIT ══ */
function initRelatoriosPage() {
  initPeriodSelector();
  initChartTabs();
  initTableFilter();
  initPrintButton();

  // Carrega dados reais
  loadRelatoriosKPIs();
  loadMovimentacoesTable();
  renderExportHistory();
  document.getElementById('btn-refresh')?.addEventListener('click', () => {
    loadRelatoriosKPIs();
    loadMovimentacoesTable();
  });
  document.getElementById('btn-export')?.addEventListener('click', gerarRelatorioSaidas);

  // Bind Novo Lote
  document.getElementById('btn-novo-lote')?.addEventListener('click', openLoteModal);
  document.getElementById('btn-lote-submit')?.addEventListener('click', handleLoteSubmit);

  // Bind Gerar Relatórios (sidebar)
  initGerarRelatorios();
}
if (document.readyState === 'loading')
  window.fcPageListen(document, 'DOMContentLoaded', initRelatoriosPage, { once: true });
else initRelatoriosPage();

/* ══ BOTÕES DE VISUALIZAÇÃO (abrem modal read-only) ══ */
function initRelatoriosViewLinks() {
  document.querySelectorAll('[data-report-view]').forEach(btn => {
    btn.addEventListener('click', e => {
      e.preventDefault();
      if (!window.fcOpenViewModal) return;
      const isCategory = btn.dataset.reportView === 'categories';
      const items = isCategory ? reportInsightData.categories : reportInsightData.topProducts;
      const total = items.reduce(
        (sum, item) => sum + Number(isCategory ? item.qtd_total : item.quantidade || 0),
        0
      );
      const rows =
        items
          .map((item, index) => {
            const qty = Number(isCategory ? item.qtd_total : item.quantidade || 0);
            const name = isCategory ? item.categoria : item.nome;
            const share = total ? (qty / total) * 100 : 0;
            return `<div class="report-modal-row"><span class="report-modal-rank">${String(index + 1).padStart(2, '0')}</span><div class="report-modal-main"><div><strong>${reportEscape(name)}</strong><span>${share.toFixed(1).replace('.', ',')}% do total</span></div><div class="report-modal-track"><i style="width:${share}%"></i></div></div><strong class="report-modal-value">${reportNumber(qty)}</strong></div>`;
          })
          .join('') || '<p class="empty-state">Nenhum dado disponível para este período.</p>';
      const kind = isCategory ? 'categorias' : 'produtos';
      const title = isCategory ? 'Saídas por categoria' : 'Ranking de produtos dispensados';
      const subtitle = `${reportNumber(total)} unidades · ${items.length} ${kind} no período selecionado`;
      window.fcOpenViewModal(
        title,
        subtitle,
        `<div class="report-modal-summary"><span>Total analisado</span><strong>${reportNumber(total)} <small>unidades</small></strong></div><div class="report-modal-list">${rows}</div>`
      );
    });
  });
}

if (document.readyState === 'loading') {
  window.fcPageListen(document, 'DOMContentLoaded', initRelatoriosViewLinks, { once: true });
} else {
  initRelatoriosViewLinks();
}

async function fetchAllReportMovements() {
  const period = currentPeriod;
  const rows = [];
  let total = Infinity;
  while (rows.length < total) {
    const res = await fetch(
      `${API_BASE}/movimentacoes-estoque?periodo=${period}&limite=1000&offset=${rows.length}`
    );
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.mensagem || 'Falha na exportação');
    const batch = data.movimentacoes || [];
    rows.push(...batch);
    total = data.total ?? rows.length;
    if (!batch.length) break;
  }
  return { ok: true, json: async () => ({ ok: true, movimentacoes: rows }) };
}
function renderExportHistory() {
  const container = document.getElementById('export-history');
  if (!container) return;
  let entries = [];
  try {
    entries = JSON.parse(sessionStorage.getItem('fc_report_exports') || '[]');
  } catch (_) {}
  container.innerHTML =
    entries
      .map(
        e =>
          `<div class="exp-hist-item"><div class="exp-hist-body"><div class="exp-hist-name">${reportEscape(e.filename)}</div><div class="exp-hist-meta">${Number(e.count)} registros · ${new Date(e.at).toLocaleString('pt-BR')}</div></div></div>`
      )
      .join('') || '<p class="empty-state">As exportações desta sessão aparecerão aqui.</p>';
}
