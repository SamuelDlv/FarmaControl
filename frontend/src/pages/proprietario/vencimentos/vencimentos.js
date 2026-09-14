/* ══════════════════════════════════════════════════════════════════════
 * FARMAControl — CONTROLE DE VENCIMENTOS (PROPRIETÁRIO)
 * ══════════════════════════════════════════════════════════════════════
 *
 * Monitora lotes de medicamentos próximos do vencimento:
 * - Grid visual de lotes com dias restantes (cores: verde/amarelo/vermelho)
 * - Timeline de vencimentos (próximos 30/60/90 dias)
 * - Filtros por status (todos, expirados, expirando, válidos)
 * - Modal de detalhe do lote
 * - Modal de descarte (baixa de lote expirado)
 * - Lista de categorias com alertas
 *
 * Dados são carregados da API: GET /vencimentos/*
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

/* ══════════════════════════════════════════════
   FarmaControl — vencimentos.js
══════════════════════════════════════════════ */

var API_BASE = window.FarmaControlSettings ? window.FarmaControlSettings.API_BASE : 'http://localhost:5000';
var lotes = [];

  /* getUsuarioId(): Retorna o ID do usuário logado (localStorage). */
  function getUsuarioId() {
  try {
    const raw = sessionStorage.getItem('farmacontrol_usuario');
    return raw ? JSON.parse(raw).id : null;
  } catch { return null; }
}

  /* fetchLotes(): Busca todos os lotes com suas datas de validade. */
  async function fetchLotes() {
  const token = window.__fcPageToken;
  try {
    const res = await fetch(`${API_BASE}/estoque`);
    if (window.__fcPageToken !== token) return;
    const data = await res.json();
    if (data.ok) {
      lotes = data.estoque.map(item => ({
        id:         item.id,
        produto_id: item.produto_id,
        nome:       item.produto_nome                          || '—',
        principio:  item.principio_ativo || item.produto_principio || '',
        lote:       item.lote                                  || '—',
        categoria:  item.categoria       || item.produto_categoria || 'Geral',
        qty:        item.quantidade      || 0,
        validade:   (item.data_validade  || '').split('T')[0],
        fornecedor: item.fornecedor_nome || item.produto_fabricante || '',
      }));
      renderAll();
    } else {
      console.error('Erro ao buscar lotes:', data.mensagem);
    }
  } catch (err) {
    console.error('Erro ao buscar lotes:', err);
  }
}

  /* renderAll(): Renderiza toda a página (grid, timeline, tabela, listas). */
  function renderAll() {
  updateKPIs();
  renderTimeline();
  renderTable();
  renderCatList();
}



/* ── Estado ── */
var activeFilter = 'all';
var currentPage = 1;
var PAGE_SIZE = 8;
var searchQ      = '';
var filterCat    = '';
var sortMode     = 'dias-asc';
var selectedLoteId = null;
var baixaTipo    = 'descarte';

/* ── Helpers ── */
var today = () => new Date();

  /* diasRestantes(): Calcula quantos dias restam até o vencimento de um lote. */
  function diasRestantes(iso) {
  const diff = (new Date(iso) - today()) / 86400000;
  return Math.round(diff);
}

  /* fmtDate(): Formata data ISO para formato brasileiro. */
  function fmtDate(iso) {
  if (!iso) return '—';
  const [y, m, d] = iso.split('-');
  return `${d}/${m}/${y}`;
}

  /* getStatusClass(): Retorna a classe CSS do status (ok/warning/danger). */
  function getStatusClass(dias) {
  if (dias < 0)   return 'exp';
  if (dias <= 30)  return 'crit';
  if (dias <= 60)  return 'warn';
  return 'ok';
}

  /* getStatusLabel(): Retorna o label do status (Válido, Vencendo, Expirado). */
  function getStatusLabel(dias) {
  if (dias < 0)   return 'Vencido';
  if (dias <= 30)  return `${dias}d restantes`;
  if (dias <= 60)  return `${dias}d restantes`;
  return `${dias}d restantes`;
}

  /* getChipLabel(): Retorna o label curto do chip de dias restantes. */
  function getChipLabel(dias) {
  if (dias < 0)   return 'Vencido';
  if (dias <= 30)  return 'Crítico';
  if (dias <= 60)  return 'Atenção';
  return 'Regular';
}

  /* getChipClass(): Retorna a classe CSS do chip de dias restantes. */
  function getChipClass(dias) {
  if (dias < 0)   return 'chip-exp';
  if (dias <= 30)  return 'chip-crit';
  if (dias <= 60)  return 'chip-warn';
  return 'chip-ok';
}

