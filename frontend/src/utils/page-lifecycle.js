/* Guia de manutenção — Descarta listeners, timers e leituras quando o documento deixa de estar ativo.
 * Os seletores dependem do HTML da tela; dados e permissões devem continuar validados na API.
 */
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

  // As telas devem usar estes wrappers para que o descarte encontre todos os
  // timers. Um setInterval avulso continuaria chamando código de uma tela encerrada.
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
  // Um único AbortController agrupa os listeners desta geração do documento.
  // Abortar remove inclusive handlers registrados em window e document.
  window.fcPageListen = (target, type, callback, options = {}) => {
    const settings = typeof options === 'boolean' ? { capture: options } : options;
    target.addEventListener(type, callback, { ...settings, signal: controller.signal });
  };
  // Libera recursos da tela para não manter callbacks ativos após a navegação.
  window.addEventListener('fc-page-unload', () => {
    // Invalida trabalhos assíncronos que ainda guardam o token da geração anterior.
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
  // Descarta os recursos associados ao documento que está saindo de cena.
  window.addEventListener('pagehide', () => {
    window.dispatchEvent(new Event('fc-page-unload'));
  });
  // Uma página restaurada do bfcache teve seus listeners/timers descartados.
  // Recarregar obtém dados atuais e inicializa cada recurso uma única vez.
  // Trata a reapresentação do documento, inclusive restauração pelo cache do navegador.
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
