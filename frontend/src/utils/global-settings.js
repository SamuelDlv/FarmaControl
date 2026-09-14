/**
 * FarmaControl — Sistema Global de Configurações (v2 — reescrito)
 *
 * ══ MUDANÇA FUNDAMENTAL v2 ══
 *
 * CAUSA RAIZ DO FLASH DE COR (confirmada):
 * O ensureStyle() usava var(--sage) nas regras CSS. O browser resolve
 * var() no cascade — se o CSS da página é parseado ANTES do setProperty()
 * rodar, o fallback do var(--sage, #4a7c59) é usado → FLASH VERDE.
 *
 * SOLUÇÃO v2:
 * ensureStyle() agora gera CSS com VALORES DIRETOS (hex resolvidos),
 * não referências a var(). O CSS é regenerado a cada applySettings().
 *
 * Além disso, o motor v14 chama applySettings() ANTES da injeção de CSS
 * da página nova — garantindo que as cores estão corretas quando o
 * browser parse qualquer CSS.
 */

/* ══════════════════════════════════════════════════════════════════════
 * FARMAControl — SISTEMA GLOBAL DE CONFIGURAÇÕES (v2)
 * ══════════════════════════════════════════════════════════════════════
 *
 * Este arquivo é carregado em TODAS as páginas do sistema.
 * Ele é responsável por:
 *
 * 1. Definir a paleta de cores do tema (verde, azul, laranja, etc.)
 * 2. Aplicar as CSS variables (--sage, --ink, --surface, etc.) no <html>
 * 3. Gerar um <style> inline com valores DIRETOS (sem var()) para
 *    evitar o "flash" de cor antes do CSS da página carregar
 * 4. Gerenciar a sessão do usuário logado (localStorage)
 * 5. Aplicar configurações de densidade, animações e sidebar
 *
 * FUNÇÕES PRINCIPAIS:
 * ─────────────────────────────────────────────────────────────────────
 * parseStored()        → Lê configurações salvas no localStorage
 * getPalette(hexColor) → Retorna a paleta de cores para um hex
 * regenerateStyle()    → Cria <style> inline com valores hex diretos
 * applySettings()      → Aplica tema + cores + densidade na página
 * applyUser()          → Mostra nome/avatar do usuário na sidebar
 * loadRemoteSettings() → Busca configurações salvas no banco
 * showToast()          → Exibe notificação temporária (sucesso/erro)
 * ─────────────────────────────────────────────────────────────────────
 */
