/* ══════════════════════════════════════════════════════════════════════
 * FARMAControl — PÁGINA DE AUTENTICAÇÃO (LOGIN/CADASTRO)
 * ══════════════════════════════════════════════════════════════════════
 *
 * Página de acesso ao sistema com duas abas:
 * - Entrar: Login com email e senha
 * - Cadastrar: Registro de novo usuário com seleção de perfil
 *
 * Recursos:
 * - Validação de email (formato válido)
 * - Medidor de força de senha (fraca/média/forte)
 * - Toggle de visibilidade de senha (olho)
 * - Loading states nos botões
 * - Toast de feedback (sucesso/erro)
 * - Design glassmorphism no painel esquerdo
 * ══════════════════════════════════════════════════════════════════════ */

/**
 * FarmaControl — Auth Script
 * API: Flask backend em /auth/login e /auth/register
 */

/* ═══════════════════════════════════════════
   CONFIGURAÇÃO DA API
═══════════════════════════════════════════ */
const API_BASE = window.FarmaControlSettings ? window.FarmaControlSettings.API_BASE : 'http://localhost:5000'; // Altere para o endereço do seu servidor

/* ═══════════════════════════════════════════
   ROLE DESCRIPTIONS
═══════════════════════════════════════════ */
const ROLE_INFO = {
  proprietario: 'Visão total do negócio: financeiro, relatórios estratégicos e gestão de usuários.',
  farmaceutico: 'Responsável técnico: controle de estoque, validade e dispensação de controlados.',
  admin:        'Gestão operacional completa: estoque, compras e relatórios de vendas.',
  atendente:    'Frente de loja: consulta de produtos e registro de vendas.',
  compras:      'Gestão de suprimentos: pedidos de compra e análise de demanda.',
  ti:           'Manutenção técnica: logs, configurações de sistema e integrações.',
};

/* ═══════════════════════════════════════════
   UTILS
═══════════════════════════════════════════ */
const $ = (id) => document.getElementById(id);
const isValidEmail = (v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);

  /* setFieldError(): Exibe mensagem de erro abaixo de um campo específico (input). */
  function setFieldError(inputId, errId, hasError) {
  const input = $(inputId);
  const err   = $(errId);
  if (!input || !err) return;
  input.classList.toggle('is-error', hasError);
  err.classList.toggle('show', hasError);
}

  /* clearFieldError(): Remove a mensagem de erro de um campo. */
  function clearFieldError(inputId, errId) {
  setFieldError(inputId, errId, false);
}

const CAMPO_MAP = {
  nome:      { input: 'reg-nome',      err: 'err-reg-nome' },
  sobrenome: { input: 'reg-sobrenome', err: 'err-reg-sobrenome' },
  email:     { input: 'reg-email',     err: 'err-reg-email' },
  role:      { input: null,            err: 'err-reg-role', custom: 'custom-select' },
  password:  { input: 'reg-password',  err: 'err-reg-password' },
};

  /* highlightApiError(): Destaca um campo com erro retornado pela API. */
  function highlightApiError(campo, mensagem) {
  const map = CAMPO_MAP[campo];
  if (!map) return;
  if (map.custom) {
    const cs = document.getElementById(map.custom);
    if (cs) cs.classList.add('is-error');
  } else if (map.input) {
    const input = $(map.input);
    if (input) input.classList.add('is-error');
  }
  const errEl = $(map.err);
  if (errEl) {
    errEl.textContent = mensagem;
    errEl.classList.add('show');
  }
}

  /* showToast(): Exibe notificação temporária no topo da tela. */
  function showToast(message, type = 'success') {
  const toast = $('toast');
  const msg   = toast.querySelector('.toast-msg');
  const icon  = toast.querySelector('.toast-icon');

  if (type === 'error') {
    icon.innerHTML = `<circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="1.5"/><path d="M10 6v5M10 13v1" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>`;
  } else if (type === 'warning') {
    icon.innerHTML = `<path d="M10 3L18 17H2L10 3z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M10 9v4M10 14.5v.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>`;
  } else {
    icon.innerHTML = `<circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="1.5"/><path d="M7 10l2 2 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>`;
  }

  msg.textContent = message;
  toast.className = `toast ${type}`;
  toast.offsetHeight;
  toast.classList.add('show');

  clearTimeout(toast._timer);
  const duration = type === 'warning' ? 7000 : 4000;
  toast._timer = setTimeout(() => toast.classList.remove('show'), duration);
}

  /* setButtonLoading(): Ativa/desativa o estado de loading (spinner) no botão. */
  function setButtonLoading(btnId, loading) {
  const btn = $(btnId);
  if (!btn) return;
  btn.classList.toggle('loading', loading);
  btn.disabled = loading;
}

