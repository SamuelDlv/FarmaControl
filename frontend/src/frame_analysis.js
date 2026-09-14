/* frame_analysis.js — análise frame a frame do crossfade
   Instalado via fetch+eval; mede a transição real clicando em "Estoque". */
(function() {
  'use strict';
  if (window.__faActive) {
    window.__faResult = 'running';
    return;
  }
  window.__faActive = true;
  window.__faResult = 'pending';
  const log = [];
  const t0 = performance.now();
  let stopAt = 1800; // coleta por 1.8s (fase mont + fade 220ms + finalize)
  const iid = setInterval(() => {
    const t = performance.now() - t0;
    const body = document.body;
    const stage = document.getElementById('fc-xf-stage');
    const cs = getComputedStyle(body);
    log.push({
      t: Math.round(t),
      cls: body.className.slice(0, 40),
      disp: cs.display,
      op: cs.opacity,
      vis: cs.visibility,
      hasStage: !!stage,
      stageOp: stage ? Math.round(parseFloat(getComputedStyle(stage).opacity) * 100) / 100 : null,
      stageBg: stage ? getComputedStyle(stage).backgroundColor : null,
      pos: stage ? getComputedStyle(stage).position : null,
    });
    if (t > stopAt) {
      clearInterval(iid);
      window.__faResult = JSON.stringify(log);
      window.__faActive = false;
    }
  }, 5);
  // Disparar a navegação após 200ms (garante amostras pré-clique)
  setTimeout(() => {
    const link = [...document.querySelectorAll('.sb-item a, a[href*="estoque.html"]')]
      .find(a => a.getAttribute('href').includes('estoque.html'));
    if (link) {
      window.__faClicked = true;
      link.click();
    } else {
      window.__faResult = 'link não encontrado';
      window.__faActive = false;
    }
  }, 200);
})();
