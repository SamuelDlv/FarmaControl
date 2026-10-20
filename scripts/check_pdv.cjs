/* Integração da tela em Chrome isolado, com API simulada e sem banco real. */
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const root = path.resolve(__dirname, '..');
const artifacts = path.join(root, '.audit-backup/pdv');
fs.mkdirSync(artifacts, { recursive: true });
const delay = ms => new Promise(r => setTimeout(r, ms));
let sales = 0;
const fixture = [1, 2, 3].map(id => ({
  produto_id: id,
  nome: [
    'Paracetamol 500 mg 20 comprimidos',
    'Paracetamol 500 mg 10 comprimidos',
    'Sabonete líquido 200 ml'
  ][id - 1],
  nome_generico: id < 3 ? 'Paracetamol' : null,
  fabricante: 'Laboratório ' + id,
  codigo_barras: '78900' + id,
  tipo_produto: id < 3 ? 'medicamento' : 'outro',
  requer_receita: 0,
  preco_venda: String(id * 5),
  estoque_id: id,
  lote: 'L' + id,
  quantidade: 10,
  data_validade: '2027-12-01',
  valido: 1
}));
const server = http.createServer((req, res) => {
  const pathname = new URL(req.url, 'http://local').pathname;
  res.setHeader('Content-Type', 'application/json');
  if (pathname === '/vendas/catalogo') {
    res.end(JSON.stringify({ ok: true, produtos: fixture }));
    return;
  }
  if (pathname === '/vendas/balcao') {
    let body = '';
    req.on('data', c => (body += c));
    req.on('end', () => {
      const data = JSON.parse(body);
      assert.equal(data.itens.length, 1);
      assert.equal(data.itens[0].quantidade, 1);
      sales++;
      res.end(JSON.stringify({ ok: true, id: 10, valor_total: '5.00' }));
    });
    return;
  }
  if (pathname.startsWith('/configuracoes')) {
    res.end(JSON.stringify({ ok: true, configuracoes: [] }));
    return;
  }
  if (pathname === '/auth/me') {
    res.end(
      JSON.stringify({
        ok: true,
        usuario: {
          id: 1,
          nome: 'Atendente',
          perfil: 'atendente',
          permissoes: ['dashboard', 'estoque']
        }
      })
    );
    return;
  }
  const base = path.join(root, 'frontend/src');
  const file = path.resolve(base, '.' + pathname);
  if (!file.startsWith(base + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
    res.writeHead(404);
    res.end('{}');
    return;
  }
  res.setHeader(
    'Content-Type',
    {
      '.html': 'text/html; charset=utf-8',
      '.js': 'text/javascript; charset=utf-8',
      '.css': 'text/css; charset=utf-8'
    }[path.extname(file)] || 'application/octet-stream'
  );
  res.end(fs.readFileSync(file));
});
(async () => {
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  const origin = 'http://127.0.0.1:' + server.address().port;
  const chrome = spawn(
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    [
      '--headless=new',
      '--disable-gpu',
      '--no-first-run',
      '--remote-debugging-port=0',
      '--user-data-dir=' + path.join(artifacts, 'chrome-profile'),
      'about:blank'
    ],
    { windowsHide: true }
  );
  let endpoint = '',
    ws;
  const errors = [];
  chrome.stderr.on('data', c => {
    const m = String(c).match(/DevTools listening on (ws:\/\/[^\s]+)/);
    if (m) endpoint = m[1];
  });
  try {
    for (let i = 0; i < 100 && !endpoint; i++) await delay(100);
    assert(endpoint, 'Chrome indisponível');
    const debug = endpoint.replace('ws://', 'http://').split('/devtools/')[0];
    const targets = await (await fetch(debug + '/json/list')).json();
    ws = new WebSocket(targets.find(t => t.type === 'page').webSocketDebuggerUrl);
    await new Promise((r, j) => {
      ws.onopen = r;
      ws.onerror = j;
    });
    let seq = 0;
    const pending = new Map();
    const send = (method, params = {}) =>
      new Promise((resolve, reject) => {
        const id = ++seq;
        pending.set(id, { resolve, reject });
        ws.send(JSON.stringify({ id, method, params }));
      });
    ws.onmessage = e => {
      const m = JSON.parse(e.data);
      if (m.id) {
        const p = pending.get(m.id);
        pending.delete(m.id);
        m.error ? p.reject(m.error) : p.resolve(m.result);
      }
      if (m.method === 'Runtime.exceptionThrown') errors.push(m.params.exceptionDetails.text);
      if (m.method === 'Fetch.requestPaused') {
        const local = m.params.request.url.startsWith(origin + '/');
        send(
          local ? 'Fetch.continueRequest' : 'Fetch.fulfillRequest',
          local
            ? { requestId: m.params.requestId }
            : { requestId: m.params.requestId, responseCode: 200, body: '' }
        );
      }
    };
    await send('Page.enable');
    await send('Runtime.enable');
    await send('Fetch.enable', { patterns: [{ urlPattern: '*' }] });
    await send('Page.addScriptToEvaluateOnNewDocument', {
      source: `sessionStorage.setItem('farmacontrol_usuario',JSON.stringify({id:1,nome:'Teste',perfil:'atendente',permissoes:['configuracoes','dashboard','estoque']}));localStorage.setItem('farmacontrol_configuracoes',JSON.stringify({nome_farmacia:'Cache antigo',cor_destaque:'#4a7c59'}));`
    });
    const evaluate = async expression => {
      const r = await send('Runtime.evaluate', {
        expression,
        returnByValue: true,
        awaitPromise: true
      });
      if (r.exceptionDetails)
        throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
      return r.result.value;
    };
    await send('Emulation.setDeviceMetricsOverride', {
      width: 1440,
      height: 1000,
      deviceScaleFactor: 1,
      mobile: false
    });
    await send('Page.navigate', { url: origin + '/pages/sistema/vendas/vendas.html' });
    for (let i = 0; i < 100; i++) {
      await delay(50);
      if (await evaluate("document.querySelectorAll('.product-card').length===3")) break;
    }
    assert.equal(
      await evaluate("document.querySelectorAll('#resultados .product-card').length"),
      3
    );
    assert.equal(
      await evaluate(
        "document.querySelector('a[href*=dashboard]').nextElementSibling.dataset.tooltip"
      ),
      'Vendas / PDV'
    );
    await evaluate(
      "document.getElementById('busca').value='789001';document.getElementById('pesquisar').click()"
    );
    assert.equal(
      await evaluate("document.querySelectorAll('#resultados .product-card').length"),
      1
    );
    await evaluate(
      "document.getElementById('busca').value='paracetamol';document.getElementById('busca').focus()"
    );
    await send('Input.dispatchKeyEvent', {
      type: 'keyDown',
      key: 'Enter',
      code: 'Enter',
      windowsVirtualKeyCode: 13
    });
    await send('Input.dispatchKeyEvent', {
      type: 'keyUp',
      key: 'Enter',
      code: 'Enter',
      windowsVirtualKeyCode: 13
    });
    assert.equal(
      await evaluate("document.querySelectorAll('#resultados .product-card').length"),
      2
    );
    assert.equal(await evaluate("document.querySelectorAll('.cart-line').length"), 0);
    await evaluate(
      "document.querySelectorAll('[data-select]')[0].click();document.querySelectorAll('[data-select]')[1].click();document.getElementById('comparar').click()"
    );
    assert(await evaluate("document.getElementById('comparacao').open"));
    await evaluate(
      "document.getElementById('comparacao').close();document.querySelector('[data-add=\"1\"]').click()"
    );
    for (const width of [1440, 390]) {
      await evaluate('document.activeElement?.blur()');
      await send('Emulation.setDeviceMetricsOverride', {
        width,
        height: 1000,
        deviceScaleFactor: 1,
        mobile: width < 500
      });
      await send('Emulation.setPageScaleFactor', { pageScaleFactor: 1 });
      await delay(500);
      fs.writeFileSync(
        path.join(artifacts, 'layout-' + width + '.json'),
        JSON.stringify(
          await evaluate(
            "[...document.querySelectorAll('.main,.page-body,.page-main,.pdv-layout,.catalogo,.product-grid,.product-card,.cart')].map(e=>({class:e.className,width:e.getBoundingClientRect().width,right:e.getBoundingClientRect().right,scroll:e.scrollWidth}))"
          ),
          null,
          2
        )
      );
      assert(await evaluate('document.documentElement.scrollWidth<=innerWidth'));
      const shot = await send('Page.captureScreenshot', { format: 'png' });
      fs.writeFileSync(
        path.join(artifacts, 'pdv-' + width + '.png'),
        Buffer.from(shot.data, 'base64')
      );
    }
    await evaluate(
      "document.getElementById('revisar').click();document.getElementById('concluir').click()"
    );
    for (let i = 0; i < 100; i++) {
      await delay(50);
      if (await evaluate("document.getElementById('status').textContent.includes('concluída')"))
        break;
    }
    assert.equal(sales, 1);
    assert.match(
      await evaluate("document.getElementById('status').textContent"),
      /Venda #10 concluída/
    );
    assert.deepEqual(errors, []);
    fs.writeFileSync(
      path.join(artifacts, 'result.json'),
      JSON.stringify(
        {
          ok: true,
          checkedAt: new Date().toISOString(),
          searchButton: true,
          enterSearch: true,
          sales,
          errors,
          widths: [1440, 390]
        },
        null,
        2
      )
    );
    console.log(
      'OK: acesso atendente, menu, busca por código/princípio, comparação, carrinho, conclusão e responsividade 1440/390.'
    );
  } finally {
    if (ws) ws.close();
    chrome.kill();
    server.close();
  }
})().catch(e => {
  console.error(e);
  process.exitCode = 1;
});
