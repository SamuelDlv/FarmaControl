/* Testes da infraestrutura compartilhada em isolamento, sem DOM remoto ou API real. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const utils = path.resolve(__dirname, '../frontend/src/utils');

function environment() {
  const calls = [];
  const document = new EventTarget();
  document.readyState = 'loading';
  const window = new EventTarget();
  window.location = { href: 'http://localhost:5000/pages/sistema/estoque/estoque.html' };
  window.fetch = (input, init) => {
    calls.push({ input, init });
    return Promise.resolve({ ok: true });
  };
  const values = new Map([['farmacontrol_csrf', 'csrf-teste']]);
  const storage = {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: key => values.delete(key)
  };
  let counter = 0;
  const timers = new Map();
  const sandbox = {
    window,
    document,
    Headers,
    URL,
    Event,
    AbortController,
    AbortSignal,
    console,
    sessionStorage: storage,
    localStorage: storage,
    setTimeout: fn => {
      timers.set(++counter, fn);
      return counter;
    },
    setInterval: fn => {
      timers.set(++counter, fn);
      return counter;
    },
    clearTimeout: id => timers.delete(id),
    clearInterval: id => timers.delete(id)
  };
  const context = vm.createContext(sandbox);
  return {
    window,
    document,
    calls,
    timers,
    storage,
    run: file => vm.runInContext(fs.readFileSync(path.join(utils, file), 'utf8'), context)
  };
}

test('401 da API aciona guarda de sessão; 403 e origem externa não redirecionam', async () => {
  const e = environment();
  let status = 401;
  let redirects = 0;
  e.window.fetch = async () => ({ status });
  e.window.fcRequireLogin = () => redirects++;
  e.run('global-settings.js');
  assert.equal((await e.window.fetch('/dashboard/stats')).status, 401);
  assert.equal(redirects, 1);
  await e.window.fetch('https://external.example/resource');
  assert.equal(redirects, 1);
  status = 403;
  await e.window.fetch('/admin/usuarios');
  assert.equal(redirects, 1);
});

test('timers de uma tela são cancelados; timers da próxima permanecem ativos', () => {
  const e = environment();
  e.run('page-lifecycle.js');
  e.window.__fcSetInterval(() => {}, 10);
  e.window.__fcSetTimeout(() => {}, 10);
  assert.equal(e.timers.size, 2);
  e.window.dispatchEvent(new Event('fc-page-unload'));
  assert.equal(e.timers.size, 0);
  e.window.__fcSetInterval(() => {}, 10);
  assert.equal(e.timers.size, 1);
});

test('timeout concluído sai do registro e executa o callback uma vez', () => {
  const e = environment();
  e.run('page-lifecycle.js');
  let count = 0;
  const id = e.window.__fcSetTimeout(() => count++, 10);
  e.timers.get(id)();
  assert.equal(count, 1);
  assert.equal(e.window.__fcTimers.length, 0);
});

test('listeners antigos são removidos, listeners da nova tela funcionam', () => {
  const e = environment();
  e.run('page-lifecycle.js');
  let old = 0,
    next = 0;
  e.window.fcPageListen(e.document, 'click', () => old++);
  e.document.dispatchEvent(new Event('click'));
  e.window.dispatchEvent(new Event('fc-page-unload'));
  e.window.fcPageListen(e.document, 'click', () => next++);
  e.document.dispatchEvent(new Event('click'));
  assert.equal(old, 1);
  assert.equal(next, 1);
});

test('carregar runtime duas vezes não duplica evento de descarte', () => {
  const e = environment();
  e.run('page-lifecycle.js');
  e.run('page-lifecycle.js');
  let count = 0;
  e.window.addEventListener('fc-page-unloaded', () => count++);
  e.window.dispatchEvent(new Event('fc-page-unload'));
  assert.equal(count, 1);
});

test('mutações da API enviam credenciais e CSRF sem alterar headers do chamador', async () => {
  const e = environment();
  e.run('global-settings.js');
  const headers = new Headers({ 'Content-Type': 'application/json' });
  await e.window.fetch('http://localhost:5000/estoque', { method: 'POST', headers });
  assert.equal(e.calls[0].init.credentials, 'include');
  assert.equal(e.calls[0].init.headers.get('X-CSRF-Token'), 'csrf-teste');
  assert.equal(headers.has('X-CSRF-Token'), false);
});

test('leitura da API não adiciona CSRF', async () => {
  const e = environment();
  e.run('global-settings.js');
  await e.window.fetch('/estoque');
  assert.equal(e.calls[0].init.credentials, 'include');
  assert.equal(e.calls[0].init.headers, undefined);
});

test('origem externa mantém opções e não recebe token nem credenciais extras', async () => {
  const e = environment();
  e.run('global-settings.js');
  const options = { method: 'POST', credentials: 'omit' };
  await e.window.fetch('https://example.invalid/upload', options);
  assert.equal(e.calls[0].init, options);
  assert.equal(options.headers, undefined);
});

test('objeto Request preserva método, headers e opção explícita de credenciais', async () => {
  const e = environment();
  e.run('global-settings.js');
  const request = new Request('http://localhost:5000/estoque', {
    method: 'PUT',
    headers: { 'X-Custom': 'value' }
  });
  await e.window.fetch(request, { credentials: 'omit' });
  const options = e.calls[0].init;
  assert.equal(options.credentials, 'omit');
  assert.equal(options.headers.get('X-Custom'), 'value');
  assert.equal(options.headers.get('X-CSRF-Token'), 'csrf-teste');
});

test('leituras pendentes são canceladas no pagehide; logout keepalive permanece independente', async () => {
  const e = environment();
  e.run('global-settings.js');
  e.run('page-lifecycle.js');
  await e.window.fetch('/estoque');
  await e.window.fetch('/auth/logout', { method: 'POST', keepalive: true });
  const signal = e.calls[0].init.signal;
  assert.equal(signal.aborted, false);
  assert.equal(e.calls[1].init.signal, undefined);
  e.window.dispatchEvent(new Event('pagehide'));
  assert.equal(signal.aborted, true);
});

test('cancelamento do chamador e ciclo da página são combinados', async () => {
  const e = environment();
  e.run('global-settings.js');
  e.run('page-lifecycle.js');
  const caller = new AbortController();
  await e.window.fetch('/estoque', { signal: caller.signal });
  caller.abort();
  assert.equal(e.calls[0].init.signal.aborted, true);
  await e.window.fetch('/estoque');
  assert.equal(e.calls[1].init.signal.aborted, false);
});

test('API usa a origem HTTPS da aplicação', async () => {
  const e = environment();
  e.window.location.href = 'https://farmacia.example/pages/sistema/estoque/estoque.html';
  e.run('global-settings.js');
  assert.equal(e.window.FarmaControlSettings.API_BASE, 'https://farmacia.example');
  await e.window.fetch('/estoque', { method: 'POST' });
  assert.equal(e.calls[0].init.headers.get('X-CSRF-Token'), 'csrf-teste');
});

test('preferência antiga é removida sem perder cor, densidade ou outros dados locais', () => {
  const e = environment();
  e.run('global-settings.js');
  const settings = e.window.FarmaControlSettings;
  e.storage.setItem(
    settings.STORAGE_KEY,
    JSON.stringify({
      tema: 'escuro',
      tema_efetivo: 'escuro',
      cor_destaque: '#2e6da4',
      densidade_interface: 'compacta',
      nome_farmacia: 'Teste'
    })
  );
  const value = settings.readLocal();
  assert.equal(value.tema, undefined);
  assert.equal(value.tema_efetivo, undefined);
  assert.equal(value.cor_destaque, '#2e6da4');
  assert.equal(value.densidade_interface, 'compacta');
  assert.equal(value.nome_farmacia, 'Teste');
  assert.equal(JSON.parse(e.storage.getItem(settings.STORAGE_KEY)).tema, undefined);
  settings.saveLocal({ tema: 'escuro' });
  assert.equal(settings.readLocal().tema, undefined);
});

test('paletas conservam acentos e não geram superfícies do modo removido', () => {
  const e = environment();
  e.run('global-settings.js');
  const settings = e.window.FarmaControlSettings;
  for (const color of [...Object.keys(settings.palettes), '#7654ab']) {
    const palette = settings.getPalette(color);
    assert.equal(palette.sage, color);
    assert.match(palette.sage2, /^#[0-9a-f]{6}$/);
    assert.equal(palette.surface, undefined);
    assert.equal(palette.surface2, undefined);
  }
  assert.equal(settings.getPalette('#4a7c59').sage2, '#3a6447');
});
