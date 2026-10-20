/* ══════════════════════════════════════════════════════════════════════
 * FARMAControl — GESTÃO DE COMPRAS (PROPRIETÁRIO)
 * ══════════════════════════════════════════════════════════════════════
 *
 * Gerencia pedidos de compra para fornecedores:
 * - Tabela de pedidos com status (pendente, aprovado, recebido, cancelado)
 * - Modal de nova compra (selecionar produtos, quantidades, fornecedor)
 * - Histórico de compras com filtros
 * - Exportação CSV de pedidos e histórico
 *
 * Dados são carregados da API: GET/POST /compras/*
 * ══════════════════════════════════════════════════════════════════════ */

/* Timers e listeners globais desta tela são descartados por page-lifecycle.js. */
// Guard de sessão e dados do usuário agora são gerenciados globalmente pelo global-settings.js e sidebar-init.js

'use strict';

var API_BASE = window.FarmaControlSettings
  ? window.FarmaControlSettings.API_BASE
  : 'http://localhost:5000';
var EASE = t => (t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t);

/* ══ CARREGAR KPIs E GRÁFICOS DE COMPRAS DO BANCO ══ */
async function loadComprasStats() {
  /* Token de página — se mudou durante o await, silenciosamente aborta */
  const token = window.__fcPageToken;
  const requestedPeriod = purchasePeriod;
  try {
    const res = await fetch(`${API_BASE}/relatorios/compras?periodo=${purchasePeriod}`);
    if (window.__fcPageToken !== token || requestedPeriod !== purchasePeriod)
      return; /* navegação mudou de página */
    const result = await res.json();
    if (!result.ok) return;

    const k = result.kpis || {};

    // 1. Atualiza os KPIs
    const kpiTextMap = [
      { text: 'Total de Pedidos', key: 'total_pedidos' },
      { text: 'Valor Total Comprado', key: 'valor_comprado' },
      { text: 'Pedidos Pendentes', key: 'pedidos_pendentes' },
      { text: 'Fornecedores Ativos', key: 'fornecedores_ativos' }
    ];
    document.querySelectorAll('.kpi-value[data-target]').forEach(el => {
      const card = el.closest('.kpi-card');
      if (!card) return;
      const cardText = card.textContent;
      for (const { text, key } of kpiTextMap) {
        if (cardText.includes(text) && k[key] !== undefined) {
          el.dataset.target = k[key];
          break;
        }
      }
    });
    initCounters();

    // 2. Renderiza Compras por Categoria
    const catContainer = document.getElementById('category-chart');
    if (catContainer && result.categorias) {
      if (result.categorias.length === 0) {
        catContainer.innerHTML =
          '<div style="text-align:center;padding:20px;color:rgba(13,21,16,0.4);font-size:12px">Nenhum dado de categoria.</div>';
      } else {
        const categorias = result.categorias.map(c => ({ ...c, valor: Number(c.valor) || 0 }));
        const maxVal = Math.max(...categorias.map(c => c.valor), 1);
        catContainer.innerHTML = categorias
          .map(c => {
            const pct = Math.round((c.valor / maxVal) * 100);
            return `
            <div class="cat-row" data-pct="${pct}">
              <div class="cat-label" title="${compraEscape(c.categoria)}">${c.categoria || 'Sem categoria'}</div>
              <div class="cat-bar-wrap"><div class="cat-bar" style="--pct:${pct}%"></div></div>
              <div class="cat-val">R$ ${c.valor.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
            </div>`;
          })
          .join('');
      }
    }

    // 3. Renderiza Top Fornecedores
    const rankList = document.getElementById('rank-list');
    if (rankList && result.fornecedores) {
      if (result.fornecedores.length === 0) {
        rankList.innerHTML =
          '<li style="text-align:center;padding:20px;color:rgba(13,21,16,0.4);font-size:12px">Nenhum fornecedor registrado.</li>';
      } else {
        supplierRows = result.fornecedores.map(f => ({
          ...f,
          valor_total: Number(f.valor_total) || 0,
          total_pedidos: Number(f.total_pedidos) || 0
        }));
        rankList.innerHTML = supplierMarkup(supplierRows.slice(0, 5));
      }
    }

    // 4. Renderiza Resumo do Período (Sidebar)
    const summaryList = document.getElementById('summary-list');
    if (summaryList && k) {
      const totalPedidos = Number(k.total_pedidos) || 0;
      const valorComprado = Number(k.valor_comprado) || 0;
      const pendentes = Number(k.pedidos_pendentes) || 0;
      const fornecedoresAtivos = Number(k.fornecedores_ativos) || 0;
      const ticketMedio = totalPedidos > 0 ? valorComprado / totalPedidos : 0;
      summaryList.innerHTML = `
        <div class="summary-row">
          <span class="summary-label">Total de pedidos</span>
          <span class="summary-val">${totalPedidos} pedidos</span>
        </div>
        <div class="summary-row">
          <span class="summary-label">Pedidos pendentes</span>
          <span class="summary-val rv">${pendentes} pedidos</span>
        </div>
        <div class="summary-row">
          <span class="summary-label">Valor total comprado</span>
          <span class="summary-val">R$ ${valorComprado.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
        </div>
        <div class="summary-row">
          <span class="summary-label">Ticket médio</span>
          <span class="summary-val">R$ ${ticketMedio.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
        </div>
        <div class="summary-row">
          <span class="summary-label">Fornecedores ativos</span>
          <span class="summary-val">${fornecedoresAtivos} fornecedores</span>
        </div>
      `;
    }

    chartMonths = result.evolucao || [];
    renderChartMode(document.querySelector('.ftab[data-chart].active')?.dataset.chart || 'saidas');
  } catch (err) {
    console.error('Erro ao carregar KPIs de compras:', err);
    document.getElementById('category-chart')?.replaceChildren(
      Object.assign(document.createElement('div'), {
        className: 'empty-state',
        textContent: 'Não foi possível carregar as categorias.'
      })
    );
    document.getElementById('rank-list')?.replaceChildren(
      Object.assign(document.createElement('li'), {
        className: 'empty-state',
        textContent: 'Não foi possível carregar os fornecedores.'
      })
    );
    document.getElementById('mc-bars')?.replaceChildren(
      Object.assign(document.createElement('div'), {
        className: 'chart-empty',
        textContent: 'Não foi possível carregar a evolução mensal.'
      })
    );
  }
}

