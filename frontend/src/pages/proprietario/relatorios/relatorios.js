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

var API_BASE = (window.FarmaControlSettings && window.FarmaControlSettings.API_BASE) || 'http://localhost:5000';
var EASE = t => t < 0.5 ? 2*t*t : -1+(4-2*t)*t;

/* ══ CARREGAR KPIs DE RELATÓRIOS DO BANCO ══ */
async function loadRelatoriosKPIs() {
  if (!document.getElementById('kpi-receita')) return;
  /* Token de página — se mudou durante o await, silenciosamente aborta */
  const token = window.__fcPageToken;
  try {
    const [resEst, resVenc, resComp] = await Promise.all([
      fetch(`${API_BASE}/relatorios/estoque`).catch(() => ({ ok: false })),
      fetch(`${API_BASE}/relatorios/vencimentos`).catch(() => ({ ok: false })),
      fetch(`${API_BASE}/relatorios/compras`).catch(() => ({ ok: false })),
    ]);
    if (window.__fcPageToken !== token) return; /* navegação mudou de página */
    
    const dEst = resEst.ok ? await resEst.json() : { ok: false };
    const dVenc = resVenc.ok ? await resVenc.json() : { ok: false };
    const dComp = resComp.ok ? await resComp.json() : { ok: false };

    const kpis = {
      ...((dEst.ok  && dEst.kpis)  || {}),
      ...((dVenc.ok && dVenc.kpis) || {}),
      ...((dComp.ok && dComp.kpis) || {}),
    };

    const kpiTextMap = [
      { text: 'Total de Saídas',       key: 'total_saidas'        },
      { text: 'Valor em Estoque',      key: 'valor_estoque'       },
      { text: 'Itens Vencidos/Alerta', key: 'itens_alerta'        },
      { text: 'Giro de Estoque',       key: 'giro_estoque'        },
    ];

    document.querySelectorAll('.kpi-value[data-target]').forEach(el => {
      const card = el.closest('.kpi-card');
      if (!card) return;
      const cardText = card.querySelector('.kpi-label')?.textContent || '';
      for (const { text, key } of kpiTextMap) {
        if (cardText.includes(text) && kpis[key] !== undefined) {
          el.dataset.target = kpis[key];
          break;
        }
      }
    });
    initCounters();

    // Atualiza distribuição por categoria
    const catContainer = document.getElementById('category-chart');
    if (catContainer && dEst.ok && dEst.por_categoria && dEst.por_categoria.length > 0) {
      const maxVal = Math.max(...dEst.por_categoria.map(c => c.qtd_total || 0), 1);
      catContainer.innerHTML = dEst.por_categoria.map(c => {
        const pct = Math.round((c.qtd_total || 0) / maxVal * 100);
        return `<div class="cat-row" data-pct="${pct}">
          <div class="cat-label">${c.categoria || 'Sem categoria'}</div>
          <div class="cat-bar-wrap"><div class="cat-bar" style="--pct:${pct}%"></div></div>
          <div class="cat-val">${c.qtd_total || 0}</div>
        </div>`;
      }).join('');
    }

    // Atualiza Top Produtos
    const rankList = document.getElementById('rank-list');
    if (rankList && dEst.ok && dEst.top_produtos && dEst.top_produtos.length > 0) {
      const maxTop = Math.max(...dEst.top_produtos.map(p => p.quantidade || 0), 1);
      rankList.innerHTML = dEst.top_produtos.map((p, i) => {
        const w = (p.quantidade / maxTop * 100).toFixed(1);
        return `<li class="rank-item">
          <span class="rank-pos">${i+1}</span>
          <div class="rank-info">
            <span class="rank-name">${p.nome}</span>
            <div class="rank-bar-wrap"><div class="rank-bar" style="--w:${w}%"></div></div>
          </div>
          <span class="rank-val">${p.quantidade}</span>
          <span class="rank-trend neutral">—</span>
        </li>`;
      }).join('');
      document.getElementById('badge-top-count').textContent = `${dEst.top_produtos.length} itens`;
    }

  } catch (err) {
    console.error('Erro ao carregar KPIs de relatórios:', err);
  }
}