/* ═══════════════════════════════════════════
   CHAMADAS À API
═══════════════════════════════════════════ */
  /* apiFetch(): Faz requisição à API com tratamento de erro e timeout. */
  async function apiFetch(path, body) {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(body),
      credentials: 'include',
    });
    const data = await res.json().catch(() => ({}));
    return { ok: res.ok, status: res.status, data };
  } catch {
    return { ok: false, status: 0, data: { mensagem: 'Sem conexão com o servidor. Verifique se o backend está rodando.' } };
  }
}

/* ═══════════════════════════════════════════
   TABS
═══════════════════════════════════════════ */
  /* initTabs(): Configura a alternância entre abas Entrar/Cadastrar. */
  function initTabs() {
  const btns      = document.querySelectorAll('.tab-btn');
  const panels    = document.querySelectorAll('.form-panel');
  const indicator = document.querySelector('.tab-indicator');

  btns.forEach((btn, idx) => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.tab;
      btns.forEach((b) => { b.classList.remove('active'); b.setAttribute('aria-selected', 'false'); });
      btn.classList.add('active');
      btn.setAttribute('aria-selected', 'true');
      indicator.classList.toggle('right', idx === 1);
      panels.forEach((p) => p.classList.remove('active'));
      const panel = $(`panel-${target}`);
      if (panel) panel.classList.add('active');
    });
  });
}

/* ═══════════════════════════════════════════
   EYE TOGGLES
═══════════════════════════════════════════ */
  /* initEyeToggles(): Configura o botão de "olho" para mostrar/esconder senha. */
  function initEyeToggles() {
  document.querySelectorAll('.eye-toggle').forEach((btn) => {
    btn.addEventListener('click', () => {
      const input  = $(btn.dataset.target);
      const isPass = input.type === 'password';
      input.type   = isPass ? 'text' : 'password';
      btn.querySelector('.eye-open').style.display   = isPass ? 'none' : '';
      btn.querySelector('.eye-closed').style.display = isPass ? ''     : 'none';
      btn.setAttribute('aria-label', isPass ? 'Ocultar senha' : 'Mostrar senha');
    });
  });
}

/* ═══════════════════════════════════════════
   PASSWORD STRENGTH
═══════════════════════════════════════════ */
const STRENGTH_LEVELS = [
  { label: 'Muito fraca', color: 'var(--err)', pct: '20%' },
  { label: 'Fraca',       color: 'var(--gold)', pct: '40%' },
  { label: 'Razoável',    color: 'var(--gold-light)', pct: '60%' },
  { label: 'Boa',         color: 'var(--ok)', pct: '80%' },
  { label: 'Forte',       color: 'var(--sage)', pct: '100%' },
];

  /* calcStrength(): Calcula a força da senha (0-4) baseado em comprimento, maiúsculas, números, símbolos. */
  function calcStrength(val) {
  if (!val) return -1;
  let score = 0;
  if (val.length >= 8)  score++;
  if (val.length >= 12) score++;
  if (/[A-Z]/.test(val)) score++;
  if (/[0-9]/.test(val)) score++;
  if (/[^A-Za-z0-9]/.test(val)) score++;
  return Math.min(score, 4);
}

  /* initStrengthMeter(): Inicializa o medidor visual de força de senha (barras coloridas). */
  function initStrengthMeter() {
  const input = $('reg-password');
  const fill  = $('strength-fill');
  const text  = $('strength-text');
  if (!input) return;
  input.addEventListener('input', () => {
    const score = calcStrength(input.value);
    if (score < 0) { fill.style.width = '0%'; text.textContent = ''; text.style.color = ''; return; }
    const level = STRENGTH_LEVELS[score];
    fill.style.width = level.pct; fill.style.background = level.color;
    text.textContent = level.label; text.style.color = level.color;
  });
}

/* ═══════════════════════════════════════════
   AUTO-CLEAR ERRORS
═══════════════════════════════════════════ */
  /* initAutoClear(): Limpa os campos ao alternar entre abas Entrar/Cadastrar. */
  function initAutoClear() {
  document.querySelectorAll('input, select').forEach((el) => {
    el.addEventListener('input', () => {
      el.classList.remove('is-error');
      const errEl = document.getElementById('err-' + el.id);
      if (errEl) errEl.classList.remove('show');
    });
  });
}

