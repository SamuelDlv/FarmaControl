/* ══════════════════════════════════════════════════════════════════════
 * FARMAControl — GESTÃO DE ESTOQUE (PROPRIETÁRIO)
 * ══════════════════════════════════════════════════════════════════════
 *
 * Gerencia o estoque completo da farmácia:
 * - Tabela paginada com todos os produtos (nome, lote, qtd, validade)
 * - Filtros por categoria, busca textual e ordenação
 * - Status de validade com cores (verde=ok, amarelo=vencendo, vermelho=expirado)
 * - Modal de adicionar/editar produto
 * - Modal de movimentação (entrada/saída de estoque)
 * - Modal de histórico de movimentações por produto
 * - Modal de exclusão com confirmação
 *
 * Dados são carregados da API: GET/POST/PUT/DELETE /estoque/*
 * ══════════════════════════════════════════════════════════════════════ */

/* ── Ciclo de vida SPA: coleta timers desta página para descarte ao sair */
if (!window.__fcTimers) { window.__fcTimers = []; window.addEventListener('fc-page-unload', () => {
  window.__fcTimers.forEach(id => { clearInterval(id); clearTimeout(id); });
  window.__fcTimers = [];
  window.dispatchEvent(new Event('fc-page-unloaded'));
}); }
var __fcSetInterval = (fn, ms) => { const i = setInterval(fn, ms); window.__fcTimers.push(i); return i; };
var __fcSetTimeout  = (fn, ms) => { const i = setTimeout(fn, ms); window.__fcTimers.push(i); return i; };
/* ═══════════════════════════════════════════════
   FarmaControl — estoque.js
   Todas as funcionalidades dos botões e interações
   ═══════════════════════════════════════════════ */

/* ── Dados simulados ── */
// Guard de sessão e dados do usuário agora são gerenciados globalmente pelo global-settings.js e sidebar-init.js

var API_BASE = window.FarmaControlSettings ? window.FarmaControlSettings.API_BASE : 'http://localhost:5000';
var produtos = [];
var categoriasCache = [];

  /* getUsuarioId(): Retorna o ID do usuário logado (localStorage). */
  function getUsuarioId() {
  try {
    const raw = sessionStorage.getItem('farmacontrol_usuario');
    return raw ? JSON.parse(raw).id : null;
  } catch { return null; }
}

  /* fetchProdutos(): Busca todos os produtos do estoque via API com paginação e filtros. */
  async function fetchProdutos() {
  const token = window.__fcPageToken;
  try {
    const res = await fetch(`${API_BASE}/estoque`);
    if (window.__fcPageToken !== token) return;
    const data = await res.json();
    if (data.ok) {
      produtos = data.estoque.map(item => {
        // Suporta tanto os aliases antigos quanto os novos
        const minimo = item.estoque_minimo || item.produto_estoque_minimo || 10;
        const qty    = item.quantidade || 0;
        let status;
        if (qty <= 0 || qty < minimo * 0.2) status = 'err';
        else if (qty < minimo)              status = 'warn';
        else                                status = 'ok';
        return {
          id:         item.id,
          produto_id: item.produto_id,
          nome:       item.produto_nome                     || '—',
          principio:  item.principio_ativo || item.produto_principio || '',
          lote:       item.lote                             || '—',
          categoria:  item.categoria       || item.produto_categoria || '',
          qty,
          min:        minimo,
          validade:   (item.data_validade || '').split('T')[0],
          status,
          fornecedor: item.fornecedor_nome || item.produto_fabricante || '',
          custo:      parseFloat(item.preco_custo || item.produto_preco_custo) || 0,
        };
      });
      renderTable();
      updateKPIs();
    } else {
      showToast('Erro ao carregar estoque: ' + (data.mensagem || ''), 'err');
    }
  } catch (err) {
    console.error('Erro ao buscar produtos:', err);
    showToast('Erro ao carregar estoque do servidor.', 'err');
  }
}

var chipMap = {
  ok:   '<span class="chip chip-ok">Normal</span>',
  warn: '<span class="chip chip-warn">Baixo</span>',
  err:  '<span class="chip chip-err">Crítico</span>',
};

/* ── Helpers ── */
function fmtDate(iso) {
  if (!iso) return '—';
  const [y, m, d] = iso.split('-');
  return `${d}/${m}/${y}`;
}

  /* isExpiringSoon(): Verifica se um produto vence em menos de 30 dias. */
  function isExpiringSoon(iso) {
  const diff = (new Date(iso) - new Date()) / 86400000;
  return diff <= 30 && diff > 0;
}

  /* isExpired(): Verifica se um produto já expirou. */
  function isExpired(iso) {
  return new Date(iso) < new Date();
}

  /* recalcStatus(): Recalcula o status de cada produto (ok/expirando/expirado) baseado na validade. */
  function recalcStatus(p) {
  if (p.qty <= 0 || p.qty < p.min * 0.2) return 'err';
  if (p.qty < p.min) return 'warn';
  return 'ok';
}

