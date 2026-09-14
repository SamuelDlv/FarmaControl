/* ══════════════════════════════════════════════════════════════════════
 * FARMAControl — CONFIGURAÇÕES DO SISTEMA (PROPRIETÁRIO)
 * ══════════════════════════════════════════════════════════════════════
 *
 * Painel de configurações personalizáveis:
 * - Tema: claro/escuro
 * - Cor de destaque: 6 paletas (verde, azul, laranja, vermelho, roxo, teal)
 * - Densidade de interface: normal, compacta, espaçada
 * - Animações: ligar/desligar
 * - Sidebar: recolhida por padrão ou expandida
 *
 * As configurações são salvas no localStorage E no banco de dados
 * para persistir entre dispositivos.
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

var savedConfigSnapshot = '{}';
var currentConfigState = {};

var VISUAL_KEYS = ['densidade_interface', 'cor_destaque', 'animacoes_interface', 'sidebar_recolhida_padrao'];
var DEFAULT_CONFIG = Object.assign({
  densidade_interface: 'normal',
  cor_destaque: '#4a7c59',
  animacoes_interface: 'true',
  sidebar_recolhida_padrao: 'false'
}, (window.FarmaControlSettings && window.FarmaControlSettings.defaults) || {});

  /* normalizeConfigValue(): Normaliza um valor de configuração para o tipo correto (string/boolean). */
  function normalizeConfigValue(value) {
  if (value === true) return 'true';
  if (value === false) return 'false';
  if (value == null) return '';
  return String(value);
}

  /* stableConfigString(): Gera uma string estável das configurações para comparar mudanças. */
  function stableConfigString(cfg) {
  const ordered = {};
  Object.keys(cfg || {}).sort().forEach(key => { ordered[key] = normalizeConfigValue(cfg[key]); });
  return JSON.stringify(ordered);
}

  /* collectConfiguracoes(): Coleta todas as configurações atuais dos campos do formulário. */
  function collectConfiguracoes() {
  const cfg = {};
  document.querySelectorAll('[data-config-key]').forEach(el => {
    const key = el.dataset.configKey;
    if (!key) return;
    if (el.classList.contains('color-swatch')) {
      if (el.classList.contains('active')) cfg[key] = el.dataset.configValue || '';
      return;
    }
    if (el.type === 'checkbox') {
      cfg[key] = el.checked ? 'true' : 'false';
      return;
    }
    cfg[key] = el.value || '';
  });
  Object.keys(DEFAULT_CONFIG).forEach(key => {
    if (!cfg[key]) cfg[key] = DEFAULT_CONFIG[key];
  });
  return cfg;
}

  /* markDirtyState(): Marca o formulário como "modificado" (habilita botão salvar). */
  function markDirtyState() {
  currentConfigState = collectConfiguracoes();
  const dirty = stableConfigString(currentConfigState) !== savedConfigSnapshot;
  const saveBtn = document.getElementById('btn-save-all');
  if (saveBtn) saveBtn.style.display = dirty ? '' : 'none';
}

  /* markCleanState(): Marca o formulário como "limpo" (desabilita botão salvar). */
  function markCleanState(cfg) {
  currentConfigState = Object.assign({}, cfg || collectConfiguracoes());
  savedConfigSnapshot = stableConfigString(currentConfigState);
  const saveBtn = document.getElementById('btn-save-all');
  if (saveBtn) saveBtn.style.display = 'none';
}

  /* applyConfigToFields(): Aplica as configurações carregadas nos campos do formulário. */
  function applyConfigToFields(cfgs) {
  const merged = Object.assign({}, DEFAULT_CONFIG, cfgs || {});
  document.querySelectorAll('[data-config-key]').forEach(el => {
    const key = el.dataset.configKey;
    if (!key) return;
    const value = normalizeConfigValue(merged[key]);
    if (el.classList.contains('color-swatch')) {
      el.classList.toggle('active', (el.dataset.configValue || '').toLowerCase() === value.toLowerCase());
      return;
    }
    if (el.type === 'checkbox') {
      el.checked = value === 'true' || value === '1' || value === 'sim';
      return;
    }
    el.value = value;
  });
}

  /* labelForConfig(): Retorna o label legível para um valor de configuração. */
  function labelForConfig(key, value) {
  const labels = {
    densidade_interface: 'Densidade', cor_destaque: 'Cor de destaque',
    nome_farmacia: 'Nome da farmácia', cnpj: 'CNPJ', crf_responsavel: 'CRF', telefone: 'Telefone', endereco: 'Endereço',
    email_notificacao: 'E-mail para alertas', prazo_vencimento: 'Antecedência de vencimento',
    estoque_minimo_padrao: 'Estoque mínimo padrão', estoque_maximo_padrao: 'Estoque máximo padrão', ponto_reposicao: 'Ponto de reposição',
    metodo_custeio: 'Método de custeio', unidade_medida_padrao: 'Unidade padrão'
  };
  if (value === 'true') value = 'Ativo';
  if (value === 'false') value = 'Inativo';
  return { label: labels[key] || key.replaceAll('_', ' '), value };
}

  /* renderDynamicPanels(): Renderiza os painéis dinâmicos de configurações. */
  function renderDynamicPanels(cfgs) {
  const summary = document.getElementById('active-config-summary');
  if (summary) {
    const entries = Object.entries(cfgs || {}).filter(([_, v]) => normalizeConfigValue(v).trim() !== '');
    summary.innerHTML = entries.length ? entries.slice(0, 8).map(([key, value]) => {
      const item = labelForConfig(key, normalizeConfigValue(value));
      return `<div class="summary-row"><span class="summary-label">${item.label}</span><span class="summary-val">${item.value}</span></div>`;
    }).join('') : '<p class="form-hint">Nenhuma configuração ativa.</p>';
  }

  const history = document.getElementById('config-history-list');
  if (history) history.innerHTML = '<p class="form-hint">Histórico ainda não disponível pela API.</p>';

  const status = document.getElementById('system-status-list');
  if (status) status.innerHTML = '<p class="form-hint">Status em tempo real ainda não disponível pela API.</p>';
}

