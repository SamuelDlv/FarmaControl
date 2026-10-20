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
  const API_BASE = window.FarmaControlSettings
    ? window.FarmaControlSettings.API_BASE
    : 'http://localhost:5000';
  const API = API_BASE + '/financeiro';
  const token = window.__fcPageToken || crypto.randomUUID();
  if (!window.__fcPageToken) window.__fcPageToken = token;

  // Dados externos só podem ser interpolados em HTML depois de escapados.
  function escapeHTML(value) {
    return String(value ?? '').replace(
      /[&<>'"]/g,
      char =>
        ({
          '&': '&amp;',
          '<': '&lt;',
          '>': '&gt;',
          "'": '&#39;',
          '"': '&quot;'
        })[char]
    );
  }

  /* toast(): Exibe notificação temporária (sucesso/erro/info) no canto da tela. */
  function toast(msg, type = 'info') {
    const t = document.createElement('div');
    t.className = 'fc-toast fc-toast-' + type;
    t.textContent = msg;
    t.style.cssText =
      'position:fixed;bottom:24px;right:24px;z-index:9999;padding:12px 20px;border-radius:8px;font-size:13px;font-family:Outfit,sans-serif;color:#fff;box-shadow:0 4px 12px rgba(0,0,0,0.15);opacity:0;transition:opacity 0.3s;';
    const colors = { info: '#2e6da4', success: '#4a7c59', error: '#c03a3a' };
    const redTheme = window.FarmaControlSettings?.getCurrentColor?.() === '#c03a3a';
    const isError = type === 'error' || type === 'err';
    t.style.background = redTheme && !isError ? '#ffffff' : colors[type] || colors.info;
    t.style.color = redTheme && !isError ? '#2d2d2d' : '#ffffff';
    t.style.border = redTheme && !isError ? '1px solid #e3e3e3' : 'none';
    document.body.appendChild(t);
    requestAnimationFrame(() => {
      t.style.opacity = '1';
    });
    setTimeout(() => {
      t.style.opacity = '0';
      setTimeout(() => t.remove(), 300);
    }, 4000);
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
    dinheiro: 'Dinheiro',
    pix: 'PIX',
    cartao_credito: 'Crédito',
    cartao_debito: 'Débito',
    boleto: 'Boleto',
    transferencia: 'Transferência'
  };

  const statusLabels = {
    pago: 'Pago',
    pendente: 'Pendente',
    cancelado: 'Cancelado'
  };

  async function apiGet(path, query = {}) {
    const sp = new URLSearchParams();
    Object.entries(query).forEach(([k, v]) => sp.set(k, v));
    const url = API + path + (sp.toString() ? '?' + sp.toString() : '');
    const res = await fetch(url, { credentials: 'include' });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.mensagem || 'HTTP ' + res.status);
    return data;
  }

  let currentDays = 30;
  let chartPeriod = 'month';
  let chartCursor = new Date();
  let expenseDetailsVisible = false;
  chartCursor.setHours(0, 0, 0, 0);

  function isoDate(date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  }

  function getChartBounds() {
    if (chartPeriod === 'week') {
      const start = new Date(chartCursor);
      start.setDate(start.getDate() - ((start.getDay() + 6) % 7));
      const end = new Date(start);
      end.setDate(end.getDate() + 6);
      return { start, end };
    }
    return {
      start: new Date(chartCursor.getFullYear(), chartCursor.getMonth(), 1),
      end: new Date(chartCursor.getFullYear(), chartCursor.getMonth() + 1, 0)
    };
  }

  function updateChartRangeLabel() {
    const range = document.getElementById('chart-range');
    const next = document.getElementById('chart-next');
    if (!range) return;
    const { start, end } = getChartBounds();
    if (chartPeriod === 'month') {
      range.textContent = start
        .toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' })
        .replace(/^./, char => char.toUpperCase());
    } else {
      const fmt = date =>
        date.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' }).replace('.', '');
      range.textContent = `${fmt(start)} — ${fmt(end)}`;
    }
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    if (next) next.disabled = start <= today && end >= today;
  }

  // ── Load KPIs ──
  async function loadKPIs() {
    const requestedDays = currentDays;
    try {
      const data = await apiGet('/stats', { days: requestedDays });
      if (requestedDays !== currentDays || window.__fcPageToken !== token) return;
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
        elReceitasDelta.textContent =
          (dr >= 0 ? '+' : '') + dr.toFixed(1) + '% vs período anterior';
        elReceitasDelta.className = 'kpi-delta ' + (dr >= 0 ? 'up' : 'down');
      }
      if (elDespesasDelta) {
        elDespesasDelta.textContent =
          (dd >= 0 ? '+' : '') + dd.toFixed(1) + '% vs período anterior';
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
      const y = h - (normalized * (h * 0.75) + h * 0.125);
      return x + ',' + y;
    });
    // Add a subtle area fill under the line
    const fillPoints = points.join(' ') + ' ' + w + ',' + h + ' 0,' + h;
    container.innerHTML =
      '<svg width="' +
      w +
      '" height="' +
      h +
      '" viewBox="0 0 ' +
      w +
      ' ' +
      h +
      '">' +
      '<polygon points="' +
      fillPoints +
      '" fill="var(--sage-pale)" opacity="0.15"/>' +
      '<polyline points="' +
      points.join(' ') +
      '" fill="none" stroke="var(--sage)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.7"/>' +
      '</svg>';
  }

  // ── Load Chart ──
  async function loadChart() {
    const { start, end } = getChartBounds();
    const requestedStartDate = isoDate(start);
    const requestedEndDate = isoDate(end);
    try {
      const data = await apiGet('/fluxo', {
        start_date: requestedStartDate,
        end_date: requestedEndDate
      });
      const activeBounds = getChartBounds();
      if (
        requestedStartDate !== isoDate(activeBounds.start) ||
        requestedEndDate !== isoDate(activeBounds.end) ||
        window.__fcPageToken !== token
      )
        return;
      if (
        !data.periodo ||
        data.periodo.inicio !== requestedStartDate ||
        data.periodo.fim !== requestedEndDate
      ) {
        throw new Error('O servidor retornou dados de um período diferente do solicitado.');
      }
      const labels = data.labels || [];
      const days = data.dias || [];
      const receitas = (data.receitas || []).map(value => Number(value) || 0);
      const despesas = (data.despesas || []).map(value => Number(value) || 0);

      const xLabels = document.getElementById('x-labels');
      const chartBadge = document.getElementById('chart-badge');
      const chartRoot = document.getElementById('fluxo-chart');

      if (!chartRoot) return;

      // O endpoint pode manter rótulos mesmo que todos os valores sejam zero.
      // Para o usuário isso continua sendo um período sem movimentações.
      const hasMovements = receitas.some(value => value > 0) || despesas.some(value => value > 0);
      if (!labels.length || !hasMovements) {
        document.getElementById('chart-receitas').textContent = fmtBRL(0);
        document.getElementById('chart-despesas').textContent = fmtBRL(0);
        chartRoot.classList.add('is-empty');
        chartRoot.innerHTML =
          '<div class="chart-empty">Nenhuma movimentação financeira no período selecionado.</div>';
        if (xLabels) {
          xLabels.innerHTML = '';
          xLabels.hidden = true;
        }
        document.querySelector('.cashflow-card .chart-legend')?.setAttribute('hidden', '');
        if (chartBadge) chartBadge.textContent = 'Sem dados';
        return;
      }

      if (chartRoot.classList.contains('is-empty')) {
        chartRoot.classList.remove('is-empty');
        chartRoot.innerHTML =
          '<div class="y-labels"></div><div class="bars-wrap"><div class="grid-lines"></div><div class="bars-group" id="bars-group"></div></div>';
        if (xLabels) xLabels.hidden = false;
        document.querySelector('.cashflow-card .chart-legend')?.removeAttribute('hidden');
      }
      const barsGroup = document.getElementById('bars-group');
      if (!barsGroup) return;
      const chartMinWidth = Math.max(
        chartRoot.parentElement?.clientWidth || 0,
        labels.length * 62 + 52
      );
      chartRoot.style.minWidth = chartMinWidth + 'px';
      if (xLabels) xLabels.style.minWidth = chartMinWidth + 'px';

      const maxVal = Math.max(...receitas, ...despesas, 1);
      const totalRec = receitas.reduce((a, b) => a + b, 0);
      const totalDesp = despesas.reduce((a, b) => a + b, 0);
      const receitasEl = document.getElementById('chart-receitas');
      const despesasEl = document.getElementById('chart-despesas');
      if (receitasEl) receitasEl.textContent = fmtBRL(totalRec);
      if (despesasEl) despesasEl.textContent = fmtBRL(totalDesp);

      // Update y-labels
      const yLabels = document.querySelector('#fluxo-chart .y-labels');
      if (yLabels) {
        yLabels.innerHTML = [
          maxVal,
          Math.floor(maxVal * 0.75),
          Math.floor(maxVal * 0.5),
          Math.floor(maxVal * 0.25),
          0
        ]
          .map(v => {
            if (v >= 1000000)
              return '<span>' + (v / 1000000).toFixed(1).replace('.0', '') + 'M</span>';
            if (v >= 1000) return '<span>' + (v / 1000).toFixed(0) + 'k</span>';
            return '<span>' + v + '</span>';
          })
          .join('');
      }
      const gridLines = chartRoot.querySelector('.grid-lines');
      if (gridLines) gridLines.innerHTML = '<i class="grid-line"></i>'.repeat(5);

      // Update badge
      if (chartBadge) chartBadge.textContent = fmtBRL(totalRec - totalDesp);
      updateChartRangeLabel();

      // Render bars
      barsGroup.innerHTML = labels
        .map((label, i) => {
          const receita = receitas[i] || 0;
          const despesa = despesas[i] || 0;
          const isCurrentDay = days[i] === isoDate(new Date());
          const rH = Math.max((receita / maxVal) * 100, 0);
          const dH = Math.max((despesa / maxVal) * 100, 0);
          // Todas as barras usam a mesma escala linear, sem piso de altura.
          const rHeight = rH + '%';
          const dHeight = dH + '%';
          const currentLabel =
            isCurrentDay && (receita > 0 || despesa > 0)
              ? '<span class="current-day-value">Hoje: ' +
                escapeHTML(fmtBRL(receita - despesa)) +
                '</span>'
              : '';
          return (
            '<div class="bar-col' +
            (isCurrentDay ? ' current-day' : '') +
            '" tabindex="0" aria-label="' +
            escapeHTML(label) +
            ': receitas ' +
            fmtBRL(receita) +
            ', despesas ' +
            fmtBRL(despesa) +
            '">' +
            currentLabel +
            '<div class="bar-tip"><strong>' +
            escapeHTML(label) +
            (isCurrentDay ? ' · Hoje' : '') +
            '</strong><span>Receitas ' +
            fmtBRL(receita) +
            '</span><span>Despesas ' +
            fmtBRL(despesa) +
            '</span></div>' +
            '<div class="bar-group">' +
            '<div class="bar income-bar' +
            (rH < 3 ? ' small-value' : '') +
            (rH < 0.1 ? ' subpixel-value' : '') +
            '"' +
            (receita > 0 ? '' : ' hidden') +
            ' style="height:' +
            rHeight +
            '" title="Receitas: ' +
            fmtBRL(receita) +
            '"></div>' +
            '<div class="bar expense-bar' +
            (dH < 3 ? ' small-value' : '') +
            (dH < 0.1 ? ' subpixel-value' : '') +
            '"' +
            (despesa > 0 ? '' : ' hidden') +
            ' style="height:' +
            dHeight +
            '" title="Despesas: ' +
            fmtBRL(despesa) +
            '"></div>' +
            '</div><span class="cashflow-day-label" aria-hidden="true">' +
            escapeHTML(label) +
            '</span></div>'
          );
        })
        .join('');

      // Update x-labels
      if (xLabels) {
        // Reserva a altura das datas, que compartilham a coluna das barras.
        xLabels.innerHTML = '';
      }
      const scroll = chartRoot.closest('.cashflow-chart-scroll');
      if (scroll) {
        const current = barsGroup.querySelector('.current-day');
        if (current) {
          const relativeLeft =
            current.getBoundingClientRect().left -
            scroll.getBoundingClientRect().left +
            scroll.scrollLeft;
          scroll.scrollLeft = Math.max(0, relativeLeft - scroll.clientWidth / 2);
        } else scroll.scrollLeft = scroll.scrollWidth;
      }
    } catch (e) {
      console.error('Error loading chart:', e);
      const chartRoot = document.getElementById('fluxo-chart');
      const xLabels = document.getElementById('x-labels');
      if (chartRoot) {
        chartRoot.classList.add('is-empty');
        chartRoot.innerHTML =
          '<div class="chart-empty">Não foi possível carregar o fluxo de caixa.</div>';
      }
      if (xLabels) {
        xLabels.innerHTML = '';
        xLabels.hidden = true;
      }
      document.querySelector('.cashflow-card .chart-legend')?.setAttribute('hidden', '');
      if (window.__fcPageToken === token) toast('Erro ao carregar gráfico', 'error');
    }
  }

  // ── Load Categories ──
  async function loadCategories() {
    const token = window.__fcPageToken;
    const days = currentDays;
    try {
      // Categorias precisam respeitar o mesmo filtro temporal dos demais blocos.
      const data = await apiGet('/categorias', { tipo: 'despesa', days });
      if (window.__fcPageToken !== token || days !== currentDays) return;
      const pending = (data.categorias || []).reduce((sum, c) => sum + Number(c.pendente || 0), 0);
      const categorias = (data.categorias || [])
        .map(category => ({ ...category, valor: Number(category.valor) || 0 }))
        .filter(category => category.valor > 0);
      const container = document.getElementById('cat-list');
      const badge = document.getElementById('cat-badge');
      const totalEl = document.getElementById('cat-total');
      const countEl = document.getElementById('cat-count');

      if (!container) return;

      if (!categorias.length) {
        if (totalEl) totalEl.textContent = fmtBRL(0);
        if (countEl) countEl.textContent = '0';
        if (badge) badge.textContent = pending > 0 ? 'A pagar' : 'Sem despesas';
        container.innerHTML =
          '<div class="empty-state">Nenhuma despesa paga no período selecionado.' +
          (pending > 0 ? '<br>Pendente: ' + fmtBRL(pending) : '') +
          '</div>';
        return;
      }

      const total = categorias.reduce((s, c) => s + (c.valor || 0), 0);
      const colors = [
        'var(--sage)',
        'var(--blue)',
        'var(--amber)',
        'var(--red)',
        'var(--sage-light)',
        '#8e6bb5'
      ];

      if (badge) badge.textContent = fmtBRL(total);
      if (totalEl) totalEl.textContent = fmtBRL(total);
      if (countEl) countEl.textContent = String(categorias.length);

      container.innerHTML = categorias
        .map((cat, i) => {
          const pct = total > 0 ? ((cat.valor / total) * 100).toFixed(0) : 0;
          const color = colors[i % colors.length];
          return (
            '<div class="cat-item">' +
            '<div class="cat-color" style="background:' +
            color +
            ';"></div>' +
            '<span class="cat-name">' +
            escapeHTML(cat.nome || cat.categoria_nome || '—') +
            '</span>' +
            '<div class="cat-bar"><div class="cat-bar-fill" style="width:' +
            pct +
            '%;background:' +
            color +
            ';"></div></div>' +
            '<span class="cat-amount">' +
            fmtBRL(cat.valor || 0) +
            '</span>' +
            '</div>'
          );
        })
        .join('');
    } catch (e) {
      console.error('Error loading categories:', e);
      const container = document.getElementById('cat-list');
      if (container)
        container.innerHTML =
          '<div class="empty-state">Não foi possível carregar as despesas por categoria.</div>';
      if (window.__fcPageToken === token) toast('Erro ao carregar categorias', 'error');
    }
  }

  // ── Load Transactions ──
  async function toggleExpenseDetails() {
    const container = document.getElementById('cat-list');
    const button = document.getElementById('btn-cat-details');
    if (!container || !button) return;
    if (expenseDetailsVisible) {
      expenseDetailsVisible = false;
      button.textContent = 'Ver detalhes';
      button.setAttribute('aria-expanded', 'false');
      loadCategories();
      return;
    }
    expenseDetailsVisible = true;
    button.textContent = 'Ocultar detalhes';
    button.setAttribute('aria-expanded', 'true');
    container.innerHTML = '<div class="empty-state">Carregando lançamentos...</div>';
    try {
      const requestedDays = currentDays;
      const data = await apiGet('/transacoes', { days: requestedDays, limit: 500 });
      if (!expenseDetailsVisible || requestedDays !== currentDays || window.__fcPageToken !== token)
        return;
      const despesas = (data.transacoes || []).filter(
        t => t.tipo === 'despesa' && t.status === 'pago'
      );
      if (!despesas.length) {
        container.innerHTML =
          '<div class="empty-state">Nenhuma despesa paga no período selecionado.</div>';
        return;
      }
      container.innerHTML =
        '<div class="expense-detail-head"><span>Descrição e categoria</span><span>Data</span><span>Valor</span></div>' +
        despesas
          .map(
            t =>
              '<article class="expense-detail-item">' +
              '<div class="expense-detail-main"><strong>' +
              escapeHTML(t.descricao || '—') +
              '</strong><span>' +
              escapeHTML(t.categoria_nome || 'Sem categoria') +
              '</span></div>' +
              '<time datetime="' +
              escapeHTML(String(t.data_transacao || '').slice(0, 10)) +
              '">' +
              fmtDate(t.data_transacao) +
              '</time>' +
              '<strong class="expense-detail-value">' +
              fmtBRL(t.valor) +
              '</strong>' +
              '</article>'
          )
          .join('');
    } catch (e) {
      console.error('Error loading expense details:', e);
      container.innerHTML =
        '<div class="empty-state">Não foi possível carregar os lançamentos detalhados.</div>';
    }
  }

  const expenseCard = document.getElementById('cat-list')?.closest('.card');
  if (expenseCard) {
    expenseCard.classList.add('expense-category-card');
    const head = expenseCard.querySelector('.card-head');
    if (head) {
      const detailsButton = document.createElement('button');
      detailsButton.type = 'button';
      detailsButton.id = 'btn-cat-details';
      detailsButton.className = 'expense-details-toggle';
      detailsButton.textContent = 'Ver detalhes';
      detailsButton.setAttribute('aria-expanded', 'false');
      detailsButton.addEventListener('click', toggleExpenseDetails);
      head.appendChild(detailsButton);
    }
  }

  async function loadTransactions() {
    const requestedDays = currentDays;
    try {
      const data = await apiGet('/transacoes', { days: requestedDays });
      if (requestedDays !== currentDays || window.__fcPageToken !== token) return;
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
      tbody.innerHTML =
        '<tr><td colspan="6" style="text-align:center;color:var(--ink-35);padding:24px;">Nenhuma transação encontrada</td></tr>';
      return;
    }
    tbody.innerHTML = transacoes
      .map(t => {
        const statusClass =
          t.status === 'pago' ? 'chip-green' : t.status === 'pendente' ? 'chip-amber' : 'chip-red';
        const valorClass = t.tipo === 'receita' ? 'receita-val' : 'despesa-val';
        return (
          '<tr>' +
          '<td><span style="font-weight:500;">' +
          escapeHTML(t.descricao || '—') +
          '</span></td>' +
          '<td style="color:var(--ink-35);font-size:12px;">' +
          escapeHTML(t.categoria_nome || '—') +
          '</td>' +
          '<td class="r ' +
          valorClass +
          '" style="font-weight:500;">' +
          (t.tipo === 'receita' ? '+' : '−') +
          fmtBRL(t.valor) +
          '</td>' +
          '<td style="font-size:12px;">' +
          escapeHTML(metodoLabels[t.metodo_pagamento] || t.metodo_pagamento || '—') +
          '</td>' +
          '<td><span class="chip ' +
          statusClass +
          '">' +
          escapeHTML(statusLabels[t.status] || t.status) +
          '</span></td>' +
          '<td style="font-size:12px;color:var(--ink-35);">' +
          fmtDate(t.data_transacao) +
          '</td>' +
          '</tr>'
        );
      })
      .join('');
  }

  // ── Load All ──
  async function loadAll() {
    await Promise.all([loadKPIs(), loadChart(), loadCategories(), loadTransactions()]);
  }

  window.fcPageListen(document, 'visibilitychange', () => {
    if (!document.hidden && window.__fcPageToken === token) loadAll();
  });
  window.__fcSetInterval?.(() => {
    if (!document.hidden && window.__fcPageToken === token) loadAll();
  }, 30000);

  // ── Period Filters ──
  document.querySelectorAll('#period-filters .ghost-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document
        .querySelectorAll('#period-filters .ghost-btn')
        .forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentDays = parseInt(btn.dataset.days);
      loadAll();
    });
  });

  document.querySelectorAll('[data-chart-period]').forEach(btn => {
    btn.addEventListener('click', () => {
      chartPeriod = btn.dataset.chartPeriod;
      document
        .querySelectorAll('[data-chart-period]')
        .forEach(item => item.classList.toggle('active', item === btn));
      updateChartRangeLabel();
      loadChart();
    });
  });
  document.getElementById('chart-prev')?.addEventListener('click', () => {
    if (chartPeriod === 'week') chartCursor.setDate(chartCursor.getDate() - 7);
    else {
      chartCursor.setDate(1);
      chartCursor.setMonth(chartCursor.getMonth() - 1);
    }
    updateChartRangeLabel();
    loadChart();
  });
  document.getElementById('chart-next')?.addEventListener('click', () => {
    if (chartPeriod === 'week') chartCursor.setDate(chartCursor.getDate() + 7);
    else {
      chartCursor.setDate(1);
      chartCursor.setMonth(chartCursor.getMonth() + 1);
    }
    updateChartRangeLabel();
    loadChart();
  });
  updateChartRangeLabel();

  // ── Refresh Button ──
  const btnRefresh = document.getElementById('btn-refresh');
  if (btnRefresh) {
    btnRefresh.addEventListener('click', () => {
      btnRefresh.style.opacity = '0.5';
      loadAll().then(() => {
        btnRefresh.style.opacity = '1';
      });
    });
  }

  // ── Modal: Nova Transação ──
  const btnNova = document.getElementById('btn-nova-transacao');
  if (btnNova) {
    btnNova.addEventListener('click', () => {
      const modal = document.getElementById('modal-nova-transacao');
      if (modal) {
        const dataInput = document.getElementById('tx-data');
        if (dataInput && !dataInput.value) dataInput.value = isoDate(new Date());
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
  window.fcPageListen(document, 'click', e => {
    if (e.target.classList.contains('modal-overlay') && e.target.id === 'modal-nova-transacao') {
      closeTransModal();
    }
  });

  // Close on Escape
  window.fcPageListen(document, 'keydown', e => {
    if (e.key === 'Escape') closeTransModal();
  });

  async function loadCategoriesForModal() {
    try {
      const tipo = document.getElementById('tx-tipo')?.value || 'receita';
      const data = await apiGet('/categorias', { tipo: tipo });
      const select = document.getElementById('tx-categoria');
      if (!select) return;
      select.innerHTML =
        '<option value="">Selecione...</option>' +
        (data.categorias || [])
          .map(
            c =>
              '<option value="' +
              escapeHTML(c.id || '') +
              '">' +
              escapeHTML(c.nome || c.categoria_nome || '') +
              '</option>'
          )
          .join('');
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
      const dataTransacao = document.getElementById('tx-data')?.value;
      const metodo = document.getElementById('tx-metodo')?.value;

      if (!categoriaId || !descricao || !valor || valor <= 0 || !dataTransacao) {
        toast('Preencha todos os campos obrigatórios', 'error');
        return;
      }

      try {
        const res = await fetch(API + '/transacoes', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({
            tipo,
            categoria_id: parseInt(categoriaId),
            descricao,
            valor,
            data_transacao: dataTransacao,
            metodo_pagamento: metodo
          })
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
        const rows = transacoes
          .map(
            t =>
              '"' +
              (t.descricao || '').replace(/"/g, '""') +
              '",' +
              '"' +
              (t.categoria_nome || '') +
              '",' +
              (t.tipo || '') +
              ',' +
              (t.valor || 0) +
              ',' +
              '"' +
              (metodoLabels[t.metodo_pagamento] || '') +
              '",' +
              '"' +
              (statusLabels[t.status] || '') +
              '",' +
              '"' +
              (t.data_transacao || '') +
              '"'
          )
          .join('\n');
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
