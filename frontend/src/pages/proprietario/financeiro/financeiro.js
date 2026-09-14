/* ══════════════════════════════════════════════════════════════════════
 * FARMAControl — MÓDULO FINANCEIRO (PROPRIETÁRIO)
 * ══════════════════════════════════════════════════════════════════════
 *
 * Controle financeiro da farmácia:
 * - KPIs: Receitas, Despesas, Saldo, Ticket Médio (últimos 30 dias)
 * - Gráfico de fluxo de caixa: Receitas vs Despesas por dia
 * - Gráfico donut: Despesas por categoria
 * - Gráfico sparkline: Evolução do saldo em caixa
 * - Tabela de transações com filtros (tipo, status, categoria)
 *
 * Dados são carregados da API:
 * - GET /financeiro/stats?days=30  (KPIs)
 * - GET /financeiro/categorias     (lista de categorias)
 * - GET /financeiro/transacoes     (tabela paginada)
 * - GET /financeiro/fluxo          (dados para gráfico)
 * ══════════════════════════════════════════════════════════════════════ */

/* ═══════════════════════════════════════════════════════════════
   FarmaControl — Página Financeiro (JavaScript)
   Padronizado conforme dashboard.js
   ═══════════════════════════════════════════════════════════════ */
'use strict';
(function () {
  const API_BASE = window.FarmaControlSettings ? window.FarmaControlSettings.API_BASE : 'http://localhost:5000';
  const API = API_BASE + '/financeiro';
  const token = window.__fcPageToken || crypto.randomUUID();
  if (!window.__fcPageToken) window.__fcPageToken = token;

    /* toast(): Exibe notificação temporária (sucesso/erro/info) no canto da tela. */
  function toast(msg, type = 'info') {
    const t = document.createElement('div');
    t.className = 'fc-toast fc-toast-' + type;
    t.textContent = msg;
    t.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:9999;padding:12px 20px;border-radius:8px;font-size:13px;font-family:Outfit,sans-serif;color:#fff;box-shadow:0 4px 12px rgba(0,0,0,0.15);opacity:0;transition:opacity 0.3s;';
    const colors = { info: '#2e6da4', success: '#4a7c59', error: '#c03a3a' };
    const redTheme = window.FarmaControlSettings?.getCurrentColor?.() === '#c03a3a';
    const isError = type === 'error' || type === 'err';
    t.style.background = redTheme && !isError ? '#ffffff' : (colors[type] || colors.info);
    t.style.color = redTheme && !isError ? '#2d2d2d' : '#ffffff';
    t.style.border = redTheme && !isError ? '1px solid #e3e3e3' : 'none';
    document.body.appendChild(t);
    requestAnimationFrame(() => { t.style.opacity = '1'; });
    setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 4000);
  }

    /* fmtBRL(): Formata número para moeda brasileira (ex: 1250.50 → "R$ 1.250,50"). */
  function fmtBRL(n) {
    return (n || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  }

    /* fmtDate(): Formata data ISO para formato brasileiro (19/08/2026). */
  function fmtDate(d) {
    if (!d || d === '—') return '—';
    // Backend may return ISO format ('YYYY-MM-DD HH:mm:ss') or DD/MM/YYYY
    // Parse manually for reliability
    if (typeof d === 'string' && d.includes('/')) {
      // DD/MM/YYYY format
      const parts = d.split(' ');
      const dateParts = parts[0].split('/');
      if (dateParts.length === 3) {
        return dateParts[0] + '/' + dateParts[1] + '/' + dateParts[2];
      }
    } else if (typeof d === 'string' && d.includes('-')) {
      // ISO format YYYY-MM-DD HH:mm:ss
      const dt = new Date(d);
      if (isNaN(dt.getTime())) return '—';
      return dt.toLocaleDateString('pt-BR');
    } else {
      const dt = new Date(d);
      if (isNaN(dt.getTime())) return '—';
      return dt.toLocaleDateString('pt-BR');
    }
  }

  const metodoLabels = {
    'dinheiro': 'Dinheiro', 'pix': 'PIX',
    'cartao_credito': 'Crédito', 'cartao_debito': 'Débito',
    'boleto': 'Boleto', 'transferencia': 'Transferência'
  };

  const statusLabels = {
    'pago': 'Pago', 'pendente': 'Pendente', 'cancelado': 'Cancelado'
  };

  async function apiGet(path, query = {}) {
    const sp = new URLSearchParams();
    Object.entries(query).forEach(([k, v]) => sp.set(k, v));
    const url = API + path + (sp.toString() ? '?' + sp.toString() : '');
    const res = await fetch(url, { credentials: 'include' });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return res.json();
  }

  let currentDays = 30;

  // ── Load KPIs ──
  async function loadKPIs() {
    try {
      const data = await apiGet('/stats', { days: currentDays });
      const saldo = data.saldo || 0;
      const receitas = data.receitas || 0;
      const despesas = data.despesas || 0;
      const ticket = data.ticket_medio || 0;

      const elSaldo = document.getElementById('kpi-saldo');
      const elReceitas = document.getElementById('kpi-receitas');
      const elDespesas = document.getElementById('kpi-despesas');
      const elTicket = document.getElementById('kpi-ticket');

      if (elSaldo) elSaldo.textContent = fmtBRL(saldo);
      if (elReceitas) elReceitas.textContent = fmtBRL(receitas);
      if (elDespesas) elDespesas.textContent = fmtBRL(despesas);
      if (elTicket) elTicket.textContent = fmtBRL(ticket);

      // Deltas
      const elSaldoDelta = document.getElementById('kpi-saldo-delta');
      const elReceitasDelta = document.getElementById('kpi-receitas-delta');
      const elDespesasDelta = document.getElementById('kpi-despesas-delta');

      const dr = data.delta_receitas || 0;
      const dd = data.delta_despesas || 0;

      if (elReceitasDelta) {
        elReceitasDelta.textContent = (dr >= 0 ? '+' : '') + dr.toFixed(1) + '% vs período anterior';
        elReceitasDelta.className = 'kpi-delta ' + (dr >= 0 ? 'up' : 'down');
      }
      if (elDespesasDelta) {
        elDespesasDelta.textContent = (dd >= 0 ? '+' : '') + dd.toFixed(1) + '% vs período anterior';
        elDespesasDelta.className = 'kpi-delta ' + (dd <= 0 ? 'up' : 'down');
      }
      if (elSaldoDelta) {
        const pct = dr - dd;
        elSaldoDelta.textContent = (pct >= 0 ? '+' : '') + pct.toFixed(1) + '% líquido';
        elSaldoDelta.className = 'kpi-delta ' + (pct >= 0 ? 'up' : 'down');
      }

      // Sparkline
      if (data.spark && data.spark.length > 0) {
        const sparkEls = document.querySelectorAll('.kpi-spark');
        if (sparkEls.length > 0 && sparkEls[0]) {
          renderSparkline(sparkEls[0], data.spark);
        }
      }
    } catch (e) {
      console.error('Error loading KPIs:', e);
      if (window.__fcPageToken === token) toast('Erro ao carregar KPIs', 'error');
    }
  }

    /* renderSparkline(): Desenha o mini-gráfico de linha (sparkline) mostrando a evolução do saldo. */
  function renderSparkline(container, data) {
    if (!container || data.length < 2) return;
    const w = container.clientWidth || 120;
    const h = 30;
    // Use cumulative sum so the sparkline shows the balance trend
    let cumulative = [];
    let running = 0;
    data.forEach(v => {
      running += v;
      cumulative.push(running);
    });
    // Ensure values are always positive (shift to start from 0)
    const minVal = Math.min(...cumulative, 0);
    const maxVal = Math.max(...cumulative, 1);
    const range = maxVal - minVal || 1;
    const points = cumulative.map((v, i) => {
      const x = (i / (cumulative.length - 1)) * w;
      // Map value to Y coordinate: bottom=high value, top=low value
      const normalized = (v - minVal) / range;
      const y = h - (normalized * (h * 0.75) + (h * 0.125));
      return x + ',' + y;
    });
    // Add a subtle area fill under the line
    const fillPoints = points.join(' ') + ' ' + w + ',' + h + ' 0,' + h;
    container.innerHTML = '<svg width="' + w + '" height="' + h + '" viewBox="0 0 ' + w + ' ' + h + '">' +
      '<polygon points="' + fillPoints + '" fill="var(--sage-pale)" opacity="0.15"/>' +
      '<polyline points="' + points.join(' ') + '" fill="none" stroke="var(--sage)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.7"/>' +
      '</svg>';
  }

  // ── Load Chart ──
  async function loadChart() {
    try {
      const data = await apiGet('/fluxo', { days: currentDays });
      const labels = data.labels || [];
      const receitas = data.receitas || [];
      const despesas = data.despesas || [];

      const barsGroup = document.getElementById('bars-group');
      const xLabels = document.getElementById('x-labels');
      const chartBadge = document.getElementById('chart-badge');

      if (!barsGroup) return;

      const maxVal = Math.max(...receitas, ...despesas, 1);

      // Update y-labels
      const yLabels = document.querySelector('#fluxo-chart .y-labels');
      if (yLabels) {
        yLabels.innerHTML = [maxVal, Math.floor(maxVal * 0.75), Math.floor(maxVal * 0.5), Math.floor(maxVal * 0.25), 0]
          .map(v => {
            if (v >= 1000000) return '<span>' + (v / 1000000).toFixed(1).replace('.0', '') + 'M</span>';
            if (v >= 1000) return '<span>' + (v / 1000).toFixed(0) + 'k</span>';
            return '<span>' + v + '</span>';
          })
          .join('');
      }

      // Update badge
      const totalRec = receitas.reduce((a, b) => a + b, 0);
      const totalDesp = despesas.reduce((a, b) => a + b, 0);
      if (chartBadge) chartBadge.textContent = fmtBRL(totalRec - totalDesp);

      // Render bars
      barsGroup.innerHTML = labels.map((label, i) => {
        const rH = Math.max((receitas[i] / maxVal) * 100, 0);
        const dH = Math.max((despesas[i] / maxVal) * 100, 0);
        return '<div class="bar-group">' +
          '<div class="bar" style="height:' + rH + '%;background:var(--sage);border-radius:3px 3px 0 0;" title="Receitas: ' + fmtBRL(receitas[i]) + '"></div>' +
          '<div class="bar" style="height:' + dH + '%;background:var(--red);opacity:0.7;border-radius:3px 3px 0 0;" title="Despesas: ' + fmtBRL(despesas[i]) + '"></div>' +
          '</div>';
      }).join('');

      // Update x-labels
      if (xLabels) {
        const maxLabels = 7;
        const step = Math.max(1, Math.ceil(labels.length / maxLabels));
        xLabels.innerHTML = labels.map((l, i) => {
          if (i % step === 0 || i === labels.length - 1) {
            return '<span>' + l + '</span>';
          }
          return '<span></span>';
        }).join('');
      }
    } catch (e) {
      console.error('Error loading chart:', e);
      if (window.__fcPageToken === token) toast('Erro ao carregar gráfico', 'error');
    }
  }

  // ── Load Categories ──
  async function loadCategories() {
    try {
      const data = await apiGet('/categorias', { tipo: 'despesa' });
      const categorias = data.categorias || [];
      const container = document.getElementById('cat-list');
      const badge = document.getElementById('cat-badge');

      if (!container) return;

      if (!categorias.length) {
        container.innerHTML = '<div style="padding:20px;color:var(--ink-35);font-size:13px;">Nenhuma despesa registrada</div>';
        return;
      }

      const total = categorias.reduce((s, c) => s + (c.valor || 0), 0);
      const colors = ['var(--sage)', 'var(--blue)', 'var(--amber)', 'var(--red)', 'var(--sage-light)', '#8e6bb5'];

      if (badge) badge.textContent = fmtBRL(total);

      container.innerHTML = categorias.map((cat, i) => {
        const pct = total > 0 ? ((cat.valor / total) * 100).toFixed(0) : 0;
        const color = colors[i % colors.length];
        return '<div class="cat-item">' +
          '<div class="cat-color" style="background:' + color + ';"></div>' +
          '<span class="cat-name">' + (cat.nome || cat.categoria_nome || '—') + '</span>' +
          '<div class="cat-bar"><div class="cat-bar-fill" style="width:' + pct + '%;background:' + color + ';"></div></div>' +
          '<span class="cat-amount">' + fmtBRL(cat.valor || 0) + '</span>' +
          '</div>';
      }).join('');
    } catch (e) {
      console.error('Error loading categories:', e);
      if (window.__fcPageToken === token) toast('Erro ao carregar categorias', 'error');
    }
  }

  // ── Load Transactions ──
  async function loadTransactions() {
    try {
      const data = await apiGet('/transacoes', { days: currentDays });
      const transacoes = data.transacoes || [];
      renderTransactionTable(transacoes);
      const countEl = document.getElementById('trans-count');
      const filterCount = document.getElementById('filter-count');
      if (countEl) countEl.textContent = transacoes.length + ' transações';
      if (filterCount) filterCount.textContent = 'Exibindo ' + transacoes.length + ' itens';
    } catch (e) {
      console.error('Error loading transactions:', e);
      if (window.__fcPageToken === token) toast('Erro ao carregar transações', 'error');
    }
  }

    /* renderTransactionTable(): Renderiza a tabela de transações com paginação e filtros. */
  function renderTransactionTable(transacoes) {
    const tbody = document.getElementById('trans-body');
    if (!tbody) return;
    if (!transacoes.length) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--ink-35);padding:24px;">Nenhuma transação encontrada</td></tr>';
      return;
    }
    tbody.innerHTML = transacoes.map(t => {
      const statusClass = t.status === 'pago' ? 'chip-green' : (t.status === 'pendente' ? 'chip-amber' : 'chip-red');
      const tipoClass = t.tipo === 'receita' ? 'text-green' : 'text-red';
      const valorClass = t.tipo === 'receita' ? 'receita-val' : 'despesa-val';
      return '<tr>' +
        '<td><span style="font-weight:500;">' + (t.descricao || '—') + '</span></td>' +
        '<td style="color:var(--ink-35);font-size:12px;">' + (t.categoria_nome || '—') + '</td>' +
        '<td class="r" style="font-family:DM Mono,monospace;font-weight:500;" class="' + valorClass + '">' +
          (t.tipo === 'receita' ? '+' : '−') + fmtBRL(t.valor) + '</td>' +
        '<td style="font-size:12px;">' + (metodoLabels[t.metodo_pagamento] || t.metodo_pagamento || '—') + '</td>' +
        '<td><span class="chip ' + statusClass + '">' + (statusLabels[t.status] || t.status) + '</span></td>' +
        '<td style="font-size:12px;color:var(--ink-35);">' + fmtDate(t.data_transacao) + '</td>' +
        '</tr>';
    }).join('');
  }

  // ── Load All ──
  async function loadAll() {
    await Promise.all([loadKPIs(), loadChart(), loadCategories(), loadTransactions()]);
  }

  // ── Period Filters ──
  document.querySelectorAll('#period-filters .ghost-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#period-filters .ghost-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentDays = parseInt(btn.dataset.days);
      loadAll();
    });
  });

  // ── Refresh Button ──
  const btnRefresh = document.getElementById('btn-refresh');
  if (btnRefresh) {
    btnRefresh.addEventListener('click', () => {
      btnRefresh.style.opacity = '0.5';
      loadAll().then(() => { btnRefresh.style.opacity = '1'; });
    });
  }

  // ── Modal: Nova Transação ──
  const btnNova = document.getElementById('btn-nova-transacao');
  if (btnNova) {
    btnNova.addEventListener('click', () => {
      const modal = document.getElementById('modal-nova-transacao');
      if (modal) {
        modal.classList.add('open');
        loadCategoriesForModal();
      }
    });
  }

  window.closeTransModal = function () {
    const modal = document.getElementById('modal-nova-transacao');
    if (modal) modal.classList.remove('open');
  };

  // Close on overlay click
  document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay') && e.target.id === 'modal-nova-transacao') {
      closeTransModal();
    }
  });

  // Close on Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeTransModal();
  });

  async function loadCategoriesForModal() {
    try {
      const tipo = document.getElementById('tx-tipo')?.value || 'receita';
      const data = await apiGet('/categorias', { tipo: tipo });
      const select = document.getElementById('tx-categoria');
      if (!select) return;
      select.innerHTML = '<option value="">Selecione...</option>' +
        (data.categorias || []).map(c =>
          '<option value="' + (c.id || '') + '">' + (c.nome || c.categoria_nome || '') + '</option>'
        ).join('');
    } catch (e) {
      console.error('Error loading categories for modal:', e);
    }
  }

  // Update categories when tipo changes
  const txTipo = document.getElementById('tx-tipo');
  if (txTipo) {
    txTipo.addEventListener('change', loadCategoriesForModal);
  }

  // Save transaction
  const btnSave = document.getElementById('btn-save-transacao');
  if (btnSave) {
    btnSave.addEventListener('click', async () => {
      const tipo = document.getElementById('tx-tipo')?.value;
      const categoriaId = document.getElementById('tx-categoria')?.value;
      const descricao = document.getElementById('tx-descricao')?.value?.trim();
      const valor = parseFloat(document.getElementById('tx-valor')?.value);
      const metodo = document.getElementById('tx-metodo')?.value;

      if (!categoriaId || !descricao || !valor || valor <= 0) {
        toast('Preencha todos os campos obrigatórios', 'error');
        return;
      }

      try {
        const res = await fetch(API + '/transacoes', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ tipo, categoria_id: parseInt(categoriaId), descricao, valor, metodo_pagamento: metodo })
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.mensagem || 'Erro ao salvar');
        }
        toast('Transação registrada com sucesso', 'success');
        closeTransModal();
        // Reset form
        document.getElementById('tx-descricao').value = '';
        document.getElementById('tx-valor').value = '';
        loadAll();
      } catch (e) {
        console.error('Error saving transaction:', e);
        toast('Erro ao salvar transação', 'error');
      }
    });
  }

  // ── Search Filter ──
  const searchInput = document.getElementById('search-trans');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      const q = searchInput.value.toLowerCase();
      const rows = document.querySelectorAll('#trans-body tr');
      rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(q) ? '' : 'none';
      });
    });
  }

  // ── Export CSV ──
  const btnExport = document.getElementById('btn-export-csv');
  if (btnExport) {
    btnExport.addEventListener('click', async () => {
      try {
        const data = await apiGet('/transacoes', { days: currentDays, limit: 1000 });
        const transacoes = data.transacoes || [];
        if (!transacoes.length) {
          toast('Nenhuma transação para exportar', 'info');
          return;
        }
        const header = 'Descrição,Categoria,Tipo,Valor,Método,Status,Data\n';
        const rows = transacoes.map(t =>
          '"' + (t.descricao || '').replace(/"/g, '""') + '",' +
          '"' + (t.categoria_nome || '') + '",' +
          (t.tipo || '') + ',' +
          (t.valor || 0) + ',' +
          '"' + (metodoLabels[t.metodo_pagamento] || '') + '",' +
          '"' + (statusLabels[t.status] || '') + '",' +
          '"' + (t.data_transacao || '') + '"'
        ).join('\n');
        const csv = header + rows;
        const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'transacoes_financeiro_' + new Date().toISOString().slice(0, 10) + '.csv';
        a.click();
        URL.revokeObjectURL(url);
        toast('CSV exportado com sucesso', 'success');
      } catch (e) {
        console.error('Error exporting CSV:', e);
        toast('Erro ao exportar CSV', 'error');
      }
    });
  }

  // ── Init ──
  loadAll();
})();
