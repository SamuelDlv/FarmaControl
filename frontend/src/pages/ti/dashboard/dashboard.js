/* ══════════════════════════════════════════════════════════════════════
 * FARMAControl — DASHBOARD (TI)
 * ══════════════════════════════════════════════════════════════════════
 *
 * Dashboard adaptado ao perfil do usuário logado.
 * Exibe KPIs e informações relevantes conforme as permissões.
 *
 * Perfis suportados: Gerente, Balconista, Compras, TI
 * ══════════════════════════════════════════════════════════════════════ */

// Guard de sessão e sidebar gerenciados globalmente pelo global-settings.js e sidebar-init.js

'use strict';
const EASE = t => t < 0.5 ? 2*t*t : -1+(4-2*t)*t;

function initCounters() {
  document.querySelectorAll('.kpi-value[data-target]').forEach(el => {
    const target = +el.dataset.target; let done = false;
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting && !done) { done = true; obs.disconnect(); const t0 = performance.now(); (function s(now) { const p = Math.min((now-t0)/900,1); el.textContent = Math.round(EASE(p)*target).toLocaleString('pt-BR'); if(p<1) requestAnimationFrame(s); })(t0); } }, {threshold:0.1});
    obs.observe(el);
  });
}

function initFilter() {
  const rows = [...document.querySelectorAll('#table-body tr')];
  const cnt = document.getElementById('filter-count');
  document.querySelectorAll('.ftab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.ftab').forEach(t => t.classList.remove('active')); tab.classList.add('active');
      const f = tab.dataset.filter; let v = 0;
      rows.forEach(r => { const ok = f==='all' || r.dataset.status===f; r.style.display=ok?'':'none'; if(ok) v++; });
      if(cnt) cnt.textContent = `Exibindo ${v} de ${rows.length} itens`;
    });
  });
}

let toastT;
function toast(msg, type='success') {
  let el = document.getElementById('fc-toast');
  if (!el) {
    el = document.createElement('div');
    el.id = 'fc-toast';
    el.setAttribute('role', 'status');
    el.style.cssText = 'position:fixed;bottom:22px;right:22px;display:flex;align-items:center;gap:8px;padding:10px 15px;border-radius:9px;font-family:Outfit,sans-serif;font-size:12.5px;font-weight:500;color:white;z-index:9999;pointer-events:none;opacity:0;transform:translateY(10px) scale(0.97);transition:all 0.25s cubic-bezier(0.23,1,0.32,1);max-width:300px;box-shadow:0 6px 20px rgba(0,0,0,0.18);';
    document.body.appendChild(el);
  }
  // Usa variáveis CSS dinâmicas para cores do toast
  const style = getComputedStyle(document.documentElement);
  const sage = style.getPropertyValue('--sage').trim() || '#4a7c59';
  const sage2 = style.getPropertyValue('--sage-2').trim() || '#3a6447';
  const bg = {
    success: `linear-gradient(135deg,${sage},${sage2})`,
    error:   'linear-gradient(135deg,#c03a3a,#a02e2e)',
    info:    'linear-gradient(135deg,#2e6da4,#235590)'
  };
  el.style.background = bg[type] || bg.success;
  el.innerHTML = `<svg width="13" height="13" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="7" stroke="white" stroke-width="1.2"/><path d="M5.5 8l2 2 3.5-3" stroke="white" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg><span>${msg}</span>`;
  el.offsetHeight;
  el.style.opacity = '1';
  el.style.transform = 'translateY(0) scale(1)';
  clearTimeout(toastT);
  toastT = setTimeout(() => { el.style.opacity = '0'; el.style.transform = 'translateY(8px) scale(0.97)'; }, 3200);
}

document.getElementById('btn-refresh')?.addEventListener('click', () => {
  const svg = document.querySelector('#btn-refresh svg');
  if (svg) { svg.style.transition = 'transform 0.6s'; svg.style.transform = 'rotate(360deg)'; setTimeout(() => { svg.style.transition = 'none'; svg.style.transform = 'rotate(0deg)'; }, 650); }
  toast('Dados atualizados com sucesso.', 'success');
});

document.querySelectorAll('.row-btn').forEach(btn => btn.addEventListener('click', e => {
  const name = e.target.closest('tr')?.querySelector('.prod-name')?.textContent || 'produto';
  toast(btn.textContent === 'Repor' ? `Reposição criada: ${name}` : `Abrindo ficha: ${name}`, btn.textContent === 'Repor' ? 'success' : 'info');
}));

document.getElementById('btn-notif')?.addEventListener('click', () => toast('4 alertas não lidos.', 'info'));

function initClock() {
  const el = document.querySelector('.page-subtitle'); if (!el) return;
  const t = () => { const n = new Date(); el.textContent = `Situação do estoque em tempo real · Última atualização: ${String(n.getHours()).padStart(2,'0')}:${String(n.getMinutes()).padStart(2,'0')}:${String(n.getSeconds()).padStart(2,'0')}`; };
  t(); setInterval(t, 1000);
}

document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'b') { e.preventDefault(); document.getElementById('btn-collapse')?.click(); }
  if (e.key === 'Escape') document.getElementById('sidebar')?.classList.remove('mobile-open');
});

document.addEventListener('DOMContentLoaded', () => {
  initCounters(); initFilter(); initClock();
  [...document.querySelectorAll('.kpi-card,.card')].forEach((el, i) => {
    el.style.cssText += `opacity:0;transform:translateY(10px);transition:opacity 0.35s ease ${i*0.04}s,transform 0.35s ease ${i*0.04}s;`;
    setTimeout(() => { el.style.opacity = '1'; el.style.transform = 'translateY(0)'; }, 20 + i * 30);
  });
});
