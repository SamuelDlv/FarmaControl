/* Guia de manutenção — Atualiza a data exibida no cabeçalho sem exigir recarregamento da página.
 * Os seletores dependem do HTML da tela; dados e permissões devem continuar validados na API.
 */
/** Data local, por extenso, em todos os cabeçalhos do sistema. */
(function () {
  'use strict';
  const labels = document.querySelectorAll('.date-chip span');
  if (!labels.length) return;
  const formatter = new Intl.DateTimeFormat('pt-BR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric'
  });
  // Recalcula a data local e só escreve no DOM quando o texto muda, evitando
  // substituições desnecessárias a cada disparo do timer de um segundo.
  function update() {
    const text = formatter.format(new Date());
    labels.forEach(label => {
      if (label.textContent !== text) label.textContent = text;
    });
  }
  update();
  window.__fcSetInterval(update, 1000);
  window.fcPageListen(document, 'visibilitychange', update);
})();
