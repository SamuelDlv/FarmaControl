const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

test('aviso persiste, conta tempo decorrido e libera nova tentativa ao final', () => {
  let now = 0;
  let tick;
  const classes = new Set();
  const message = {
    textContent: '',
    classList: { add: c => classes.add(c), remove: c => classes.delete(c) }
  };
  const context = vm.createContext({
    window: {}, performance: { now: () => 0 },
    Date: { now: () => now },
    document: { getElementById: () => message, addEventListener() {} },
    setInterval: fn => { tick = fn; return 1; },
    clearInterval: () => { tick = null; }
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname,
    '../frontend/src/pages/acesso/acesso.js'), 'utf8'), context);
  context.showLoginAttempts({ tentativas_restantes: 3, aguarde_segundos: 0,
    mensagem: 'Restam 3 tentativas disponíveis.' });
  assert.equal(message.textContent, 'Restam 3 tentativas disponíveis.');
  assert.equal(classes.has('show'), true);
  context.showLoginAttempts({ tentativas_restantes: 0, aguarde_segundos: 65 });
  assert.match(message.textContent, /01:05/);
  now = 61000; // Uma aba inativa pode atrasar os callbacks do temporizador.
  tick();
  assert.match(message.textContent, /00:04/);
  now = 65000;
  tick();
  assert.match(message.textContent, /pode tentar entrar novamente/);
  assert.equal(tick, null);
  context.showLoginAttempts({});
  assert.equal(message.textContent, '');
  assert.equal(classes.has('show'), false);
});