/* ── Filtrar + Ordenar ── */
function getFiltered() {
  return lotes.filter(l => {
    const dias = diasRestantes(l.validade);
    const st = getStatusClass(dias);
    const matchFilter =
      activeFilter === 'all'  ||
      activeFilter === 'exp'  && st === 'exp'  ||
      activeFilter === 'crit' && st === 'crit' ||
      activeFilter === 'warn' && st === 'warn' ||
      activeFilter === 'ok'   && st === 'ok';
    const matchQ   = !searchQ || l.nome.toLowerCase().includes(searchQ) || l.lote.toLowerCase().includes(searchQ) || l.principio.toLowerCase().includes(searchQ);
    const matchCat = !filterCat || l.categoria === filterCat;
    return matchFilter && matchQ && matchCat;
  }).sort((a, b) => {
    const da = diasRestantes(a.validade);
    const db = diasRestantes(b.validade);
    if (sortMode === 'dias-asc')   return da - db;
    if (sortMode === 'dias-desc')  return db - da;
    if (sortMode === 'nome')       return a.nome.localeCompare(b.nome);
    if (sortMode === 'qty-desc')   return b.qty - a.qty;
    return 0;
  });
}

/* ══ KPIs ══ */
function updateKPIs() {
  if (!document.getElementById('expiry-list')) return;
  const vencidos = lotes.filter(l => diasRestantes(l.validade) < 0).length;
  const crit30   = lotes.filter(l => { const d = diasRestantes(l.validade); return d >= 0 && d <= 30; }).length;
  const warn60   = lotes.filter(l => { const d = diasRestantes(l.validade); return d > 30 && d <= 60; }).length;
  const ok       = lotes.filter(l => diasRestantes(l.validade) > 60).length;

  animateCounter(document.getElementById('kpi-vencidos'), vencidos);
  animateCounter(document.getElementById('kpi-30dias'),   crit30);
  animateCounter(document.getElementById('kpi-60dias'),   warn60);
  animateCounter(document.getElementById('kpi-ok'),       ok);

  const d30 = document.getElementById('kpi-30-delta');
  const d60 = document.getElementById('kpi-60-delta');
  const dok = document.getElementById('kpi-ok-delta');
  if (d30) d30.textContent  = crit30 > 0 ? `${crit30} lote${crit30 > 1 ? 's' : ''} requer${crit30 === 1 ? '' : 'em'} ação` : 'Nenhum alerta';
  if (d60) d60.textContent  = warn60 > 0 ? `Monitorar ${warn60} lote${warn60 > 1 ? 's' : ''}` : 'Tudo sob controle';
  if (dok) dok.textContent  = `${lotes.length ? Math.round(ok / lotes.length * 100) : 0}% do total`;

  // Sidebar badge
  const alertas = vencidos + crit30;
  const sbBadge = document.getElementById('sb-badge-venc');
  if (sbBadge) sbBadge.textContent = alertas;
}

  /* animateCounter(): Anima um contador numérico de 0 até o valor alvo. */
  function animateCounter(el, target) {
  if (!el) return;
  const ease = t => t < 0.5 ? 2*t*t : -1+(4-2*t)*t;
  const t0 = performance.now();
  (function step(now) {
    const p = Math.min((now - t0) / 700, 1);
    el.textContent = Math.round(ease(p) * target);
    if (p < 1) requestAnimationFrame(step);
  })(t0);
}

