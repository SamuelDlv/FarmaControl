// Contratos do fluxo unificado de recebimento e cancelamento, com API simulada.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../frontend/src/pages/sistema/compras/compras.js'), 'utf8');
const flow = source.slice(source.indexOf('function openModalAgendarEntrega('), source.indexOf('/* ══ EXPORTAR COMPRAS'));

function page() {
  const elements = new Map();
  const get = id => {
    if (!elements.has(id)) elements.set(id, {
      value: '', disabled: false, hidden: false, textContent: '', innerHTML: '',
      classList: { add() {}, remove() {} }
    });
    return elements.get(id);
  };
  const requests = [], messages = [];
  const compra = { id: 1, status: 'pendente', fornecedor_nome: 'Fornecedor', itens: [
    { id: 5, produto_nome: 'Produto', quantidade: 2, exige_validade: true }
  ] };
  const context = vm.createContext({
    window: { __allCompras: [compra] },
    document: { getElementById: get, body: { style: {} } },
    API_BASE: '/api', console,
    compraEscape: s => String(s || ''),
    toast: (...args) => messages.push(args),
    loadComprasStats: async () => {}, loadComprasTable: async () => {},
    updatePendentesBadge() {}, renderPurchases() {},
    fetch: async (url, options) => {
      requests.push({ url, payload: JSON.parse(options.body) });
      return { ok: true, json: async () => ({ ok: true }) };
    }
  });
  vm.runInContext(flow, context);
  get('pedido-status-1').value = 'recebido';
  get('agenda-1').value = '2026-11-11';
  get('recebe-lote-5').value = 'L001';
  return { context, get, requests, messages, compra, save: () => context.window.salvarAgendamento(1) };
}

test('abre somente o pedido solicitado, com as duas opções', () => {
  const p = page();
  p.context.window.__allCompras.push({ id: 2, status: 'pendente', fornecedor_nome: 'Outro' });
  p.context.openModalAgendarEntrega(1);
  assert.match(p.get('agenda-entrega-body').innerHTML, /PC-0001/);
  assert.doesNotMatch(p.get('agenda-entrega-body').innerHTML, /PC-0002/);
  assert.match(p.get('agenda-entrega-body').innerHTML, /value="cancelado"/);
  assert.match(p.get('agenda-entrega-body').innerHTML, /value="recebido"/);
});

test('cancelar dispensa data e validade e envia apenas o status', async () => {
  const p = page();
  p.get('pedido-status-1').value = 'cancelado';
  p.get('agenda-1').value = '';
  p.context.window.alterarStatusPedido(1);
  assert.equal(p.get('pedido-recebimento-1').hidden, true);
  await p.save();
  assert.deepEqual(p.requests, [{ url: '/api/compras/1', payload: { status: 'cancelado' } }]);
  assert.equal(p.compra.status, 'cancelado');
  assert.equal(p.context.document.body.style.overflow, '');
});

test('receber exige validade e envia lote, data e itens', async () => {
  const p = page();
  await p.save();
  assert.equal(p.requests.length, 0);
  assert.match(p.messages[0][0], /validade/);
  p.get('recebe-validade-5').value = '2027-12-31';
  await p.save();
  assert.deepEqual(p.requests[0].payload, {
    status: 'recebido', data_recebimento: '2026-11-11',
    itens_recebimento: [{ id: 5, lote_recebido: 'L001', data_validade_recebida: '2027-12-31' }]
  });
  assert.equal(p.compra.status, 'recebido');
});

test('trocar de cancelado para recebido restaura os campos', () => {
  const p = page();
  p.get('pedido-status-1').value = 'cancelado';
  p.context.window.alterarStatusPedido(1);
  p.get('pedido-status-1').value = 'recebido';
  p.context.window.alterarStatusPedido(1);
  assert.equal(p.get('pedido-recebimento-1').hidden, false);
  assert.equal(p.get('pedido-salvar-1').textContent, 'Confirmar recebimento');
});

test('falha da API mantém o pedido pendente e permite tentar novamente', async () => {
  const p = page();
  p.get('pedido-status-1').value = 'cancelado';
  p.context.fetch = async () => ({ ok: false, json: async () => ({ ok: false, mensagem: 'Sem permissão' }) });
  await p.save();
  assert.equal(p.compra.status, 'pendente');
  assert.equal(p.get('pedido-salvar-1').disabled, false);
  assert.equal(p.get('pedido-status-1').disabled, false);
  assert.equal(p.messages[0][0], 'Sem permissão');
});

test('cliques repetidos não duplicam a atualização', async () => {
  const p = page();
  p.get('pedido-status-1').value = 'cancelado';
  let finish, calls = 0;
  p.context.fetch = () => { calls++; return new Promise(resolve => { finish = resolve; }); };
  const saving = p.save();
  await p.save();
  assert.equal(calls, 1);
  assert.equal(p.get('pedido-salvar-1').disabled, true);
  finish({ ok: true, json: async () => ({ ok: true }) });
  await saving;
  assert.equal(p.get('pedido-salvar-1').disabled, false);
});