/* ── Render Table ── */
var sortField = null;
var sortDir   = 'asc';
var currentPage = 1;
var PAGE_SIZE = 10;

  /* getSorted(): Ordena os produtos por coluna selecionada (nome, lote, qtd, validade). */
  function getSorted(data) {
  if (!sortField) return data;
  return [...data].sort((a, b) => {
    let va = a[sortField], vb = b[sortField];
    if (typeof va === 'string') va = va.toLowerCase(), vb = vb.toLowerCase();
    if (va < vb) return sortDir === 'asc' ? -1 : 1;
    if (va > vb) return sortDir === 'asc' ? 1 : -1;
    return 0;
  });
}

  /* getFiltered(): Filtra os produtos conforme busca textual e categoria selecionada. */
  function getFiltered() {
  const q   = document.getElementById('search-input').value.toLowerCase();
  const cat = document.getElementById('filter-cat').value;
  const st  = document.getElementById('filter-status').value;
  return produtos.filter(p => {
    const matchQ = !q || p.nome.toLowerCase().includes(q) || p.principio.toLowerCase().includes(q) || p.lote.toLowerCase().includes(q);
    const matchC = !cat || p.categoria === cat;
    const matchS = !st  || p.status === st;
    return matchQ && matchC && matchS;
  });
}

  /* renderTable(): Renderiza a tabela de produtos com os dados filtrados e ordenados. */
  function renderTable() {
  if (!document.getElementById('table-body')) return;
  const filtered = getFiltered();
  const sorted   = getSorted(filtered);
  const total    = sorted.length;
  const pages    = Math.max(1, Math.ceil(total / PAGE_SIZE));
  currentPage    = Math.min(currentPage, pages);
  const slice    = sorted.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  const tbody = document.getElementById('table-body');
  tbody.innerHTML = slice.map(p => {
    const rowClass = p.status === 'err' ? 'row-err' : p.status === 'warn' ? 'row-warn' : '';
    const qtyClass = p.status === 'err' ? 'crit' : p.status === 'warn' ? 'low' : '';
    const expClass = isExpired(p.validade) ? 'past' : isExpiringSoon(p.validade) ? 'soon' : '';
    return `
      <tr class="${rowClass}" data-id="${p.id}">
        <td>
          <div class="med-info">
            <span class="med-name">${p.nome}</span>
            <span class="med-meta">${p.principio}</span>
          </div>
        </td>
        <td><span class="lot-pill">${p.lote}</span></td>
        <td style="font-size:12px;color:var(--ink-35)">${p.categoria}</td>
        <td><span class="qty-cell ${qtyClass}">${p.qty}</span></td>
        <td style="font-size:12.5px;color:var(--ink-35)">${p.min}</td>
        <td class="exp-cell ${expClass}">${fmtDate(p.validade)}</td>
        <td>${chipMap[p.status]}</td>
        <td>
          <div class="row-actions">
            <button class="action-btn btn-edit"   data-id="${p.id}" title="Editar">
              <svg viewBox="0 0 16 16" fill="none"><path d="M11 2l3 3-8 8H3v-3l8-8z" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </button>
            <button class="action-btn btn-move"   data-id="${p.id}" title="Movimentar">
              <svg viewBox="0 0 16 16" fill="none"><path d="M8 3v10M4 9l4 4 4-4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </button>
            <button class="action-btn btn-history" data-id="${p.id}" title="Histórico">
              <svg viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.2"/><path d="M8 5v3l2 2" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
            </button>
            <button class="action-btn btn-delete" data-id="${p.id}" title="Excluir">
              <svg viewBox="0 0 16 16" fill="none"><path d="M3 4h10M5 4V3a1 1 0 011-1h4a1 1 0 011 1v1m2 0v10a1 1 0 01-1 1H4a1 1 0 01-1-1V4h10" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/><path d="M6 7v6M10 7v6" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
            </button>
          </div>
        </td>
      </tr>`;
  }).join('');

  /* Update info */
  const start = total === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1;
  const end   = Math.min(currentPage * PAGE_SIZE, total);
  document.getElementById('page-info').textContent = `Mostrando ${start}–${end} de ${total}`;

  renderPagination(pages);
  bindRowActions();
}

  /* renderPagination(): Renderiza os botões de paginação (1, 2, 3...) conforme total de páginas. */
  function renderPagination(pages) {
  const container = document.getElementById('page-btns');
  let html = '';
  html += `<button class="page-btn${currentPage === 1 ? ' disabled' : ''}" id="pg-prev">
    <svg viewBox="0 0 20 20" fill="none"><path d="M12 15l-5-5 5-5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
  </button>`;

  const range = [];
  if (pages <= 7) {
    for (let i = 1; i <= pages; i++) range.push(i);
  } else {
    range.push(1);
    if (currentPage > 3) range.push('…');
    for (let i = Math.max(2, currentPage - 1); i <= Math.min(pages - 1, currentPage + 1); i++) range.push(i);
    if (currentPage < pages - 2) range.push('…');
    range.push(pages);
  }

  range.forEach(v => {
    if (v === '…') {
      html += `<button class="page-btn disabled">…</button>`;
    } else {
      html += `<button class="page-btn${v === currentPage ? ' current' : ''}" data-pg="${v}">${v}</button>`;
    }
  });

  html += `<button class="page-btn${currentPage === pages ? ' disabled' : ''}" id="pg-next">
    <svg viewBox="0 0 20 20" fill="none"><path d="M8 5l5 5-5 5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>
  </button>`;

  container.innerHTML = html;

  document.getElementById('pg-prev')?.addEventListener('click', () => { if (currentPage > 1) { currentPage--; renderTable(); } });
  document.getElementById('pg-next')?.addEventListener('click', () => { if (currentPage < pages) { currentPage++; renderTable(); } });
  container.querySelectorAll('[data-pg]').forEach(btn => {
    btn.addEventListener('click', () => { currentPage = parseInt(btn.dataset.pg); renderTable(); });
  });
}

