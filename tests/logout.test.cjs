const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function setup() {
  const values = new Map([
    ['farmacontrol_usuario', 'usuario'],
    ['farmacontrol_csrf', 'csrf']
  ]);
  const handlers = {};
  const requests = [];
  const warnings = [];
  const window = {
    location: { href: '/estoque' },
    FarmaControlSettings: { showToast: (...args) => warnings.push(args) }
  };
  const document = {
    readyState: 'complete',
    documentElement: { classList: { add() {} } },
    getElementById: () => null,
    addEventListener: (name, handler) => { handlers[name] = handler; }
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,
    '../frontend/src/utils/sidebar-init.js'), 'utf8'), {
    window, document,
    sessionStorage: {
      removeItem: key => values.delete(key),
      setItem: (key, value) => values.set(key, value)
    },
    fetch: () => new Promise(resolve => requests.push(resolve))
  });
  const button = { getAttribute: () => '/acesso' };
  return {
    values, requests, warnings, window,
    click: () => handlers.click({
      target: { closest: () => button }, preventDefault() {}, stopPropagation() {}
    })
  };
}

test('logout lento preserva sessão local, ignora clique repetido e só navega após sucesso', async () => {
  const e = setup();
  const pending = e.click();
  await e.click();
  assert.equal(e.requests.length, 1);
  assert.equal(e.window.location.href, '/estoque');
  assert.equal(e.values.get('farmacontrol_usuario'), 'usuario');
  e.requests[0]({ ok: true });
  await pending;
  assert.equal(e.window.location.href, '/acesso');
  assert.equal(e.values.has('farmacontrol_usuario'), false);
  assert.equal(e.values.has('farmacontrol_csrf'), false);
});

test('falha no logout mantém sessão e permite tentar novamente', async () => {
  const e = setup();
  const failed = e.click();
  e.requests[0]({ ok: false });
  await failed;
  assert.equal(e.window.location.href, '/estoque');
  assert.equal(e.values.get('farmacontrol_csrf'), 'csrf');
  assert.equal(e.warnings.length, 1);
  const retry = e.click();
  assert.equal(e.requests.length, 2);
  e.requests[1]({ ok: true });
  await retry;
  assert.equal(e.window.location.href, '/acesso');
});