/* ══ CARREGAR MOVIMENTAÇÕES DO BANCO ══ */
var allMovs = [];
var movPage = 1;
var MOV_PAGE_SIZE = 10;

  /* loadMovimentacoesTable(): Carrega a tabela de movimentações com paginação e filtros. */
  async function loadMovimentacoesTable() {
  const tbody   = document.getElementById('mov-table-body');
  const badgeEl = document.getElementById('mov-count');
  if (!tbody) return;

  /* Token de página — se mudou durante o await, silenciosamente aborta */
  const token = window.__fcPageToken;
  try {
    const res    = await fetch(`${API_BASE}/movimentacoes-estoque`).catch(() => ({ ok: false }));
    if (window.__fcPageToken !== token) return; /* navegação mudou de página */
    if (!res.ok) return;
    const result = await res.json();
    if (!result.ok) return;

    allMovs = result.movimentacoes || [];
    movPage = 1;
    renderMovimentacoesPage();
    if (badgeEl) badgeEl.textContent = `${allMovs.length} registros`;
  } catch (err) {
    console.error('Erro ao carregar movimentações:', err);
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
  const tbody   = document.getElementById('mov-table-body');
  const countEl = document.getElementById('mov-filter-count');
  if (!tbody) return;

  const typeFilter = movFilterActive();
  const searchTerm = movSearchActive();

  const filtered = allMovs.filter(m => {
    const typeOk = typeFilter === 'all' || (m.tipo_movimentacao || 'saida') === typeFilter;
    const name = (m.produto_nome || '').toLowerCase();
    const nameOk = !searchTerm || name.includes(searchTerm);
    return typeOk && nameOk;
  });

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:40px;color:var(--ink-35)">Nenhum dado encontrado</td></tr>';
    if (countEl) countEl.textContent = 'Exibindo 0 de 0 registros';
    updateMovPagination(0);
    return;
  }

  const pages  = Math.max(1, Math.ceil(filtered.length / MOV_PAGE_SIZE));
  movPage = Math.min(movPage, pages);
  const slice = filtered.slice((movPage - 1) * MOV_PAGE_SIZE, movPage * MOV_PAGE_SIZE);

  tbody.innerHTML = slice.map(m => {
      const dataBr = m.data_movimentacao
        ? new Date(m.data_movimentacao).toLocaleDateString('pt-BR')
        : '—';
      const tipo = m.tipo_movimentacao || 'saida';
      const pillCls = tipo === 'entrada' ? 'in' : 'out';
      const pillLabel = tipo === 'entrada' ? 'Entrada' : 'Saída';
      const valorUnit = m.valor_unitario || 0;
      const valorTotal = (m.quantidade * valorUnit) || 0;

      return `<tr data-type="${tipo}">
        <td class="mono">${dataBr}</td>
        <td class="prod-cell"><span class="prod-name">${m.produto_nome || '—'}</span></td>
        <td><span class="cat-tag">${m.categoria || '—'}</span></td>
        <td class="mono">${m.lote || '—'}</td>
        <td class="c"><span class="pill-type ${pillCls}">${pillLabel}</span></td>
        <td class="r fw6">${m.quantidade}</td>
        <td class="r muted">R$ ${valorUnit.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</td>
        <td class="r fw6">R$ ${valorTotal.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</td>
        <td>${m.usuario_nome || '—'}</td>
      </tr>`;
    }).join('');

    const start = (movPage - 1) * MOV_PAGE_SIZE + 1;
    const end   = Math.min(movPage * MOV_PAGE_SIZE, filtered.length);
    if (countEl) countEl.textContent = `Exibindo ${start}–${end} de ${filtered.length} registros`;
    updateMovPagination(filtered.length);
}


  /* updateMovPagination(): Atualiza os controles de paginação conforme total de registros. */
  function updateMovPagination(total) {
  const pagination = document.querySelector('.pagination');
  if (!pagination) return;
  const pages = Math.max(1, Math.ceil(total / MOV_PAGE_SIZE));
  pagination.innerHTML = `
    <button class="pag-btn" id="pg-prev" ${movPage <= 1 ? 'disabled' : ''}>← Anterior</button>
    <span class="pag-num" style="font-size:11px;color:var(--ink-35);padding:0 6px">Página ${movPage} de ${pages}</span>
    <button class="pag-btn" id="pg-next" ${movPage >= pages ? 'disabled' : ''}>Próximo →</button>`;
  document.getElementById('pg-prev')?.addEventListener('click', () => { if (movPage > 1) { movPage--; renderMovimentacoesPage(); } });
  document.getElementById('pg-next')?.addEventListener('click', () => { if (movPage < pages) { movPage++; renderMovimentacoesPage(); } });
}

  /* goMovPage1(): Volta para a primeira página da tabela. */
  function goMovPage1() { movPage = 1; renderMovimentacoesPage(); }