(function () {
  'use strict';

  const API_BASE = 'http://localhost:5000';
  const STORAGE_KEY = 'farmacontrol_configuracoes';

  /* ══ PALETAS PREDEFINIDAS ══ */
  const palettes = {
    '#4a7c59': { sage: '#4a7c59', sage2: '#3a6447', light: '#6aaa7e', pale: 'rgba(74,124,89,0.1)', border: 'rgba(74,124,89,0.22)', surface: '#0d1510', surface2: '#141f18' },
    '#2e6da4': { sage: '#2e6da4', sage2: '#235590', light: '#4f8bc0', pale: 'rgba(46,109,164,0.1)', border: 'rgba(46,109,164,0.22)', surface: '#0a121a', surface2: '#101a26' },
    '#b87a1a': { sage: '#b87a1a', sage2: '#965f14', light: '#d59636', pale: 'rgba(184,122,26,0.1)', border: 'rgba(184,122,26,0.22)', surface: '#1a140a', surface2: '#261e10' },
    '#c03a3a': { sage: '#c03a3a', sage2: '#9b2d2d', light: '#d85c5c', pale: 'rgba(192,58,58,0.1)', border: 'rgba(192,58,58,0.22)', surface: '#1a0a0a', surface2: '#261010' },
    '#6b4fbb': { sage: '#6b4fbb', sage2: '#523a97', light: '#876fd0', pale: 'rgba(107,79,187,0.1)', border: 'rgba(107,79,187,0.22)', surface: '#110a1a', surface2: '#1a1026' },
    '#1a7a6e': { sage: '#1a7a6e', sage2: '#125f55', light: '#32998c', pale: 'rgba(26,122,110,0.1)', border: 'rgba(26,122,110,0.22)', surface: '#0a1a18', surface2: '#102623' }
  };

  const defaultSettings = {
    tema: 'claro',
    densidade_interface: 'normal',
    cor_destaque: '#4a7c59',
    animacoes_interface: 'true',
    sidebar_recolhida_padrao: 'false'
  };

  /* ══ PALETTE ATUAL (cache para evitar re-cálculo) ══ */
  let currentPalette = null;
  let currentColorHex = null;

  /* ══ parseStored(): Lê as configurações salvas no localStorage do navegador.
   * Se não houver nada salvo ou o JSON estiver corrompido, retorna objeto vazio. */
  function parseStored() {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}') || {}; }
    catch (_) { return {}; }
  }

  /* ══ saveStored(cfg): Salva as configurações no localStorage.
   * Mantém as configurações antigas e sobrescreve apenas as novas. */
  function saveStored(cfg) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(Object.assign(parseStored(), cfg || {})));
  }

  function getEffectiveSettings(cfg) {
    const merged = Object.assign({}, defaultSettings, parseStored(), cfg || {});
    merged.tema_efetivo = 'claro';
    return merged;
  }

  /* ══ setVar(name, value): Define uma CSS variable no elemento <html> (root).
   * Ex: setVar('--sage', '#4a7c59') → o tema usa essa cor imediatamente. */
  function setVar(name, value) {
    document.documentElement.style.setProperty(name, value);
  }

  /* ══ CONVERSÕES DE COR ══ */
  function hexToRgb(hex) {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? { r: parseInt(result[1], 16), g: parseInt(result[2], 16), b: parseInt(result[3], 16) } : null;
  }

  function rgbToHex(r, g, b) {
    return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
  }

  function rgbToHsl(r, g, b) {
    r /= 255; g /= 255; b /= 255;
    const max = Math.max(r, g, b), min = Math.min(r, g, b);
    let h, s, l = (max + min) / 2;
    if (max === min) { h = s = 0; }
    else {
      const d = max - min;
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
      switch (max) {
        case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
        case g: h = ((b - r) / d + 2) / 6; break;
        case b: h = ((r - g) / d + 4) / 6; break;
      }
    }
    return { h, s, l };
  }

  function hslToRgb(h, s, l) {
    let r, g, b;
    if (s === 0) { r = g = b = l; }
    else {
      const hue2rgb = (p, q, t) => {
        if (t < 0) t += 1; if (t > 1) t -= 1;
        if (t < 1/6) return p + (q - p) * 6 * t;
        if (t < 1/2) return q;
        if (t < 2/3) return p + (q - p) * (2/3 - t) * 6;
        return p;
      };
      const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
      const p = 2 * l - q;
      r = hue2rgb(p, q, h + 1/3); g = hue2rgb(p, q, h); b = hue2rgb(p, q, h - 1/3);
    }
    return { r: Math.round(r * 255), g: Math.round(g * 255), b: Math.round(b * 255) };
  }

  /* ══ generateDarkVariant(): Converte uma cor para versão mais escura (L=0.28).
   * Usado para gerar a cor "sage2" (darker) a partir da cor principal. */
  function generateDarkVariant(hexColor) {
    const rgb = hexToRgb(hexColor); if (!rgb) return hexColor;
    const hsl = rgbToHsl(rgb.r, rgb.g, rgb.b);
    return rgbToHex(...Object.values(hslToRgb(hsl.h, hsl.s * 0.6, 0.28)));
  }

  function generateUltraDarkVariant(hexColor) {
    const rgb = hexToRgb(hexColor); if (!rgb) return hexColor;
    const hsl = rgbToHsl(rgb.r, rgb.g, rgb.b);
    return rgbToHex(...Object.values(hslToRgb(hsl.h, hsl.s * 0.3, 0.08)));
  }

  function generateVeryDarkVariant(hexColor) {
    const rgb = hexToRgb(hexColor); if (!rgb) return hexColor;
    const hsl = rgbToHsl(rgb.r, rgb.g, rgb.b);
    return rgbToHex(...Object.values(hslToRgb(hsl.h, hsl.s * 0.4, 0.12)));
  }

  function generateLightVariant(hexColor) {
    const rgb = hexToRgb(hexColor); if (!rgb) return hexColor;
    const hsl = rgbToHsl(rgb.r, rgb.g, rgb.b);
    return rgbToHex(...Object.values(hslToRgb(hsl.h, hsl.s * 0.7, 0.50)));
  }

  function generatePaleVariant(hexColor, opacity = 0.1) {
    const rgb = hexToRgb(hexColor); if (!rgb) return hexColor;
    return `rgba(${rgb.r},${rgb.g},${rgb.b},${opacity})`;
  }

  function generateColorPalette(hexColor) {
    return {
      sage: hexColor,
      sage2: generateDarkVariant(hexColor),
      light: generateLightVariant(hexColor),
      pale: generatePaleVariant(hexColor, 0.1),
      border: generatePaleVariant(hexColor, 0.22),
      surface: generateUltraDarkVariant(hexColor),
      surface2: generateVeryDarkVariant(hexColor)
    };
  }

  /* ══ GET OR GENERATE PALETTE ══ */
  function getPalette(hexColor) {
    const key = String(hexColor || '').toLowerCase();
    if (palettes[key]) return palettes[key];
    return generateColorPalette(key) || generateColorPalette('#4a7c59');
  }

  /* ══ REGENERAR STYLE COM VALORES DIRETOS (v2 — sem var() references) ══ */
  function regenerateStyle(palette) {
    /* Remover o antigo se existir */
    const old = document.getElementById('fc-global-visual-settings');
    if (old) old.remove();

    const style = document.createElement('style');
    style.id = 'fc-global-visual-settings';
    style.textContent = `
      .sb-logo, .tb-btn.primary, .primary-btn, .btn-save, .row-btn, .modal-primary, .btn-primary { background: ${palette.sage} !important; color: #ffffff !important; }
      .sb-item.active { background: ${palette.pale} !important; }
      .sb-item.active .sb-icon, .config-nav-item.active, .config-nav-item.active .cni-icon { color: ${palette.light} !important; }
      .badge, .pill, .status-badge.ok { border-color: ${palette.border}; }
      .fc-density-compact { font-size: 13px; }
      .fc-density-compact .topbar { height: 50px; min-height: 50px; }
      .fc-density-compact .sb-head { padding: 14px 12px 10px; }
      .fc-density-compact .sb-item { padding: 6px 8px; gap: 8px; }
      .fc-density-compact .card-body { padding: 12px 14px; gap: 10px; }
      .fc-density-compact .card-head { padding: 10px 14px; }
      .fc-density-compact .form-input, .fc-density-compact .form-select { height: 32px; }
      .fc-density-compact .toggle-row { padding: 7px 0; }
      .fc-density-compact .page-body { gap: 10px; }
      .fc-density-compact .page-main { padding: 14px; }
      .fc-density-spaced .card-body { padding: 20px 22px; gap: 18px; }
      .fc-density-spaced .page-main { padding: 22px; }
      .fc-no-animations *, .fc-no-animations *::before, .fc-no-animations *::after { animation: none !important; transition: none !important; scroll-behavior: auto !important; }
    `;
    document.head.appendChild(style);
    return style;
  }

  /* ══ APLICAR TEMA (v2 — determinístico) ══
   * 1. Calcular palette
   * 2. Setar CSS vars no root (inline style no <html>)
   * 3. Regenerar o <style> com valores DIRETOS (não var())
   * 4. Forçar recálculo de estilo
   */
  /* ══ applySettings(): Função principal que aplica todo o tema na página.
   * Faz: 1) Calcula a paleta de cores, 2) Setar CSS vars no <html>,
   * 3) Gera <style> inline com valores diretos, 4) Aplica densidade/animações,
   * 5) Configura sidebar recolhida. É chamada ao carregar cada página. */
  function applySettings(cfg) {
    const settings = getEffectiveSettings(cfg);
    const selectedColor = String(settings.cor_destaque || '').toLowerCase();
    const palette = getPalette(selectedColor);

    /* Cache */
    currentPalette = palette;
    currentColorHex = selectedColor;

    /* CSS Vars no root (inline — aplica imediatamente) */
    setVar('--sage', palette.sage);
    setVar('--sage-2', palette.sage2);
    setVar('--sage-light', palette.light);
    setVar('--sage-pale', palette.pale);
    setVar('--sage-border', palette.border);

    /* Texto e fundo (tema claro fixo) */
    setVar('--ink', '#1a1a1a');
    setVar('--ink-60', '#2d2d2d');
    setVar('--ink-35', '#5a5a5a');
    setVar('--ink-12', '#d0d0d0');
    setVar('--ink-06', '#e8e8e8');
    setVar('--cream', '#ffffff');
    setVar('--cream-2', '#f8f8f8');
    setVar('--white', '#ffffff');
    setVar('--surface', '#ffffff');
    setVar('--surface-2', '#fafafa');
    setVar('--bg-body', '#f0f2f1');

    /* Regenerar o <style> com valores DIRETOS */
    regenerateStyle(palette);

    /* Exceção visual do tema vermelho: somente este tema recebe a classe
       usada pelos toasts locais para manter mensagens comuns brancas. */
    document.documentElement.classList.toggle('fc-theme-red', selectedColor === '#c03a3a');
    document.body?.classList.toggle('fc-theme-red', selectedColor === '#c03a3a');

    /* Densidade */
    document.body?.classList.toggle('fc-density-compact', settings.densidade_interface === 'compacta');
    document.body?.classList.toggle('fc-density-spaced', settings.densidade_interface === 'espacada');
    document.body?.classList.toggle('fc-no-animations', String(settings.animacoes_interface) === 'false');

    /* Sidebar recolhida padrão */
    const sb = document.getElementById('sidebar');
    if (sb && window.innerWidth > 860 && String(settings.sidebar_recolhida_padrao) === 'true' && localStorage.getItem('fc_sb') === null) {
      sb.classList.add('collapsed');
    }

    /* Forçar recálculo para garantir que o browser processou tudo */
    try {
      if (document.body) void document.body.offsetHeight;
    } catch(e) {}
  }

  /* ══ USUÁRIO ══ */
  function getCurrentUser() {
    try { return JSON.parse(sessionStorage.getItem('farmacontrol_usuario') || '{}') || {}; }
    catch (_) { return {}; }
  }

  /* ══ applyUser(): Busca o usuário logado no localStorage e atualiza
   * o nome, cargo e avatar na sidebar/topbar de todas as páginas. */
  function applyUser() {
    const user = getCurrentUser();
    const fullName = [user.nome, user.sobrenome].filter(Boolean).join(' ').trim() || user.nome || user.email || 'Usuário';
    const role = user.perfil_nome || user.cargo || user.funcao || user.perfil || 'Usuário';
    const initials = (fullName.split(/\s+/).filter(Boolean).map(n => n[0]).join('').slice(0, 2) || 'U').toUpperCase();

    document.querySelectorAll('#user-name, .sb-user-name').forEach(el => { el.textContent = fullName; });
    document.querySelectorAll('#user-role, .sb-user-role').forEach(el => { el.textContent = role; });
    document.querySelectorAll('#user-avatar, .sb-avatar').forEach(el => { el.textContent = initials; });
  }

  /* ══ LOAD REMOTO ══ */
  async function loadRemoteSettings() {
    try {
      const res = await fetch(`${API_BASE}/configuracoes`);
      const result = await res.json();
      if (!result.ok) return {};
      const cfg = {}; (result.configuracoes || []).forEach(item => { cfg[item.chave] = item.valor; });
      return cfg; /* NÃO salva aqui — saveStored só deve ocorrer quando o usuário explicitamente salva */
    } catch (_) { return {}; }
  }

  /* ══ INIT (executa uma vez no carregamento) ══
   * GUARDA __initialized: previne re-execução durante navegação SPA.
   * O sidebar-init.js dispara document.dispatchEvent('DOMContentLoaded') a cada
   * navegação — sem essa guarda, o listener abaixo chama init() → loadRemoteSettings()
   * → saveStored(), sobrescrevendo o localStorage do usuário com os defaults do backend. */
  let __initialized = false;
  /* ══ init(): Função de inicialização automática.
   * Executada ao carregar o script. Aplica as configurações salvas
   * e atualiza as informações do usuário na interface. */
  async function init() {
    if (__initialized) return;
    __initialized = true;
    const remote = await loadRemoteSettings();
    /* Local tem precedência sobre remoto: só aplica valores remotos que NÃO existem localmente */
    const stored = parseStored();
    const merged = Object.assign({}, remote, stored);
    applyUser();
    applySettings(merged);
  }

  /* ══ TOAST GLOBAL ══ */
  let __toastTimer = null;
  /* ══ showToast(): Exibe uma notificação temporária (toast) no canto da tela.
   * Tipos: 'success' (verde), 'error' (vermelho), 'info' (azul).
   * Desaparece automaticamente após 3 segundos. */
  function showToast(msg, type = 'success') {
    let el = document.getElementById('fc-toast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'fc-toast';
      el.setAttribute('role', 'status');
      el.style.cssText = 'position:fixed;bottom:22px;right:22px;display:flex;align-items:center;gap:8px;padding:10px 15px;border-radius:9px;font-family:Outfit,sans-serif;font-size:12.5px;font-weight:500;color:white;z-index:9999;pointer-events:none;opacity:0;transform:translateY(10px) scale(0.97);transition:all 0.25s cubic-bezier(0.23,1,0.32,1);max-width:300px;box-shadow:0 6px 20px rgba(0,0,0,0.18);';
      document.body.appendChild(el);
    }
    const colors = {
      success: 'linear-gradient(135deg,#4a7c59,#3a6447)',
      error:   'linear-gradient(135deg,#c03a3a,#a02e2e)',
      info:    'linear-gradient(135deg,#2e6da4,#235590)',
      warn:    'linear-gradient(135deg,#b87a1a,#965f14)'
    };
    const isRedTheme = currentColorHex === '#c03a3a';
    const isError = type === 'error' || type === 'err';
    /* No tema vermelho, apenas erros preservam o fundo vermelho.
       Sucesso, informação e aviso passam a usar um toast branco neutro. */
    el.style.background = isRedTheme && !isError
      ? '#ffffff'
      : (colors[type] || colors.success);
    el.style.color = isRedTheme && !isError ? '#2d2d2d' : '#ffffff';
    const iconColor = isRedTheme && !isError ? '#c03a3a' : '#ffffff';
    el.innerHTML = `<svg width="13" height="13" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="7" stroke="${iconColor}" stroke-width="1.2"/><path d="M5.5 8l2 2 3.5-3" stroke="${iconColor}" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg><span>${msg}</span>`;
    el.offsetHeight;
    el.style.opacity   = '1';
    el.style.transform = 'translateY(0) scale(1)';
    clearTimeout(__toastTimer);
    __toastTimer = setTimeout(() => {
      el.style.opacity   = '0';
      el.style.transform = 'translateY(8px) scale(0.97)';
    }, 3200);
  }

  /* ══ API PÚBLICA ══ */
  window.FarmaControlSettings = {
    API_BASE, STORAGE_KEY, defaults: defaultSettings, showToast,
    apply: applySettings, applyUser, loadRemote: loadRemoteSettings,
    saveLocal: saveStored, readLocal: parseStored, clearLocal: () => localStorage.removeItem(STORAGE_KEY),
    palettes, generateColorPalette, getPalette,
    getCurrentPalette: () => currentPalette,
    getCurrentColor: () => currentColorHex
  };

  /* ══ INICIALIZAÇÃO ══
   * Usa { once: true } para garantir que o listener é removido após a primeira execução.
   * Durante SPA nav, o sidebar-init.js dispara DOMContentLoaded manualmente, mas a
   * guarda __initialized impede que init() re-executa e sobrescreva o localStorage. */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }

})();
