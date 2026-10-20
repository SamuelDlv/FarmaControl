/* Chrome isolado + servidor de arquivos local. APIs e CDNs são simuladas;
 * nunca abre o Flask nem conecta ao banco. Requer Node 22+ e Chrome.
 * Grava evidências em .audit-backup/2026-10-06/browser-<fase>.json. */
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const { spawn, spawnSync } = require('node:child_process');
const root = path.resolve(__dirname, '..');
const phase = process.argv[2] || 'after';
const backup = path.join(root, '.audit-backup', '2026-10-06');
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
let originals = {};
if (phase === 'before') {
  const result = spawnSync(
    'python',
    [
      '-B',
      '-c',
      "import zipfile,json; z=zipfile.ZipFile('.audit-backup/2026-10-06/original.zip'); print(json.dumps({n:z.read(n).decode('utf-8') for n in z.namelist() if n.endswith(('.html','.css','.js'))}))"
    ],
    { cwd: root, encoding: 'utf8', windowsHide: true, maxBuffer: 10 * 1024 * 1024 }
  );
  if (result.status !== 0) throw new Error(result.stderr);
  originals = JSON.parse(result.stdout);
}
const server = http.createServer((req, res) => {
  const pathname = decodeURIComponent(new URL(req.url, 'http://local').pathname);
  const filename = path.resolve(root, 'frontend/src', '.' + pathname);
  const base = path.join(root, 'frontend/src') + path.sep;
  if (!filename.startsWith(base) || !fs.existsSync(filename) || !fs.statSync(filename).isFile()) {
    res.writeHead(404);
    res.end();
    return;
  }
  const key = path.relative(root, filename).replaceAll('\\', '/');
  const content = originals[key] ?? fs.readFileSync(filename);
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
  if (phase === 'after' && filename.endsWith('.css') && !filename.includes('styles'))
    setTimeout(() => res.end(content), 40);
  else res.end(content);
});
function bootstrap(catalogMode = false, cashflowMode = false) {
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
      url.port === '5000' ||
      ((catalogMode || cashflowMode) &&
        /^\/(dashboard\/|estoque(?:\/|$)|produtos|compras|fornecedores|categorias-produto|movimentacoes-estoque|financeiro\/|relatorios\/|admin\/|configuracoes|alertas|auth\/)/.test(
          url.pathname
        ))
    ) {
      window.__testFetches.push({
        path: url.pathname,
        method: init?.method || 'GET',
        body: init?.body ? JSON.parse(init.body) : null
      });
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
      if (cashflowMode && url.pathname === '/financeiro/fluxo') {
        const start = url.searchParams.get('start_date');
        const end = url.searchParams.get('end_date');
        Object.assign(data, {
          periodo: { inicio: start, fim: end },
          labels: ['01/10', '02/10', '11/10', '12/10'],
          dias: [
            start,
            start.slice(0, 8) + '02',
            start.slice(0, 8) + '11',
            start.slice(0, 8) + '12'
          ],
          receitas: [9000, 6000, 0, window.__cashflowReceita ?? 527.56],
          despesas: [0, 2500, 38.86, 110]
        });
      }
      if (catalogMode) {
        data.categorias = [
          { id: 1, nome: 'Alimentos' },
          { id: 2, nome: 'Higiene pessoal' },
          { id: 3, nome: 'Acessórios' },
          { id: 4, nome: 'Primeiros socorros' }
        ];
        data.fornecedores = [{ id: 5, nome_fantasia: 'Fornecedor teste' }];
        data.produtos = [
          {
            id: 7,
            nome: 'Escova teste',
            tipo_produto: 'outro',
            exige_validade: 0,
            requer_receita: 0,
            ativo: 1,
            preco_custo: 2,
            preco_venda: 4,
            codigo_barras: '00123',
            categoria_id: 2,
            fornecedor_id: 5,
            estoque_minimo: 0
          }
        ];
        data.estoque = [
          {
            id: 71,
            produto_id: 7,
            produto_nome: 'Escova teste',
            tipo_produto: 'outro',
            exige_validade: 0,
            produto_codigo_barras: '00123',
            categoria: 'Higiene pessoal',
            categoria_id: 2,
            fornecedor_id: 5,
            fornecedor_nome: 'Fornecedor teste',
            preco_custo: 2,
            preco_venda: 4,
            estoque_minimo: 0,
            quantidade: 3,
            lote: 'SEM-LOTE',
            data_validade: null
          },
          {
            id: 72,
            produto_id: 8,
            produto_nome: 'Água teste',
            tipo_produto: 'outro',
            exige_validade: 1,
            categoria: 'Alimentos',
            categoria_id: 1,
            preco_custo: 1,
            preco_venda: 2,
            estoque_minimo: 10,
            quantidade: 5,
            lote: 'AGUA-1',
            data_validade: '2027-04-01'
          }
        ];
      }
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
    '.sb-item',
    '.main',
    '.topbar',
    '.kpi-grid',
    '.kpi-card',
    '.card',
    '.modal-overlay',
    '.modal'
  ];
  const properties = [
    'display',
    'position',
    'color',
    'backgroundColor',
    'fontFamily',
    'fontSize',
    'width',
    'padding',
    'borderRadius',
    'overflow',
    'gridTemplateColumns'
  ];
  return Object.fromEntries(
    selectors.map(selector => {
      const element = document.querySelector(selector);
      if (!element) return [selector, null];
      const style = getComputedStyle(element);
      return [selector, Object.fromEntries(properties.map(key => [key, style[key]]))];
    })
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
  const report = { phase, static: [], spa: [], errors: [], visualDifferences: [] };
  try {
    let endpoint = '';
    chrome.stderr.on('data', chunk => {
      const match = String(chunk).match(/DevTools listening on (ws:\/\/[^\s]+)/);
      if (match) endpoint = match[1];
    });
    for (let i = 0; i < 100 && !endpoint; i++) await delay(100);
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
      source:
        '(' +
        bootstrap.toString() +
        ')(' +
        JSON.stringify(phase === 'catalogo') +
        ',' +
        JSON.stringify(phase === 'cashflow') +
        ')'
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
    if (phase === 'cashflow') {
      await send('Emulation.setDeviceMetricsOverride', {
        width: 1440,
        height: 1000,
        deviceScaleFactor: 1,
        mobile: false
      });
      await send('Page.navigate', { url: origin + '/pages/sistema/relatorios/relatorios.html' });
      await delay(800);
      assert(
        await evaluate(`(() => {
        const buttons = [...document.querySelectorAll('[data-report-view]')];
        return buttons.length === 2 && buttons.every(button => {
          const style = getComputedStyle(button);
          return ['flex', 'inline-flex'].includes(style.display) && style.borderRadius === '20px' && style.paddingLeft === '14px';
        });
      })()`),
        'Botoes de relatorios devem manter o estilo'
      );
      const reportsShot = await send('Page.captureScreenshot', { format: 'png' });
      fs.writeFileSync(
        path.join(backup, 'reports-buttons.png'),
        Buffer.from(reportsShot.data, 'base64')
      );
      await send('Page.navigate', { url: origin + '/pages/sistema/vencimentos/vencimentos.html' });
      await delay(800);
      assert(
        await evaluate(
          "!document.getElementById('action-list') && !document.body.textContent.includes('Ações Sugeridas')"
        ),
        'Card de acoes sugeridas removido'
      );
      await send('Page.navigate', { url: origin + '/pages/sistema/financeiro/financeiro.html' });
      for (let i = 0; i < 100; i++) {
        await delay(50);
        if (await evaluate("document.querySelectorAll('.income-bar').length===4")) break;
      }
      await evaluate("document.querySelector('.cashflow-card').scrollIntoView({block:'center'})");
      await delay(600);
      report.geometry = await evaluate(`(() => {
        const selectors=['.cashflow-card','.cashflow-card .card-body','.cashflow-chart-scroll','#fluxo-chart','.bars-wrap','.bars-group','.bar-col','.bar-group','#x-labels'];
        const measure=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return {top:r.top,bottom:r.bottom,height:r.height,width:r.width,overflow:s.overflow,flex:s.flex,maxHeight:s.maxHeight}};
        return {containers:Object.fromEntries(selectors.map(s=>[s,measure(document.querySelector(s))])),bars:[...document.querySelectorAll('.bar')].map(e=>({...measure(e),style:e.getAttribute('style')}))};
      })()`);
      const screenshot = await send('Page.captureScreenshot', { format: 'png' });
      fs.writeFileSync(path.join(backup, 'cashflow.png'), Buffer.from(screenshot.data, 'base64'));
      const viewport = report.geometry.containers['.cashflow-chart-scroll'];
      assert(
        await evaluate(`(() => {
        const col = document.querySelector('.bar-col');
        col.classList.add('current-day');
        const transparent = getComputedStyle(col).backgroundColor === 'rgba(0, 0, 0, 0)';
        col.classList.remove('current-day');
        return transparent && !document.querySelector('.cashflow-scale-note');
      })()`),
        'Dia atual nao deve criar uma faixa no grafico'
      );
      for (const bar of report.geometry.bars.filter(b => b.height > 0)) {
        assert(
          bar.bottom <= viewport.bottom + 1 && bar.top >= viewport.top - 1,
          'Barra cortada pelo container rolável'
        );
      }
      assert(report.geometry.containers['#x-labels'].bottom <= viewport.bottom, 'Datas cortadas');
      for (const width of [1440, 1146, 390]) {
        await send('Emulation.setDeviceMetricsOverride', {
          width,
          height: 1000,
          deviceScaleFactor: 1,
          mobile: width < 700
        });
        await delay(200);
        const fits = await evaluate(`(() => {
          const area=document.querySelector('.cashflow-chart-scroll').getBoundingClientRect();
          const card=document.querySelector('.cashflow-card').getBoundingClientRect();
          const labels=document.querySelector('#x-labels').getBoundingClientRect();
          return labels.bottom<=area.bottom && area.bottom<=card.bottom && [...document.querySelectorAll('.bar:not([hidden])')].every(e=>{
            const r=e.getBoundingClientRect();return r.bottom<=area.bottom && r.top>=area.top;
          });
        })()`);
        assert(fits, 'Gráfico cortado na largura ' + width);
        const aligned =
          await evaluate(`(() => [...document.querySelectorAll('.bar-col')].every(col=>{
          const date=col.querySelector('.cashflow-day-label').getBoundingClientRect();
          const bars=[...col.querySelectorAll('.bar:not([hidden])')].map(e=>e.getBoundingClientRect());
          const area=document.querySelector('.cashflow-chart-scroll').getBoundingClientRect();
          if (!bars.length) return true;
          const center=(Math.min(...bars.map(r=>r.left))+Math.max(...bars.map(r=>r.right)))/2;
          return Math.abs(center-(date.left+date.width/2))<1 && date.bottom<=area.bottom;
        }))()`);
        assert(aligned, 'Data deve estar centralizada no grupo visível, largura ' + width);
        const ratio = await evaluate(`(() => {
          const col=document.querySelectorAll('.bar-col')[3];
          return col.querySelector('.income-bar').getBoundingClientRect().height /
                 col.querySelector('.expense-bar').getBoundingClientRect().height;
        })()`);
        assert(
          Math.abs(ratio - 527.56 / 110) < 0.05,
          'Alturas devem respeitar a proporção dos valores, largura ' + width
        );
      }
      await send('Emulation.setDeviceMetricsOverride', {
        width: 1440,
        height: 1000,
        deviceScaleFactor: 1,
        mobile: false
      });
      const before = await evaluate(
        "document.querySelectorAll('.income-bar')[3].getBoundingClientRect().height"
      );
      await evaluate(
        "window.__cashflowReceita=2500;document.getElementById('btn-refresh').click()"
      );
      await delay(800);
      const after = await evaluate(
        "document.querySelectorAll('.income-bar')[3].getBoundingClientRect().height"
      );
      assert(after > before, 'A barra deve crescer ao receber novos lançamentos no dia');
      report.passed = true;
      console.log(
        'Fluxo de caixa: barras e datas visíveis em 1440, 1146 e 390 px; crescimento diário confirmado.'
      );
      return;
    }
    if (phase === 'catalogo') {
      await send('Emulation.setDeviceMetricsOverride', {
        width: 1440,
        height: 1000,
        deviceScaleFactor: 1,
        mobile: false
      });
      await send('Page.navigate', { url: origin + '/pages/sistema/estoque/estoque.html' });
      for (let i = 0; i < 100; i++) {
        await delay(50);
        if (
          await evaluate(
            "document.readyState==='complete' && typeof produtos!=='undefined' && produtos.length===2"
          )
        )
          break;
      }
      const result = await evaluate(
        '(' +
          async function () {
            const check = (condition, message) => {
              if (!condition) throw new Error(message);
            };
            const el = id => document.getElementById(id);
            const wait = () => new Promise(resolve => setTimeout(resolve, 150));
            check(produtos.length === 2, 'Catálogo não carregado');
            check(el('filter-cat').textContent.includes('Alimentos'), 'Categoria nova ausente');
            for (const id of ['filter-cat', 'add-categoria']) {
              const names = Array.from(el(id).options, option => option.textContent);
              check(
                names.includes('Acessórios') && names.includes('Primeiros socorros'),
                'Categorias separadas ausentes'
              );
              check(
                !names.includes('Bebidas') && !names.includes('Acessórios e primeiros socorros'),
                'Categoria antiga presente'
              );
            }
            el('search-input').value = '00123';
            renderTable();
            check(el('table-body').children.length === 1, 'Busca por código de barras');
            el('search-input').value = '';
            renderTable();
            el('btn-add').click();
            await wait();
            check(el('add-exige-validade').disabled, 'Medicamento exige validade');
            el('add-tipo').value = 'outro';
            el('add-tipo').dispatchEvent(new Event('change'));
            check(
              getComputedStyle(el('add-principio-group')).display === 'none',
              'Princípio ativo deve ficar oculto'
            );
            check(
              getComputedStyle(el('add-receita-group')).display === 'none',
              'Receita deve ficar oculta'
            );
            el('add-exige-validade').checked = false;
            el('add-exige-validade').dispatchEvent(new Event('change'));
            el('add-nome').value = 'Escova nova';
            el('add-custo').value = '2';
            el('add-venda').value = '4';
            el('add-min').value = '0';
            el('add-qty').value = '3';
            el('add-categoria').value = '2';
            el('modal-save').click();
            await wait();
            const created = window.__testFetches.find(
              x => x.path === '/estoque' && x.method === 'POST'
            ).body;
            check(
              created.produto_tipo === 'outro' &&
                created.data_validade === null &&
                created.estoque_minimo === 0,
              'Payload sem validade'
            );
            check(
              created.produto_preco_venda === 4 && created.produto_categoria_id === 2,
              'Preço e categoria'
            );
            await openEditModal(71);
            check(
              el('edit-tipo').value === 'outro' && el('edit-min').value === '0',
              'Carregamento da edição'
            );
            check(
              el('edit-fornecedor').value === '5' && el('edit-categoria').value === '2',
              'Referências da edição'
            );
            el('edit-save').click();
            await wait();
            const edited = window.__testFetches.find(
              x => x.path === '/estoque/71' && x.method === 'PUT'
            ).body;
            check(
              edited.data_validade === null && edited.produto_codigo_barras === '00123',
              'Edição preserva campos'
            );
            el('btn-add').click();
            await wait();
            el('add-existente').value = '7';
            el('add-existente').dispatchEvent(new Event('change'));
            check(
              el('add-nome').disabled && el('add-exige-validade').disabled,
              'Cadastro existente deve ficar bloqueado'
            );
            el('add-qty').value = '2';
            el('add-lote').value = 'NOVO-LOTE';
            el('modal-save').click();
            await wait();
            const last = window.__testFetches
              .filter(x => x.path === '/estoque' && x.method === 'POST')
              .at(-1).body;
            check(last.produto_id === 7 && last.lote === 'NOVO-LOTE', 'Novo lote usa ID existente');
            await openEditModal(71);
            return {
              cadastro: true,
              edicao: true,
              novoLote: true,
              codigoBarras: true,
              categorias: true
            };
          }.toString() +
          ')()'
      );
      for (const width of [1440, 390]) {
        await send('Emulation.setDeviceMetricsOverride', {
          width,
          height: 900,
          deviceScaleFactor: 1,
          mobile: width < 500
        });
        await delay(150);
        const screenshot = await send('Page.captureScreenshot', { format: 'png' });
        fs.writeFileSync(
          path.join(backup, `catalogo-${width}.png`),
          Buffer.from(screenshot.data, 'base64')
        );
        assert(
          await evaluate(
            "document.querySelector('#edit-overlay .modal').getBoundingClientRect().width <= innerWidth"
          ),
          'Modal excede a largura da tela'
        );
      }
      await send('Page.navigate', { url: origin + '/pages/sistema/compras/compras.html' });
      for (let i = 0; i < 100; i++) {
        await delay(50);
        if (
          await evaluate(
            "document.readyState==='complete' && typeof openModalAgendarEntrega==='function'"
          )
        )
          break;
      }
      result.recebimento = await evaluate(
        '(' +
          async function () {
            window.__allCompras = [
              {
                id: 4,
                status: 'pendente',
                fornecedor_nome: 'Fornecedor teste',
                valor_total: 2,
                itens: [
                  {
                    id: 41,
                    produto_id: 8,
                    produto_nome: 'Água teste',
                    quantidade: 2,
                    exige_validade: 1
                  }
                ]
              }
            ];
            openModalAgendarEntrega();
            document.getElementById('agenda-4').value = '2026-10-09';
            document.getElementById('recebe-lote-41').value = 'AGUA-2';
            document.getElementById('recebe-validade-41').value = '2027-06-01';
            await salvarAgendamento(4);
            const body = window.__testFetches.find(
              x => x.path === '/compras/4' && x.method === 'PUT'
            )?.body;
            if (body?.itens_recebimento[0]?.data_validade_recebida !== '2027-06-01')
              throw new Error('Recebimento não enviou validade');
            return true;
          }.toString() +
          ')()'
      );
      await send('Page.navigate', { url: origin + '/pages/sistema/vencimentos/vencimentos.html' });
      for (let i = 0; i < 100; i++) {
        await delay(50);
        if (
          await evaluate(
            "document.readyState==='complete' && typeof lotes!=='undefined' && lotes.length===1"
          )
        )
          break;
      }
      assert(
        await evaluate(
          "lotes.length===1 && lotes[0].nome==='Água teste' && document.getElementById('filter-cat').textContent.includes('Alimentos')"
        ),
        'Vencimentos deve incluir perecíveis e excluir produtos sem data'
      );
      result.vencimentos = true;
      assert.deepEqual(report.errors, []);
      report.catalogo = result;
      report.passed = true;
      console.log(JSON.stringify({ catalogo: result, errors: report.errors }, null, 2));
      return;
    }
    for (const width of [1440, 390]) {
      await send('Emulation.setDeviceMetricsOverride', {
        width,
        height: 900,
        deviceScaleFactor: 1,
        mobile: width < 500
      });
      for (const name of pages) {
        await send('Page.navigate', {
          url: origin + '/pages/sistema/' + name + '/' + name + '.html'
        });
        for (let i = 0; i < 60; i++) {
          await delay(50);
          if (await evaluate("document.readyState==='complete' && !!window.FarmaControlSettings"))
            break;
        }
        await delay(350);
        const fp = await evaluate('(' + fingerprint.toString() + ')()');
        const modals = await evaluate(
          "[...document.querySelectorAll('.modal-overlay')].map(e=>e.id).filter(Boolean).sort()"
        );
        report.static.push({ name, width, styles: fp, modals });
        assert(fp['.main'], name + ': conteúdo ausente');
      }
    }
    if (phase === 'after') {
      const baseline = JSON.parse(
        fs.readFileSync(path.join(backup, 'browser-before.json'), 'utf8')
      );
      for (const current of report.static) {
        const previous = baseline.static.find(
          p => p.name === current.name && p.width === current.width
        );
        if (JSON.stringify(current.styles) !== JSON.stringify(previous.styles))
          report.visualDifferences.push({ name: current.name, width: current.width });
      }
      await send('Emulation.setDeviceMetricsOverride', {
        width: 1440,
        height: 900,
        deviceScaleFactor: 1,
        mobile: false
      });
      await send('Page.navigate', { url: origin + '/pages/sistema/dashboard/dashboard.html' });
      await delay(650);
      for (const name of [...pages.slice(1), 'dashboard', 'estoque', 'dashboard', 'estoque']) {
        await evaluate("window.fcNavigate('/pages/sistema/" + name + '/' + name + ".html')");
        for (let i = 0; i < 100; i++) {
          await delay(50);
          if (
            await evaluate(
              "!!document.querySelector('script[data-fc-page-src]') && document.querySelector('script[data-fc-page-src]').getAttribute('data-fc-page-src').includes('/" +
                name +
                "/')"
            )
          )
            break;
        }
        await delay(250);
        const result = await evaluate(
          "({main:!!document.querySelector('.main'), modals:[...document.querySelectorAll('.modal-overlay')].map(e=>e.id).filter(Boolean).sort(), pageStyles:[...document.querySelectorAll('style[data-fc-page]')].map(e=>e.getAttribute('data-fc-page')), legacyLinks:[...document.querySelectorAll('link[rel=stylesheet]')].filter(e=>/pages\\/sistema/.test(e.href)).length})"
        );
        const expected = report.static.find(p => p.name === name && p.width === 1440);
        assert(result.main, name + ': main SPA ausente');
        const spaStyles = await evaluate('(' + fingerprint.toString() + ')()');
        assert.deepEqual(
          spaStyles,
          expected.styles,
          name + ': aparência SPA diferente do carregamento direto'
        );
        assert.equal(
          await evaluate("!!document.getElementById('fc-dashboard-boot')"),
          false,
          'Indicador de boot permaneceu após navegação'
        );
        assert.deepEqual(result.modals, expected.modals, name + ': modais perdidos na SPA');
        assert.equal(result.legacyLinks, 0, 'CSS da página inicial permaneceu');
        assert(
          result.pageStyles.every(href => href.includes('/' + name + '/')),
          'CSS de outra página permaneceu'
        );
        const once = await evaluate(
          "(function(){const sb=document.querySelector('.sidebar'); const b=document.getElementById('btn-collapse'); const before=sb.classList.contains('collapsed'); b.click(); const changed=before!==sb.classList.contains('collapsed'); b.click(); return changed;})()"
        );
        assert(once, 'Botão recolher alternou mais de uma vez');
        report.spa.push({ name, modals: result.modals, collapseOnce: once });
      }
      // Um modal interno recém-inserido deve sobreviver ao swap.
      await evaluate(
        "document.querySelector('.main').insertAdjacentHTML('beforeend','<div class=\"modal-overlay\" id=\"old-probe\"></div>')"
      );
      // Listeners pertencentes à tela deixam de responder após fc-page-unload.
      const cleanup = await evaluate(
        "(function(){let count=0; window.fcPageListen(document,'fc-test-event',()=>count++); document.dispatchEvent(new Event('fc-test-event')); window.dispatchEvent(new Event('fc-page-unload')); document.dispatchEvent(new Event('fc-test-event')); return count;})()"
      );
      assert.equal(cleanup, 1, 'Listener de tela não foi descartado');
      await send('Emulation.setDeviceMetricsOverride', {
        width: 390,
        height: 844,
        deviceScaleFactor: 1,
        mobile: true
      });
      const mobile = await evaluate(
        "(function(){document.getElementById('btn-mobile-menu').click(); const opened=document.querySelector('.sidebar').classList.contains('mobile-open'); document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true})); return opened&&!document.querySelector('.sidebar').classList.contains('mobile-open');})()"
      );
      assert(mobile, 'Menu móvel/Escape');
      report.mobileMenu = true;
      const screenshot = await send('Page.captureScreenshot', { format: 'png' });
      fs.writeFileSync(
        path.join(backup, 'estoque-mobile-after.png'),
        Buffer.from(screenshot.data, 'base64')
      );
      // Comparação das características visuais verificadas em carregamento direto.
      assert.equal(report.visualDifferences.length, 0, 'Estilos computados divergiram do original');
      const newErrors = report.errors.filter(error => !baseline.errors.includes(error));
      report.newErrors = newErrors;
      assert.equal(newErrors.length, 0, 'Novas exceções no navegador');
    }
    report.passed = true;
    console.log(
      JSON.stringify(
        {
          phase,
          staticPages: report.static.length,
          spaNavigations: report.spa.length,
          errors: report.errors,
          visualDifferences: report.visualDifferences
        },
        null,
        2
      )
    );
  } finally {
    fs.writeFileSync(
      path.join(backup, 'browser-' + phase + '.json'),
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
