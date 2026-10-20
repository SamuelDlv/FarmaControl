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
