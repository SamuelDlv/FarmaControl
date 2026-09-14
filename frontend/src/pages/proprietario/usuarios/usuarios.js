/* ══════════════════════════════════════════════════════════════════════
 * FARMAControl — GESTÃO DE USUÁRIOS (PROPRIETÁRIO)
 * ══════════════════════════════════════════════════════════════════════
 *
 * Gerencia os usuários do sistema:
 * - Grid de usuários com avatar, cargo, status (ativo/inativo)
 * - Modal de edição (nome, email, senha, cargo)
 * - Modal de permissões por perfil de acesso
 * - Modal de criação de novo usuário
 * - Análise de cadastros pendentes (aprovar/rejeitar)
 * - Exportação CSV de usuários
 * - Relatórios de atividades (logs)
 *
 * Dados são carregados da API: GET/POST/PUT /usuarios/*
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

var allUsers = [];

  /* fetchUsuarios(): Busca todos os usuários do sistema via API. */
  async function fetchUsuarios() {
  const token = window.__fcPageToken;
  try {
    const res = await fetch(`${API_BASE}/admin/usuarios`);
    if (window.__fcPageToken !== token) return;
    const data = await res.json();
    if (data.ok) {
      allUsers = data.usuarios;
      renderUserGrid();
      updateKPIs();
      loadLogs();
    }
  } catch (err) {
    console.error('Erro ao buscar usuários:', err);
    toast('Não foi possível conectar ao servidor. Verifique se o backend está rodando.', 'error');
  } finally {
    // Garante que o estado vazio seja mostrado mesmo em caso de falha
    renderUserGrid();
  }
}

  /* renderUserEmptyState(): Mostra mensagem quando não há usuários cadastrados. */
  function renderUserEmptyState(message) {
  const grid = document.querySelector('.user-grid');
  if (!grid) return;
  grid.innerHTML = `
    <div style="grid-column: 1/-1; padding: 48px 24px; text-align: center; color: var(--ink-35);">
      <div style="font-size: 34px; margin-bottom: 10px; opacity: 0.6;">👥</div>
      <div style="font-weight: 600; margin-bottom: 4px;">${message}</div>
      <div style="font-size: 12.5px;">Clique em <strong>Novo Usuário</strong> para cadastrar o primeiro acesso ao sistema.</div>
    </div>
  `;
}

  /* renderUserGrid(): Renderiza o grid de cards de usuários com avatar e status. */
  function renderUserGrid() {
  const grid = document.querySelector('.user-grid');
  if (!grid) return;
  
  grid.innerHTML = '';
  
  const searchTerm = document.getElementById('table-search')?.value.toLowerCase() || '';
  const activeType = document.querySelector('.ftab.active')?.dataset.type || 'all';

    const filtered = allUsers.filter(u => {
    const matchSearch = u.nome.toLowerCase().includes(searchTerm) || u.email.toLowerCase().includes(searchTerm);
    const matchType = activeType === 'all' || 
                     (activeType === 'pendentes' && u.status === 'pendente') ||
                     (activeType === 'ativos' && u.status === 'ativo') ||
                     (activeType === 'inativos' && u.status === 'inativo');
    return matchSearch && matchType;
  });

  const headBadge = document.querySelector('.card-head-l .badge');
  if (headBadge) headBadge.textContent = `${filtered.length} usuário${filtered.length !== 1 ? 's' : ''}`;

  if (filtered.length === 0 && allUsers.length === 0) {
    renderUserEmptyState('Nenhum usuário cadastrado');
    return;
  }
  if (filtered.length === 0) {
    grid.innerHTML = `
      <div style="grid-column: 1/-1; padding: 40px 24px; text-align: center; color: var(--ink-35);">
        Nenhum resultado encontrado para este filtro.
      </div>
    `;
    return;
  }

  filtered.forEach(u => {
    const initials = u.nome.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
    const statusClass = u.status === 'ativo' ? '' : (u.status === 'inativo' ? 'offline' : 'pendente');
    const roleClass = u.perfil === 'admin' ? 'admin' : (u.perfil === 'visualizador' ? 'viewer' : '');
    const avatarClass = u.perfil === 'admin' ? '' : (u.perfil === 'farmaceutico' ? 'blue' : (u.perfil === 'atendente' ? 'amber' : 'red'));

    const card = document.createElement('div');
    card.className = 'user-card';
    card.dataset.type = u.status === 'ativo' ? 'ativos' : (u.status === 'inativo' ? 'inativos' : 'pendentes');
    
    let actionsHtml = '';
    if (u.status === 'pendente') {
      actionsHtml = `
        <button class="user-action-btn" style="background: var(--sage-pale); color: var(--sage); border-color: var(--sage-border);" onclick="analisarCadastro(${u.id}, 'aprovado')">Aprovar</button>
        <button class="user-action-btn danger" onclick="analisarCadastro(${u.id}, 'rejeitado')">Rejeitar</button>
      `;
    } else {
      actionsHtml = `
        <button class="user-action-btn" onclick="openEditModal(${u.id})">Editar</button>
        <button class="user-action-btn ${u.status === 'ativo' ? 'danger' : ''}" onclick="toggleUserStatus(${u.id}, '${u.status}')">
          ${u.status === 'ativo' ? 'Desativar' : 'Ativar'}
        </button>
      `;
    }

    card.innerHTML = `
      <div class="user-card-status ${statusClass}"></div>
      <div class="user-card-avatar ${avatarClass}">${initials}</div>
      <div class="user-card-name">${u.nome}</div>
      <span class="user-card-role ${roleClass}">${u.perfil_nome}</span>
      <div class="user-card-meta">${u.email}</div>
      <div class="user-card-meta">Último acesso: ${u.ultimo_acesso ? new Date(u.ultimo_acesso).toLocaleString('pt-BR') : 'Nunca'}</div>
      <div class="user-card-actions">
        ${actionsHtml}
      </div>
    `;
    grid.appendChild(card);
  });
}

  /* toggleUserStatus(): Ativa/desativa um usuário (com confirmação). */
  async function toggleUserStatus(id, currentStatus) {
  // Toggle: ativo ↔ inativo (frontend normalizado pelo backend; backend converte para aprovado/rejeitado)
  const newStatus = currentStatus === 'ativo' ? 'inativo' : 'ativo';
  try {
    const res = await fetch(`${API_BASE}/admin/usuarios/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus })
    });
    const data = await res.json();
    if (data.ok) {
      toast(`Usuário ${newStatus === 'ativo' ? 'ativado' : 'desativado'}!`, 'success');
      fetchUsuarios();
    } else {
      toast(data.mensagem || 'Erro ao alterar status.', 'error');
    }
  } catch (err) {
    toast('Erro ao alterar status.', 'error');
  }
}

  /* updateKPIs(): Atualiza os contadores de KPI (total usuários, ativos, inativos). */
  function updateKPIs() {
  const ativos = allUsers.filter(u => u.status === 'ativo').length;
  const pendentes = allUsers.filter(u => u.status === 'pendente').length;
  // Atualizar badge da sidebar, se existir
  const sbBadge = document.getElementById('sb-badge-pendentes');
  if (sbBadge) {
    sbBadge.textContent = pendentes;
    sbBadge.style.display = pendentes > 0 ? 'block' : 'none';
  }
}

  /* renderLogItems(): Renderiza os itens de log de atividades do usuário. */
  function renderLogItems(logs) {
  const items = (logs || []).map(log => {
    const nome = log.usuario_nome || 'Usuário';
    const initials = nome.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
    const when = log.criado_em ? new Date(log.criado_em).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : '—';
    return `
      <div class="log-item">
        <div class="log-avatar">${initials}</div>
        <div class="log-body">
          <div class="log-action"><strong>${nome}</strong> ${log.acao}</div>
          <div class="log-meta">${log.detalhes || ''}</div>
        </div>
        <div class="log-time">${when}</div>
      </div>
    `;
  });
  if (items.length === 0) {
    items.push('<div style="padding:20px;text-align:center;font-size:11px;color:var(--ink-35);">Nenhum log de atividade disponível.</div>');
  }
  return items.join('');
}

  /* loadLogs(): Carrega o histórico de atividades (logs) do sistema. */
  async function loadLogs() {
  try {
    const res = await fetch(`${API_BASE}/admin/logs?limit=10`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data.ok) {
      // Painel lateral de logs
      const list = document.querySelector('.log-list');
      if (list) list.innerHTML = renderLogItems(data.logs);
      // Modal de histórico completo
      const full = document.getElementById('full-history-list');
      if (full) full.innerHTML = renderLogItems(data.logs);
    } else {
      throw new Error('resposta inválida');
    }
  } catch (err) {
    console.error('Erro ao carregar logs:', err);
    // Falha graciosa: não quebra a página, apenas mostra estado vazio
    const list = document.querySelector('.log-list');
    if (list) list.innerHTML = '<div style="padding:20px;text-align:center;font-size:11px;color:var(--ink-35);">Nenhum log de atividade disponível.</div>';
  }
}

  /* openEditModal(): Abre o modal de edição com dados do usuário preenchidos. */
  function openEditModal(id) {
  const u = allUsers.find(x => x.id === id);
  if (!u) return;
  
  const modal = document.getElementById('modal-edit-user');
  modal.dataset.userId = id;
  
  modal.querySelector('input[placeholder="Nome completo"]').value = u.nome;
  modal.querySelector('input[placeholder="email@farmacia.com"]').value = u.email;
  // Seleciona o perfil pelo slug retornado pelo backend (slug: admin, farmaceutico, ...)
  const select = modal.querySelector('select');
  const slugToLabel = { 'admin': 'Administrador', 'farmaceutico': 'Farmacêutico', 'atendente': 'Atendente', 'visualizador': 'Visualizador', 'ti': 'TI' };
  select.value = slugToLabel[u.perfil] || u.perfil_nome || select.value;
  
  modal.classList.add('open');
}

  /* saveUserChanges(): Salva as alterações feitas no modal de edição. */
  async function saveUserChanges() {
  const modal = document.getElementById('modal-edit-user');
  const id = modal.dataset.userId;
  
  const perfilMap = { 'Administrador': 'admin', 'Farmacêutico': 'farmaceutico', 'Atendente': 'atendente', 'Visualizador': 'visualizador', 'TI': 'ti' };
  const nomeCompleto = (modal.querySelector('input[placeholder="Nome completo"]').value || '').trim();
  const partes = nomeCompleto.split(' ');
  const payload = {
    nome: partes[0] || nomeCompleto,
    email: modal.querySelector('input[placeholder="email@farmacia.com"]').value,
    perfil: perfilMap[modal.querySelector('select').value] || modal.querySelector('select').value,
    senha: modal.querySelector('#user-password').value || null
  };
  if (partes.length >= 2) payload.sobrenome = partes.slice(1).join(' ');

  try {
    const res = await fetch(`${API_BASE}/admin/usuarios/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.ok) {
      toast('Alterações salvas!', 'success');
      modal.classList.remove('open');
      fetchUsuarios();
    } else {
      toast(data.mensagem, 'error');
    }
  } catch (err) {
    toast('Erro ao salvar alterações.', 'error');
  }
}

  /* analisarCadastro(): Aprova ou rejeita um cadastro pendente de novo usuário. */
  async function analisarCadastro(id, decisao) {
  try {
    const res = await fetch(`${API_BASE}/admin/analisar-cadastro`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ usuario_id: id, decisao })
    });
    const data = await res.json();
    if (data.ok) {
      toast(data.mensagem, 'success');
      fetchUsuarios();
    } else {
      toast(data.mensagem, 'error');
    }
  } catch (err) {
    toast('Erro ao processar solicitação.', 'error');
  }
}