var toast = window.FarmaControlSettings
  ? window.FarmaControlSettings.showToast
  : (() => console.warn('Toast indisponível'));

/* ══ CONFIGURAÇÕES — BANCO DE DADOS ══ */
async function loadConfiguracoes() {
  try {
    let cfgs = {};
    const res = await fetch(`${API_BASE}/configuracoes`);
    const result = await res.json();
    if (result.ok) {
      (result.configuracoes || []).forEach(c => { cfgs[c.chave] = normalizeConfigValue(c.valor); });
    }
    applyConfigToFields(cfgs);
    const collected = collectConfiguracoes();
    renderDynamicPanels(cfgs);
    /* IMPORTANTE: Nunca sobrescrever o localStorage durante o load.
     * O saveLocal() só deve acontecer quando o usuário clica em "Salvar".
     * Aqui apenas aplicamos o tema visual ao UI sem modificar o storage. */
    if (window.FarmaControlSettings) {
      /* Ler o localStorage do usuário (preserva a cor de destaque escolhida) */
      const local = window.FarmaControlSettings.readLocal ? window.FarmaControlSettings.readLocal() : {};
      /* Aplicar o tema visual do usuário (sem salvar — apenas renderizar) */
      window.FarmaControlSettings.apply(local);
      /* Populamos os campos do formulário com os valores do localStorage
       * para que o usuário veja a cor que ele escolheu como selecionada */
      applyConfigToFields(Object.assign({}, local, cfgs));
    }
    markCleanState(collected);
  } catch (err) {
    const local = (window.FarmaControlSettings && window.FarmaControlSettings.readLocal()) || {};
    applyConfigToFields(local);
    renderDynamicPanels(local);
    markCleanState(collectConfiguracoes());
    console.error('Erro ao carregar configurações:', err);
  }
}

  /* saveConfiguracoes(): Salva as configurações alteradas no banco de dados. */
  async function saveConfiguracoes() {
  const cfg = collectConfiguracoes();
  const promises = Object.entries(cfg).map(([chave, valor]) =>
    fetch(`${API_BASE}/configuracoes/${chave}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ valor: normalizeConfigValue(valor), descricao: 'Configurações do sistema' }),
    }).then(r => r.json())
  );

  try {
    await Promise.all(promises);
    if (window.FarmaControlSettings) {
      window.FarmaControlSettings.saveLocal(cfg);
      window.FarmaControlSettings.apply(cfg);
    }
    renderDynamicPanels(cfg);
    markCleanState(cfg);
    toast('Configurações salvas com sucesso!', 'success');
  } catch (err) {
    toast('Erro ao salvar configurações.', 'error');
  }
}

// initSidebar() removido: já inicializado pelo sidebar-init.js

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


/* ══ PERIOD SELECTOR (placeholder funcional) ══ */
function initPeriodSelector() {
  document.querySelectorAll('.period-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const labels = { month: 'Mês atual', quarter: 'Trimestre atual', year: 'Ano atual' };
      const sub = document.getElementById('page-subtitle');
      if (sub) sub.textContent = 'Personalize o sistema de acordo com as necessidades da sua farmácia';
      toast(`Período alterado: ${btn.textContent} (${labels[btn.dataset.period] || 'atual'})`, 'info');
    });
  });
}

/* ══ CONFIG ACTIONS ══ */
function initReportButtons() {
  document.querySelectorAll('.config-nav-item').forEach(item => {
    item.addEventListener('click', () => {
      document.querySelectorAll('.config-nav-item').forEach(i => i.classList.remove('active'));
      item.classList.add('active');
    });
  });

  document.querySelectorAll('[data-config-key]').forEach(field => {
    field.addEventListener('input', () => {
      if (VISUAL_KEYS.includes(field.dataset.configKey) && window.FarmaControlSettings) {
        window.FarmaControlSettings.apply(collectConfiguracoes());
      }
      markDirtyState();
    });
    field.addEventListener('change', () => {
      if (VISUAL_KEYS.includes(field.dataset.configKey) && window.FarmaControlSettings) {
        window.FarmaControlSettings.apply(collectConfiguracoes());
      }
      markDirtyState();
      if (field.type === 'checkbox') {
        toast('Clique em "Salvar alterações" para aplicar a configuração.', 'info');
      }
    });
  });

  document.querySelectorAll('.color-swatch').forEach(swatch => {
    swatch.addEventListener('click', () => {
      document.querySelectorAll('.color-swatch').forEach(s => s.classList.remove('active'));
      swatch.classList.add('active');
      if (window.FarmaControlSettings) window.FarmaControlSettings.apply(collectConfiguracoes());
      markDirtyState();
    });
  });

  document.getElementById('btn-save-all')?.addEventListener('click', saveConfiguracoes);

  document.getElementById('btn-export')?.addEventListener('click', () => {
    const data = JSON.stringify(collectConfiguracoes(), null, 2);
    const blob = new Blob([data], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'farmacontrol-configuracoes.json';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    toast('Configurações exportadas em JSON.', 'success');
  });

  document.querySelectorAll('.exp-hist-dl').forEach(btn => {
    btn.addEventListener('click', () => toast('Nenhum arquivo disponível para download.', 'info'));
  });
}

/* ══ REFRESH ─ recarrega configurações do banco ══ */
document.getElementById('btn-refresh')?.addEventListener('click', async () => {
  const svg = document.querySelector('#btn-refresh svg');
  if (svg) {
    svg.style.transition = 'transform 0.6s';
    svg.style.transform  = 'rotate(360deg)';
    setTimeout(() => { svg.style.transition = 'none'; svg.style.transform = 'rotate(0deg)'; }, 650);
  }
  // Restaura os valores padrão visuais e recarrega as configurações do banco
  if (window.FarmaControlSettings && window.FarmaControlSettings.clearLocal) {
    window.FarmaControlSettings.clearLocal();
  }
  await loadConfiguracoes();
  toast('Configurações restauradas com sucesso.', 'success');
});


/* ══ INIT ══ */
document.addEventListener('DOMContentLoaded', () => {
  // initSidebar(); // Removido: já inicializado pelo sidebar-init.js
  initDate();
  initCounters();
  initPeriodSelector();
  initReportButtons();
  loadConfiguracoes();
});

// Logout já tratado pelo sidebar-init.js
