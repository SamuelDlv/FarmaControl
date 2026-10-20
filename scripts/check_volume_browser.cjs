/* Renderiza os snapshots de check_volume_data.py em Chrome isolado.
 * Nenhuma gravação chega ao banco. Inclui nomes longos e todos os 11 mil movimentos. */
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const root = path.resolve(__dirname, '..');
const output = path.join(root, '.audit-backup/volume');
const fixtures = JSON.parse(fs.readFileSync(path.join(output, 'api.json'), 'utf8'));
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const empty = {
  ok: true,
  configuracoes: [],
  alertas: [],
  categorias: [],
  transacoes: [],
  usuarios: [],
  historico: []
};
let scenario = 'normal';
const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');
  let data = fixtures[url.pathname + url.search] || fixtures[url.pathname];
  if (url.pathname === '/movimentacoes-estoque') {
    let rows = fixtures[url.pathname].movimentacoes;
    const period = url.searchParams.get('periodo');
    if (period) {
      const dates = fixtures['/relatorios/estoque?periodo=' + period].periodo;
      rows = rows.filter(
        m =>
          m.data_movimentacao.slice(0, 10) >= dates.inicio &&
          m.data_movimentacao.slice(0, 10) <= dates.fim
      );
    }
    const type = url.searchParams.get('tipo');
    const search = url.searchParams.get('busca');
    if (type) rows = rows.filter(m => m.tipo_movimentacao === type);
    if (search)
      rows = rows.filter(m => m.produto_nome.toLowerCase().includes(search.toLowerCase()));
    const offset = Number(url.searchParams.get('offset') || 0);
    data = {
      ok: true,
      total: rows.length,
      movimentacoes: rows.slice(offset, offset + Number(url.searchParams.get('limite') || 1000))
    };
  }
  if (!data && url.pathname.startsWith('/financeiro/')) {
    const days = url.searchParams.get('days') || '30';
    data =
      fixtures[
        url.pathname +
          (url.pathname.endsWith('categorias') ? '?tipo=despesa&days=' : '?days=') +
          days
      ] || empty;
  }
  if (data || !path.extname(url.pathname)) {
    if (scenario === 'error' && url.pathname === '/relatorios/estoque') {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ok: false, mensagem: 'Erro simulado' }));
      return;
    }
    if (scenario === 'empty' && data) {
      data = Object.fromEntries(
        Object.entries(data).map(([key, value]) => [
          key,
          Array.isArray(value) ? [] : typeof value === 'number' ? 0 : value
        ])
      );
      if (data.kpis) data.kpis = {};
      if (data.resumo) data.resumo = {};
    }
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(data || empty));
    return;
  }
  const filename = path.resolve(root, 'frontend/src', '.' + url.pathname);
  if (
    !filename.startsWith(path.join(root, 'frontend/src') + path.sep) ||
    !fs.existsSync(filename)
  ) {
    res.writeHead(404);
    res.end();
    return;
  }
  res.writeHead(200, {
    'Content-Type':
      {
        '.html': 'text/html; charset=utf-8',
        '.js': 'text/javascript; charset=utf-8',
        '.css': 'text/css; charset=utf-8'
      }[path.extname(filename)] || 'application/octet-stream'
  });
  res.end(fs.readFileSync(filename));
});
function bootstrap() {
  sessionStorage.setItem(
    'farmacontrol_usuario',
    JSON.stringify({ id: 42, nome: 'Teste', perfil: 'proprietario' })
  );
  sessionStorage.setItem('farmacontrol_csrf', 'isolado');
  localStorage.setItem(
    'farmacontrol_configuracoes',
    JSON.stringify({ animacoes_interface: 'false' })
  );
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = 'http://127.0.0.1:' + server.address().port;
  const profile = fs.mkdtempSync(path.join(output, 'chrome-'));
  const chrome = spawn(
    process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    [
      '--headless=new',
      '--disable-gpu',
      '--no-first-run',
      '--no-default-browser-check',
      '--disable-background-networking',
      '--remote-debugging-port=0',
      '--user-data-dir=' + profile,
      'about:blank'
    ],
    { windowsHide: true, stdio: ['ignore', 'ignore', 'pipe'] }
  );
  let ws,
    endpoint = '',
    startupError;
  const report = { pages: [], errors: [] };
  chrome.on('error', e => (startupError = e));
  chrome.stderr.on('data', chunk => {
    const m = String(chunk).match(/DevTools listening on (ws:\/\/[^\s]+)/);
    if (m) endpoint = m[1];
  });
  try {
    for (let i = 0; i < 100 && !endpoint && !startupError; i++) await delay(100);
    if (startupError) throw startupError;
    assert(endpoint, 'Chrome indisponível');
    const targets = await (
      await fetch(endpoint.replace('ws://', 'http://').split('/devtools/')[0] + '/json/list')
    ).json();
    ws = new WebSocket(targets.find(t => t.type === 'page').webSocketDebuggerUrl);
    await new Promise((resolve, reject) => {
      ws.onopen = resolve;
      ws.onerror = reject;
    });
    let id = 0;
    const pending = new Map();
    const send = (method, params = {}) =>
      new Promise((resolve, reject) => {
        const key = ++id;
        const timer = setTimeout(() => {
          pending.delete(key);
          reject(new Error('Timeout ' + method));
        }, 15000);
        pending.set(key, { resolve, reject, timer });
        ws.send(JSON.stringify({ id: key, method, params }));
      });
    ws.onmessage = event => {
      const m = JSON.parse(event.data);
      if (m.id) {
        const p = pending.get(m.id);
        if (p) {
          clearTimeout(p.timer);
          pending.delete(m.id);
          m.error ? p.reject(new Error(JSON.stringify(m.error))) : p.resolve(m.result);
        }
        return;
      }
      if (m.method === 'Runtime.exceptionThrown')
        report.errors.push(
          m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text
        );
      if (m.method === 'Fetch.requestPaused') {
        const u = new URL(m.params.request.url);
        const action = u.origin === origin ? 'Fetch.continueRequest' : 'Fetch.fulfillRequest';
        send(action, {
          requestId: m.params.requestId,
          ...(u.origin === origin ? {} : { responseCode: 200, body: '' })
        }).catch(() => {});
      }
    };
    await send('Page.enable');
    await send('Runtime.enable');
    await send('Fetch.enable', { patterns: [{ urlPattern: '*' }] });
    await send('Page.addScriptToEvaluateOnNewDocument', {
      source: '(' + bootstrap.toString() + ')()'
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
    const navigate = async page => {
      await send('Page.navigate', {
        url: origin + '/pages/sistema/' + page + '/' + page + '.html'
      });
      await delay(1200);
      if (page === 'dashboard') {
        for (let i = 0; i < 80; i++) {
          if (
            await evaluate(
              "getComputedStyle(document.getElementById('fc-dashboard-boot')).opacity === '0' || getComputedStyle(document.getElementById('fc-dashboard-boot')).display === 'none'"
            )
          )
            break;
          await delay(100);
        }
      }
      assert(
        await evaluate("document.readyState==='complete' && !!window.FarmaControlSettings"),
        page + ': não carregou'
      );
    };
    const screenshot = async name => {
      const shot = await send('Page.captureScreenshot', {
        format: 'png',
        captureBeyondViewport: false
      });
      fs.writeFileSync(path.join(output, name + '.png'), Buffer.from(shot.data, 'base64'));
    };
    for (const width of [1440, 1024, 390]) {
      await send('Emulation.setDeviceMetricsOverride', {
        width,
        height: 1000,
        deviceScaleFactor: 1,
        mobile: width < 500
      });
      for (const page of [
        'dashboard',
        'estoque',
        'vencimentos',
        'relatorios',
        'financeiro',
        'compras'
      ]) {
        await navigate(page);
        const overflow = await evaluate('document.documentElement.scrollWidth > innerWidth+1');
        assert(!overflow, `${page} ${width}: overflow da página`);
        if (page === 'dashboard') {
          assert.equal(
            await evaluate("document.querySelectorAll('#bars-group .bar-col').length"),
            7
          );
          assert(await evaluate("document.querySelectorAll('#exp-list .exp-item').length > 0"));
          assert(
            await evaluate(
              "[...document.querySelectorAll('.bar-fill')].every(b=>b.getBoundingClientRect().bottom<=b.closest('.chart-area').getBoundingClientRect().bottom)"
            )
          );
          await evaluate(
            "document.querySelector('#rank-list').closest('.card, .panel-section').querySelector('.card-link, .panel-link').click()"
          );
          await screenshot(`dashboard-modal-${width}`);
          await evaluate("document.querySelector('.fc-view-overlay .modal-close').click()");
          await evaluate(
            "document.querySelector('#palerts').closest('.panel-section').querySelector('.panel-link').click()"
          );
          assert.equal(
            await evaluate("document.querySelectorAll('.fc-view-overlay .palert').length"),
            fixtures['/dashboard/stats'].produtos_criticos.length
          );
          await screenshot(`alertas-modal-${width}`);
          await evaluate("document.querySelector('.fc-view-overlay .modal-close').click()");
        }
        if (page === 'vencimentos') {
          assert(await evaluate("Number(document.getElementById('kpi-vencidos').textContent)>0"));
          assert(await evaluate("document.querySelectorAll('#timeline-wrap .tl-row').length>100"));
          assert.equal(await evaluate("diasRestantes(new Date().toLocaleDateString('en-CA'))"), 0);
          assert.equal(
            await evaluate(
              "(() => {const old=today;today=()=>new Date(2026,9,10,23,59);const value=diasRestantes('2026-10-10');today=old;return value;})()"
            ),
            0
          );
        }
        if (page === 'relatorios') {
          assert.equal(
            await evaluate("Number(document.querySelector('.kpi-value').dataset.target)"),
            fixtures['/relatorios/estoque?periodo=month'].kpis.total_saidas
          );
          assert(await evaluate("document.querySelectorAll('#category-chart .cat-row').length>0"));
          assert(
            await evaluate(
              "document.querySelector('#category-chart .cat-bar').getBoundingClientRect().width>0"
            )
          );
          assert.equal(
            await evaluate(
              "getComputedStyle(document.getElementById('table-search')).borderTopWidth"
            ),
            '0px'
          );
          await evaluate("document.querySelector('[data-period=year]').click()");
          await delay(1100);
          assert.equal(await evaluate('movTotal'), fixtures['/movimentacoes-estoque'].total);
          await evaluate("document.getElementById('pg-next').click()");
          await delay(300);
          assert.equal(await evaluate('movPage'), 2);
          const count = await evaluate(
            '(async () => (await (await fetchAllReportMovements()).json()).movimentacoes.length)()'
          );
          assert.equal(count, fixtures['/movimentacoes-estoque'].total);
          await evaluate("downloadFile('teste.csv', [[1,2]], ['A','B'])");
          assert(
            await evaluate(
              "document.getElementById('export-history').textContent.includes('teste.csv')"
            )
          );
        }
        if (page === 'financeiro')
          assert(
            await evaluate(
              "document.querySelectorAll('#cat-list .cat-item').length>0 || document.getElementById('cat-list').textContent.includes('Pendente')"
            )
          );
        if (page === 'compras') {
          assert(await evaluate("document.querySelectorAll('#rank-list .rank-item').length<=5"));
          assert(await evaluate("document.querySelectorAll('#mov-table-body tr').length<=10"));
          await evaluate("document.querySelector('[data-period=year]').click()");
          await delay(1000);
          assert.equal(await evaluate('purchasePeriod'), 'year');
          await evaluate("document.getElementById('purchase-next').click()");
          assert.equal(await evaluate('purchasePage'), 2);
          await evaluate("document.getElementById('rpt-venc').click()");
          assert.equal(
            await evaluate(
              "[...document.querySelectorAll('#mov-table-body tr')].every(r=>r.dataset.type==='pendente')"
            ),
            true
          );
          await evaluate("document.querySelector('.ftab[data-type=all]').click()");
          await evaluate("document.querySelector('.ftab[data-chart=ambos]').click()");
          assert.equal(
            await evaluate("document.querySelectorAll('#mc-bars .mc-bar').length"),
            fixtures['/relatorios/compras?periodo=year'].evolucao.length * 2
          );
          assert.equal(
            await evaluate(
              "getComputedStyle(document.getElementById('table-search')).borderTopWidth"
            ),
            '0px'
          );
        }
        await screenshot(`${page}-${width}`);
        report.pages.push({ page, width, passed: true });
      }
    }
    await navigate('dashboard');
    const target = await evaluate(
      "document.querySelector('#table-body .row-btn').getAttribute('onclick')"
    );
    assert(target.includes('?repor='));
    await evaluate("document.querySelector('#table-body .row-btn').click()");
    await delay(1200);
    assert(await evaluate("document.getElementById('move-overlay').classList.contains('open')"));
    scenario = 'empty';
    for (const page of ['dashboard', 'vencimentos', 'relatorios', 'compras']) {
      await navigate(page);
      assert(
        !(await evaluate(
          "document.body.textContent.includes('NaN') || document.body.textContent.includes('Infinity')"
        )),
        page + ': número inválido sem dados'
      );
    }
    scenario = 'error';
    await navigate('relatorios');
    assert(
      await evaluate("document.getElementById('summary-list').textContent.includes('indisponível')")
    );
    scenario = 'normal';
    await evaluate("document.getElementById('btn-refresh').click()");
    await delay(1200);
    assert(await evaluate("document.querySelectorAll('#category-chart .cat-row').length>0"));
    assert.deepEqual(report.errors, []);
    report.passed = true;
    console.log(
      JSON.stringify({ pages: report.pages.length, errors: report.errors, passed: true })
    );
  } finally {
    fs.writeFileSync(path.join(output, 'browser-report.json'), JSON.stringify(report, null, 2));
    ws?.close();
    chrome.kill();
    server.close();
  }
})().catch(e => {
  console.error(e);
  process.exitCode = 1;
});