/* ══ CARREGAR TABELA DE COMPRAS DO BANCO ══ */
async function loadComprasTable() {
  const tbody = document.getElementById('mov-table-body');
  const countEl = document.getElementById('mov-filter-count');
  if (!tbody) return;

  /* Token de página — se mudou durante o await, silenciosamente aborta */
  const token = window.__fcPageToken;
  try {
    const res = await fetch(`${API_BASE}/compras`);
    if (window.__fcPageToken !== token) return; /* navegação mudou de página */
    const result = await res.json();
    if (!result.ok) return;

    const compras = result.compras || [];
    window.__allCompras = compras;
    updatePendentesBadge();
    renderPurchases();
  } catch (err) {
    console.error('Erro ao carregar tabela de compras:', err);
  }
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
                val.toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
            } else if (isDecimal) {
              el.textContent = val.toFixed(1);
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
  const months = [
    'janeiro',
    'fevereiro',
    'março',
    'abril',
    'maio',
    'junho',
    'julho',
    'agosto',
    'setembro',
    'outubro',
    'novembro',
    'dezembro'
  ];
  const now = new Date();
  const currentYear = now.getFullYear();
  const monthLabel = () => `Período atual: ${months[now.getMonth()]} ${currentYear}`;
  const quarterLabel = () =>
    `Período atual: ${Math.ceil((now.getMonth() + 1) / 3)}º trimestre ${currentYear}`;
  const yearLabel = () => `Período atual: ${currentYear}`;

  document.querySelectorAll('.period-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const labels = { month: monthLabel(), quarter: quarterLabel(), year: yearLabel() };
      const sub = document.getElementById('page-subtitle');
      if (sub)
        sub.textContent = `Gestão de pedidos e fornecedores · ${labels[btn.dataset.period] || monthLabel()}`;
      purchasePeriod = btn.dataset.period;
      purchasePage = 1;
      loadComprasStats();
      renderPurchases();
    });
  });
}

/* ══ CHART TABS ══ */
var purchasePeriod = 'month';
var purchasePage = 1;
var supplierRows = [];
var chartMonths = [];
function renderChartMode(mode) {
  const container = document.getElementById('mc-bars');
  if (!container) return;
  const maxValue = Math.max(...chartMonths.map(m => Number(m.valor)), 1);
  const maxCount = Math.max(...chartMonths.map(m => Number(m.total)), 1);
  const max = mode === 'entradas' ? maxCount : maxValue;
  const labels = document.querySelectorAll('.mc-y-labels span');
  labels.forEach((el, i) => {
    const ratio = 1 - i / (labels.length - 1);
    el.textContent =
      mode === 'ambos'
        ? `${Math.round(ratio * 100)}%`
        : Math.round(ratio * max).toLocaleString('pt-BR');
  });
  container.innerHTML =
    chartMonths
      .map(m => {
        const [year, month] = m.mes.split('-').map(Number);
        const name = new Date(year, month - 1, 1).toLocaleDateString('pt-BR', { month: 'short' });
        const valueBar = `<div class="mc-bar saidas" style="height:${(Number(m.valor) / maxValue) * 100}%"><span class="mc-tip">${Number(m.valor).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</span></div>`;
        const countBar = `<div class="mc-bar entradas" style="height:${(Number(m.total) / maxCount) * 100}%"><span class="mc-tip">${m.total} pedidos</span></div>`;
        return `<div class="mc-col"><div class="mc-bar-group">${mode === 'ambos' ? valueBar + countBar : mode === 'entradas' ? countBar : valueBar}</div><span class="mc-label">${name}</span></div>`;
      })
      .join('') || '<div class="chart-empty">Nenhuma compra registrada no período.</div>';
  container.title =
    mode === 'ambos'
      ? 'Cada série é uma porcentagem de seu maior valor no período. Verde: valor; verde claro: pedidos.'
      : '';
}