/* ── Sort ── */
document.querySelectorAll('thead th.sortable').forEach(th => {
  th.addEventListener('click', () => {
    const field = th.dataset.sort;
    if (sortField === field) {
      sortDir = sortDir === 'asc' ? 'desc' : 'asc';
    } else {
      sortField = field;
      sortDir = 'asc';
    }
    document.querySelectorAll('thead th.sortable').forEach(t => {
      t.classList.remove('sort-asc', 'sort-desc');
    });
    th.classList.add(sortDir === 'asc' ? 'sort-asc' : 'sort-desc');
    currentPage = 1;
    renderTable();
  });
});

/* ── Filters ── */
document.getElementById('search-input')?.addEventListener('input', () => { currentPage = 1; renderTable(); });
document.getElementById('filter-cat')?.addEventListener('change', () => { currentPage = 1; renderTable(); });
document.getElementById('filter-status')?.addEventListener('change', () => { currentPage = 1; renderTable(); });

/* ── Row action bindings ── */
function bindRowActions() {
  document.querySelectorAll('.btn-edit').forEach(btn => {
    btn.addEventListener('click', () => openEditModal(parseInt(btn.dataset.id)));
  });
  document.querySelectorAll('.btn-move').forEach(btn => {
    btn.addEventListener('click', () => openMoveModal(parseInt(btn.dataset.id)));
  });
  document.querySelectorAll('.btn-history').forEach(btn => {
    btn.addEventListener('click', () => openHistoryModal(parseInt(btn.dataset.id)));
  });
  document.querySelectorAll('.btn-delete').forEach(btn => {
    btn.addEventListener('click', () => deleteItemEstoque(parseInt(btn.dataset.id)));
  });
}

  /* deleteItemEstoque(): Remove um produto do estoque (com confirmação do usuário). */
  async function deleteItemEstoque(id) {
  const p = produtos.find(x => x.id === id);
  if (!p) return;
  
  if (!confirm(`Tem certeza que deseja excluir o lote "${p.lote}" do produto "${p.nome}"? Esta ação não pode ser desfeita.`)) {
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/estoque/${id}`, {
      method: 'DELETE'
    });
    const result = await res.json();
    if (result.ok) {
      showToast('Item excluído com sucesso!', 'ok');
      fetchProdutos();
    } else {
      showToast(result.mensagem || 'Erro ao excluir item.', 'err');
    }
  } catch (err) {
    console.error('Erro ao excluir item:', err);
    showToast('Erro ao excluir item do servidor.', 'err');
  }
}

/* ══════════════════════════════
   ADD PRODUCT MODAL
══════════════════════════════ */
var addOverlay = () => document.getElementById('modal-overlay');

document.getElementById('btn-add')?.addEventListener('click', () => {
  clearAddForm();
  const o = addOverlay();
  if (o) o.classList.add('open');
});

/* Popula categorias no modal ao abrir */
const o0 = addOverlay();
if (o0) o0.addEventListener('transitionend', e => {
  if (o0.classList.contains('open') && e.propertyName === 'opacity') populateAddCategories();
});
document.getElementById('modal-close')?.addEventListener('click',   () => addOverlay()?.classList.remove('open'));
document.getElementById('modal-cancel')?.addEventListener('click', () => addOverlay()?.classList.remove('open'));
document.addEventListener('click', e => {
  const o = addOverlay();
  if (o && e.target === o) o.classList.remove('open');
});

  /* populateAddCategories(): Carrega as categorias disponíveis no select do modal de adicionar. */
  async function populateAddCategories() {
  const sel = document.getElementById('add-categoria');
  if (!sel) return;
  try {
    const res = await fetch(`${API_BASE}/categorias-produto`);
    const data = await res.json();
    if (data.ok) {
      categoriasCache = data.categorias || [];
      sel.innerHTML = '<option value="">Geral</option>' +
        categoriasCache.map(c => `<option value="${c.id}">${c.nome}</option>`).join('');
    }
  } catch (err) {
    console.error('Erro ao carregar categorias:', err);
  }
}

  /* clearAddForm(): Limpa todos os campos do formulário de adicionar produto. */
  function clearAddForm() {
  document.getElementById('add-nome').value       = '';
  document.getElementById('add-principio').value  = '';
  const catSel = document.getElementById('add-categoria');
  if (catSel) catSel.value = '';
  document.getElementById('add-lote').value       = '';
  document.getElementById('add-validade').value   = '';
  document.getElementById('add-qty').value        = '';
  document.getElementById('add-min').value        = '';
  document.getElementById('add-custo').value      = '';
  document.getElementById('add-fornecedor').value = '';
  populateAddCategories();
  populateFornecedores();
}

  /* populateFornecedores(): Carrega a lista de fornecedores no select do modal. */
  async function populateFornecedores() {
  const addSel = document.getElementById('add-fornecedor');
  const editSel = document.getElementById('edit-fornecedor');
  if (!addSel && !editSel) return;
  try {
    const res  = await fetch(`${API_BASE}/fornecedores`);
    const data = await res.json();
    const list = (data.ok ? data.fornecedores : []) || [];
    const opts = '<option value="">Selecione…</option>' +
      list.map(f => `<option value="${f.id}">${f.nome_fantasia}</option>`).join('');
    if (addSel) addSel.innerHTML = opts;
    if (editSel) editSel.innerHTML = opts;
  } catch (err) {
    console.error('Erro ao carregar fornecedores:', err);
  }
}

document.getElementById('modal-save')?.addEventListener('click', async () => {
  const nome = document.getElementById('add-nome').value.trim();
  if (!nome) { showToast('Preencha o nome do medicamento.', 'warn'); return; }
  const qty      = parseInt(document.getElementById('add-qty').value)      || 0;
  const min      = parseInt(document.getElementById('add-min').value)      || 0;
  const lote     = document.getElementById('add-lote').value.trim()        || 'SEM-LOTE';
  const validade = document.getElementById('add-validade').value           || '2099-01-01';
  const custo    = parseFloat(document.getElementById('add-custo').value)  || 0.01;
  const principio = document.getElementById('add-principio').value.trim();
  const fornecedor = document.getElementById('add-fornecedor').value.trim();
  if (!qty || qty <= 0) { showToast('Informe uma quantidade válida.', 'warn'); return; }
  try {
    const catSel    = document.getElementById('add-categoria');
    const categoria = (catSel && catSel.value) ? parseInt(catSel.value) : null;
    const res = await fetch(`${API_BASE}/estoque`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        produto_nome:        nome,
        produto_principio:   principio || null,
        produto_preco_custo: custo,
        produto_categoria_id: categoria,
        produto_fornecedor_id: document.getElementById('add-fornecedor').value || null,
        lote,
        quantidade:          qty,
        data_validade:       validade,
        usuario_id:          getUsuarioId(),
      })
    });
    const result = await res.json();
    if (result.ok) {
      addOverlay()?.classList.remove('open');
      fetchProdutos();
      showToast(`"${nome}" cadastrado com sucesso!`, 'ok');
    } else {
      showToast(result.mensagem || 'Erro ao cadastrar.', 'err');
    }
  } catch (err) {
    showToast('Erro ao salvar produto no servidor.', 'err');
  }
});

/* ══════════════════════════════
   EDIT MODAL
══════════════════════════════ */
var editOverlay = () => document.getElementById('edit-overlay');
document.getElementById('edit-close')?.addEventListener('click',   () => editOverlay()?.classList.remove('open'));
document.getElementById('edit-cancel')?.addEventListener('click', () => editOverlay()?.classList.remove('open'));
document.addEventListener('click', e => {
  const o = editOverlay();
  if (o && e.target === o) o.classList.remove('open');
});

  /* openEditModal(): Abre o modal de edição com os dados atuais do produto preenchidos. */
  async function openEditModal(id) {
  const p = produtos.find(x => x.id === id);
  if (!p) return;
  const eo = editOverlay();
  if (!eo) return;
  eo.dataset.editId = id;
  document.getElementById('edit-nome').value       = p.nome;
  document.getElementById('edit-principio').value  = p.principio;
  document.getElementById('edit-lote').value       = p.lote === '—' ? '' : p.lote;
  document.getElementById('edit-validade').value   = p.validade || '';
  document.getElementById('edit-qty').value        = p.qty;
  document.getElementById('edit-min').value        = p.min;
  document.getElementById('edit-custo').value      = p.custo || '';
  document.getElementById('edit-fornecedor').value = p.fornecedor || '';
  // Popula o select de categoria com as categorias reais e seleciona a atual
  const catSel = document.getElementById('edit-categoria');
  if (catSel) {
    try {
      const res = await fetch(`${API_BASE}/categorias-produto`);
      const data = await res.json();
      if (data.ok) {
        categoriasCache = data.categorias || [];
        catSel.innerHTML = '<option value="">Geral</option>' +
          categoriasCache.map(c => `<option value="${c.id}"${c.nome === p.categoria ? ' selected' : ''}>${c.nome}</option>`).join('');
        // Seleciona o fornecedor atual e popula o select via API
        await populateFornecedores();
        if (p.fornecedor_id) {
          const fSel = document.getElementById('edit-fornecedor');
          if (fSel) fSel.value = String(p.fornecedor_id);
        }
      }
    } catch (err) {
      console.error('Erro ao carregar categorias:', err);
      catSel.value = p.categoria;
    }
  }
  editOverlay().classList.add('open');
}

document.getElementById('edit-save')?.addEventListener('click', async () => {
  const eo2 = editOverlay();
  const id   = parseInt(eo2.dataset.editId);
  const nome = document.getElementById('edit-nome').value.trim();
  if (!nome) { showToast('Preencha o nome do medicamento.', 'warn'); return; }
  const qty  = parseInt(document.getElementById('edit-qty').value);
  if (isNaN(qty) || qty < 0) { showToast('Quantidade inválida.', 'warn'); return; }
  try {
    const catSel    = document.getElementById('edit-categoria');
    const categoria = (catSel && catSel.value) ? parseInt(catSel.value) : null;
    const min       = parseInt(document.getElementById('edit-min').value) || 0;
    const lote      = document.getElementById('edit-lote').value.trim()   || 'SEM-LOTE';
    const res = await fetch(`${API_BASE}/estoque/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        produto_nome:        nome,
        produto_principio:   document.getElementById('edit-principio').value.trim() || null,
        produto_preco_custo: parseFloat(document.getElementById('edit-custo').value) || null,
        produto_categoria_id: categoria || null,
        produto_fornecedor_id: document.getElementById('edit-fornecedor').value || '',
        estoque_minimo:      min,
        lote,
        quantidade:          qty,
        data_validade:       document.getElementById('edit-validade').value          || null,
        usuario_id:          getUsuarioId(),
      })
    });
    const result = await res.json();
    if (result.ok) {
      editOverlay()?.classList.remove('open');
      fetchProdutos();
      showToast(`"${nome}" atualizado!`, 'ok');
    } else {
      showToast(result.mensagem || 'Erro ao atualizar.', 'err');
    }
  } catch (err) {
    showToast('Erro ao atualizar produto no servidor.', 'err');
  }
});

