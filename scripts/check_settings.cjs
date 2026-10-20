/* Integração da tela em Chrome isolado, com API simulada e sem banco real. */
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const root = path.resolve(__dirname, '..');
const artifacts = path.join(root, '.audit-backup/settings');
fs.mkdirSync(artifacts, { recursive: true });
const delay = ms => new Promise(r => setTimeout(r, ms));
let values = {},
  failSave = false,
  failLoad = false,
  saves = 0;
const server = http.createServer((req, res) => {
  const pathname = new URL(req.url, 'http://local').pathname;
  res.setHeader('Content-Type', 'application/json');
  if (pathname === '/configuracoes') {
    if (req.method === 'PUT') {
      let body = '';
      req.on('data', c => (body += c));
      req.on('end', () => {
        saves++;
        if (failSave) {
          res.writeHead(500);
          res.end(JSON.stringify({ ok: false, mensagem: 'Falha simulada ao salvar' }));
          return;
        }
        values = JSON.parse(body).configuracoes;
        res.end(JSON.stringify({ ok: true, valores: values }));
      });
      return;
    }
    if (failLoad) {
      res.writeHead(500);
      res.end('{"ok":false}');
      return;
    }
    res.end(
      JSON.stringify({
        ok: true,
        configuracoes: Object.entries(values).map(([chave, valor]) => ({ chave, valor }))
      })
    );
    return;
  }
  if (pathname === '/auth/me') {
    res.end(
      JSON.stringify({
        ok: true,
        usuario: {
          id: 1,
          nome: 'Teste',
          perfil: 'proprietario',
          permissoes: ['configuracoes', 'dashboard', 'estoque']
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
      source: `sessionStorage.setItem('farmacontrol_usuario',JSON.stringify({id:1,nome:'Teste',perfil:'proprietario',permissoes:['configuracoes','dashboard','estoque']}));localStorage.setItem('farmacontrol_configuracoes',JSON.stringify({nome_farmacia:'Cache antigo',cor_destaque:'#4a7c59'}));`
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
    await send('Page.navigate', {
      url: origin + '/pages/sistema/configuracoes/configuracoes.html'
    });
    for (let i = 0; i < 100; i++) {
      await delay(50);
      if (await evaluate('window.configLoaded === true')) break;
    }
    assert(await evaluate('configLoaded'));
    assert.equal(
      await evaluate("document.querySelector('[data-config-key=nome_farmacia]').value"),
      ''
    );
    await evaluate(
      `document.querySelector('[data-config-key=nome_farmacia]').value='Farmácia Teste'; document.querySelector('[data-config-key=alerta_vencimento]').checked=false;document.querySelector('[data-config-key=estoque_minimo_padrao]').value='15';markDirtyState();saveConfiguracoes()`
    );
    assert.equal(saves, 1);
    assert.equal(values.nome_farmacia, 'Farmácia Teste');
    assert.equal(values.alerta_vencimento, 'false');
    assert(await evaluate("document.querySelector('[data-config-key=nome_farmacia]').disabled"));
    await evaluate('loadConfiguracoes()');
    assert.equal(
      await evaluate("document.querySelector('[data-config-key=nome_farmacia]').value"),
      'Farmácia Teste'
    );
    await evaluate(
      `document.getElementById('btn-edit-pharmacy').click();document.querySelector('[data-config-key=nome_farmacia]').value='Alterada';document.getElementById('btn-cancel-pharmacy').click()`
    );
    assert.equal(
      await evaluate("document.querySelector('[data-config-key=nome_farmacia]').value"),
      'Farmácia Teste'
    );
    failSave = true;
    await evaluate(
      `document.getElementById('btn-edit-pharmacy').click();document.querySelector('[data-config-key=nome_farmacia]').value='Alterada';markDirtyState();saveConfiguracoes()`
    );
    assert.equal(values.nome_farmacia, 'Farmácia Teste');
    assert.equal(await evaluate("document.getElementById('btn-save-all').style.display"), '');
    assert.equal(
      await evaluate("document.querySelector('[data-config-key=nome_farmacia]').value"),
      'Alterada'
    );
    assert.match(
      await evaluate("document.getElementById('fc-toast').textContent"),
      /Falha simulada/
    );
    failSave = false;
    await evaluate('saveConfiguracoes()');
    assert.equal(values.nome_farmacia, 'Alterada');
    failLoad = true;
    await evaluate('loadConfiguracoes()');
    assert(await evaluate("document.getElementById('btn-save-all').disabled"));
    failLoad = false;
    await evaluate('loadConfiguracoes()');
    await send('Emulation.setDeviceMetricsOverride', {
      width: 1440,
      height: 1000,
      deviceScaleFactor: 1,
      mobile: false
    });
    const shot = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(path.join(artifacts, 'configuracoes.png'), Buffer.from(shot.data, 'base64'));
    assert.deepEqual(errors, []);
    console.log(
      'OK: salvar três seções, persistir, editar, cancelar, ignorar cache antigo, manter rascunho após erro, recuperar falha de carga.'
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