function initChartTabs() {
  document.querySelectorAll('.ftab[data-chart]').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.ftab[data-chart]').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      renderChartMode(tab.dataset.chart);
    });
  });
}

/* ══ TABLE FILTER ══ */
function initTableFilter() {
  document.querySelectorAll('.ftab[data-type]').forEach(tab =>
    tab.addEventListener('click', () => {
      document.querySelectorAll('.ftab[data-type]').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      purchasePage = 1;
      renderPurchases();
    })
  );
  document.getElementById('table-search')?.addEventListener('input', () => {
    purchasePage = 1;
    renderPurchases();
  });
  document.getElementById('purchase-prev')?.addEventListener('click', () => {
    if (purchasePage > 1) {
      purchasePage--;
      renderPurchases();
    }
  });
  document.getElementById('purchase-next')?.addEventListener('click', () => {
    purchasePage++;
    renderPurchases();
  });
}

/* ══ ACTION BUTTONS ══ */
function updatePendentesBadge() {
  const pendentes = (window.__allCompras || []).filter(
    c => (c.status || 'pendente') === 'pendente'
  );
  const desc = document.querySelector('#rpt-venc .report-desc');
  if (desc) {
    desc.textContent = `${pendentes.length} aguardando confirmação`;
  }
}

function initReportButtons() {
  // 1. Novo Pedido → abre o modal Nova Compra
  document.getElementById('rpt-estoque')?.addEventListener('click', () => {
    openModalNovaCompra();
  });

  // 2. Agendar Entrega → modal para definir a data de recebimento do pedido pendente
  document.getElementById('rpt-saidas')?.addEventListener('click', () => {
    openModalAgendarEntrega();
  });

  // 3. Pedidos Pendentes → filtra a tabela pelos pedidos pendentes usando o mesmo mecanismo das tabs
  document.getElementById('rpt-venc')?.addEventListener('click', () => {
    let pendingTab = document.querySelector('.ftab[data-type="pendente"]');
    if (!pendingTab) return;
    document.querySelectorAll('.ftab[data-type]').forEach(t => t.classList.remove('active'));
    pendingTab.classList.add('active');
    purchasePage = 1;
    renderPurchases();
    toast('Mostrando pedidos pendentes…', 'info');
  });

  // 4. Relatório de Compras → exporta o histórico do período em CSV
  document.getElementById('rpt-fin')?.addEventListener('click', () => {
    exportComprasCSV();
  });

  document.querySelectorAll('.exp-hist-dl').forEach(btn => {
    btn.addEventListener('click', () => toast('Baixando arquivo…', 'info'));
  });

  document.getElementById('btn-export')?.addEventListener('click', () => {
    exportComprasCSV();
  });
  document.getElementById('btn-new-order')?.addEventListener('click', () => {
    openModalNovaCompra();
  });
}

/* ══ MODAL: AGENDAR ENTREGA ══ */
function compraEscape(value) {
  return String(value ?? '').replace(
    /[&<>"']/g,
    ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch]
  );
}

