/* ══════════════════════════════════════════════════════════════════════
 * FARMAControl — CONFIGURAÇÕES DO SISTEMA (PROPRIETÁRIO)
 * ══════════════════════════════════════════════════════════════════════
 *
 * Painel de configurações personalizáveis:
 * - Aparência clara
 * - Cor de destaque: 6 paletas (verde, azul, laranja, vermelho, roxo, teal)
 * - Densidade de interface: normal, compacta, espaçada
 * - Animações: ligar/desligar
 * - Sidebar: recolhida por padrão ou expandida
 *
 * As configurações são salvas no localStorage E no banco de dados
 * para persistir entre dispositivos.
 * ══════════════════════════════════════════════════════════════════════ */

/* Timers e listeners globais desta tela são descartados por page-lifecycle.js. */
// Guard de sessão e dados do usuário agora são gerenciados globalmente pelo global-settings.js e sidebar-init.js

'use strict';

var API_BASE =
  (window.FarmaControlSettings && window.FarmaControlSettings.API_BASE) || 'http://localhost:5000';
var EASE = t => (t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t);

var savedConfigSnapshot = '{}';
var currentConfigState = {};
var configLoaded = false;
var configSaving = false;

var VISUAL_KEYS = [
  'densidade_interface',
  'cor_destaque',
  'animacoes_interface',
  'sidebar_recolhida_padrao'
];
var DEFAULT_CONFIG = Object.assign(
  {
    nome_farmacia: '',
    cnpj: '',
    crf_responsavel: '',
    telefone: '',
    endereco: '',
    fuso_horario: 'America/Sao_Paulo',
    idioma: 'pt-BR',
    moeda: 'BRL',
    alerta_estoque_minimo: 'true',
    alerta_vencimento: 'true',
    alertas_pedidos_pendentes: 'true',
    notificacoes_email: 'false',
    relatorio_semanal: 'false',
    email_notificacao: '',
    prazo_vencimento: '30',
    estoque_minimo_padrao: '10',
    estoque_maximo_padrao: '100',
    ponto_reposicao: '20',
    metodo_custeio: 'PEPS',
    unidade_medida_padrao: 'unidade',
    controle_lote_obrigatorio: 'false',
    bloquear_produtos_vencidos: 'true',
    densidade_interface: 'normal',
    cor_destaque: '#4a7c59',
    animacoes_interface: 'true',
    sidebar_recolhida_padrao: 'false'
  },
  (window.FarmaControlSettings && window.FarmaControlSettings.defaults) || {}
);

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
  Object.keys(cfg || {})
    .sort()
    .forEach(key => {
      ordered[key] = normalizeConfigValue(cfg[key]);
    });
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
    if (!(key in cfg)) cfg[key] = DEFAULT_CONFIG[key];
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
  Object.keys(DEFAULT_CONFIG).forEach(key => {
    if (merged[key] == null || merged[key] === '') merged[key] = DEFAULT_CONFIG[key];
  });
  document.querySelectorAll('[data-config-key]').forEach(el => {
    const key = el.dataset.configKey;
    if (!key) return;
    const value = normalizeConfigValue(merged[key]);
    if (el.classList.contains('color-swatch')) {
      el.classList.toggle(
        'active',
        (el.dataset.configValue || '').toLowerCase() === value.toLowerCase()
      );
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
    densidade_interface: 'Densidade',
    cor_destaque: 'Cor de destaque',
    nome_farmacia: 'Nome da farmácia',
    cnpj: 'CNPJ',
    crf_responsavel: 'CRF',
    telefone: 'Telefone',
    endereco: 'Endereço',
    email_notificacao: 'E-mail para alertas',
    prazo_vencimento: 'Antecedência de vencimento',
    estoque_minimo_padrao: 'Estoque mínimo padrão',
    estoque_maximo_padrao: 'Estoque máximo padrão',
    ponto_reposicao: 'Ponto de reposição',
    metodo_custeio: 'Método de custeio',
    unidade_medida_padrao: 'Unidade padrão'
  };
  if (value === 'true') value = 'Ativo';
  if (value === 'false') value = 'Inativo';
  return { label: labels[key] || key.replaceAll('_', ' '), value };
}

/* renderDynamicPanels(): Renderiza os painéis dinâmicos de configurações. */
function renderDynamicPanels(cfgs) {
  const summary = document.getElementById('active-config-summary');
  if (summary) {
    const entries = Object.entries(cfgs || {}).filter(
      ([_, v]) => normalizeConfigValue(v).trim() !== ''
    );
    summary.innerHTML = entries.length
      ? entries
          .slice(0, 8)
          .map(([key, value]) => {
            const item = labelForConfig(key, normalizeConfigValue(value));
            return `<div class="summary-row"><span class="summary-label">${escapeConfigText(item.label)}</span><span class="summary-val">${escapeConfigText(item.value)}</span></div>`;
          })
          .join('')
      : '<p class="form-hint">Nenhuma configuração ativa.</p>';
  }

  const history = document.getElementById('config-history-list');
  if (history)
    history.innerHTML = '<p class="form-hint">Histórico ainda não disponível pela API.</p>';

  const status = document.getElementById('system-status-list');
  if (status)
    status.innerHTML =
      '<p class="form-hint">Status em tempo real ainda não disponível pela API.</p>';
}

var toast = window.FarmaControlSettings
  ? window.FarmaControlSettings.showToast
  : () => console.warn('Toast indisponível');

/* ══ CONFIGURAÇÕES — BANCO DE DADOS ══ */
function escapeConfigText(value) {
  return String(value).replace(
    /[&<>"']/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]
  );
}

function lockPharmacy(locked) {
  document.querySelectorAll('#pharmacy-card [data-config-key]').forEach(el => {
    el.disabled = locked;
  });
  document.getElementById('btn-edit-pharmacy').hidden = !locked || !configLoaded;
  document.getElementById('btn-cancel-pharmacy').hidden = locked || !configLoaded;
  document.getElementById('pharmacy-status').textContent = locked
    ? 'Dados salvos. Clique em Editar para alterar.'
    : 'Preencha os dados e clique em Salvar alterações.';
}
function setConfigBusy(busy) {
  document
    .querySelectorAll(
      '[data-config-key], #btn-save-all, #btn-refresh, #btn-edit-pharmacy, #btn-cancel-pharmacy'
    )
    .forEach(el => {
      el.disabled = busy;
    });
}
async function loadConfiguracoes() {
  if (configSaving) return false;
  configLoaded = false;
  setConfigBusy(true);
  try {
    const res = await fetch(`${API_BASE}/configuracoes`);
    const result = await res.json();
    if (!res.ok || !result.ok)
      throw new Error(result.erro || result.mensagem || 'Erro ao carregar configurações.');
    const emailStatus = document.getElementById('email-service-status');
    if (emailStatus)
      emailStatus.textContent = result.email_disponivel
        ? 'Serviço de e-mail configurado. Os resumos são verificados ao acessar o painel: diariamente e às segundas-feiras.'
        : 'Para enviar os resumos, configure o serviço SMTP no servidor. As preferências podem ser salvas, mas nenhum e-mail será enviado sem essa configuração.';
    const cfgs = {};
    (result.configuracoes || []).forEach(c => {
      cfgs[c.chave] = normalizeConfigValue(c.valor);
    });
    const local = window.FarmaControlSettings?.readLocal() || {};
    VISUAL_KEYS.forEach(key => {
      if (key in local) cfgs[key] = local[key];
    });
    applyConfigToFields(cfgs);
    renderDynamicPanels(collectConfiguracoes());
    window.FarmaControlSettings?.apply(cfgs);
    markCleanState(collectConfiguracoes());
    configLoaded = true;
    setConfigBusy(false);
    lockPharmacy(
      ['nome_farmacia', 'cnpj', 'crf_responsavel', 'telefone', 'endereco'].some(k => !!cfgs[k])
    );
    return true;
  } catch (err) {
    document.getElementById('btn-refresh').disabled = false;
    toast(
      'Não foi possível carregar os dados. Clique em Recarregar dados para tentar novamente.',
      'error'
    );
    console.error('Erro ao carregar configurações:', err);
    return false;
  }
}
async function saveConfiguracoes() {
  if (!configLoaded || configSaving) return;
  for (const el of document.querySelectorAll('[data-config-key]')) {
    if (el.reportValidity && !el.reportValidity()) return;
  }
  const cfg = collectConfiguracoes();
  const wasLocked = !document.getElementById('btn-edit-pharmacy').hidden;
  configSaving = true;
  setConfigBusy(true);
  let saved = false;
  try {
    const res = await fetch(`${API_BASE}/configuracoes`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ configuracoes: cfg })
    });
    const result = await res.json();
    if (!res.ok || !result.ok)
      throw new Error(result.erro || result.mensagem || 'Erro ao salvar configurações.');
    const values = result.valores || cfg;
    applyConfigToFields(values);
    try {
      const visual = Object.fromEntries(VISUAL_KEYS.map(k => [k, values[k]]));
      window.FarmaControlSettings?.saveLocal(visual);
      window.FarmaControlSettings?.apply(visual);
    } catch (err) {
      console.warn('Preferências locais indisponíveis:', err);
    }
    renderDynamicPanels(values);
    markCleanState(collectConfiguracoes());
    saved = true;
    toast('Configurações salvas com sucesso!', 'success');
  } catch (err) {
    toast(err.message || 'Erro ao salvar configurações. Tente novamente.', 'error');
  } finally {
    configSaving = false;
    setConfigBusy(false);
    lockPharmacy(saved || wasLocked);
  }
}