/* ═══════════════════════════════════════════
   LOGIN FORM
═══════════════════════════════════════════ */
  /* initLoginForm(): Configura o formulário de login (validação + envio). */
  function initLoginForm() {
  const form = $('form-login');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const email = $('login-email').value.trim();
    const pass  = $('login-password').value;
    let valid   = true;

    if (!isValidEmail(email)) { setFieldError('login-email', 'err-login-email', true); valid = false; }
    else { clearFieldError('login-email', 'err-login-email'); }

    if (!pass) { setFieldError('login-password', 'err-login-password', true); valid = false; }
    else { clearFieldError('login-password', 'err-login-password'); }

    if (!valid) return;

    setButtonLoading('btn-login', true);
    const { ok, status, data } = await apiFetch('/auth/login', { email, password: pass });
    setButtonLoading('btn-login', false);

    if (!ok) {
      const tipo = status === 403 ? 'warning' : 'error';
      showToast(data.mensagem || 'Erro ao fazer login.', tipo);
      if (status === 401) {
        setFieldError('login-email',    'err-login-email',    true);
        setFieldError('login-password', 'err-login-password', true);
      }
      return;
    }

    const usuario = data.usuario;
    showToast(`Bem-vindo, ${usuario.nome}! Redirecionando…`, 'success');
    sessionStorage.setItem('farmacontrol_usuario', JSON.stringify(usuario));

    const ROTAS = {
      proprietario: '../proprietario/dashboard/dashboard.html',
      farmaceutico: '../farmaceutico/dashboard/dashboard.html',
      admin:        '../gerente/dashboard/dashboard.html',
      atendente:    '../balconista/dashboard/dashboard.html',
      compras:      '../compras/dashboard/dashboard.html',
      ti:           '../ti/dashboard/dashboard.html',
    };
    const destino = ROTAS[usuario.perfil] || ROTAS['admin'];
    setTimeout(() => { window.location.href = destino; }, 1200);
  });
}

/* ═══════════════════════════════════════════
   REGISTER FORM
═══════════════════════════════════════════ */
  /* initRegisterForm(): Configura o formulário de cadastro (validação + envio + seleção de perfil). */
  function initRegisterForm() {
  const form = $('form-register');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    let valid = true;

    const nome      = $('reg-nome').value.trim();
    const sobrenome = $('reg-sobrenome').value.trim();
    const email     = $('reg-email').value.trim();
    const role      = $('reg-role').value;
    const pass      = $('reg-password').value;
    const confirm   = $('reg-confirm').value;
    const cs        = document.getElementById('custom-select');

    if (nome.length < 2) { setFieldError('reg-nome', 'err-reg-nome', true); valid = false; }
    else { clearFieldError('reg-nome', 'err-reg-nome'); }

    if (sobrenome.length < 2) { setFieldError('reg-sobrenome', 'err-reg-sobrenome', true); valid = false; }
    else { clearFieldError('reg-sobrenome', 'err-reg-sobrenome'); }

    if (!isValidEmail(email)) { setFieldError('reg-email', 'err-reg-email', true); valid = false; }
    else { clearFieldError('reg-email', 'err-reg-email'); }

    if (!role) {
      cs.classList.add('is-error');
      const errRole = $('err-reg-role');
      if (errRole) errRole.classList.add('show');
      valid = false;
    } else {
      cs.classList.remove('is-error');
      const errRole = $('err-reg-role');
      if (errRole) errRole.classList.remove('show');
    }

    if (pass.length < 8) { setFieldError('reg-password', 'err-reg-password', true); valid = false; }
    else { clearFieldError('reg-password', 'err-reg-password'); }

    if (!confirm || confirm !== pass) { setFieldError('reg-confirm', 'err-reg-confirm', true); valid = false; }
    else { clearFieldError('reg-confirm', 'err-reg-confirm'); }

    if (!valid) return;

    setButtonLoading('btn-register', true);
    const { ok, status, data } = await apiFetch('/auth/register', { nome, sobrenome, email, role, password: pass });
    setButtonLoading('btn-register', false);

    if (!ok) {
      if (data.campo && data.mensagem) highlightApiError(data.campo, data.mensagem);
      showToast(data.mensagem || 'Erro ao criar conta.', 'error');
      return;
    }

    // Sucesso — cadastro enviado para análise
    showToast(data.mensagem, 'warning');

    setTimeout(() => {
      form.reset();
      $('strength-fill').style.width = '0%';
      $('strength-text').textContent = '';
      const badge = $('role-badge');
      if (badge) badge.classList.remove('visible');
      const selectValue = document.getElementById('select-value');
      if (selectValue) selectValue.textContent = 'Selecione um perfil…';
      if (cs) {
        cs.classList.remove('selected', 'is-error');
        cs.querySelectorAll('.custom-select__option').forEach(o => {
          o.classList.remove('is-active');
          o.setAttribute('aria-selected', 'false');
        });
      }
      document.querySelector('[data-tab="login"]').click();
    }, 2500);
  });
}