function openModalAgendarEntrega() {
  const pendentes = (window.__allCompras || []).filter(c => c.status === 'pendente');

  let html = '';
  if (pendentes.length === 0) {
    html =
      '<p style="text-align:center;padding:20px;color:var(--ink-35);font-size:13px">Não há pedidos pendentes para agendar. Crie um pedido clicando em <strong>Novo Pedido</strong>.</p>';
  } else {
    html = pendentes
      .map(
        c => `
      <div style="display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid var(--border-color,rgba(13,21,16,0.1))">
        <div style="flex:1;min-width:0">
          <div style="font-weight:600;font-size:12.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${compraEscape(c.fornecedor_nome || c.fornecedor || `Pedido #${c.id}`)}</div>
          <div style="font-size:11.5px;color:var(--ink-35)">R$ ${Number(
            c.valor_total ?? c.valor ?? 0
          )
            .toFixed(2)
            .replace('.', ',')}</div>
        </div>
        <input type="date" class="form-input" style="width:auto;flex:0 0 auto" id="agenda-${c.id}" value="${c.data_entrega || ''}">
        <button class="ghost-btn sm" onclick="salvarAgendamento(${c.id})">Receber</button>
      </div>
      ${(c.itens || [])
        .map(
          item => `
        <div class="form-group" style="padding:10px 0">
          <div class="form-label">${compraEscape(item.produto_nome)} · ${item.quantidade} un.</div>
          <label class="form-label" for="recebe-lote-${item.id}">Lote da embalagem (quando houver)</label>
          <input class="form-input" id="recebe-lote-${item.id}" maxlength="50" value="${compraEscape(item.lote_recebido === 'SEM-LOTE' ? '' : item.lote_recebido)}">
          <label class="form-label" for="recebe-validade-${item.id}">Validade${item.exige_validade ? ' *' : ' (opcional)'}</label>
          <input class="form-input" type="date" id="recebe-validade-${item.id}" value="${compraEscape(item.data_validade_recebida || '')}">
        </div>`
        )
        .join('')}
    `
      )
      .join('');
  }

  const modal = document.getElementById('modal-agenda-entrega');
  const body = document.getElementById('agenda-entrega-body');
  if (modal && body) {
    body.innerHTML = html;
    modal.classList.add('open');
    document.body.style.overflow = 'hidden';
  }
}

window.salvarAgendamento = async function salvarAgendamento(id) {
  const input = document.getElementById(`agenda-${id}`);
  const dataEntrega = input?.value;
  if (!dataEntrega) {
    toast('Selecione a data de entrega.', 'error');
    return;
  }
  const compra = (window.__allCompras || []).find(c => c.id === id);
  const itensRecebimento = (compra?.itens || []).map(item => ({
    id: item.id,
    lote_recebido: document.getElementById(`recebe-lote-${item.id}`)?.value.trim() || null,
    data_validade_recebida: document.getElementById(`recebe-validade-${item.id}`)?.value || null
  }));
  if (
    itensRecebimento.some(
      item =>
        compra.itens.find(original => original.id === item.id)?.exige_validade &&
        !item.data_validade_recebida
    )
  ) {
    toast('Informe a validade dos itens marcados com *.', 'error');
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/compras/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        status: 'recebido',
        data_recebimento: dataEntrega,
        itens_recebimento: itensRecebimento
      })
    });
    // Nota: o backend atualiza de forma parcial — campos não enviados
    // (fornecedor_id, usuario_id, valor_total) são mantidos com seus valores atuais.
    // data_recebimento é registrada automaticamente quando o status vira 'recebido'.
    const data = await res.json();
    if (data.ok) {
      toast(data.mensagem || 'Entrega recebida! Entrada registrada no estoque.', 'success');
      loadComprasTable();
      document.getElementById('modal-agenda-entrega')?.classList.remove('open');
      document.body.style.overflow = '';
    } else {
      toast(data.mensagem || 'Erro ao confirmar recebimento.', 'error');
    }
  } catch (err) {
    console.error('Erro ao agendar entrega:', err);
    toast('Servidor indisponível. Verifique o backend.', 'error');
  }
};

/* ══ EXPORTAR COMPRAS (CSV) ══ */
async function exportComprasCSV() {
  try {
    const res = await fetch(`${API_BASE}/compras`);
    const data = await res.json();
    if (!data.ok) throw new Error('resposta inválida');
    const compras = (data.compras || []).filter(purchaseInPeriod);
    if (compras.length === 0) {
      toast('Nenhum pedido para exportar.', 'info');
      return;
    }
    const header = 'Fornecedor;Status;Valor Total;Data Pedido;Data Recebimento;Itens';
    const rows = compras.map(c => {
      const itens = (c.itens || [])
        .map(i => `${i.produto_nome || i.nome} x${i.quantidade}`)
        .join(', ');
      return [
        c.fornecedor_nome || c.fornecedor || '',
        c.status || '',
        String(c.valor_total ?? c.valor ?? 0).replace('.', ','),
        (c.data_pedido || '').split(' ')[0],
        (c.data_recebimento || '').split(' ')[0],
        itens
      ].join(';');
    });
    const csv = '\uFEFF' + [header, ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `relatorio_compras_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast('Relatório de compras exportado!', 'success');
  } catch (err) {
    console.error('Erro ao exportar compras:', err);
    toast('Servidor indisponível. Verifique o backend.', 'error');
  }
}

/* ══ MODAL: NOVA COMPRA ══ */
var cmpOverlay = () => document.getElementById('modal-nova-compra');
var cmpItens = [];
var cmpProdutos = [];
var cmpFornecedores = [];

async function fetchFornecedores() {
  try {
    const res = await fetch(`${API_BASE}/fornecedores`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const lista = data.fornecedores || data || [];
    cmpFornecedores = Array.isArray(lista) ? lista : [];
    const select = document.getElementById('cmp-fornecedor');
    if (select) {
      if (cmpFornecedores.length === 0) {
        select.innerHTML = '<option value="">Nenhum fornecedor cadastrado</option>';
        // Avisa que o cadastro de fornecedores é feito na página de Estoque
        const notice = document.getElementById('cmp-fornecedor-notice');
        if (notice) {
          notice.textContent =
            'Cadastre fornecedores na página de Estoque (botão de fornecedor na barra superior). Eles aparecerão aqui automaticamente.';
          notice.style.display = 'block';
        }
      } else {
        select.innerHTML =
          '<option value="">Selecione um fornecedor...</option>' +
          cmpFornecedores
            .map(
              f => `<option value="${f.id}">${f.nome_fantasia || f.nome || f.razao_social}</option>`
            )
            .join('');
        const notice = document.getElementById('cmp-fornecedor-notice');
        if (notice) notice.style.display = 'none';
      }
    }
    return true;
  } catch (err) {
    console.error('Erro ao buscar fornecedores:', err);
    const select = document.getElementById('cmp-fornecedor');
    if (select) {
      select.innerHTML = '<option value="">Erro ao carregar — clique para tentar de novo</option>';
      const notice = document.getElementById('cmp-fornecedor-notice');
      if (notice) notice.style.display = 'none';
    }
    return false;
  }
}

async function fetchProdutosCompra() {
  try {
    const res = await fetch(`${API_BASE}/produtos`);
    const data = await res.json();
    const lista = data.produtos || data || [];
    cmpProdutos = (Array.isArray(lista) ? lista : [])
      .slice()
      .sort((a, b) =>
        String(a.nome || a.produto_nome || '').localeCompare(
          String(b.nome || b.produto_nome || ''),
          'pt-BR',
          { sensitivity: 'base' }
        )
      );
  } catch (err) {
    console.error('Erro ao buscar produtos:', err);
  }
}

/* renderCmpItem(): Renderiza uma linha da tabela de compras com status colorido. */
function renderCmpItem(row) {
  const produtoOptions =
    '<option value="">Selecione…</option>' +
    cmpProdutos
      .map(
        p =>
          `<option value="${p.id}"${row.produto_id === p.id ? ' selected' : ''}>${p.nome || p.produto_nome}</option>`
      )
      .join('');

  const div = document.createElement('div');
  div.className = 'cmp-item-row';
  div.dataset.itemId = row.id;
  div.innerHTML = `
    <div class="form-group">
      <label class="form-label">Produto</label>
      <select class="form-select" data-field="produto_id">${produtoOptions}</select>
    </div>
    <div class="form-group">
      <label class="form-label">Qtd.</label>
      <input type="number" class="form-input" data-field="quantidade" value="${row.quantidade || ''}" min="1" placeholder="0">
    </div>
    <div class="form-group">
      <label class="form-label">Preço unit. (R$)</label>
      <input type="number" class="form-input" data-field="preco_unitario" value="${row.preco_unitario || ''}" min="0" step="0.01" placeholder="0,00">
    </div>
    <div class="form-group">
      <label class="form-label">Lote (se recebido)</label>
      <input type="text" class="form-input" data-field="lote_recebido" value="${row.lote_recebido || ''}" placeholder="Ex: LT-2026">
    </div>
    <div class="form-group">
      <label class="form-label">Validade (se recebido)</label>
      <input type="date" class="form-input" data-field="data_validade_recebida" value="${row.data_validade_recebida || ''}">
    </div>
    <button class="btn-remove-item" type="button" aria-label="Remover item">
      <svg width="12" height="12" viewBox="0 0 13 13" fill="none"><path d="M3 3l7 7M10 3l-7 7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
    </button>`;

  div.querySelectorAll('[data-field]').forEach(input => {
    input.addEventListener('input', () => {
      const item = cmpItens.find(i => i.id === row.id);
      if (item) item[input.dataset.field] = input.value;
    });
    input.addEventListener('change', () => {
      const item = cmpItens.find(i => i.id === row.id);
      if (item) item[input.dataset.field] = input.value;
    });
  });
  div.querySelector('.btn-remove-item').addEventListener('click', () => {
    cmpItens = cmpItens.filter(i => i.id !== row.id);
    div.remove();
    renderCmpEmptyState();
  });

  document.getElementById('cmp-itens-list').appendChild(div);
}

/* renderCmpEmptyState(): Mostra mensagem quando não há compras para exibir. */
function renderCmpEmptyState() {
  const lista = document.getElementById('cmp-itens-list');
  if (cmpItens.length === 0 && !lista.querySelector('.cmp-empty-state')) {
    lista.innerHTML =
      '<div class="cmp-empty-state">Nenhum item adicionado. Clique em “Adicionar item” para começar.</div>';
  } else if (cmpItens.length > 0) {
    lista.querySelectorAll('.cmp-empty-state').forEach(el => el.remove());
  }
}

/* openModalNovaCompra(): Abre o modal para criar uma nova ordem de compra. */
function openModalNovaCompra() {
  const overlay = cmpOverlay();
  if (!overlay) return;

  // Reseta formulário
  const selectForn = document.getElementById('cmp-fornecedor');
  document.getElementById('cmp-valor-total').value = '';
  document.getElementById('cmp-status').value = 'pendente';
  if (selectForn) selectForn.value = '';
  cmpItens = [];
  document.getElementById('cmp-itens-list').innerHTML = '';

  renderCmpEmptyState();

  // Carrega fornecedores sempre que o modal abre (garante lista atualizada)
  fetchFornecedores().then(ok => {
    if (!ok) toast('Falha ao carregar fornecedores. Tente novamente.', 'error');
  });

  // Atualiza o select de produtos em qualquer item já renderizado
  fetchProdutosCompra().then(() => {
    document.querySelectorAll('#cmp-itens-list .cmp-item-row').forEach(row => {
      const select = row.querySelector('[data-field="produto_id"]');
      const item = cmpItens.find(i => i.id === row.dataset.itemId);
      if (select && item) {
        select.innerHTML =
          '<option value="">Selecione…</option>' +
          cmpProdutos
            .map(
              p =>
                `<option value="${p.id}"${item.produto_id == p.id ? ' selected' : ''}>${p.nome || p.produto_nome}</option>`
            )
            .join('');
      }
    });
  });

  overlay.classList.add('open');
  document.body.style.overflow = 'hidden';
}

/* closeModalNovaCompra(): Fecha o modal de nova compra e limpa o formulário. */
function closeModalNovaCompra() {
  const overlay = cmpOverlay();
  if (overlay) overlay.classList.remove('open');
  document.body.style.overflow = '';
}

document.getElementById('btn-close-modal-compra')?.addEventListener('click', closeModalNovaCompra);
document.getElementById('btn-cancel-modal-compra')?.addEventListener('click', closeModalNovaCompra);
window.fcPageListen(document, 'click', e => {
  const overlay = cmpOverlay();
  if (overlay && e.target === overlay) closeModalNovaCompra();
});

// Fechar modal com Escape
window.fcPageListen(document, 'keydown', e => {
  const overlay = cmpOverlay();
  if (e.key === 'Escape' && overlay?.classList.contains('open')) {
    closeModalNovaCompra();
  }
});

// Adicionar item
document.getElementById('btn-add-item')?.addEventListener('click', () => {
  const row = {
    id: Date.now(),
    produto_id: '',
    quantidade: '',
    preco_unitario: '',
    lote_recebido: '',
    data_validade_recebida: ''
  };
  cmpItens.push(row);
  renderCmpItem(row);
  renderCmpEmptyState();
});

// Salvar compra
document.getElementById('btn-save-compra')?.addEventListener('click', async () => {
  const fornecedorId = document.getElementById('cmp-fornecedor').value;
  const valorTotal = parseFloat(document.getElementById('cmp-valor-total').value);
  const status = document.getElementById('cmp-status').value;

  if (!fornecedorId) {
    toast('Selecione um fornecedor.', 'error');
    return;
  }
  if (!valorTotal || valorTotal <= 0) {
    toast('Informe o valor total da compra.', 'error');
    return;
  }
  // Coleta itens válidos (com produto e quantidade)
  // Usa o valor atual do DOM como fonte principal (o estado cmpItens pode ficar
  // dessincronizado se o evento de input/change não disparar, ex.: preenchimento
  // automático do formulário), com fallback para o estado memorizado.
  const itensValidos = [];
  for (const item of cmpItens) {
    const row = document.querySelector(`.cmp-item-row[data-item-id="${item.id}"]`);
    const val = (field, mem) => {
      const el = row?.querySelector(`[data-field="${field}"]`);
      const v = el && el.value ? el.value : mem;
      return typeof v === 'string' ? v.trim() : v;
    };

    const produtoId = val('produto_id', item.produto_id);
    const quantidade = parseInt(val('quantidade', item.quantidade));
    const precoUnitario = parseFloat(val('preco_unitario', item.preco_unitario));

    if (produtoId && quantidade && quantidade > 0 && !isNaN(precoUnitario) && precoUnitario > 0) {
      itensValidos.push({
        produto_id: parseInt(produtoId),
        quantidade,
        preco_unitario: precoUnitario,
        lote_recebido: val('lote_recebido', item.lote_recebido) || null,
        data_validade_recebida: val('data_validade_recebida', item.data_validade_recebida) || null
      });
    }
  }

  // Compras recebidas exigem ao menos um item (para dar entrada no estoque)
  if (status === 'recebido') {
    const semValidade = itensValidos.find(item => {
      const produto = cmpProdutos.find(p => Number(p.id) === item.produto_id);
      return produto && produto.exige_validade && !item.data_validade_recebida;
    });
    if (semValidade) {
      toast(
        'Informe a validade dos produtos que exigem vencimento antes de receber a compra.',
        'error'
      );
      return;
    }
  }
  if (status === 'recebido' && itensValidos.length === 0) {
    toast(
      'Compras "Recebidas" precisam de pelo menos um item com produto, quantidade e preço.',
      'error'
    );
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/compras`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        fornecedor_id: parseInt(fornecedorId),
        valor_total: valorTotal,
        status,
        itens: itensValidos
      })
    });

    const data = await res.json();
    if (data.ok) {
      toast('Compra registrada com sucesso!', 'success');
      closeModalNovaCompra();
      // Recarrega KPIs e tabela
      await Promise.all([loadComprasStats(), loadComprasTable()]);
    } else {
      toast(data.mensagem || 'Erro ao registrar a compra.', 'error');
    }
  } catch (err) {
    console.error('Erro ao salvar compra:', err);
    toast('Erro de conexão com o servidor.', 'error');
  }
});

/* ══ REFRESH ═─ recarrega dados reais do banco ══ */
document.getElementById('btn-refresh')?.addEventListener('click', async () => {
  const svg = document.querySelector('#btn-refresh svg');
  if (svg) {
    svg.style.transition = 'transform 0.6s';
    svg.style.transform = 'rotate(360deg)';
    setTimeout(() => {
      svg.style.transition = 'none';
      svg.style.transform = 'rotate(0deg)';
    }, 650);
  }
  await Promise.all([loadComprasStats(), loadComprasTable()]);
  toast('Dados atualizados com sucesso.', 'success');
});

/* ══ TOAST — usa o sistema global do global-settings.js ══ */
var toast = window.FarmaControlSettings
  ? window.FarmaControlSettings.showToast
  : () => console.warn('Toast indisponível');

/* (Atalhos de teclado e gerenciamento da sidebar delegados ao sidebar-init.js) */

/* ══ INIT ══ */
function initComprasPage() {
  initCounters();
  initPeriodSelector();
  initChartTabs();
  initTableFilter();
  initReportButtons();

  // Carrega dados reais do banco
  loadComprasStats();
  loadComprasTable();
}
if (document.readyState === 'loading')
  window.fcPageListen(document, 'DOMContentLoaded', initComprasPage, { once: true });
else initComprasPage();

/* (Logout delegado ao sidebar-init.js: já limpa a sessão e redireciona corretamente) */

/* ══ BOTÕES DE VISUALIZAÇÃO (abrem modal read-only) ══ */
function initComprasViewLinks() {
  document.querySelectorAll('.card-link, .panel-link').forEach(btn => {
    btn.addEventListener('click', e => {
      e.preventDefault();
      const text = btn.textContent.trim();
      const card = btn.closest('.card, .panel-section');
      const cardTitle = card?.querySelector('.card-title, .panel-title')?.textContent || '';

      if (text.includes('Ver detalhe')) {
        if (!window.fcOpenViewModal) return;
        // Abre modal com detalhes das compras por categoria
        const chartEl = document.getElementById('category-chart');
        const chartContent = chartEl ? chartEl.innerHTML : '<p>Nenhum dado disponível</p>';
        window.fcOpenViewModal(
          'Compras por Categoria — Detalhe',
          'Distribuição de compras por categoria no período',
          chartContent
        );
      } else if (text.includes('Ver todos')) {
        if (!window.fcOpenViewModal) return;
        // Abre modal com todos os fornecedores
        window.fcOpenViewModal(
          'Fornecedores',
          `${supplierRows.length} fornecedores no período`,
          `<ul class="rank-list">${supplierMarkup(supplierRows)}</ul>`
        );
      }
    });
  });
}

if (document.readyState === 'loading') {
  window.fcPageListen(document, 'DOMContentLoaded', initComprasViewLinks, { once: true });
} else {
  initComprasViewLinks();
}

function supplierMarkup(rows) {
  const max = Math.max(...supplierRows.map(f => f.valor_total), 1);
  return rows
    .map(
      (f, i) =>
        `<li class="rank-item"><span class="rank-pos">${i + 1}</span><div class="rank-info"><span class="rank-name" title="${compraEscape(f.nome_fantasia || f.razao_social)}">${compraEscape(f.nome_fantasia || f.razao_social || 'Fornecedor')}</span><div class="rank-bar-wrap"><div class="rank-bar" style="--w:${(f.valor_total / max) * 100}%"></div></div></div><span class="rank-val">${f.valor_total.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</span><span class="rank-trend neutral">${f.total_pedidos} ped.</span></li>`
    )
    .join('');
}
function renderPurchases() {
  const tbody = document.getElementById('mov-table-body');
  const countEl = document.getElementById('mov-filter-count');
  const status = document.querySelector('.ftab[data-type].active')?.dataset.type || 'all';
  const search = document.getElementById('table-search')?.value.toLowerCase().trim() || '';
  const compras = (window.__allCompras || []).filter(c => {
    return (
      purchaseInPeriod(c) &&
      (status === 'all' || c.status === status) &&
      (!search ||
        `${c.fornecedor_nome} PC-${String(c.id).padStart(4, '0')}`.toLowerCase().includes(search))
    );
  });
  document.getElementById('mov-count').textContent = `${compras.length} registros`;
  const pages = Math.max(1, Math.ceil(compras.length / 10));
  purchasePage = Math.min(purchasePage, pages);
  document.getElementById('purchase-prev').disabled = purchasePage <= 1;
  document.getElementById('purchase-next').disabled = purchasePage >= pages;
  if (compras.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="9" style="text-align:center;padding:24px;color:rgba(13,21,16,0.4)">Nenhuma compra registrada.</td></tr>';
    if (countEl) countEl.textContent = 'Exibindo 0 de 0 registros';
    return;
  }

  const statusLabel = {
    pendente: 'Pendente',
    recebido: 'Recebido',
    cancelado: 'Cancelado',
    parcial: 'Parcial'
  };
  const statusCls = { pendente: 'warn', recebido: 'ok', cancelado: 'err', parcial: 'info' };

  tbody.innerHTML = compras
    .slice((purchasePage - 1) * 10, purchasePage * 10)
    .map(c => {
      const dataBr = c.data_pedido
        ? new Date(c.data_pedido).toLocaleDateString('pt-BR')
        : c.criado_em
          ? new Date(c.criado_em).toLocaleDateString('pt-BR')
          : '—';

      const valorTotal = c.valor_total
        ? 'R$ ' +
          parseFloat(c.valor_total).toLocaleString('pt-BR', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
          })
        : '—';

      const st = c.status || 'pendente';
      const cls = st === 'recebido' ? 'out' : st === 'pendente' ? 'in' : 'err';
      const label = statusLabel[st] || st;

      // Como a rota /compras não traz o produto principal (pois uma compra pode ter vários),
      // vamos exibir o fornecedor na coluna de produto ou indicar "Múltiplos itens"
      const resumoProdutos =
        c.itens_count > 1 ? `${c.itens_count} itens` : c.itens_count === 1 ? '1 item' : 'Sem itens';

      return `<tr data-type="${st}" data-id="${c.id}">
        <td class="mono">${dataBr}</td>
        <td class="prod-cell">
          <span class="prod-name">${resumoProdutos}</span>
        </td>
        <td><span class="cat-tag">${c.fornecedor_nome || '—'}</span></td>
        <td class="mono">PC-${c.id.toString().padStart(4, '0')}</td>
        <td class="c"><span class="pill-type ${cls}">${label}</span></td>
        <td class="r fw6">${c.itens_count || 0}</td>
        <td class="r muted">—</td>
        <td class="r fw6">${valorTotal}</td>
        <td>${c.usuario_nome || '—'}</td>
      </tr>`;
    })
    .join('');

  if (countEl)
    countEl.textContent = `Exibindo ${(purchasePage - 1) * 10 + 1}–${Math.min(purchasePage * 10, compras.length)} de ${compras.length} registros`;

  // Bind detalhes (clique na linha abre o resumo da compra)
  tbody.querySelectorAll('[data-id]').forEach(row => {
    row.style.cursor = 'pointer';
    row.addEventListener('click', async e => {
      // Ignora cliques dentro de células de ações
      if (e.target.closest('.row-actions, .row-btn')) return;
      const id = row.dataset.id;
      try {
        const res2 = await fetch(`${API_BASE}/compras/${id}`);
        const r2 = await res2.json();
        if (r2.ok) {
          const c2 = r2.compra;
          const itensHtml = (c2.itens || [])
            .map(
              it =>
                `<tr><td>${it.produto_nome || '—'}</td><td class="r">${it.quantidade}</td><td class="r">R$ ${parseFloat(it.preco_unitario || 0).toFixed(2)}</td></tr>`
            )
            .join('');
          window.fcOpenViewModal?.(
            `Compra #${id}`,
            `${compraEscape(c2.fornecedor_nome || '—')} · ${statusLabel[c2.status] || c2.status}`,
            `<div class="table-wrap"><table><thead><tr><th>Produto</th><th>Quantidade</th><th>Preço unitário</th></tr></thead><tbody>${itensHtml}</tbody></table></div>`
          );
        }
      } catch (err) {
        console.error('Erro ao carregar detalhes da compra:', err);
      }
    });
  });
}

function purchaseInPeriod(c) {
  const now = new Date();
  const month =
    purchasePeriod === 'year'
      ? 0
      : purchasePeriod === 'quarter'
        ? Math.floor(now.getMonth() / 3) * 3
        : now.getMonth();
  const start = `${now.getFullYear()}-${String(month + 1).padStart(2, '0')}-01`;
  const end = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
  const day = (c.data_pedido || c.criado_em || '').slice(0, 10);
  return day >= start && day <= end;
}