/* ══════════════════════════════
   MOVE (MOVIMENTAÇÃO) MODAL
══════════════════════════════ */
var moveOverlay = () => document.getElementById('move-overlay');
var moveDirection = 'in';
document.getElementById('move-close')?.addEventListener('click',   () => moveOverlay()?.classList.remove('open'));
document.getElementById('move-cancel')?.addEventListener('click', () => moveOverlay()?.classList.remove('open'));
document.addEventListener('click', e => {
  const o = moveOverlay();
  if (o && e.target === o) o.classList.remove('open');
});

document.getElementById('move-btn-in')?.addEventListener('click',  () => setMoveDir('in'));
document.getElementById('move-btn-out')?.addEventListener('click', () => setMoveDir('out'));

function setMoveDir(dir) {
  moveDirection = dir;
  document.getElementById('move-btn-in').classList.toggle('selected',  dir === 'in');
  document.getElementById('move-btn-out').classList.toggle('selected', dir === 'out');
}

  /* openMoveModal(): Abre o modal de movimentação de estoque para um produto específico. */
  function openMoveModal(id) {
  const p = produtos.find(x => x.id === id);
  if (!p) return;
  const mo = moveOverlay();
  if (!mo) return;
  mo.dataset.moveId = id;
  document.getElementById('move-product-name').textContent = p.nome;
  document.getElementById('move-current-qty').textContent  = p.qty;
  document.getElementById('move-qty').value   = '';
  document.getElementById('move-obs').value   = '';
  setMoveDir('in');
  moveOverlay().classList.add('open');
}