// initSidebar() removido: já inicializado pelo sidebar-init.js

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

/* ══ PERIOD SELECTOR (placeholder funcional) ══ */
function initPeriodSelector() {
  document.querySelectorAll('.period-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const labels = { month: 'Mês atual', quarter: 'Trimestre atual', year: 'Ano atual' };
      const sub = document.getElementById('page-subtitle');
      if (sub)
        sub.textContent = 'Personalize o sistema de acordo com as necessidades da sua farmácia';
      toast(
        `Período alterado: ${btn.textContent} (${labels[btn.dataset.period] || 'atual'})`,
        'info'
      );
    });
  });
}

/* ══ CONFIG ACTIONS ══ */
function initReportButtons() {
  document.getElementById('btn-edit-pharmacy')?.addEventListener('click', () => {
    lockPharmacy(false);
    document.querySelector('[data-config-key="nome_farmacia"]')?.focus();
  });
  document.getElementById('btn-cancel-pharmacy')?.addEventListener('click', () => {
    const saved = JSON.parse(savedConfigSnapshot);
    document.querySelectorAll('#pharmacy-card [data-config-key]').forEach(el => {
      el.value = saved[el.dataset.configKey] || '';
    });
    lockPharmacy(true);
    markDirtyState();
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
      if (!configLoaded || configSaving) return;
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
    svg.style.transform = 'rotate(360deg)';
    setTimeout(() => {
      svg.style.transition = 'none';
      svg.style.transform = 'rotate(0deg)';
    }, 650);
  }
  if (await loadConfiguracoes()) toast('Dados salvos recarregados.', 'success');
});

/* ══ INIT ══ */
function initConfiguracoesPage() {
  // initSidebar(); // Removido: já inicializado pelo sidebar-init.js

  initCounters();
  initPeriodSelector();
  initReportButtons();
  loadConfiguracoes();
}
if (document.readyState === 'loading')
  window.fcPageListen(document, 'DOMContentLoaded', initConfiguracoesPage, { once: true });
else initConfiguracoesPage();

// Logout já tratado pelo sidebar-init.js