window.analisarCadastro = analisarCadastro;



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
            el.textContent = 'R$ ' + val.toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
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
  const months = ['janeiro','fevereiro','março','abril','maio','junho','julho','agosto','setembro','outubro','novembro','dezembro'];
  const now = new Date();
  const currentYear = now.getFullYear();
  const monthLabel = () => `Período atual: ${months[now.getMonth()]} ${currentYear}`;
  const quarterLabel = () => `Período atual: ${Math.ceil((now.getMonth() + 1) / 3)}º trimestre ${currentYear}`;
  const yearLabel = () => `Período atual: ${currentYear - 1}–${currentYear}`;

  document.querySelectorAll('.period-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const labels = { month: monthLabel(), quarter: quarterLabel(), year: yearLabel() };
      const label = labels[btn.dataset.period] || monthLabel();
      const sub = document.getElementById('page-subtitle');
      const ativos = allUsers.filter(u => u.status === 'ativo').length;
      if (sub) sub.textContent = `Gerenciamento de acesso e permissões do sistema · ${ativos} usuário${ativos !== 1 ? 's' : ''} ativo${ativos !== 1 ? 's' : ''}`;
      toast(`Período alterado: ${label}`, 'info');
    });
  });
}

/* (Filtro por grade substituído pela filtragem reativa em renderUserGrid) */

