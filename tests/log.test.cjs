const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const flush = () => new Promise(resolve => setImmediate(resolve));

async function page() {
  const elements = new Map(),
    requests = [];
  const node = () => ({
    value: '',
    textContent: '',
    disabled: false,
    dataset: {},
    children: [],
    handlers: {},
    addEventListener(event, fn) {
      this.handlers[event] = fn;
    },
    appendChild(child) {
      this.children.push(child);
    },
    append(...children) {
      this.children.push(...children);
    },
    replaceChildren(...children) {
      this.children = children;
    },
    add(option) {
      this.children.push(option);
    },
    checkValidity() {
      return true;
    },
    focus() {}
  });
  function element(id) {
    if (!elements.has(id)) elements.set(id, node());
    return elements.get(id);
  }
  const ids = ['filtro-busca', 'filtro-atividade', 'filtro-usuario', 'filtro-inicio', 'filtro-fim'];
  element('filtro-atividade').value = 'alteracoes';
  element('log-filters').elements = ids.map(element);
  element('log-filters').reset = () =>
    ids.forEach(id => {
      element(id).value = '';
    });
  const fixture = {
    id: 19,
    usuario_id: 42,
    usuario_nome: 'Operador',
    perfil: 'atendente',
    acao: 'Concluiu venda',
    detalhes: 'registro=7\n<img src=x onerror=alert(1)>',
    criado_em: '2026-10-12T12:00:00Z',
    status_http: 201
  };
  const context = {
    URLSearchParams,
    Intl,
    Date,
    Option: function (text, value) {
      return { text, value };
    },
    document: { getElementById: element, createElement: node },
    sessionStorage: { getItem: () => JSON.stringify({ nome: 'Teste', perfil: 'proprietario' }) },
    window: { FarmaControlSettings: { API_BASE: '' } },
    fetch: async url => {
      requests.push(new URL(url, 'http://localhost'));
      return {
        ok: true,
        json: async () => ({ ok: true, filtros: {}, usuarios: [], logs: [fixture], proximo: 19 })
      };
    }
  };
  vm.runInNewContext(
    fs.readFileSync(path.join(__dirname, '../frontend/src/pages/sistema/log/log.js'), 'utf8'),
    context
  );
  await flush();
  return { element, requests, fixture };
}

test('log expande detalhes como texto e exibe resultado', async () => {
  const { element, fixture } = await page();
  const cells = element('log-rows').children[0].children;
  assert.equal(cells.length, 6);
  assert.equal(cells[3].textContent, 'Concluiu venda');
  assert.equal(cells[5].textContent, 'Realizada');
  const details = cells[4].children[0];
  assert.match(details.children[0].textContent, /Evento #19/);
  assert.equal(details.children[1].textContent, fixture.detalhes);
  assert.equal(details.children[1].children.length, 0);
});

test('busca, filtro e paginação mantêm a consulta; limpar remove filtros', async () => {
  const { element, requests } = await page();
  assert.equal(requests[0].searchParams.get('atividade'), 'alteracoes');
  element('filtro-busca').value = 'Distribuidora Central';
  element('filtro-usuario').value = '42';
  element('log-filters').handlers.submit({ preventDefault() {} });
  await flush();
  assert.equal(requests.at(-1).searchParams.get('busca'), 'Distribuidora Central');
  element('proxima').handlers.click();
  await flush();
  assert.equal(requests.at(-1).searchParams.get('antes'), '19');
  assert.equal(requests.at(-1).searchParams.get('busca'), 'Distribuidora Central');
  assert.equal(requests.at(-1).searchParams.get('usuario_id'), '42');
  element('limpar-filtros').handlers.click();
  await flush();
  assert.equal(requests.at(-1).searchParams.get('antes'), '0');
  assert.equal(requests.at(-1).searchParams.has('busca'), false);
  assert.equal(requests.at(-1).searchParams.has('atividade'), false);
});
