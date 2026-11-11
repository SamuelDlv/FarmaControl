"""Chrome isolado + HTML real do Flask; banco/API simulados, sem dados operacionais."""
from pathlib import Path
import re
import sys
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import test_backend as base

ROLES = ('proprietario','admin','farmaceutico','atendente','compras','ti','visualizador')
EDIT_STOCK = {'proprietario','admin','farmaceutico','compras','ti'}
ADMINS = {'proprietario','admin','ti'}
SALES = {'proprietario','admin','farmaceutico','atendente','ti'}


def main():
    output = ROOT / '.audit-backup/permissoes'
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True)
        for role in ROLES:
            harness = base.BackendTests()
            harness.setUp()
            try:
                harness.login_session(role)
                response = harness.client.get('/pages/sistema/estoque/estoque.html')
                assert response.status_code == 200
                html = response.data.decode('utf-8')
                html = re.sub(r'<script\b(?![^>]*type="application/json")[^>]*>.*?</script>', '', html, flags=re.S)
                html = re.sub(r'<style id="fc-body-lock">.*?</style>', '', html, flags=re.S)
                folder = ROOT / 'frontend/src/pages/sistema/estoque'
                styles = []
                for href in re.findall(r'<link[^>]*href="([^"]+\.css)"', html):
                    css = ((ROOT / 'frontend/src' / href.lstrip('/')) if href.startswith('/') else folder / href).resolve()
                    if css.is_relative_to(ROOT) and css.is_file():
                        styles.append(css.read_text(encoding='utf-8'))
                html = re.sub(r'<link\b[^>]*>', '', html)
                context = browser.new_context(viewport={'width':1440,'height':1000})
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.route('**/*', lambda route: route.fulfill(content_type='text/html', body=(
                    '<h1>Acesso</h1>' if '/pages/acesso/' in route.request.url else html)))
                page.goto('http://permission.test/pages/sistema/estoque/estoque.html')
                page.add_style_tag(content='\n'.join(styles))
                page.evaluate('''() => {
                  sessionStorage.setItem('farmacontrol_usuario', JSON.stringify({id:42,perfil:'proprietario',permissoes:['configuracoes','estoque']}));
                  sessionStorage.setItem('farmacontrol_csrf', 'token-antigo');
                  window.__fcPageToken = 'permission-test';
                  window.__fcSetInterval = () => 0;
                  window.fcPageListen = (target, name, fn, options) => target.addEventListener(name, fn, options);
                  window.requests = [];
                  window.fetch = async (url, options={}) => {
                    const pathname = new URL(typeof url === 'string' ? url : url.url, location.href).pathname;
                    requests.push({pathname,method:options.method || 'GET',headers:Object.fromEntries(new Headers(options.headers || {}))});
                    if (pathname === '/auth/logout' && new Headers(options.headers).get('X-CSRF-Token') !== 'teste-csrf')
                      throw new Error('Logout enviou token antigo em vez do token validado');
                    const data = {ok:true,configuracoes:[],estoque:[{
                      id:1,produto_id:1,produto_nome:'Produto de demonstração',lote:'TESTE',quantidade:30,
                      estoque_minimo:5,preco_venda:10,preco_custo:5,data_validade:'2028-12-31',categoria:'Outros'
                    }]};
                    return {ok:true,status:200,json:async()=>data};
                  };
                }''')
                for script in ('sidebar-init.js','global-settings.js'):
                    page.add_script_tag(content=(ROOT / 'frontend/src/utils' / script).read_text(encoding='utf-8'))
                page.add_script_tag(content=(folder / 'estoque.js').read_text(encoding='utf-8'))
                page.locator('.btn-history').wait_for()
                for selector in ('#btn-add','.btn-edit','.btn-move','.btn-delete'):
                    assert page.locator(selector).is_visible() == (role in EDIT_STOCK), (role, selector)
                assert page.locator('#btn-suppliers').is_visible() == (role in EDIT_STOCK), role
                assert page.locator('.btn-history').is_visible()
                for module, permitted in (('financeiro',role in ADMINS),('usuarios',role in ADMINS),
                                          ('log',role in ADMINS),('vendas',role in SALES)):
                    assert page.locator(f'.sb-item[href*="/{module}/"]').is_visible() == permitted, (role,module)
                assert page.evaluate("requests.some(r => r.pathname === '/configuracoes')") == (role in ADMINS), role
                if role in ('atendente','visualizador'):
                    page.screenshot(path=str(output / f'{role}-estoque.png'))
                # A sessão validada injeta o token atual, mesmo com cache antigo.
                page.get_by_role('button', name=re.compile('Sair', re.I)).click()
                page.wait_for_url('**/pages/acesso/acesso.html')
                assert not errors, (role,errors)
                context.close()
                print(f'{role}: menu, estoque, preferências e logout OK')
            finally:
                harness.doCleanups()
        browser.close()


if __name__ == '__main__':
    main()