/* ══ MODALS MANAGEMENT ══ */
function initModals() {
  // Fechar modal ao clicar no overlay
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', e => {
      if (e.target === overlay) {
        overlay.classList.remove('open');
      }
    });
  });

  // Fechar modal ao pressionar Escape
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-overlay.open').forEach(modal => {
        modal.classList.remove('open');
      });
    }
  });
}

/* ══ CRIAR NOVO USUÁRIO ══ */
async function criarNovoUsuario() {
  const modal = document.getElementById('modal-new-user');
  const nomeInput   = modal.querySelector('input[placeholder="Ex: Maria Silva"]');
  const emailInput  = modal.querySelector('input[placeholder="email@farmacia.com"]');
  const perfilSel   = modal.querySelector('select');
  const senhaInput  = modal.querySelector('input[type="password"]');

  const nomeCompleto = (nomeInput?.value || '').trim();
  const partes = nomeCompleto.split(' ');
  const nome = partes[0] || '';
  const sobrenome = partes.slice(1).join(' ') || 'Sobrenome';
  const email = (emailInput?.value || '').trim();
  const perfilMap = { 'Administrador': 'admin', 'Farmacêutico': 'farmaceutico', 'Atendente': 'atendente', 'Visualizador': 'visualizador' };
  const role = perfilMap[perfilSel?.value] || 'atendente';
  const senha = senhaInput?.value || '';

  if (partes.length < 2) { toast('Informe o nome e o sobrenome completos.', 'error'); return; }
  if (!email) { toast('Informe o e-mail.', 'error'); return; }

  try {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nome, sobrenome, email, role, password: senha || `${role}${Date.now() % 10000}!` })
    });
    const data = await res.json();
    if (data.ok || res.ok) {
      toast('Usuário cadastrado! Ele aparecerá como pendente até ser aprovado.', 'success');
      modal.classList.remove('open');
      // Limpa os campos para o próximo cadastro
      nomeInput.value = ''; emailInput.value = ''; senhaInput.value = '';
      fetchUsuarios();
    } else {
      toast(data.mensagem || 'Erro ao cadastrar o usuário.', 'error');
    }
  } catch (err) {
    console.error('Erro ao criar usuário:', err);
    toast('Servidor indisponível. Verifique o backend.', 'error');
  }
}