document.getElementById('move-save')?.addEventListener('click', async () => {
  const mo2 = moveOverlay();
  const id  = parseInt(mo2.dataset.moveId);
  const p   = produtos.find(x => x.id === id);
  if (!p) return;
  const qty = parseInt(document.getElementById('move-qty').value);
  const obs = document.getElementById('move-obs').value.trim();
  const uid = getUsuarioId();

  if (!qty || qty <= 0) { showToast('Informe uma quantidade válida.', 'warn'); return; }
  if (!uid) { showToast('Sessão inválida. Faça login novamente.', 'err'); return; }

  try {
    const res = await fetch(`${API_BASE}/movimentacoes-estoque`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        estoque_id:        id,
        usuario_id:        uid,
        tipo_movimentacao: moveDirection === 'in' ? 'entrada' : 'saida',
        quantidade:        qty,
        observacao:        obs || (moveDirection === 'in' ? 'Entrada manual' : 'Saída manual'),
      })
    });
    const result = await res.json();
    if (result.ok) {
      moveOverlay()?.classList.remove('open');
      fetchProdutos();
      showToast(moveDirection === 'in' ? `+${qty} unidades adicionadas` : `-${qty} unidades retiradas`, 'ok');
    } else {
      showToast(result.mensagem || 'Erro ao registrar movimentação.', 'err');
    }
  } catch (err) {
    showToast('Erro ao registrar movimentação no servidor.', 'err');
  }
});

/* ══════════════════════════════
   HISTORY MODAL
══════════════════════════════ */
var historyOverlay = () => document.getElementById('history-overlay');
document.getElementById('history-close')?.addEventListener('click', () => historyOverlay()?.classList.remove('open'));
document.addEventListener('click', e => {
  const o = historyOverlay();
  if (o && e.target === o) o.classList.remove('open');
});

  /* openHistoryModal(): Abre o modal com o histórico de movimentações de um produto. */
  async function openHistoryModal(id) {
  const p = produtos.find(x => x.id === id);
  if (!p) return;
  document.getElementById('history-product-name').textContent = p.nome;
  const container = document.getElementById('history-list');
  container.innerHTML = '<div style="padding:24px;text-align:center;color:var(--ink-35);font-size:13px">Carregando…</div>';
  const ho = historyOverlay();
  if (!ho) return;
  ho.classList.add('open');

  try {
    const res  = await fetch(`${API_BASE}/estoque/${id}/historico`);
    const data = await res.json();
    const list = data.ok ? data.historico : [];

    if (list.length === 0) {
      container.innerHTML = '<div style="padding:24px;text-align:center;color:var(--ink-35);font-size:13px">Nenhuma movimentação registrada.</div>';
    } else {
      const tipoLabel = { entrada: 'Entrada', saida: 'Saída', ajuste: 'Ajuste', transferencia: 'Transferência' };
      container.innerHTML = list.map(h => {
        const tipo     = h.tipo_movimentacao || 'ajuste';
        const dotClass = tipo === 'entrada' ? 'in' : tipo === 'saida' ? 'out' : 'adj';
        const qtySign  = dotClass === 'in' ? '+' : dotClass === 'out' ? '-' : '±';
        const qtyClass = dotClass === 'in' ? 'pos' : dotClass === 'out' ? 'neg' : '';
        const dataFmt  = h.data_movimentacao
          ? new Date(h.data_movimentacao).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
          : '—';
        return `
          <div class="history-item">
            <div class="history-dot ${dotClass}"></div>
            <div class="history-info">
              <div class="history-action">${tipoLabel[tipo] || tipo}</div>
              <div class="history-detail">${h.observacao || ''} · ${h.usuario_nome || ''} · ${dataFmt}</div>
            </div>
            <div class="history-qty ${qtyClass}">${qtySign}${h.quantidade}</div>
          </div>`;
      }).join('');
    }
  } catch (e) {
    container.innerHTML = '<div style="padding:24px;text-align:center;color:var(--ink-35);font-size:13px">Erro ao carregar histórico.</div>';
  }
}