/* ══ TIMELINE ══ */
function renderTimeline() {
  if (!document.getElementById('timeline')) return;
  const wrap = document.getElementById('timeline-wrap');
  if (!wrap) return;

  // Ordenar por validade (mais urgente primeiro)
  const sorted = [...lotes].sort((a, b) => new Date(a.validade) - new Date(b.validade));
  const maxDias = Math.max(...sorted.map(l => Math.max(diasRestantes(l.validade), 0)));

  document.getElementById('timeline-badge').textContent = `${sorted.length} lotes`;

  // Agrupar por status
  const groups = [
    { key: 'exp',  label: 'Vencido',    items: sorted.filter(l => getStatusClass(diasRestantes(l.validade)) === 'exp') },
    { key: 'crit', label: '≤ 30 dias',   items: sorted.filter(l => getStatusClass(diasRestantes(l.validade)) === 'crit') },
    { key: 'warn', label: '31–60 dias',  items: sorted.filter(l => getStatusClass(diasRestantes(l.validade)) === 'warn') },
    { key: 'ok',   label: '> 60 dias',  items: sorted.filter(l => getStatusClass(diasRestantes(l.validade)) === 'ok') },
  ].filter(g => g.items.length > 0);

  const rowsHtml = groups.map(g => {
    const sepHtml = `
      <div class="tl-group-sep">
        <span class="tl-group-label ${g.key}">${g.label}</span>
        <span class="tl-group-line"></span>
      </div>`;

    const itemsHtml = g.items.map(l => {
      const dias = diasRestantes(l.validade);
      const cls  = getStatusClass(dias);
      const pct  = dias < 0 ? 100 : maxDias > 0 ? Math.max((1 - dias / maxDias) * 100, 4) : 4;
      const label = dias < 0 ? `Vencido há ${Math.abs(dias)}d` : dias === 0 ? 'Vence hoje' : `${dias}d`;
      return `
        <div class="tl-row tl-row--${cls}" data-id="${l.id}" title="${l.nome} · Lote ${l.lote} · ${l.categoria}">
          <span class="tl-row-name">${l.nome}</span>
          <span class="tl-row-lote">${l.lote}</span>
          <div class="tl-bar-track">
            <div class="tl-bar-fill ${cls}" style="width:${pct.toFixed(1)}%"></div>
          </div>
          <span class="tl-row-days ${cls}">${label}</span>
        </div>`;
    }).join('');

    return sepHtml + itemsHtml;
  }).join('');

  wrap.innerHTML = rowsHtml;

  wrap.querySelectorAll('.tl-row').forEach(row => {
    row.addEventListener('click', () => {
      const l = lotes.find(x => x.id === +row.dataset.id);
      if (l) openDetail(l);
    });
  });
}

/* ══ TABLE ══ */
function renderTable() {
  if (!document.getElementById('table-body')) return;
  const filtered = getFiltered();
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  currentPage = Math.min(currentPage, totalPages);

  const slice = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  const tbody = document.getElementById('table-body');

  document.getElementById('filter-count').textContent = `Exibindo ${slice.length} de ${filtered.length} item${filtered.length !== 1 ? 's' : ''}`;
  document.getElementById('table-count-badge').textContent = `${filtered.length} item${filtered.length !== 1 ? 's' : ''}`;
  document.getElementById('page-indicator').textContent = `${currentPage} / ${totalPages}`;
  document.getElementById('btn-prev').disabled = currentPage <= 1;
  document.getElementById('btn-next').disabled = currentPage >= totalPages;

  tbody.innerHTML = slice.map(l => {
    const dias = diasRestantes(l.validade);
    const cls  = getStatusClass(dias);
    const rowCls = cls === 'exp' ? 'row-exp' : cls === 'crit' ? 'row-crit' : '';
    const barPct = dias < 0 ? 100 : Math.max(Math.min((1 - dias / 365) * 100, 96), 4);
    const chipLabel = getChipLabel(dias);
    const chipCls   = getChipClass(dias);
    const daysLabel = dias < 0 ? `Vencido há ${Math.abs(dias)}d` : dias === 0 ? 'Hoje' : `${dias} dias`;

    return `
      <tr class="${rowCls}" data-id="${l.id}">
        <td>
          <div class="med-name">${l.nome}</div>
          <div class="med-meta">${l.principio} · ${l.fornecedor}</div>
        </td>
        <td><span class="lote-pill">${l.lote}</span></td>
        <td>${l.categoria}</td>
        <td class="r"><span class="qty-val">${l.qty}</span></td>
        <td>${fmtDate(l.validade)}</td>
        <td>
          <div class="days-cell">
            <div class="days-bar-track">
              <div class="days-bar-fill ${cls}" style="width:${barPct.toFixed(0)}%"></div>
            </div>
            <span class="days-num ${cls}">${daysLabel}</span>
          </div>
        </td>
        <td><span class="chip ${chipCls}">${chipLabel}</span></td>
        <td class="c">
          <div class="row-actions">
            <button class="action-btn" title="Ver detalhes" data-action="detail" data-id="${l.id}">
              <svg viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.25"/><path d="M8 7.5v4M8 5v.5" stroke="currentColor" stroke-width="1.25" stroke-linecap="round"/></svg>
            </button>
            <button class="action-btn danger" title="Registrar descarte / devolução" data-action="descarte" data-id="${l.id}">
              <svg viewBox="0 0 16 16" fill="none"><path d="M3 4h10M5.5 4V3a.5.5 0 01.5-.5h4a.5.5 0 01.5.5v1M6 7v4.5M10 7v4.5" stroke="currentColor" stroke-width="1.25" stroke-linecap="round"/><rect x="3" y="4" width="10" height="9" rx="1" stroke="currentColor" stroke-width="1.25"/></svg>
            </button>
          </div>
        </td>
      </tr>`;
  }).join('');

  tbody.querySelectorAll('[data-action="detail"]').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      const l = lotes.find(x => x.id === +btn.dataset.id);
      if (l) openDetail(l);
    });
  });

  tbody.querySelectorAll('[data-action="descarte"]').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      const l = lotes.find(x => x.id === +btn.dataset.id);
      if (l) openDescarte(l);
    });
  });
}

