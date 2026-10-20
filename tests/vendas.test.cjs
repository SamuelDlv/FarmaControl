const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

async function page() {
  const elements = new Map(),
    requests = [];
  function element(id) {
    if (!elements.has(id))
      elements.set(id, {
        value: '',
        checked: false,
        disabled: false,
        innerHTML: '',
        textContent: '',
        handlers: {},
        addEventListener(name, handler) {
          this.handlers[name] = handler;
        },
        focus() {},
        close() {},
        showModal() {}
      });
    return elements.get(id);
  }
  const common = {
    produto_id: 1,
    nome: 'Marca A',
    principio_ativo: 'Ácido acetilsalicílico',
    tipo_produto: 'medicamento',
    preco_venda: '12.50',
    valido: 1
  };
  const rows = [
    { ...common, estoque_id: 10, quantidade: 5, data_validade: '2028-01-01' },
    { ...common, estoque_id: 11, quantidade: 1, data_validade: '2027-01-01' },
    { ...common, produto_id: 2, nome: 'Marca B', estoque_id: 12, quantidade: 0 },
    {
      ...common,
      produto_id: 3,
      nome: 'Produto exclusivo',
      principio_ativo: 'Outro ativo',
      estoque_id: 13,
      quantidade: 4
    }
  ];
  const context = {
    document: { getElementById: element, querySelectorAll: () => [], addEventListener() {} },
    window: { FarmaControlSettings: { API_BASE: '' }, addEventListener() {} },
    sessionStorage: { getItem: () => JSON.stringify({ nome: 'Teste', perfil: 'atendente' }) },
    fetch: async (url, options) => {
      requests.push({ url, options });
      return {
        ok: true,
        json: async () =>
          url.endsWith('/catalogo')
            ? { ok: true, produtos: rows }
            : { ok: true, id: 5, valor_total: '37.50' }
      };
    }
  };
  vm.runInNewContext(
    fs.readFileSync(path.join(__dirname, '../frontend/src/pages/sistema/vendas/vendas.js'), 'utf8'),
    context
  );
  await new Promise(resolve => setImmediate(resolve));
  const click = (id, dataset) =>
    element(id).handlers.click({ target: { closest: () => ({ dataset }) } });
  return { element, click, requests };
}

test('catálogo agrupa lotes por produto e vende unidades pelo preço individual', async () => {
  const { element, click, requests } = await page();
  assert.equal((element('resultados').innerHTML.match(/<article/g) || []).length, 3);
  assert.match(element('resultados').innerHTML, /6 un\./);
  assert.match(element('resultados').innerHTML, /\/ unidade/);
  click('resultados', { add: '1' });
  click('resultados', { add: '1' });
  click('resultados', { add: '1' });
  assert.match(element('total').textContent, /37,50/);
  element('pagamento').value = 'pix';
  await element('concluir').onclick();
  const payload = JSON.parse(requests.find(r => r.options).options.body);
  assert.deepEqual(payload.itens, [
    { estoque_id: 11, quantidade: 1, preco_unitario: '12.50' },
    { estoque_id: 10, quantidade: 2, preco_unitario: '12.50' }
  ]);
});

test('busca por princípio ativo aceita acentos e pontuação e limpa filtros conflitantes', async () => {
  const { element, click } = await page();
  element('busca').value = 'acido-acetilsalicilico';
  element('busca').handlers.input();
  assert.equal(element('contagem').textContent, '2 produtos encontrados');
  element('tipo').value = 'outro';
  element('disponiveis').checked = true;
  click('resultados', { related: '1' });
  assert.equal(element('contagem').textContent, '2 produtos encontrados');
  element('busca').value = 'Produto exclusivo';
  element('busca').handlers.input();
  assert.equal(element('contagem').textContent, '1 produtos encontrados');
});