/* ══════════════════════════════
   EXPORT BUTTON
══════════════════════════════ */
document.getElementById('btn-export')?.addEventListener('click', () => {
  const data = getFiltered();
  const headers = ['Nome', 'Princípio Ativo', 'Lote', 'Categoria', 'Quantidade', 'Mínimo', 'Validade', 'Status', 'Fornecedor', 'Custo (R$)'];
  const rows = data.map(p => [
    p.nome, p.principio, p.lote, p.categoria,
    p.qty, p.min, fmtDate(p.validade),
    p.status === 'ok' ? 'Normal' : p.status === 'warn' ? 'Baixo' : 'Crítico',
    p.fornecedor, p.custo.toFixed(2)
  ]);
  const csv = [headers, ...rows].map(r => r.map(v => `"${v}"`).join(',')).join('\n');
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = `estoque_${new Date().toISOString().slice(0,10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
  showToast('Exportação CSV gerada!', 'ok');
});

/* ══════════════════════════════
   NAV ITEMS (SPA simulation) - handled by initSidebar()
══════════════════════════════ */

/* ══════════════════════════════
   KPI UPDATE
══════════════════════════════ */
  /* updateKPIs(): Atualiza os contadores de KPI (total itens, valor estoque, etc.). */
  function updateKPIs() {
  const total   = produtos.length;
  const criticos = produtos.filter(p => p.status === 'err');
  const baixos   = produtos.filter(p => p.status === 'warn');
  const vencendo = produtos.filter(p => isExpiringSoon(p.validade));

  document.getElementById('kpi-total').textContent    = total;
  document.getElementById('kpi-criticos').textContent = criticos.length;
  document.getElementById('kpi-baixos').textContent   = baixos.length;
  document.getElementById('kpi-vencendo').textContent = vencendo.length;

  /* Render Alertas */
  const alertList = document.getElementById('alert-list');
  const alertSubtitle = document.getElementById('alert-subtitle');
  const allAlerts = [...criticos, ...baixos, ...vencendo];
  
  if (allAlerts.length === 0) {
    alertList.innerHTML = '<div style="padding:24px;text-align:center;color:var(--ink-35);font-size:13px">Nenhum alerta no momento.</div>';
    alertSubtitle.textContent = 'Nenhum item requer atenção';
  } else {
    alertSubtitle.textContent = `${allAlerts.length} itens requerem atenção`;
    alertList.innerHTML = allAlerts.slice(0, 6).map(p => {
      const isExp = isExpiringSoon(p.validade);
      const dotClass = p.status === 'err' || isExp ? 'err' : 'warn';
      let desc = '';
      if (isExp) {
        const diff = Math.ceil((new Date(p.validade) - new Date()) / 86400000);
        desc = `Vence em ${diff} dias — Lote ${p.lote}`;
      } else {
        desc = `Estoque ${p.status === 'err' ? 'crítico' : 'baixo'}: ${p.qty} unidades`;
      }
      return `
        <div class="alert-item">
          <div class="alert-dot ${dotClass}"></div>
          <div class="alert-text">
            <div class="alert-name">${p.nome}</div>
            <div class="alert-desc">${desc}</div>
          </div>
          <span class="alert-time">agora</span>
        </div>`;
    }).join('');
  }

  /* Render Próximos ao Vencimento */
  const expiryList = document.getElementById('expiry-list');
  if (vencendo.length === 0) {
    expiryList.innerHTML = '<div style="padding:24px;text-align:center;color:var(--ink-35);font-size:13px">Nenhum item vencendo em breve.</div>';
  } else {
    expiryList.innerHTML = vencendo.slice(0, 5).map(p => {
      const diff = (new Date(p.validade) - new Date()) / 86400000;
      const progress = Math.max(5, Math.min(100, 100 - (diff / 30 * 100)));
      return `
        <div class="expiry-item">
          <div class="expiry-bar-wrap">
            <div class="expiry-meta">
              <span class="expiry-name">${p.nome}</span>
              <span class="expiry-date">${fmtDate(p.validade)}</span>
            </div>
            <div class="expiry-bar"><div class="expiry-fill" style="width:${progress}%"></div></div>
          </div>
        </div>`;
    }).join('');
  }

  /* Update alert badges in sidebar */
  const totalAlerts = criticos.length + vencendo.length; // Críticos + Vencendo
  const lowStockCount = baixos.length;

  // Badge de Estoque (Baixo/Crítico)
  const stockBadge = document.querySelector('.sb-item[href*="estoque"] .sb-badge');
  if (stockBadge) {
    const count = criticos.length + baixos.length;
    stockBadge.textContent = count;
    stockBadge.style.display = count > 0 ? '' : 'none';
  }

  // Badge de Vencimentos
  const expiryBadge = document.querySelector('.sb-item[href*="vencimentos"] .sb-badge');
  if (expiryBadge) {
    expiryBadge.textContent = vencendo.length;
    expiryBadge.style.display = vencendo.length > 0 ? '' : 'none';
  }

  // Badge global (se existir)
  const navBadge = document.querySelector('.nav-badge');
  if (navBadge) {
    navBadge.textContent = totalAlerts + lowStockCount;
    navBadge.style.display = (totalAlerts + lowStockCount) > 0 ? '' : 'none';
  }
}

/* ══════════════════════════════
   TOAST — usa o visual local (#toast no HTML); fallback para o global
══════════════════════════════ */
var toastTimer;
function showToast(msg, type = 'ok') {
  clearTimeout(toastTimer);
  const t     = document.getElementById('toast');
  const msgEl = document.getElementById('toast-msg');
  if (t && msgEl) {
    const icon  = t.querySelector('svg');
    t.className = 'toast';
    if (type === 'err')  { t.classList.add('toast-err');  if (icon) icon.innerHTML = '<circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="1.5"/><path d="M7 13l6-6M13 13L7 7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>'; }
    else if (type === 'warn') { t.classList.add('toast-warn'); if (icon) icon.innerHTML = '<path d="M10 3L18 17H2L10 3z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M10 10v3M10 15v.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>'; }
    else { if (icon) icon.innerHTML = '<circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="1.5"/><path d="M7 10l2 2 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'; }
    msgEl.textContent = msg;
    t.classList.add('show');
    toastTimer = setTimeout(() => t.classList.remove('show'), 3800);
  } else if (window.FarmaControlSettings && typeof window.FarmaControlSettings.showToast === 'function') {
    // Fallback para o sistema global quando o elemento #toast não existe
    window.FarmaControlSettings.showToast(
      msg,
      type === 'ok' ? 'success' : type === 'err' ? 'error' : type
    );
  }
}

/* ══════════════════════════════
   SIDEBAR (dashboard reference logic)
══════════════════════════════ */


/* ══════════════════════════════
   SIDEBAR SEARCH + LOGOUT + INIT
══════════════════════════════ */
document.getElementById('btn-logout')?.addEventListener('click', (e) => {
  e.preventDefault();
  sessionStorage.removeItem('farmacontrol_usuario');
  showToast('Sessão encerrada. Redirecionando…', 'ok');
  setTimeout(() => {
    window.location.href = '../../auth/auth.html';
  }, 1000);
});

/* ── INIT ── */
// Date chip
(function() {
  const el = document.getElementById('date-text');
  if (!el) return;
  const now = new Date();
  el.textContent = now.toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
    .replace(/^\w/, c => c.toUpperCase());
})();

// initSidebar(); // Removido: já inicializado pelo sidebar-init.js
fetchProdutos();

/* ══════════════════════════════
   FORNECEDORES (cadastro real no banco)
══════════════════════════════ */
var fornecedoresCache = [];
var editandoFornecedorId = null;

var supOverlay     = () => document.getElementById('suppliers-overlay');
var supFormOverlay = () => document.getElementById('supplier-form-overlay');

async function fetchFornecedoresEstoque() {
  try {
    const res  = await fetch(`${API_BASE}/fornecedores`);
    const data = await res.json();
    if (data.ok) {
      fornecedoresCache = data.fornecedores || [];
    } else {
      fornecedoresCache = [];
    }
  } catch (err) {
    console.error('Erro ao buscar fornecedores:', err);
    fornecedoresCache = [];
  }
}

function renderFornecedoresList() {
  const list = document.getElementById('suppliers-list');
  if (!list) return;
  if (fornecedoresCache.length === 0) {
    list.innerHTML = `
      <div style="text-align:center;padding:32px 16px;color:var(--ink-35,rgba(13,21,16,0.4))">
        <svg width="40" height="40" viewBox="0 0 20 20" fill="none" style="opacity:0.4;margin-bottom:10px;display:inline-block">
          <path d="M4 16v-2a3 3 0 013-3h6a3 3 0 013 3v2" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
          <circle cx="10" cy="6" r="3.2" stroke="currentColor" stroke-width="1.3"/>
        </svg>
        <div style="font-weight:600;margin-bottom:4px">Nenhum fornecedor cadastrado</div>
        <div style="font-size:13px">Clique em <strong>“Novo Fornecedor”</strong> para adicionar.
        Eles aparecerão automaticamente no select da página de Compras.</div>
      </div>`;
    return;
  }
  list.innerHTML = fornecedoresCache.map(f => `
    <div class="sup-item" data-id="${f.id}" style="display:flex;align-items:flex-start;gap:12px;padding:12px;border:1px solid var(--sage-border,#e3e9e4);border-radius:12px;background:var(--bg-card,#fff);margin-bottom:10px">
      <div style="flex:1;min-width:0">
        <div style="font-weight:600;color:var(--text-1,#0d1510)">${f.nome_fantasia || f.razao_social}</div>
        <div style="font-size:12px;color:var(--ink-35,rgba(13,21,16,0.45));margin-top:2px">${f.razao_social || ''}</div>
        <div style="font-size:12px;color:var(--ink-35,rgba(13,21,16,0.45))">CNPJ ${f.cnpj}${f.contato_nome ? ' · ' + f.contato_nome : ''}${f.contato_telefone ? ' · ' + f.contato_telefone : ''}</div>
      </div>
      <div class="sup-item-actions">
        <button class="sup-btn sup-btn-edit" data-act="edit" data-id="${f.id}" title="Editar">
          <svg viewBox="0 0 16 16" fill="none" width="14" height="14"><path d="M11.5 2.5l2 2L5 13H3v-2L11.5 2.5z" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>
          Editar
        </button>
        <button class="sup-btn sup-btn-delete" data-act="delete" data-id="${f.id}" title="Excluir">
          <svg viewBox="0 0 16 16" fill="none" width="14" height="14"><path d="M3 4.5h10M6.2 4.5V3.2a1 1 0 011-1h1.6a1 1 0 011 1v1.3M12.6 4.5v8.5a1 1 0 01-1 1H4.4a1 1 0 01-1-1V4.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>
          Excluir
        </button>
      </div>
    </div>
  `).join('');
  list.querySelectorAll('[data-act="edit"]').forEach(btn => {
    btn.addEventListener('click', () => openFornecedorForm(parseInt(btn.dataset.id)));
  });
  list.querySelectorAll('[data-act="delete"]').forEach(btn => {
    btn.addEventListener('click', async () => {
      if (!confirm('Tem certeza que deseja excluir este fornecedor?\n\nEle deixará de aparecer na página de Compras.')) return;
      const id = parseInt(btn.dataset.id);
      try {
        const res = await fetch(`${API_BASE}/fornecedores/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if (res.ok) {
          showToast(data.mensagem || 'Fornecedor excluído com sucesso.', 'ok');
          fornecedoresCache = fornecedoresCache.filter(x => x.id !== id);
          renderFornecedoresList();
        } else {
          showToast(data.mensagem || 'Erro ao excluir fornecedor.', 'err');
        }
      } catch (err) {
        console.error('Erro ao excluir fornecedor:', err);
        showToast('Servidor indisponível. Verifique o backend.', 'err');
      }
    });
  });
}