/* ══ SIDE PANEL: Por Categoria ══ */
function renderCatList() {
  if (!document.getElementById('cat-list')) return;
  const catMap = {};
  lotes.forEach(l => {
    if (!catMap[l.categoria]) catMap[l.categoria] = { exp: 0, warn: 0, ok: 0, total: 0 };
    const dias = diasRestantes(l.validade);
    catMap[l.categoria].total++;
    if (dias < 0 || dias <= 30)  catMap[l.categoria].exp++;
    else if (dias <= 60)          catMap[l.categoria].warn++;
    else                          catMap[l.categoria].ok++;
  });

  const cats = Object.entries(catMap).sort((a, b) => b[1].exp - a[1].exp);
  const colors = ['#4a7c59','#b87a1a','#2e6da4','#c03a3a','#8b6ea4','#3a9968','#b8892e','#5a7a8a'];

  document.getElementById('cat-list').innerHTML = cats.map(([nome, c], i) => `
    <div class="cat-item">
      <span class="cat-dot" style="background:${colors[i % colors.length]}"></span>
      <span class="cat-name">${nome}</span>
      <div class="cat-counts">
        ${c.exp  > 0 ? `<span class="cat-chip exp">${c.exp}</span>` : ''}
        ${c.warn > 0 ? `<span class="cat-chip warn">${c.warn}</span>` : ''}
        ${c.ok   > 0 ? `<span class="cat-chip ok">${c.ok}</span>` : ''}
      </div>
    </div>
  `).join('');
}

