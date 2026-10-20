/**
 * Ciclo de vida do documento de cada tela.
 * Mantém os nomes legados dos timers, mas registra sua limpeza uma única vez.
 * Listeners em document/window precisam ser descartados: esses elementos
 * sobrevivem ao DOM da página e acumulariam ações a cada visita.
 */
(function () {
  'use strict';
  if (window.FarmaControlPage) return;
  let controller = new AbortController();
  window.__fcPageToken = 1;
  window.__fcTimers = [];

  window.__fcSetInterval = (callback, delay) => {
    const id = setInterval(callback, delay);
    window.__fcTimers.push(id);
    return id;
  };
  window.__fcSetTimeout = (callback, delay) => {
    const id = setTimeout(() => {
      window.__fcTimers = window.__fcTimers.filter(timer => timer !== id);
      callback();
    }, delay);
    window.__fcTimers.push(id);
    return id;
  };
  window.fcPageListen = (target, type, callback, options = {}) => {
    const settings = typeof options === 'boolean' ? { capture: options } : options;
    target.addEventListener(type, callback, { ...settings, signal: controller.signal });
  };
  window.addEventListener('fc-page-unload', () => {
    window.__fcPageToken++;
    controller.abort();
    controller = new AbortController();
    window.__fcTimers.forEach(id => {
      clearInterval(id);
      clearTimeout(id);
    });
    window.__fcTimers = [];
    window.dispatchEvent(new Event('fc-page-unloaded'));
  });
  window.addEventListener('pagehide', () => {
    window.dispatchEvent(new Event('fc-page-unload'));
  });
  // Uma página restaurada do bfcache teve seus listeners/timers descartados.
  // Recarregar obtém dados atuais e inicializa cada recurso uma única vez.
  window.addEventListener('pageshow', event => {
    if (event.persisted) window.location.reload();
  });
  window.FarmaControlPage = Object.freeze({
    listen: window.fcPageListen,
    get signal() {
      return controller.signal;
    }
  });
})();
