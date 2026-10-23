const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../frontend/src/utils/auth-guard.js'), 'utf8');

function setup(protocol = 'http:') {
  const attrs = new Set();
  const removed = [];
  const redirects = [];
  let reloads = 0;
  const document = new EventTarget();
  document.documentElement = {
    setAttribute: name => attrs.add(name), removeAttribute: name => attrs.delete(name)
  };
  document.head = { appendChild() {} };
  document.createElement = () => ({});
  const window = new EventTarget();
  window.location = {
    protocol, replace: url => redirects.push(url), reload: () => reloads++
  };
  vm.runInNewContext(source, {
    document, window, sessionStorage: { removeItem: key => removed.push(key) }
  });
  return { document, window, removed, redirects,
    hidden: () => attrs.has('data-fc-auth-hidden'), reloads: () => reloads };
}

test('documento validado no servidor aparece ao carregar, sem exigir sessionStorage', () => {
  const e = setup();
  assert.equal(e.hidden(), true);
  e.document.dispatchEvent(new Event('DOMContentLoaded'));
  assert.equal(e.hidden(), false);
  assert.equal(e.redirects.length, 0);
});

test('Voltar pelo cache mantém documento oculto e solicita nova validação ao servidor', () => {
  const e = setup();
  e.document.dispatchEvent(new Event('DOMContentLoaded'));
  e.window.dispatchEvent(new Event('pagehide'));
  assert.equal(e.hidden(), true);
  const restored = new Event('pageshow');
  Object.defineProperty(restored, 'persisted', { value: true });
  e.window.dispatchEvent(restored);
  assert.equal(e.hidden(), true);
  assert.equal(e.reloads(), 1);
});

test('sessão inválida oculta conteúdo, limpa dados e redireciona apenas uma vez', () => {
  const e = setup();
  e.window.fcRequireLogin();
  e.window.fcRequireLogin();
  e.document.dispatchEvent(new Event('DOMContentLoaded'));
  assert.equal(e.hidden(), true);
  assert.deepEqual(e.redirects, ['/pages/acesso/acesso.html']);
  assert.equal(e.removed.length, 4);
  assert.ok(e.removed.includes('farmacontrol_csrf'));
});

test('HTML aberto como arquivo permanece oculto e vai ao login do servidor', () => {
  const e = setup('file:');
  e.document.dispatchEvent(new Event('DOMContentLoaded'));
  assert.equal(e.hidden(), true);
  assert.deepEqual(e.redirects, ['http://localhost:5000/pages/acesso/acesso.html']);
});