/* ═══════════════════════════════════════════
   FORGOT PASSWORD
═══════════════════════════════════════════ */
  /* initForgotPassword(): Configura o modal de recuperação de senha. */
  function initForgotPassword() {
  const btn = $('btn-forgot');
  if (!btn) return;
  btn.addEventListener('click', () => {
    showToast('Recuperação de senha: contate o administrador do sistema.', 'error');
  });
}

/* ═══════════════════════════════════════════
   CUSTOM SELECT
═══════════════════════════════════════════ */
const ROLE_ICONS = {
  proprietario: `<svg viewBox="0 0 20 20" fill="none"><path d="M10 2l7 3v5c0 4-3.5 7-7 8-3.5-1-7-4-7-8V5l7-3z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/><path d="M7 10l2 2 4-4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  admin:        `<svg viewBox="0 0 20 20" fill="none"><path d="M10 2l6 2.5v5C16 13.5 13.2 17 10 18 6.8 17 4 13.5 4 9.5v-5L10 2z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/><path d="M7.5 10l2 2 3-3" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  farmaceutico: `<svg viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="7.5" stroke="currentColor" stroke-width="1.4"/><path d="M10 6.5v7M6.5 10h7" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>`,
  atendente:    `<svg viewBox="0 0 20 20" fill="none"><rect x="2" y="5" width="16" height="10" rx="1.5" stroke="currentColor" stroke-width="1.4"/><circle cx="7" cy="10" r="2" stroke="currentColor" stroke-width="1.4"/><path d="M11 8.5h4M11 11.5h3" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>`,
  compras:      `<svg viewBox="0 0 20 20" fill="none"><path d="M17 13.5V7a1 1 0 00-.5-.87l-6-3.46a1 1 0 00-1 0L3.5 6.13A1 1 0 003 7v6.5a1 1 0 00.5.87l6 3.46a1 1 0 001 0l6-3.46a1 1 0 00.5-.87z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/><path d="M3.27 6.5L10 10.5l6.73-4M10 17.5v-7" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>`,
  ti:           `<svg viewBox="0 0 20 20" fill="none"><rect x="2" y="4" width="16" height="12" rx="1.5" stroke="currentColor" stroke-width="1.4"/><path d="M6 8l3 3-3 3M11 14h3" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
};

  /* initCustomSelect(): Inicializa os selects customizados (dropdowns estilizados). */
  function initCustomSelect() {
  const cs       = document.getElementById('custom-select');
  const hidden   = document.getElementById('reg-role');
  const valueEl  = document.getElementById('select-value');
  const iconWrap = document.getElementById('select-icon-wrap');
  const badge    = document.getElementById('role-badge');
  const errEl    = document.getElementById('err-reg-role');

  if (!cs) return;

  const options = cs.querySelectorAll('.custom-select__option');

  cs.addEventListener('click', (e) => {
    if (e.target.closest('.custom-select__option')) return;
    const isOpen = cs.classList.toggle('open');
    cs.setAttribute('aria-expanded', isOpen);
  });

  document.addEventListener('click', (e) => {
    if (!cs.contains(e.target)) { cs.classList.remove('open'); cs.setAttribute('aria-expanded', 'false'); }
  });

  cs.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); cs.classList.toggle('open'); cs.setAttribute('aria-expanded', cs.classList.contains('open')); }
    if (e.key === 'Escape') { cs.classList.remove('open'); cs.setAttribute('aria-expanded', 'false'); }
  });

  options.forEach((opt) => {
    opt.addEventListener('click', (e) => {
      e.stopPropagation();
      const val   = opt.dataset.value;
      const label = opt.querySelector('strong').textContent;

      hidden.value        = val;
      valueEl.textContent = label;
      cs.classList.add('selected');
      cs.classList.remove('open', 'is-error');
      cs.setAttribute('aria-expanded', 'false');

      if (ROLE_ICONS[val]) iconWrap.innerHTML = ROLE_ICONS[val];

      options.forEach(o => { o.classList.remove('is-active'); o.setAttribute('aria-selected', 'false'); });
      opt.classList.add('is-active');
      opt.setAttribute('aria-selected', 'true');

      if (errEl) errEl.classList.remove('show');

      const info = ROLE_INFO[val];
      if (badge && info) { badge.textContent = info; badge.classList.add('visible'); }
    });
  });
}

/* ═══════════════════════════════════════════
   INIT
═══════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initEyeToggles();
  initStrengthMeter();
  initCustomSelect();
  initAutoClear();
  initLoginForm();
  initRegisterForm();
  initForgotPassword();
});