function openSuppliersModal() {
  const so = supOverlay();
  if (!so) return;
  fetchFornecedoresEstoque().then(renderFornecedoresList);
  so.classList.add('open');
  document.body.style.overflow = 'hidden';
}
function closeSuppliersModal() {
  const so = supOverlay();
  if (so) so.classList.remove('open');
  document.body.style.overflow = '';
}
function openSupplierFormModal() {
  const sfo = supFormOverlay();
  if (!sfo) return;
  editandoFornecedorId = null;
  document.getElementById('supplier-form-title').textContent = 'Novo Fornecedor';
  ['sup-nome','sup-razao','sup-cnpj','sup-contato','sup-telefone','sup-email','sup-endereco'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  sfo.classList.add('open');
  document.body.style.overflow = 'hidden';
}
function closeSupplierFormModal() {
  const sfo = supFormOverlay();
  if (sfo) sfo.classList.remove('open');
  document.body.style.overflow = '';
  editandoFornecedorId = null;
}
async function openFornecedorForm(id) {
  const f = fornecedoresCache.find(x => x.id === id);
  if (!f) return;
  editandoFornecedorId = id;
  document.getElementById('supplier-form-title').textContent = 'Editar Fornecedor';
  const v = (idEl, val) => { const el = document.getElementById(idEl); if (el) el.value = val ?? ''; };
  v('sup-nome', f.nome_fantasia);
  v('sup-razao', f.razao_social);
  v('sup-cnpj', f.cnpj);
  v('sup-contato', f.contato_nome);
  v('sup-telefone', f.contato_telefone);
  v('sup-email', f.contato_email);
  v('sup-endereco', f.endereco);
  const so2 = supOverlay();
  if (so2) so2.classList.remove('open');
  const sfo2 = supFormOverlay();
  if (sfo2) sfo2.classList.add('open');
  document.body.style.overflow = 'hidden';
}
async function salvarFornecedor() {
  const nome   = document.getElementById('sup-nome').value.trim();
  const razao  = document.getElementById('sup-razao').value.trim();
  const cnpj   = document.getElementById('sup-cnpj').value.trim();
  if (!nome || !razao || !cnpj) {
    showToast('Preencha nome fantasia, razão social e CNPJ.', 'err');
    return;
  }
  const payload = {
    nome_fantasia: nome,
    razao_social:  razao,
    cnpj,
    contato_nome:     document.getElementById('sup-contato').value.trim() || null,
    contato_telefone: document.getElementById('sup-telefone').value.trim() || null,
    contato_email:    document.getElementById('sup-email').value.trim() || null,
    endereco:         document.getElementById('sup-endereco').value.trim() || null,
  };
  try {
    let res;
    if (editandoFornecedorId) {
      res = await fetch(`${API_BASE}/fornecedores/${editandoFornecedorId}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
      });
    } else {
      res = await fetch(`${API_BASE}/fornecedores`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
      });
    }
    const data = await res.json();
    if (data.ok) {
      showToast(editandoFornecedorId ? 'Fornecedor atualizado!' : 'Fornecedor cadastrado!', 'ok');
      closeSupplierFormModal();
      await fetchFornecedoresEstoque();
      renderFornecedoresList();
    } else {
      showToast(data.mensagem || 'Erro ao salvar fornecedor.', 'err');
    }
  } catch (err) {
    console.error('Erro ao salvar fornecedor:', err);
    showToast('Erro de conexão com o servidor.', 'err');
  }
}

document.getElementById('btn-suppliers')?.addEventListener('click', openSuppliersModal);
document.getElementById('suppliers-close')?.addEventListener('click', closeSuppliersModal);
document.getElementById('suppliers-cancel')?.addEventListener('click', closeSuppliersModal);
document.getElementById('suppliers-new')?.addEventListener('click', openSupplierFormModal);
document.addEventListener('click', e => {
  const so = supOverlay();
  if (so && e.target === so) closeSuppliersModal();
});
document.getElementById('supplier-form-close')?.addEventListener('click', closeSupplierFormModal);
document.getElementById('supplier-form-cancel')?.addEventListener('click', closeSupplierFormModal);
document.getElementById('supplier-form-save')?.addEventListener('click', salvarFornecedor);
document.addEventListener('click', e => {
  const sfo = supFormOverlay();
  if (sfo && e.target === sfo) closeSupplierFormModal();
});

/* ── Relógio em tempo real ── */
function updateRealtimeClock() {
  const subtitle = document.getElementById('page-subtitle');
  if (!subtitle) return;
  const now = new Date();
  const time = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`;
  subtitle.textContent = `Situação do estoque em tempo real · Última atualização: ${time}`;
}
updateRealtimeClock();
__fcSetInterval(updateRealtimeClock, 1000);
