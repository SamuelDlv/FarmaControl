/* Regressão de navegação nativa com Chrome isolado, APIs/CDNs simuladas.
 * Não inicia Flask nem acessa o banco. Evidências em .audit-backup/navigation.
 * Requer Node 22+ e Chrome. */
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const root = path.resolve(__dirname, '..');
const phase = process.argv.includes('--profiles') ? 'profiles' : 'navigation';
const backup = path.join(root, '.audit-backup', 'navigation');
fs.mkdirSync(backup, { recursive: true });
const pages = [
  'dashboard',
  'estoque',
  'compras',
  'usuarios',
  'vencimentos',
  'financeiro',
  'relatorios',
  'log',
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
    sessionStorage.getItem('test-user') ||
      JSON.stringify({
        id: 42,
        nome: 'Teste',
        sobrenome: 'Local',
        perfil: 'proprietario',
        perfil_nome: 'Proprietário'
      })
  );
  sessionStorage.setItem(
    'farmacontrol_csrf',
    sessionStorage.getItem('test-session-csrf') || 'teste-csrf'
  );
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
        search: url.search,
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
      if (url.pathname === '/admin/logs')
        Object.assign(data, {
          proximo: null,
          usuarios: [
            { id: 42, nome: 'Teste Local' },
            { id: 43, nome: 'Usuário sem atividades' }
          ],
          logs: [
            {
              id: 3,
              usuario_id: 42,
              usuario_nome: 'Teste Local',
              perfil: 'proprietario',
              acao: 'Adicionou movimentação de estoque',
              detalhes: 'POST /movimentacoes-estoque · estoque_id=15, quantidade=10, tipo=entrada',
              criado_em: '2026-10-09T18:00:00+00:00'
            },
            {
              id: 2,
              usuario_id: 42,
              usuario_nome: 'Teste Local',
              perfil: 'proprietario',
              acao: 'Entrou no sistema',
              detalhes: 'POST /auth/login',
              criado_em: '2026-10-09T17:59:00+00:00'
            }
          ]
        });
      if (url.pathname === '/admin/logs') {
        data.filtros = Object.fromEntries(
          ['usuario_id', 'data_inicio', 'data_fim'].map(key => [
            key,
            url.searchParams.get(key) || ''
          ])
        );
        data.logs = data.logs.filter(entry => {
          const day = entry.criado_em.slice(0, 10);
          return (
            (!data.filtros.usuario_id || String(entry.usuario_id) === data.filtros.usuario_id) &&
            (!data.filtros.data_inicio || day >= data.filtros.data_inicio) &&
            (!data.filtros.data_fim || day <= data.filtros.data_fim)
          );
        });
        if (window.__testOldLogServer) delete data.filtros;
      }
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
  const report = { phase, static: [], navigation: [], errors: [] };
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
    if (phase === 'profiles') {
      const defaults = {
        proprietario: pages,
        admin: pages,
        ti: pages,
        farmaceutico: ['dashboard', 'estoque', 'vencimentos', 'compras', 'relatorios'],
        compras: ['dashboard', 'estoque', 'vencimentos', 'compras', 'relatorios'],
        atendente: ['dashboard', 'estoque'],
        visualizador: ['dashboard', 'estoque', 'vencimentos', 'relatorios']
      };
      const scenarios = Object.entries(defaults).flatMap(([perfil, allowed]) => [
        { perfil, allowed, mode: 'persisted' },
        { perfil, allowed, mode: 'legacy' }
      ]);
      // A permissão personalizada prevalece inclusive sobre o cargo proprietário.
      scenarios.push(
        { perfil: 'proprietario', allowed: ['dashboard', 'relatorios', 'log'], mode: 'custom' },
        {
          perfil: 'atendente',
          allowed: ['dashboard', 'estoque', 'financeiro', 'relatorios'],
          mode: 'custom'
        }
      );
      await send('Emulation.setDeviceMetricsOverride', {
        width: 1440,
        height: 900,
        deviceScaleFactor: 1,
        mobile: false
      });
      await send('Page.navigate', { url: origin + '/pages/sistema/dashboard/dashboard.html' });
      await delay(500);
      report.profiles = [];
      for (const scenario of scenarios) {
        const user = { id: 42, nome: 'Teste', sobrenome: 'Local', perfil: scenario.perfil };
        if (scenario.mode !== 'legacy') user.permissoes = scenario.allowed;
        await evaluate(
          'sessionStorage.setItem("test-user",' + JSON.stringify(JSON.stringify(user)) + ')'
        );
        for (const page of pages) {
          const expectedPage = scenario.allowed.includes(page) ? page : 'dashboard';
          await evaluate('window.__profileOldDoc=true');
          await send('Page.navigate', {
            url: origin + '/pages/sistema/' + page + '/' + page + '.html'
          });
          let ready = false;
          for (let i = 0; i < 160; i++) {
            await delay(50);
            try {
              ready = await evaluate(
                "!window.__profileOldDoc && document.readyState==='complete' && location.pathname.endsWith('/" +
                  expectedPage +
                  '/' +
                  expectedPage +
                  ".html') && !!document.querySelector('.sb-item[aria-hidden]')"
              );
              if (ready) break;
            } catch (error) {
              if (!/context|navigat/i.test(error.message)) throw error;
            }
          }
          assert(ready, `${scenario.perfil}/${scenario.mode}/${page}: destino incorreto`);
          const state = await evaluate(`(() => {
            const module = item => new URL(item.href).pathname.split('/').at(-2);
            const visible = [...document.querySelectorAll('.sb-nav .sb-item')].filter(item => getComputedStyle(item).display !== 'none');
            return {
              all:[...document.querySelectorAll('.sb-nav .sb-item')].map(module).sort(),
              visible:visible.map(module).sort(),
              active:visible.filter(item=>item.classList.contains('active')).map(module),
              legacyLinks:visible.filter(item=>item.href.includes('/proprietario/')).length,
              emptyGroups:[...document.querySelectorAll('.sb-group-label')].filter(label=>{
                if (label.hidden) return false;
                let next=label.nextElementSibling;
                while(next && !next.classList.contains('sb-group-label')) {
                  if (next.matches('.sb-item:not([hidden])')) return false;
                  next=next.nextElementSibling;
                }
                return true;
              }).length
            };
          })()`);
          const context = `${scenario.perfil}/${scenario.mode}/${page}`;
          assert.deepEqual(
            state.all,
            [...pages].sort(),
            context + ': módulo ausente ou duplicado no HTML'
          );
          assert.deepEqual(
            state.visible,
            [...scenario.allowed].sort(),
            context + ': módulos visíveis incorretos'
          );
          assert.deepEqual(state.active, [expectedPage], context + ': item ativo incorreto');
          assert.equal(state.legacyLinks, 0, context + ': link legado');
          assert.equal(state.emptyGroups, 0, context + ': grupo vazio visível');
          report.profiles.push({
            perfil: scenario.perfil,
            mode: scenario.mode,
            page,
            redirected: expectedPage !== page
          });
        }
        console.log(`OK: ${scenario.perfil} (${scenario.mode}), ${pages.length} páginas`);
      }
      assert.deepEqual(report.errors, [], 'Exceções no navegador');
      report.passed = true;
      console.log(
        JSON.stringify(
          {
            profiles: Object.keys(defaults).length,
            scenarios: report.profiles.length,
            errors: report.errors
          },
          null,
          2
        )
      );
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
        if (name === 'log') {
          assert.equal(await evaluate("document.querySelectorAll('#log-rows tr').length"), 2);
          await evaluate(
            "document.getElementById('filtro-usuario').value='42'; document.getElementById('filtro-inicio').value='2026-10-09'; document.getElementById('filtro-fim').value='2026-10-09'; document.getElementById('log-filters').requestSubmit()"
          );
          await delay(100);
          const filtered = await evaluate(
            "window.__testFetches.filter(r=>r.path==='/admin/logs').at(-1).search"
          );
          assert.equal(new URLSearchParams(filtered).get('usuario_id'), '42');
          assert.equal(new URLSearchParams(filtered).get('data_inicio'), '2026-10-09');
          assert.equal(new URLSearchParams(filtered).get('data_fim'), '2026-10-09');
          await evaluate("document.getElementById('limpar-filtros').click()");
          await delay(100);
          const cleared = await evaluate(
            "window.__testFetches.filter(r=>r.path==='/admin/logs').at(-1).search"
          );
          assert.equal(new URLSearchParams(cleared).has('usuario_id'), false);
          assert.equal(new URLSearchParams(cleared).has('data_inicio'), false);
          assert.equal(
            await evaluate("document.querySelectorAll('#filtro-usuario option').length"),
            3
          );
          await evaluate(
            "document.getElementById('filtro-inicio').value='2000-01-01'; document.getElementById('filtro-fim').value='2000-01-01'; document.getElementById('log-filters').requestSubmit()"
          );
          await delay(100);
          assert.match(
            await evaluate("document.getElementById('log-status').textContent"),
            /Nenhuma atividade/
          );
          assert.equal(
            await evaluate("document.querySelectorAll('#log-rows .log-empty').length"),
            1
          );
          assert.equal(await evaluate("document.getElementById('proxima').disabled"), true);
          const beforeFuture = await evaluate('window.__testFetches.length');
          await evaluate(
            "document.getElementById('filtro-inicio').value='9999-01-01'; document.getElementById('filtro-fim').value='9999-01-01'; document.getElementById('log-filters').requestSubmit()"
          );
          assert.match(
            await evaluate("document.getElementById('log-status').textContent"),
            /datas futuras/
          );
          assert.equal(await evaluate('window.__testFetches.length'), beforeFuture);
          await evaluate(
            "document.getElementById('log-filters').reset(); document.getElementById('filtro-usuario').value='43'; document.getElementById('log-filters').requestSubmit()"
          );
          await delay(100);
          assert.match(
            await evaluate("document.getElementById('log-status').textContent"),
            /Nenhuma atividade/
          );
          await evaluate(
            "window.__testOldLogServer=true; document.getElementById('limpar-filtros').click()"
          );
          await delay(100);
          assert.match(
            await evaluate("document.getElementById('log-status').textContent"),
            /Reinicie o FarmaControl/
          );
          await evaluate(
            "window.__testOldLogServer=false; document.getElementById('limpar-filtros').click()"
          );
          await delay(100);
          assert.equal(await evaluate("document.querySelectorAll('#log-rows tr').length"), 2);
          assert.equal(
            await evaluate('document.documentElement.scrollWidth <= window.innerWidth'),
            true,
            'Log sem overflow da página'
          );
          const screenshot = await send('Page.captureScreenshot', { format: 'png' });
          fs.writeFileSync(
            path.join(backup, `log-${width}.png`),
            Buffer.from(screenshot.data, 'base64')
          );
        }
        if (name === 'usuarios') {
          assert.equal(
            await evaluate("document.querySelector('.log-list, #modal-full-history, .page-panel')"),
            null
          );
          assert.equal(
            await evaluate("window.__testFetches.some(r=>r.path==='/admin/logs')"),
            false
          );
        }
      }
    }
    const waitFor = async (expression, message) => {
      for (let i = 0; i < 160; i++) {
        await delay(50);
        try {
          if (await evaluate(expression)) return;
        } catch (error) {
          if (!/context|navigat/i.test(error.message)) throw error;
        }
      }
      throw new Error(message);
    };
    const ready = name =>
      "location.pathname.endsWith('/" +
      name +
      '/' +
      name +
      ".html') && document.readyState==='complete' && !!window.fcNavigate";
    const navigate = async name => {
      await evaluate("window.fcNavigate('/pages/sistema/" + name + '/' + name + ".html')");
      await waitFor(ready(name), 'Navegação não concluiu: ' + name);
      await delay(100);
    };
    await send('Emulation.setDeviceMetricsOverride', {
      width: 1440,
      height: 900,
      deviceScaleFactor: 1,
      mobile: false
    });
    await send('Page.navigate', { url: origin + '/pages/sistema/dashboard/dashboard.html' });
    await waitFor(ready('dashboard'), 'Dashboard inicial');
    // A inicialização pertence à sessão de login, não a cada documento do painel.
    await evaluate("sessionStorage.removeItem('farmacontrol_dashboard_boot_session')");
    await navigate('financeiro');
    await navigate('dashboard');
    assert(
      await evaluate(
        "document.documentElement.classList.contains('fc-dashboard-first-visit') && getComputedStyle(document.getElementById('fc-dashboard-boot')).display==='grid'"
      ),
      'Primeira abertura sem inicialização'
    );
    await waitFor(
      "document.getElementById('fc-dashboard-boot').classList.contains('is-ready')",
      'Inicialização não concluiu'
    );
    for (const source of ['financeiro', 'relatorios']) {
      await navigate(source);
      await navigate('dashboard');
      assert(
        await evaluate(
          "!document.documentElement.classList.contains('fc-dashboard-first-visit') && getComputedStyle(document.getElementById('fc-dashboard-boot')).display==='none'"
        ),
        'Inicialização repetida ao voltar de ' + source
      );
      assert(
        await evaluate("window.__testFetches.some(r=>r.path==='/dashboard/stats')"),
        'Dashboard deixou de atualizar os dados'
      );
    }
    await evaluate('window.__reloadProbe=true');
    await send('Page.reload');
    await waitFor(
      "!window.__reloadProbe && document.readyState==='complete'",
      'Novo documento após reload'
    );
    await waitFor(ready('dashboard'), 'Reload do dashboard');
    assert(
      await evaluate(
        "getComputedStyle(document.getElementById('fc-dashboard-boot')).display==='none'"
      ),
      'Inicialização repetida no reload'
    );
    await evaluate("sessionStorage.setItem('test-session-csrf','nova-sessao-csrf')");
    await navigate('financeiro');
    await navigate('dashboard');
    assert(
      await evaluate("document.documentElement.classList.contains('fc-dashboard-first-visit')"),
      'Novo login não renovou a inicialização'
    );
    await waitFor(
      "document.getElementById('fc-dashboard-boot').classList.contains('is-ready')",
      'Inicialização da nova sessão'
    );
    report.dashboardBootOncePerSession = true;
    for (const name of [...pages.slice(1), 'dashboard', 'estoque', 'dashboard', 'estoque']) {
      await evaluate('window.__oldPageProbe=true');
      await navigate(name);
      assert.equal(await evaluate('!!window.__oldPageProbe'), false, 'Contexto antigo sobreviveu');
      assert.equal(await evaluate("!!document.querySelector('.main')"), true, 'Conteúdo ausente');
      const current = await evaluate('(' + fingerprint.toString() + ')()');
      const expected = report.static.find(p => p.name === name && p.width === 1440);
      assert.deepEqual(current, expected.styles, name + ': aparência diferente da abertura direta');
      const modals = await evaluate(
        "[...document.querySelectorAll('.modal-overlay')].map(e=>e.id).filter(Boolean).sort()"
      );
      assert.deepEqual(modals, expected.modals, name + ': modais ausentes');
      assert(
        await evaluate(
          "(function(){const sb=document.querySelector('.sidebar');const b=document.getElementById('btn-collapse');const before=sb.classList.contains('collapsed');b.click();const changed=before!==sb.classList.contains('collapsed');b.click();return changed;})()"
        ),
        'Sidebar não alternou'
      );
      report.navigation.push({ name, contextIsolated: true });
    }
    // Histórico real, incluindo reload ao restaurar bfcache.
    await navigate('compras');
    await navigate('financeiro');
    let history = await send('Page.getNavigationHistory');
    await send('Page.navigateToHistoryEntry', {
      entryId: history.entries[history.currentIndex - 1].id
    });
    await waitFor(ready('compras'), 'Voltar não restaurou Compras');
    history = await send('Page.getNavigationHistory');
    await send('Page.navigateToHistoryEntry', {
      entryId: history.entries[history.currentIndex + 1].id
    });
    await waitFor(ready('financeiro'), 'Avançar não restaurou Financeiro');
    report.history = true;
    // Fluxo completo de abertura, preenchimento e envio do modal (API simulada).
    await evaluate("document.getElementById('btn-nova-transacao').click()");
    await waitFor(
      "document.querySelectorAll('#tx-categoria option').length===2",
      'Categorias do modal'
    );
    await evaluate(
      "document.getElementById('tx-categoria').value='1';document.getElementById('tx-descricao').value='Teste de navegação';document.getElementById('tx-valor').value='10';document.getElementById('tx-metodo').value='pix';document.getElementById('btn-save-transacao').click()"
    );
    await waitFor(
      "!document.getElementById('modal-nova-transacao').classList.contains('open')",
      'Modal não concluiu'
    );
    assert.equal(
      await evaluate(
        "window.__testFetches.filter(x=>x.path==='/financeiro/transacoes'&&x.method==='POST').length"
      ),
      1,
      'Envio duplicado'
    );
    report.modalSubmit = true;
    // Uma leitura lenta da tela abandonada precisa ser cancelada, sem callback tardio.
    await evaluate(
      "window.__testApiDelay=1500;sessionStorage.removeItem('test-aborted');sessionStorage.removeItem('test-late');fetch('/estoque').then(()=>sessionStorage.setItem('test-late','true')).catch(()=>{});true"
    );
    await navigate('estoque');
    await delay(1600);
    assert.equal(
      await evaluate("sessionStorage.getItem('test-aborted')"),
      'true',
      'Leitura antiga não cancelada'
    );
    assert.equal(
      await evaluate("sessionStorage.getItem('test-late')"),
      null,
      'Resposta antiga continuou'
    );
    report.slowReadCancelled = true;
    // Recursos lentos e navegações rápidas: a última navegação vence.
    await evaluate("window.fcNavigate('/pages/sistema/compras/compras.html?slow=1')");
    await delay(100);
    await evaluate("window.location.assign('/pages/sistema/usuarios/usuarios.html')");
    await waitFor(ready('usuarios'), 'Última navegação não venceu');
    await delay(1000);
    assert.equal(await evaluate("location.pathname.endsWith('/usuarios/usuarios.html')"), true);
    report.rapidNavigation = true;
    await navigate('estoque');
    await evaluate("document.getElementById('btn-add').click()");
    assert(await evaluate("document.getElementById('modal-overlay').classList.contains('open')"));
    await evaluate("document.getElementById('modal-cancel').click()");
    assert.equal(
      await evaluate("document.getElementById('modal-overlay').classList.contains('open')"),
      false
    );
    await send('Emulation.setDeviceMetricsOverride', {
      width: 390,
      height: 844,
      deviceScaleFactor: 1,
      mobile: true
    });
    assert(
      await evaluate(
        "(function(){document.getElementById('btn-mobile-menu').click();const opened=document.querySelector('.sidebar').classList.contains('mobile-open');document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));return opened&&!document.querySelector('.sidebar').classList.contains('mobile-open');})()"
      ),
      'Menu móvel'
    );
    report.mobileMenu = true;
    assert.deepEqual(report.errors, [], 'Exceções no navegador');
    report.passed = true;
    console.log(
      JSON.stringify(
        {
          phase,
          staticPages: report.static.length,
          navigations: report.navigation.length,
          dashboardBootOncePerSession: report.dashboardBootOncePerSession,
          history: report.history,
          modalSubmit: report.modalSubmit,
          slowReadCancelled: report.slowReadCancelled,
          rapidNavigation: report.rapidNavigation,
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
