/* Guia de manutenção — Oculta o documento durante a validação visual da sessão e encaminha ao login quando necessário.
 * Os seletores dependem do HTML da tela; dados e permissões devem continuar validados na API.
 */
/* Carregado antes do conteúdo. O servidor valida a sessão antes de entregar
 * cada HTML; o histórico deve repetir essa validação antes de reaparecer. */
(function () {
  'use strict';
  const root = document.documentElement;
  const lock = document.createElement('style');
  lock.textContent = 'html[data-fc-auth-hidden] { visibility: hidden !important; }';
  document.head.appendChild(lock);
  const hide = () => root.setAttribute('data-fc-auth-hidden', '');
  hide();
  let redirecting = false;
  // Todos os fluxos que recebem 401 convergem aqui. A marca redirecting torna
  // chamadas concorrentes inofensivas e a limpeza remove a identidade visual antiga.
  window.fcRequireLogin = function () {
    hide();
    if (redirecting) return;
    redirecting = true;
    try {
      ['farmacontrol_usuario', 'farmacontrol_perfil', 'farmacontrol_token',
        'farmacontrol_csrf'].forEach(key => sessionStorage.removeItem(key));
    } catch (_) { /* O redirecionamento independe do armazenamento. */ }
    // Usa o mesmo servidor para URLs atuais e aliases antigos.
    window.location.replace(window.location.protocol === 'file:'
      ? 'http://localhost:5000/pages/acesso/acesso.html'
      : '/pages/acesso/acesso.html');
  };
  if (window.location.protocol === 'file:') {
    window.fcRequireLogin();
    return;
  }
  document.addEventListener('DOMContentLoaded', () => {
    if (!redirecting) root.removeAttribute('data-fc-auth-hidden');
  }, { once: true });
  // Descarta os recursos associados ao documento que está saindo de cena.
  window.addEventListener('pagehide', hide);
  // Trata a reapresentação do documento, inclusive restauração pelo cache do navegador.
  window.addEventListener('pageshow', event => {
    if (event.persisted) {
      hide();
      window.location.reload();
    }
  });
})();