/* ══ EXPORTAR USUÁRIOS (CSV) ══ */
async function exportUsuariosCSV() {
  try {
    const res = await fetch(`${API_BASE}/admin/usuarios`);
    const data = await res.json();
    const usuarios = (data.ok ? data.usuarios : []) || [];
    if (usuarios.length === 0) {
      toast('Nenhum usuário para exportar.', 'info');
      return;
    }
    const header = 'Nome;E-mail;Perfil;Status;Último Acesso';
    const rows = usuarios.map(u => [
      u.nome, u.email,
      u.perfil_nome || '', u.status || '',
      u.ultimo_acesso ? new Date(u.ultimo_acesso).toLocaleString('pt-BR') : 'Nunca'
    ].map(v => String(v).replace(/"/g, '""')).join(';'));
    const csv = '\uFEFF' + [header, ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `usuarios_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast(`Exportados ${usuarios.length} usuário(s)!`, 'success');
  } catch (err) {
    console.error('Erro ao exportar usuários:', err);
    toast('Erro ao exportar. Verifique o backend.', 'error');
  }
}

/* ══ PERMISSIONS MODAL ══ */
function initPermissionsModal() {
  // Bolinhas de permissões selecionáveis
  document.querySelectorAll('#modal-permissions .perm-item').forEach(item => {
    item.addEventListener('click', e => {
      // Evita que o clique no checkbox interfira
      if (e.target.tagName === 'INPUT') return;
      
      e.preventDefault();
      item.classList.toggle('active');
      const checkbox = item.querySelector('input[type="checkbox"]');
      if (checkbox) {
        checkbox.checked = item.classList.contains('active');
      }
    });
  });

  // Também permitir clique direto no checkbox
  document.querySelectorAll('#modal-permissions .perm-item input[type="checkbox"]').forEach(checkbox => {
    checkbox.addEventListener('change', () => {
      const item = checkbox.closest('.perm-item');
      if (item) {
        if (checkbox.checked) {
          item.classList.add('active');
        } else {
          item.classList.remove('active');
        }
      }
    });
  });
}

/* ══ USER ACTIONS ══ */
function initReportButtons() {
  const actionNames = {
    'rpt-estoque': 'Novo Usuário',

    'rpt-venc':    'Redefinir Senhas',
    'rpt-fin':     'Exportar Log Completo',
  };
  Object.entries(actionNames).forEach(([id, name]) => {
    const item = document.getElementById(id);
    if (!item) return;
    const modalMap = { 'rpt-estoque': 'modal-new-user', 'rpt-venc': 'modal-manage-profiles', 'rpt-fin': 'modal-full-history' };
    item.addEventListener('click', () => {
      const target = modalMap[id];
      if (target) document.getElementById(target)?.classList.add('open');
      toast(`Abrindo: ${name}…`, 'info');
    });
  });

  // Botões de ação globais com modais
  document.querySelectorAll('[data-modal]').forEach(btn => {
    if (btn.classList.contains('user-action-btn')) return; // já tratado acima
    btn.addEventListener('click', e => {
      e.stopPropagation();
      const modalId = btn.dataset.modal;
      const modalMap = {
        'edit-profiles': 'modal-edit-profiles',
        'manage-profiles': 'modal-manage-profiles',
        'full-history': 'modal-full-history'
      };

      if (modalMap[modalId]) {
        document.getElementById(modalMap[modalId])?.classList.add('open');
      }
    });
  });

  // Encerrar sessões
  document.querySelectorAll('.exp-hist-dl').forEach(btn => {
    btn.addEventListener('click', () => toast('Sessão encerrada com sucesso.', 'success'));
  });

  document.getElementById('btn-export')?.addEventListener('click', () => exportUsuariosCSV());
  document.getElementById('btn-new-user')?.addEventListener('click', () => {
    document.getElementById('modal-new-user')?.classList.add('open');
  });
  document.querySelector('.tb-btn.primary')?.addEventListener('click', () => {
    document.getElementById('modal-new-user')?.classList.add('open');
  });

  // Fechar modal ao clicar no overlay
  document.getElementById('modal-new-user')?.addEventListener('click', e => {
    if (e.target === document.getElementById('modal-new-user')) {
      document.getElementById('modal-new-user').classList.remove('open');
    }
  });

  // Botão criar usuário no modal
  document.querySelector('#modal-new-user .btn-save')?.addEventListener('click', criarNovoUsuario);

  // Botão salvar do modal de editar perfis (apenas feedback)
  document.querySelector('#modal-edit-profiles .btn-save')?.addEventListener('click', () => {
    document.getElementById('modal-edit-profiles').classList.remove('open');
    toast('Perfis salvos com sucesso!', 'success');
  });
}

/* ══ CARREGAR KPIs DE USUÁRIOS DO BANCO ══ */
async function loadUsuariosKPIs() {
  try {
    const res    = await fetch(`${API_BASE}/admin/pendentes`);
    const result = await res.json();
    if (!result.ok) return;
    const pendentes = (result.pendentes || []).length;
    // Atualiza badge de pendentes se existir
    document.querySelectorAll('.kpi-value[data-target]').forEach(el => {
      const card = el.closest('.kpi-card');
      if (!card) return;
      if (card.textContent.includes('Pendentes') || card.textContent.includes('pendente')) {
        el.dataset.target = pendentes;
      }
    });
    initCounters();
  } catch (err) {
    console.error('Erro ao carregar KPIs de usuários:', err);
  }
}

/* ══ REFRESH ─ recarrega dados reais do banco ══ */
document.getElementById('btn-refresh')?.addEventListener('click', async () => {
  const svg = document.querySelector('#btn-refresh svg');
  if (svg) {
    svg.style.transition = 'transform 0.6s';
    svg.style.transform  = 'rotate(360deg)';
    setTimeout(() => { svg.style.transition = 'none'; svg.style.transform = 'rotate(0deg)'; }, 650);
  }
  await Promise.all([fetchUsuarios(), loadUsuariosKPIs()]);
  toast('Dados atualizados com sucesso.', 'success');
});


/* ══ TOAST — centralizado no global-settings.js ══ */
function toast(msg, type = 'success') {
  if (window.FarmaControlSettings && typeof window.FarmaControlSettings.showToast === 'function') {
    window.FarmaControlSettings.showToast(
      msg,
      type === 'success' ? 'success' : type === 'error' ? 'error' : type
    );
  }
}

/* ══ PROFILE TABS ══ */
function switchProfileTab(btn) {
  const profileId = btn.dataset.profile;
  
  // Remover aba ativa anterior
  document.querySelectorAll('.profile-tab').forEach(tab => {
    tab.classList.remove('active');
    tab.style.color = 'var(--ink-35)';
    tab.style.borderBottomColor = 'transparent';
  });
  
  // Ativar aba clicada
  btn.classList.add('active');
  btn.style.color = 'var(--sage)';
  btn.style.borderBottomColor = 'var(--sage)';
  
  // Esconder todos os conteúdos
  document.querySelectorAll('.profile-content').forEach(content => {
    content.style.display = 'none';
  });
  
  // Mostrar conteúdo da aba selecionada
  document.getElementById('profile-' + profileId).style.display = 'block';
}

/* ══ PROFILE PERMISSIONS ══ */
function initProfilePermissions() {
  document.querySelectorAll('#modal-edit-profiles .profile-perm').forEach(item => {
    item.addEventListener('click', e => {
      if (e.target.tagName === 'INPUT') return;
      
      e.preventDefault();
      item.classList.toggle('active');
      const checkbox = item.querySelector('input[type="checkbox"]');
      if (checkbox && !checkbox.disabled) {
        checkbox.checked = item.classList.contains('active');
      }
    });
  });
  
  document.querySelectorAll('#modal-edit-profiles .profile-perm input[type="checkbox"]').forEach(checkbox => {
    if (checkbox.disabled) return;
    checkbox.addEventListener('change', () => {
      const item = checkbox.closest('.profile-perm');
      if (item) {
        if (checkbox.checked) {
          item.classList.add('active');
        } else {
          item.classList.remove('active');
        }
      }
    });
  });
}

/* ══ PASSWORD MANAGEMENT ══ */
function togglePasswordVisibility() {
  const input = document.getElementById('user-password');
  const btn = document.getElementById('toggle-password');
  if (input.type === 'password') {
    input.type = 'text';
    btn.textContent = 'Ocultar';
  } else {
    input.type = 'password';
    btn.textContent = 'Mostrar';
  }
}

function generatePassword() {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%';
  let password = '';
  for (let i = 0; i < 12; i++) {
    password += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  const input = document.getElementById('user-password');
  if (input) {
    input.value = password;
    input.type = 'text';
    const btn = document.getElementById('toggle-password');
    if (btn) btn.textContent = 'Ocultar';
    toast('Senha gerada com sucesso!', 'success');
  }
}

/* (Atalhos de teclado e gerenciamento da sidebar delegados ao sidebar-init.js) */

/* ══ INIT ══ */
document.addEventListener('DOMContentLoaded', () => {
  // O global-settings.js já cuida da identidade do usuário e configurações básicas.
  // Vamos apenas garantir que a sidebar local funcione se necessário, mas o global-settings já faz o applyUser.
  

  initDate();
  initCounters();
  initPeriodSelector();
  
  document.getElementById('table-search')?.addEventListener('input', renderUserGrid);
  document.querySelectorAll('.ftab[data-type]').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.ftab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      renderUserGrid();
    });
  });

  initModals();
  initPermissionsModal();
  initProfilePermissions();
  initReportButtons();
  fetchUsuarios();
  
  document.querySelector('#modal-edit-user .btn-save')?.addEventListener('click', saveUserChanges);

  // Garantir que o usuário logado apareça na sidebar
  if (window.FarmaControlSettings) {
    window.FarmaControlSettings.applyUser();
  }

});

/* (Logout delegado ao sidebar-init.js: já limpa a sessão e redireciona corretamente) */

/* ══ BOTÃO EDITAR PERFIS (abre modal read-only de visualização) ══ */
function initUsuariosViewLink() {
  document.querySelectorAll('.card-link').forEach(btn => {
    const text = btn.textContent.trim();
    if (text.includes('Editar perfis')) {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        if (!window.fcOpenViewModal) return;
        // Pega a tabela de permissões por perfil
        const permSection = btn.closest('.card');
        const table = permSection?.parentElement?.querySelector('table') || document.querySelector('.permissions-table, table');
        if (table) {
          window.fcOpenViewModal('Permissões por Perfil', 'Visão geral dos perfis e módulos ativos', `<div style="overflow-x:auto;">${table.outerHTML}</div>`);
        } else {
          window.fcOpenViewModal('Permissões por Perfil', 'Visão geral dos perfis e módulos ativos', '<p>Dados não disponíveis.</p>');
        }
      });
    }
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initUsuariosViewLink);
} else {
  initUsuariosViewLink();
}
