/* Comparação visual da refatoração CSS: baseline antes de editar, verify depois.
 * Chrome isolado; APIs/fontes simuladas. Sem acesso ao banco.
 * node scripts/check_theme.cjs baseline | verify
 */
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const root = path.resolve(__dirname, '..');
const phase = process.argv[2] || 'verify';
if (!['baseline', 'verify'].includes(phase)) throw new Error('Use baseline ou verify');
const backup = path.join(root, '.audit-backup', 'theme-cleanup');
fs.mkdirSync(backup, { recursive: true });
const pages = [
  'dashboard',
  'estoque',
  'compras',
  'usuarios',
  'vencimentos',
  'financeiro',
  'relatorios',
  'configuracoes'
];
const chromePath =
  process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const server = http.createServer((req, res) => {
  const pathname = decodeURIComponent(new URL(req.url, 'http://local').pathname);
  const filename = path.resolve(root, 'frontend/src', '.' + pathname);
  const base = path.join(root, 'frontend/src') + path.sep;
  if (!filename.startsWith(base) || !fs.existsSync(filename) || !fs.statSync(filename).isFile()) {
    res.writeHead(404);
    res.end();
    return;
  }
  const content = fs.readFileSync(filename);
  const mime = {
    '.html': 'text/html; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.png': 'image/png',
    '.ico': 'image/x-icon'
  }[path.extname(filename)];
  res.writeHead(200, {
    'Content-Type': mime || 'application/octet-stream',
    'Cache-Control': 'no-store'
  });
  // Inverter a conclusão das folhas verifica se a cascata depende da rede.
  if (req.url.includes('slow=1')) setTimeout(() => res.end(content), 800);
  else if (filename.endsWith('.css')) setTimeout(() => res.end(content), 40);
  else res.end(content);
});
function bootstrap() {
  sessionStorage.setItem(
    'farmacontrol_usuario',
    JSON.stringify({
      id: 42,
      nome: 'Teste',
      sobrenome: 'Local',
      perfil: 'proprietario',
      perfil_nome: 'Proprietário'
    })
  );
  sessionStorage.setItem('farmacontrol_csrf', 'teste-csrf');
  localStorage.setItem(
    'farmacontrol_configuracoes',
    JSON.stringify({ tema: 'claro', cor_destaque: '#4a7c59', animacoes_interface: 'false' })
  );
  localStorage.removeItem('fc_sb');
  window.__testFetches = [];
  const nativeFetch = window.fetch.bind(window);
  window.fetch = async function (input, init) {
    const url = new URL(typeof input === 'string' ? input : input.url, location.href);
    if (
      /^\/(dashboard\/|estoque(?:\/|$)|produtos|compras|fornecedores|categorias-produto|movimentacoes-estoque|financeiro\/|relatorios\/|admin\/|configuracoes|alertas|auth\/)/.test(
        url.pathname
      )
    ) {
      window.__testFetches.push({
        path: url.pathname,
        method: init?.method || 'GET',
        body: init?.body
      });
      if (window.__testApiDelay) {
        await new Promise((resolve, reject) => {
          const signal = init?.signal;
          const abort = () => {
            clearTimeout(timer);
            sessionStorage.setItem('test-aborted', 'true');
            reject(new DOMException('Leitura cancelada', 'AbortError'));
          };
          const timer = setTimeout(() => {
            signal?.removeEventListener('abort', abort);
            resolve();
          }, window.__testApiDelay);
          if (signal?.aborted) abort();
          else signal?.addEventListener('abort', abort, { once: true });
        });
      }
      const data = {
        ok: true,
        kpis: {},
        estoque: [],
        produtos: [],
        compras: [],
        fornecedores: [],
        categorias: [],
        movimentacoes: [],
        historico: [],
        usuarios: [],
        pendentes: [],
        logs: [],
        perfis: [],
        modulos: [],
        configuracoes: [],
        por_categoria: [],
        top_produtos: [],
        produtos_criticos: [],
        movimentacoes_semana: [],
        evolucao: [],
        transacoes: [],
        labels: [],
        receitas: [],
        despesas: [],
        spark: []
      };
      if (url.pathname === '/financeiro/stats')
        Object.assign(data, { receitas: 0, despesas: 0, saldo: 0, ticket_medio: 0 });
      if (url.pathname === '/financeiro/categorias')
        data.categorias = [{ id: 1, nome: 'Teste', tipo: 'receita', valor: 0, qtd: 0 }];
      return new Response(JSON.stringify(data), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    return nativeFetch(input, init);
  };
}
function fingerprint() {
  const selectors = [
    'html',
    'body',
    '.app',
    '.sidebar',
    '.sb-head',
    '.sb-brand',
    '.sb-logo',
    '.sb-collapse',
    '.sb-nav',
    '.sb-group-label',
    '.sb-item',
    '.sb-icon',
    '.sb-badge',
    '.sb-footer',
    '.sb-user-card',
    '.sb-avatar',
    '.sb-user-info',
    '.sb-user-name',
    '.sb-logout',
    '.sb-overlay',
    '.main',
    '.topbar',
    '.page-main',
    '.page-panel',
    '.page-title',
    '.card',
    '.card-head',
    '.card-body',
    '.kpi-grid',
    '.kpi-card',
    '.ghost-btn',
    '.tb-btn',
    'table th',
    'table td',
    '.form-input',
    '.form-select',
    'input',
    'select',
    '.modal-overlay',
    '.modal',
    '.modal-title',
    '.modal-foot',
    '.search-field',
    '.transaction-search',
    '#fc-toast'
  ];
  const properties = [
    'display',
    'position',
    'color',
    'backgroundColor',
    'borderColor',
    'borderWidth',
    'borderStyle',
    'fontFamily',
    'fontSize',
    'fontWeight',
    'lineHeight',
    'width',
    'height',
    'minWidth',
    'maxWidth',
    'padding',
    'margin',
    'borderRadius',
    'overflow',
    'gap',
    'gridTemplateColumns',
    'flexDirection',
    'alignItems',
    'boxShadow',
    'visibility',
    'opacity',
    'pointerEvents',
    'transform'
  ];
  return Object.fromEntries(
    selectors.map(selector => [
      selector,
      [...document.querySelectorAll(selector)].slice(0, 3).map(element => {
        const style = getComputedStyle(element);
        return Object.fromEntries(properties.map(key => [key, style[key]]));
      })
    ])
  );
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = 'http://127.0.0.1:' + server.address().port;
  const profile = fs.mkdtempSync(path.join(backup, 'chrome-'));
  const chrome = spawn(
    chromePath,
    [
      '--headless=new',
      '--disable-gpu',
      '--no-first-run',
      '--no-default-browser-check',
      '--disable-background-networking',
      '--disable-component-update',
      '--remote-debugging-port=0',
      '--user-data-dir=' + profile,
      'about:blank'
    ],
    { windowsHide: true, stdio: ['ignore', 'ignore', 'pipe'] }
  );
  let ws;
  const report = { phase, samples: [], errors: [], differences: [] };
  let startupError;
  chrome.on('error', error => {
    startupError = error;
  });
  try {
    let endpoint = '';
    chrome.stderr.on('data', chunk => {
      const match = String(chunk).match(/DevTools listening on (ws:\/\/[^\s]+)/);
      if (match) endpoint = match[1];
    });
    for (let i = 0; i < 100 && !endpoint && !startupError; i++) await delay(100);
    if (startupError) throw startupError;
    assert(endpoint, 'Chrome DevTools indisponível');
    const debugOrigin = endpoint.replace('ws://', 'http://').split('/devtools/')[0];
    const targets = await (await fetch(debugOrigin + '/json/list')).json();
    ws = new WebSocket(targets.find(t => t.type === 'page').webSocketDebuggerUrl);
    await new Promise((resolve, reject) => {
      ws.onopen = resolve;
      ws.onerror = reject;
    });
    let id = 0;
    const pending = new Map();
    const send = (method, params = {}) =>
      new Promise((resolve, reject) => {
        const messageId = ++id;
        const timer = setTimeout(() => {
          pending.delete(messageId);
          reject(new Error('Timeout ' + method));
        }, 12000);
        pending.set(messageId, { resolve, reject, timer });
        ws.send(JSON.stringify({ id: messageId, method, params }));
      });
    ws.onmessage = event => {
      const msg = JSON.parse(event.data);
      if (msg.id) {
        const p = pending.get(msg.id);
        if (p) {
          clearTimeout(p.timer);
          pending.delete(msg.id);
          msg.error ? p.reject(new Error(JSON.stringify(msg.error))) : p.resolve(msg.result);
        }
        return;
      }
      if (msg.method === 'Runtime.exceptionThrown')
        report.errors.push(
          msg.params.exceptionDetails.exception?.description || msg.params.exceptionDetails.text
        );
      if (msg.method === 'Fetch.requestPaused') {
        const u = new URL(msg.params.request.url);
        if (u.origin === origin)
          send('Fetch.continueRequest', { requestId: msg.params.requestId }).catch(() => {});
        else {
          const body = u.pathname.includes('chart')
            ? 'window.Chart = class { constructor(ctx, config) { this.data=config.data; this.options=config.options; } destroy(){} update(){} };'
            : '';
          send('Fetch.fulfillRequest', {
            requestId: msg.params.requestId,
            responseCode: 200,
            responseHeaders: [
              {
                name: 'Content-Type',
                value: u.pathname.endsWith('.js') ? 'text/javascript' : 'text/css'
              }
            ],
            body: Buffer.from(body).toString('base64')
          }).catch(() => {});
        }
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
    const baseline =
      phase === 'verify'
        ? JSON.parse(fs.readFileSync(path.join(backup, 'theme-baseline.json'), 'utf8'))
        : null;
    const sample = async (name, width, color, density, state = 'normal') => {
      await evaluate(
        'FarmaControlSettings.apply(' +
          JSON.stringify({
            cor_destaque: color,
            densidade_interface: density,
            animacoes_interface: 'false'
          }) +
          ')'
      );
      await delay(60);
      const key = [name, width, color, density, state].join(':');
      const styles = await evaluate('(' + fingerprint.toString() + ')()');
      report.samples.push({ key, styles });
      if (baseline) {
        const before = baseline.samples.find(x => x.key === key);
        assert(before, 'Cenário ausente na referência: ' + key);
        for (const [selector, value] of Object.entries(styles)) {
          if (JSON.stringify(value) !== JSON.stringify(before.styles[selector])) {
            report.differences.push({
              key,
              selector,
              before: before.styles[selector],
              after: value
            });
          }
        }
      }
    };
    for (const width of [1440, 860, 390]) {
      await send('Emulation.setDeviceMetricsOverride', {
        width,
        height: 900,
        deviceScaleFactor: 1,
        mobile: width < 500
      });
      // O sistema operacional solicitar escuro não deve alterar a aplicação.
      await send('Emulation.setEmulatedMedia', {
        features: [{ name: 'prefers-color-scheme', value: 'dark' }]
      });
      for (const name of pages) {
        await send('Page.navigate', {
          url: origin + '/pages/sistema/' + name + '/' + name + '.html'
        });
        let ready = false;
        for (let i = 0; i < 100; i++) {
          await delay(50);
          if (await evaluate("document.readyState==='complete' && !!window.FarmaControlSettings")) {
            ready = true;
            break;
          }
        }
        assert(ready, 'Página não carregou: ' + name);
        await delay(350);
        await sample(name, width, '#4a7c59', 'normal');
        await evaluate(
          "document.querySelector('.sidebar').classList.add(" +
            JSON.stringify(width > 860 ? 'collapsed' : 'mobile-open') +
            ");document.querySelector('.sb-overlay')?.classList.add('visible')"
        );
        await sample(name, width, '#4a7c59', 'normal', 'sidebar');
        await evaluate(
          "document.querySelector('.sidebar').classList.remove('collapsed','mobile-open');document.querySelector('.sb-overlay')?.classList.remove('visible')"
        );
        await evaluate(
          "document.querySelector('.modal-overlay')?.classList.add('open');FarmaControlSettings.showToast('Mensagem de teste')"
        );
        await sample(name, width, '#4a7c59', 'normal', 'modal-toast');
        await evaluate(
          "document.querySelector('.modal-overlay')?.classList.remove('open');document.getElementById('fc-toast')?.remove()"
        );
        if (name === 'configuracoes') {
          for (const color of [
            '#4a7c59',
            '#2e6da4',
            '#b87a1a',
            '#c03a3a',
            '#6b4fbb',
            '#1a7a6e',
            '#7654ab'
          ]) {
            for (const density of ['normal', 'compacta', 'espacada'])
              await sample(name, width, color, density);
          }
        }
        if (name === 'estoque' && width !== 860) {
          await evaluate(
            "FarmaControlSettings.apply({cor_destaque:'#4a7c59',densidade_interface:'normal',animacoes_interface:'false'})"
          );
          const screenshot = await send('Page.captureScreenshot', { format: 'png' });
          fs.writeFileSync(
            path.join(backup, 'estoque-' + width + '-' + phase + '.png'),
            Buffer.from(screenshot.data, 'base64')
          );
        }
      }
    }
    assert.deepEqual(report.errors, [], 'Exceções no navegador');
    assert.equal(
      report.differences.length,
      0,
      'Estilos divergiram: confira theme-' + phase + '.json'
    );
    report.passed = true;
    console.log(
      JSON.stringify(
        {
          phase,
          samples: report.samples.length,
          differences: report.differences.length,
          errors: report.errors
        },
        null,
        2
      )
    );
  } catch (error) {
    report.failure = error.stack;
    throw error;
  } finally {
    fs.writeFileSync(
      path.join(backup, 'theme-' + phase + '.json'),
      JSON.stringify(report, null, 2)
    );
    if (ws && ws.readyState === WebSocket.OPEN) ws.close();
    chrome.kill();
    server.close();
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