/* ══ DATE ══ */
function initDate() {
  const el = document.getElementById('date-label');
  if (!el) return;
  const days   = ['Domingo','Segunda-feira','Terça-feira','Quarta-feira','Quinta-feira','Sexta-feira','Sábado'];
  const months = ['janeiro','fevereiro','março','abril','maio','junho','julho','agosto','setembro','outubro','novembro','dezembro'];
  const d = new Date();
  el.textContent = `${days[d.getDay()]}, ${d.getDate()} de ${months[d.getMonth()]} de ${d.getFullYear()}`;
}

/* ══ COUNTERS ══ */
function initCounters() {
  document.querySelectorAll('.kpi-value[data-target]').forEach(el => {
    const target     = +el.dataset.target;
    const isCurrency = el.classList.contains('kpi-currency');
    const isDecimal  = el.classList.contains('kpi-decimal');
    let done = false;

    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting && !done) {
        done = true; obs.disconnect();
        const t0 = performance.now();
        (function step(now) {
          const p   = Math.min((now - t0) / 900, 1);
          const val = EASE(p) * target;
          if (isCurrency) {
            el.textContent = 'R$ ' + val.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
          } else if (isDecimal) {
            el.textContent = val.toFixed(1);
          } else {
            el.textContent = Math.round(val).toLocaleString('pt-BR');
          }
          if (p < 1) requestAnimationFrame(step);
        })(t0);
      }
    }, { threshold: 0.1 });
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
      const labels = {
        month:   'Período atual: ' + new Date().toLocaleString('pt-BR', { month: 'long', year: 'numeric' }),
        quarter: 'Período atual: trimestre',
        year:    'Período atual: ano'
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
async function loadMonthlyData() {
  /* Token de página — se mudou durante o await, silenciosamente aborta */
  const token = window.__fcPageToken;
  try {
    const res = await fetch(`${API_BASE}/movimentacoes-estoque`).catch(() => ({ ok: false }));
    if (window.__fcPageToken !== token) return; /* navegação mudou de página */
    if (!res.ok) return;
    const result = await res.json();
    if (!result.ok) return;

    const movs = result.movimentacoes || [];
    const meses = {};
    movs.forEach(m => {
      const data = new Date(m.data_movimentacao);
      if (isNaN(data.getTime())) return;
      const key = `${data.getFullYear()}-${String(data.getMonth() + 1).padStart(2, '0')}`;
      if (!meses[key]) meses[key] = { saidas: 0, entradas: 0 };
      const qtd = parseInt(m.quantidade) || 0;
      if (m.tipo_movimentacao === 'saida') meses[key].saidas += qtd;
      else if (m.tipo_movimentacao === 'entrada') meses[key].entradas += qtd;
    });

    // Últimos 6 meses (inclui o mês atual)
    const labels = [];
    const now = new Date();
    for (let i = 5; i >= 0; i--) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      labels.push(key);
    }

    monthlyData.saidas = labels.map(k => ({
      label: k.split('-')[1],
      monthName: ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'][parseInt(k.split('-')[1]) - 1],
      value: (meses[k] || { saidas: 0 }).saidas
    }));
    monthlyData.entradas = labels.map(k => ({
      label: k.split('-')[1],
      monthName: ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'][parseInt(k.split('-')[1]) - 1],
      value: (meses[k] || { entradas: 0 }).entradas
    }));

    const totalSaidas = monthlyData.saidas.reduce((s, m) => s + m.value, 0);
    const badge = document.getElementById('badge-evolucao');
    if (badge) badge.textContent = totalSaidas > 0 ? `${totalSaidas.toLocaleString('pt-BR')} saídas` : 'Sem dados';

    renderMonthlyChart();
  } catch (err) {
    console.error('Erro ao carregar dados mensais:', err);
  }
}

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

  const maxVal = Math.max(...(mode === 'ambos'
    ? dataset.flatMap(d => [d.saidas, d.entradas])
    : dataset.map(d => d.value)), 1);

  // Rótulos do eixo Y
  const yLabels = document.querySelectorAll('.mc-y-labels span');
  if (yLabels.length === 5) {
    const steps = [maxVal, Math.round(maxVal * 0.75), Math.round(maxVal * 0.5), Math.round(maxVal * 0.25), 0];
    yLabels.forEach((el, i) => { el.textContent = steps[i] >= 1000 ? `${(steps[i] / 1000).toFixed(1)}k` : steps[i]; });
  }

  const currentMonth = String(new Date().getMonth() + 1).padStart(2, '0');
  const hasAnyData = mode === 'ambos'
    ? dataset.some(d => d.saidas > 0 || d.entradas > 0)
    : dataset.some(d => d.value > 0);

  if (dataset.length === 0 || !hasAnyData) {
    const label = mode === 'saidas' ? 'saídas' : mode === 'entradas' ? 'entradas' : 'movimentações';
    barsContainer.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--ink-35);font-size:12px">Nenhuma ' + label + ' registrada nos últimos 6 meses</div>';
    return;
  }

  barsContainer.innerHTML = dataset.map(d => {
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
  }).join('');
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
  searchInput?.addEventListener('input', () => {
    goMovPage1();
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
      produtosFull = data.produtos;
      const select = document.getElementById('lote-produto-id');
      if (select) {
        select.innerHTML = '<option value="">Selecione um produto...</option>' + 
          produtosFull.map(p => `<option value="${p.id}">${p.nome}${p.categoria_nome ? ' · ' + p.categoria_nome : ''}</option>`).join('');
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

  if (!produto_id || !lote || !quantidade || !data_validade) {
    toast('Preencha todos os campos obrigatórios', 'error');
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
        data_validade: data_validade,
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
    ...rows.map(r => r.map(v => `"${String(v ?? '').replace(/"/g, '""')}"`).join(CSV_SEP)),
  ];
  const csv = '\uFEFF' + lines.join(lineSep);
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

async function gerarRelatorioEstoque() {
  try {
    const res = await fetch(`${API_BASE}/estoque`).catch(() => ({ ok: false }));
    if (!res.ok) { toast('Servidor indisponível. Verifique o backend.', 'error'); return; }
    const data = await res.json();
    if (!data.ok) { toast(data.mensagem || 'Erro ao buscar estoque.', 'error'); return; }
    const rows = (data.estoque || []).map(e => [
      e.produto_nome || '—', e.lote || '—', e.categoria_nome || e.categoria || '—',
      e.quantidade ?? 0, e.data_validade ? new Date(e.data_validade).toLocaleDateString('pt-BR') : '—',
      e.fornecedor_nome || '—',
    ]);
    downloadFile('relatorio_estoque_atual.csv', rows, ['Medicamento', 'Lote', 'Categoria', 'Quantidade', 'Validade', 'Fornecedor']);
    toast('Relatório de estoque baixado.', 'ok');
  } catch {
    toast('Erro ao gerar o relatório de estoque.', 'error');
  }
}

async function gerarRelatorioSaidas() {
  try {
    const res = await fetch(`${API_BASE}/movimentacoes-estoque`).catch(() => ({ ok: false }));
    if (!res.ok) { toast('Servidor indisponível. Verifique o backend.', 'error'); return; }
    const data = await res.json();
    if (!data.ok) { toast(data.mensagem || 'Erro ao buscar movimentações.', 'error'); return; }
    const rows = (data.movimentacoes || [])
      .filter(m => (m.tipo_movimentacao || 'saida') === 'saida')
      .map(m => [
        m.data_movimentacao ? new Date(m.data_movimentacao).toLocaleDateString('pt-BR') : '—',
        m.produto_nome || '—', m.categoria || '—', m.lote || '—',
        m.quantidade ?? 0, m.valor_unitario ?? 0,
        ((m.quantidade || 0) * (m.valor_unitario || 0)).toFixed(2).replace('.', ','),
        m.usuario_nome || '—', m.observacao || '',
      ]);
    downloadFile('relatorio_saidas_periodo.csv', rows,
      ['Data', 'Medicamento', 'Categoria', 'Lote', 'Quantidade', 'Valor Unitário (R$)', 'Valor Total (R$)', 'Usuário', 'Observação']);
    toast('Relatório de saídas baixado.', 'ok');
  } catch {
    toast('Erro ao gerar o relatório de saídas.', 'error');
  }
}

async function gerarRelatorioVencimentos() {
  try {
    const res = await fetch(`${API_BASE}/estoque`).catch(() => ({ ok: false }));
    if (!res.ok) { toast('Servidor indisponível. Verifique o backend.', 'error'); return; }
    const data = await res.json();
    if (!data.ok) { toast(data.mensagem || 'Erro ao buscar estoque.', 'error'); return; }
    const hoje = new Date(); hoje.setHours(0,0,0,0);
    const rows = (data.estoque || [])
      .filter(e => e.data_validade)
      .map(e => {
        const d = new Date(e.data_validade);
        const diff = Math.ceil((d - hoje) / 86400000);
        let status = 'Regular';
        if (diff < 0) status = 'Vencido';
        else if (diff <= 30) status = 'Crítico';
        else if (diff <= 60) status = 'Atenção';
        return [
          e.produto_nome || '—', e.lote || '—', e.categoria_nome || e.categoria || '—',
          e.quantidade ?? 0,
          d.toLocaleDateString('pt-BR'),
          `${diff} dias`, status,
        ];
      })
      .sort((a, b) => new Date(`${a[4].split('/').reverse().join('-')}`) - new Date(`${b[4].split('/').reverse().join('-')}`));
    downloadFile('relatorio_vencimentos.csv', rows, ['Medicamento', 'Lote', 'Categoria', 'Quantidade', 'Validade', 'Prazo', 'Status']);
    toast('Relatório de vencimentos baixado.', 'ok');
  } catch {
    toast('Erro ao gerar o relatório de vencimentos.', 'error');
  }
}

async function gerarRelatorioFinanceiro() {
  try {
    const res = await fetch(`${API_BASE}/movimentacoes-estoque`).catch(() => ({ ok: false }));
    if (!res.ok) { toast('Servidor indisponível. Verifique o backend.', 'error'); return; }
    const data = await res.json();
    if (!data.ok) { toast(data.mensagem || 'Erro ao buscar movimentações.', 'error'); return; }
    const rows = (data.movimentacoes || []).map(m => {
      const tipo = (m.tipo_movimentacao || 'saida') === 'entrada' ? 'Entrada (compra)' : 'Saída';
      const valorTotal = ((m.quantidade || 0) * (m.valor_unitario || 0));
      return [
        m.data_movimentacao ? new Date(m.data_movimentacao).toLocaleDateString('pt-BR') : '—',
        tipo,
        m.produto_nome || '—', m.lote || '—', m.quantidade ?? 0,
        (m.valor_unitario ?? 0).toFixed(2).replace('.', ','),
        valorTotal.toFixed(2).replace('.', ','),
      ];
    });
    downloadFile('relatorio_financeiro.csv', rows,
      ['Data', 'Tipo', 'Medicamento', 'Lote', 'Quantidade', 'Valor Unitário (R$)', 'Valor Total (R$)']);
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
  document.getElementById('rpt-ia')?.addEventListener('click', () => toast('Relatório de Previsão IA em breve.', 'info'));
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
document.addEventListener('DOMContentLoaded', () => {
  initDate();
  initPeriodSelector();
  initChartTabs();
  initTableFilter();
  initPrintButton();
  
  // Carrega dados reais
  loadRelatoriosKPIs();
  loadMovimentacoesTable();
  loadMonthlyData();

  // Bind Novo Lote
  document.getElementById('btn-novo-lote')?.addEventListener('click', openLoteModal);
  document.getElementById('btn-lote-submit')?.addEventListener('click', handleLoteSubmit);

  // Bind Gerar Relatórios (sidebar)
  initGerarRelatorios();
});



/* ══ BOTÕES DE VISUALIZAÇÃO (abrem modal read-only) ══ */
function initRelatoriosViewLinks() {
  document.querySelectorAll('.card-link, .panel-link').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const text = btn.textContent.trim();

      if (text.includes('Ver detalhe')) {
        if (!window.fcOpenViewModal) return;
        // Abre modal com detalhe do gráfico de saídas por categoria
        const chartEl = document.getElementById('category-chart');
        const chartContent = chartEl ? chartEl.innerHTML : '<p>Nenhum dado disponível</p>';
        window.fcOpenViewModal('Saídas por Categoria — Detalhe', 'Distribuição de saídas por categoria no período selecionado', chartContent);
      }
      else if (text.includes('Ver relatório completo')) {
        if (!window.fcOpenViewModal) return;
        // Abre modal com o relatório completo de produtos
        const rankList = document.getElementById('rank-list');
        const items = rankList ? [...rankList.querySelectorAll('li')] : [];
        let html = '<div style="display:flex;flex-direction:column;gap:8px;">';
        items.forEach(li => { html += `<div style="padding:10px 12px;background:var(--surface);border:1px solid var(--ink-06);border-radius:8px;font-size:13px;">${li.innerHTML}</div>`; });
        html += '</div>';
        window.fcOpenViewModal('Relatório Completo — Top Produtos', `Total de ${items.length} itens no ranking`, html);
      }
    });
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initRelatoriosViewLinks);
} else {
  initRelatoriosViewLinks();
}