/* ══ SIDE PANEL: Ações Sugeridas ══ */
function renderActionList() {
  const actions = [];

  const expired = lotes.filter(l => diasRestantes(l.validade) < 0);
  if (expired.length > 0) {
    actions.push({
      cls: 'exp', icon: `<svg viewBox="0 0 16 16" fill="none"><path d="M8 2L14.5 13.5H1.5L8 2Z" stroke="currentColor" stroke-width="1.25" stroke-linejoin="round"/><path d="M8 7v2.5M8 11v.5" stroke="currentColor" stroke-width="1.25" stroke-linecap="round"/></svg>`,
      title: `Descartar ${expired.length} lote${expired.length > 1 ? 's' : ''} vencido${expired.length > 1 ? 's' : ''}`,
      desc: expired.slice(0, 2).map(l => l.nome).join(', ') + (expired.length > 2 ? ` e mais ${expired.length - 2}` : ''),
    });
  }

  const crit = lotes.filter(l => { const d = diasRestantes(l.validade); return d >= 0 && d <= 30; });
  if (crit.length > 0) {
    actions.push({
      cls: 'warn', icon: `<svg viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.25"/><path d="M8 5v3.5" stroke="currentColor" stroke-width="1.25" stroke-linecap="round"/><circle cx="8" cy="11" r=".75" fill="currentColor"/></svg>`,
      title: `Priorizar venda: ${crit.length} lote${crit.length > 1 ? 's' : ''} crítico${crit.length > 1 ? 's' : ''}`,
      desc: `Vence${crit.length > 1 ? 'm' : ''} nos próximos 30 dias — considere promoção`,
    });
  }

  const altoCusto = lotes.filter(l => { const d = diasRestantes(l.validade); return d >= 0 && d <= 60 && l.qty > 50; });
  if (altoCusto.length > 0) {
    actions.push({
      cls: 'warn', icon: `<svg viewBox="0 0 16 16" fill="none"><path d="M8 2v12M5 5.5a3 3 0 013-3 3 3 0 013 3v1a3 3 0 01-3 3 3 3 0 01-3-3" stroke="currentColor" stroke-width="1.25" stroke-linecap="round"/></svg>`,
      title: 'Negociar devolução ao fornecedor',
      desc: `${altoCusto.length} lote${altoCusto.length > 1 ? 's' : ''} com alto volume vence em até 60 dias`,
    });
  }

  actions.push({
    cls: 'ok', icon: `<svg viewBox="0 0 16 16" fill="none"><path d="M3 8l3.5 3.5L13 5" stroke="currentColor" stroke-width="1.25" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
    title: 'Relatório de vencimentos',
    desc: 'Exporte o relatório mensal para auditoria e SNGPC',
  });

  document.getElementById('action-list').innerHTML = actions.map(a => `
    <li class="action-item">
      <div class="action-ico ${a.cls}">${a.icon}</div>
      <div class="action-body">
        <div class="action-title">${a.title}</div>
        <div class="action-desc">${a.desc}</div>
      </div>
    </li>
  `).join('');
}

/* ══ MODAL: Detail ══ */
function openDetail(l) {
  const dias = diasRestantes(l.validade);
  const cls  = getStatusClass(dias);
  const chipLabel = getChipLabel(dias);
  const chipCls   = getChipClass(dias);
  const daysLabel = dias < 0 ? `Vencido há ${Math.abs(dias)} dias` : dias === 0 ? 'Vence hoje' : `${dias} dias restantes`;

  document.getElementById('detail-product-name').textContent = `${l.nome} · ${l.lote}`;
  document.getElementById('detail-body').innerHTML = `
    <div class="detail-grid">
      <div class="detail-field">
        <span class="detail-label">Medicamento</span>
        <span class="detail-value">${l.nome}</span>
      </div>
      <div class="detail-field">
        <span class="detail-label">Princípio Ativo</span>
        <span class="detail-value">${l.principio}</span>
      </div>
      <div class="detail-field">
        <span class="detail-label">Lote</span>
        <span class="detail-value">${l.lote}</span>
      </div>
      <div class="detail-field">
        <span class="detail-label">Categoria</span>
        <span class="detail-value">${l.categoria}</span>
      </div>
      <div class="detail-field">
        <span class="detail-label">Validade</span>
        <span class="detail-value">${fmtDate(l.validade)}</span>
      </div>
      <div class="detail-field">
        <span class="detail-label">Situação</span>
        <span class="detail-value"><span class="chip ${chipCls}">${chipLabel}</span></span>
      </div>
      <div class="detail-field">
        <span class="detail-label">Quantidade em Estoque</span>
        <span class="detail-value big">${l.qty}</span>
      </div>
      <div class="detail-field">
        <span class="detail-label">Dias Restantes</span>
        <span class="detail-value big days-num ${cls}">${daysLabel}</span>
      </div>
      <div class="detail-field" style="grid-column:1/-1">
        <span class="detail-label">Fornecedor</span>
        <span class="detail-value">${l.fornecedor}</span>
      </div>
    </div>`;

  openOverlay('detail-overlay');
}

/* ══ MODAL: Descarte ══ */
function openDescarte(l) {
  selectedLoteId = l.id;
  document.getElementById('descarte-product-name').textContent = `${l.nome} · ${l.lote}`;
  document.getElementById('descarte-current-qty').textContent = l.qty;
  document.getElementById('descarte-qty').value = '';
  document.getElementById('descarte-motivo').value = '';
  document.getElementById('descarte-obs').value = '';

  // Auto-select motivo se vencido
  if (diasRestantes(l.validade) < 0) {
    document.getElementById('descarte-motivo').value = 'Produto vencido';
  }

  openOverlay('descarte-overlay');
}

/* ── Overlay helpers ── */
function openOverlay(id) {
  document.getElementById(id).classList.add('open');
  document.body.style.overflow = 'hidden';
}
  /* closeOverlay(): Fecha um overlay/modal pelo ID. */
  function closeOverlay(id) {
  document.getElementById(id).classList.remove('open');
  document.body.style.overflow = '';
}

/* ── Close modals ── */
document.getElementById('detail-close')?.addEventListener('click',   () => closeOverlay('detail-overlay'));
document.getElementById('descarte-close')?.addEventListener('click', () => closeOverlay('descarte-overlay'));
document.getElementById('descarte-cancel')?.addEventListener('click',() => closeOverlay('descarte-overlay'));

document.querySelectorAll('.modal-overlay').forEach(overlay => {
  overlay.addEventListener('click', e => {
    if (e.target === overlay) closeOverlay(overlay.id);
  });
});

/* ── Baixa tipo buttons ── */
document.getElementById('baixa-btn-descarte')?.addEventListener('click', () => {
  baixaTipo = 'descarte';
  document.getElementById('baixa-btn-descarte').classList.add('selected');
  document.getElementById('baixa-btn-devolucao').classList.remove('selected');
});
document.getElementById('baixa-btn-devolucao')?.addEventListener('click', () => {
  baixaTipo = 'devolucao';
  document.getElementById('baixa-btn-devolucao').classList.add('selected');
  document.getElementById('baixa-btn-descarte').classList.remove('selected');
});

/* ── Salvar descarte ── */
document.getElementById('descarte-save')?.addEventListener('click', async () => {
  const l   = lotes.find(x => x.id === selectedLoteId);
  if (!l) return;
  const qty = +document.getElementById('descarte-qty').value;
  if (!qty || qty <= 0 || qty > l.qty) {
    showToast('Quantidade inválida.', 'warn');
    return;
  }
  const motivo = document.getElementById('descarte-motivo').value;
  if (!motivo) { showToast('Selecione um motivo.', 'warn'); return; }
  const obs    = document.getElementById('descarte-obs').value.trim();
  const uid    = getUsuarioId();
  if (!uid) { showToast('Sessão inválida. Faça login novamente.', 'err'); return; }

  const tipoMov = baixaTipo === 'devolucao' ? 'transferencia' : 'saida';
  const obsCompleta = `${baixaTipo === 'descarte' ? 'Descarte' : 'Devolução'}: ${motivo}${obs ? ' — ' + obs : ''}`;

  try {
    const res = await fetch(`${API_BASE}/movimentacoes-estoque`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        estoque_id:        l.id,
        usuario_id:        uid,
        tipo_movimentacao: tipoMov,
        quantidade:        qty,
        observacao:        obsCompleta,
      })
    });
    const result = await res.json();
    if (result.ok) {
      closeOverlay('descarte-overlay');
      await fetchLotes();
      showToast(`${baixaTipo === 'descarte' ? 'Descarte' : 'Devolução'} registrado: ${qty}x ${l.nome}.`, 'ok');
    } else {
      showToast(result.mensagem || 'Erro ao registrar baixa.', 'err');
    }
  } catch (e) {
    showToast('Erro de comunicação com o servidor.', 'err');
  }
});

/* ══ FILTERS & TABS ══ */
document.querySelectorAll('.ftab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.ftab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    activeFilter = tab.dataset.filter;
    currentPage  = 1;
    renderTable();
  });
});

document.getElementById('search-input')?.addEventListener('input', function() {
  searchQ     = this.value.toLowerCase().trim();
  currentPage = 1;
  renderTable();
});

document.getElementById('filter-cat')?.addEventListener('change', function() {
  filterCat   = this.value;
  currentPage = 1;
  renderTable();
});

document.getElementById('filter-sort')?.addEventListener('change', function() {
  sortMode    = this.value;
  currentPage = 1;
  renderTable();
});

/* ── Paginação ── */
document.getElementById('btn-prev')?.addEventListener('click', () => {
  if (currentPage > 1) { currentPage--; renderTable(); }
});
document.getElementById('btn-next')?.addEventListener('click', () => {
  const filtered = getFiltered();
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  if (currentPage < totalPages) { currentPage++; renderTable(); }
});

/* ══ TOPBAR BUTTONS ══ */
document.getElementById('btn-refresh')?.addEventListener('click', () => {
  const svg = document.querySelector('#btn-refresh svg');
  if (svg) {
    svg.style.transition = 'transform 0.6s';
    svg.style.transform  = 'rotate(360deg)';
    setTimeout(() => { svg.style.transition = 'none'; svg.style.transform = 'rotate(0)'; }, 650);
  }
  fetchLotes();
  showToast('Dados atualizados.', 'ok');
});

document.getElementById('btn-print')?.addEventListener('click', () => {
  showToast('Preparando impressão…', 'info');
  printVencimentos();
});

/* ══ IMPRESSÃO DE VENCIMENTOS ══ */
function printVencimentos() {
  const vencidos = document.getElementById('kpi-vencidos')?.textContent || '0';
  const d30      = document.getElementById('kpi-30dias')?.textContent || '0';
  const d60      = document.getElementById('kpi-60dias')?.textContent || '0';
  const ok       = document.getElementById('kpi-ok')?.textContent || '0';
  const dataHoje = new Date().toLocaleDateString('pt-BR', { weekday:'long', day:'numeric', month:'long', year:'numeric' });

  // Imprime todos os lotes (não apenas a página atual), respeitando o filtro ativo
  const lista = getFiltered();

  const rows = lista.map(l => {
    const dias = diasRestantes(l.validade);
    let stCls = 'status-ok', stTxt = 'Regular';
    if (dias < 0)      { stCls = 'status-vencido'; stTxt = 'Vencido'; }
    else if (dias <= 30) { stCls = 'status-30'; stTxt = 'Crítico'; }
    else if (dias <= 60) { stCls = 'status-60'; stTxt = 'Atenção'; }
    return `      <tr>
        <td class="med">${l.nome}</td>
        <td class="meta">${l.principio}</td>
        <td>${l.lote}</td>
        <td>${l.categoria}</td>
        <td class="qty">${l.qty}</td>
        <td>${fmtDate(l.validade)}</td>
        <td>${dias < 0 ? `Vencido há ${Math.abs(dias)}d` : `${dias} dias restantes`}</td>
        <td class="${stCls}">${stTxt}</td>
      </tr>`;
  }).join('\n');

  const html = `
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>FarmaControl — Relatório de Vencimentos</title>
<style>
  @page { margin: 14mm 12mm; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Helvetica Neue', Arial, sans-serif; color: #1a2420; font-size: 11px; }
  .header { border-bottom: 2px solid #3f6b4e; padding-bottom: 10px; margin-bottom: 14px; }
  .header h1 { font-size: 18px; font-weight: 600; color: #3f6b4e; }
  .header p { font-size: 10.5px; color: #5a6a62; margin-top: 3px; }
  .kpi-row { display: flex; gap: 10px; margin-bottom: 16px; }
  .kpi-box { flex: 1; border: 1px solid #dfe4e1; border-radius: 6px; padding: 8px 10px; }
  .kpi-box .lb { font-size: 9px; text-transform: uppercase; letter-spacing: .06em; color: #6a7872; }
  .kpi-box .vl { font-size: 17px; font-weight: 600; margin-top: 2px; }
  .vl.red { color: #b3403a; } .vl.amber { color: #b07a18; } .vl.soft { color: #3f6b4e; } .vl.gray { color: #4a5752; }
  table { width: 100%; border-collapse: collapse; }
  th { background: #eef3f0; color: #35463d; text-align: left; font-size: 9.5px; text-transform: uppercase; letter-spacing: .05em; padding: 6px 8px; border-bottom: 2px solid #cfd9d4; }
  td { padding: 6px 8px; border-bottom: 1px solid #e3e9e6; font-size: 10.5px; }
  tr:nth-child(even) td { background: #f6f9f7; }
  .status-vencido { color: #b3403a; font-weight: 600; }
  .status-30 { color: #b07a18; font-weight: 600; }
  .status-60 { color: #7a8a14; font-weight: 600; }
  .status-ok { color: #3f6b4e; }
  .footer { margin-top: 14px; font-size: 9.5px; color: #8a9690; border-top: 1px solid #e3e9e6; padding-top: 8px; }
  @media print { body { -webkit-print-color-adjust: exact; } }
</style>
</head>
<body>
  <div class="header">
    <h1>FarmaControl — Relatório de Vencimentos</h1>
    <p>${dataHoje} · Lotes do estoque da farmácia</p>
  </div>
  <div class="kpi-row">
    <div class="kpi-box"><div class="lb">Vencidos</div><div class="vl red">${vencidos}</div></div>
    <div class="kpi-box"><div class="lb">Vencem em 30 dias</div><div class="vl amber">${d30}</div></div>
    <div class="kpi-box"><div class="lb">Vencem em 60 dias</div><div class="vl soft">${d60}</div></div>
    <div class="kpi-box"><div class="lb">Dentro da validade</div><div class="vl gray">${ok}</div></div>
  </div>
  <table>
    <thead><tr><th>Medicamento</th><th>Princípio Ativo</th><th>Lote</th><th>Categoria</th><th>Qtd.</th><th>Validade</th><th>Prazo</th><th>Status</th></tr></thead>
    <tbody>
${rows}
    </tbody>
  </table>
  <div class="footer">FarmaControl v1.0 · Gerado em ${dataHoje}</div>
</body>
</html>`;

  const w = window.open('', '_blank');
  if (w) {
    w.document.write(html);
    w.document.close();
    setTimeout(() => w.print(), 400);
  } else {
    showToast('Permita pop-ups para imprimir.', 'err');
  }
}

document.getElementById('btn-export')?.addEventListener('click', () => {
  const rows  = lotes.map(l => `${l.nome},${l.lote},${l.categoria},${l.qty},${fmtDate(l.validade)},${diasRestantes(l.validade)}`);
  const csv   = ['Medicamento,Lote,Categoria,Qtd,Validade,DiasRestantes', ...rows].join('\n');
  const blob  = new Blob([csv], { type: 'text/csv' });
  const url   = URL.createObjectURL(blob);
  const a     = document.createElement('a');
  a.href = url; a.download = 'vencimentos.csv'; a.click();
  URL.revokeObjectURL(url);
  showToast('Exportado: vencimentos.csv', 'ok');
});

/* ══ MODAL NOVO LOTE ══ */
var produtosFull = [];

async function fetchProdutos() {
  try {
    const res = await fetch(`${API_BASE}/produtos`);
    const data = await res.json();
    if (data.ok) {
      produtosFull = data.produtos;
      const select = document.getElementById('lote-produto-id');
      if (select) {
        select.innerHTML = '<option value="">Selecione um produto...</option>' + 
          produtosFull.map(p => `<option value="${p.id}">${p.nome} (${p.categoria})</option>`).join('');
      }
    }
  } catch (err) {
    console.error('Erro ao buscar produtos:', err);
  }
}

function openLoteModal() {
  document.getElementById('modal-lote').classList.add('open');
  fetchProdutos();
}

function closeLoteModal() {
  document.getElementById('modal-lote').classList.remove('open');
}

async function handleLoteSubmit() {
  const produto_id = document.getElementById('lote-produto-id').value;
  const lote = document.getElementById('lote-numero').value;
  const quantidade = document.getElementById('lote-quantidade').value;
  const data_validade = document.getElementById('lote-validade').value;
  const preco_compra = document.getElementById('lote-preco').value;

  if (!produto_id || !lote || !quantidade || !data_validade) {
    showToast('Preencha todos os campos obrigatórios', 'err');
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
      showToast('Novo lote cadastrado com sucesso!', 'ok');
      closeLoteModal();
      fetchLotes();
    } else {
      showToast(data.mensagem || 'Erro ao cadastrar lote', 'err');
    }
  } catch (err) {
    showToast('Erro de conexão ao cadastrar lote', 'err');
  }
}

document.getElementById('btn-add-lote')?.addEventListener('click', openLoteModal);
document.getElementById('btn-lote-submit')?.addEventListener('click', handleLoteSubmit);

// Logout e sidebar gerenciados globalmente pelo sidebar-init.js

/* Atalho Escape para fechar modais */
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.open').forEach(o => o.classList.remove('open'));
  }
});

/* ══ TOAST — sistema global do global-settings.js (mapeia os tipos locais) ══ */
var toastTimer;
function showToast(msg, type = 'ok') {
  const t = document.getElementById('toast');
  const m = document.getElementById('toast-msg');
  if (t && m) {
    // Mantém o toast visual existente da página (elemento #toast no HTML)
    t.className = 'toast' + (type === 'warn' ? ' toast-warn' : type === 'err' ? ' toast-err' : '');
    m.textContent = msg;
    t.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove('show'), 3800);
  } else if (window.FarmaControlSettings && typeof window.FarmaControlSettings.showToast === 'function') {
    // Fallback para o sistema global quando o elemento #toast não existe
    window.FarmaControlSettings.showToast(
      msg,
      type === 'ok' ? 'success' : type === 'err' ? 'error' : type
    );
  }
}

/* ══ DATE CHIP ══ */
function initClock() {
  const el = document.getElementById('date-text');
  const subtitle = document.getElementById('page-subtitle');
  if (!el) return;
  const updateDate = () => {
    const now = new Date();
    el.textContent = now.toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }).replace(/^\w/, c => c.toUpperCase());
    if (subtitle) {
      subtitle.textContent = `Monitoramento de validade dos lotes · Última atualização: ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`;
    }
  };
  updateDate();
  __fcSetInterval(updateDate, 1000);
}

/* ══ INIT ══ */
document.addEventListener('DOMContentLoaded', () => {
  // initSidebar(); // Removido: já inicializado pelo sidebar-init.js
  initClock();
  fetchLotes();

});
