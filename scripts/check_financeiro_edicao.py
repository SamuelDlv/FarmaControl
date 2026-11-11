"""Valida a tela real com API simulada; evidências ficam fora do versionamento."""
from pathlib import Path
import re
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'frontend/src/pages/sistema/financeiro'
OUT = ROOT / '.audit-backup/financeiro-edicao'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    html = (PAGE / 'financeiro.html').read_text(encoding='utf-8')
    html = re.sub(r'<script\b[^>]*>.*?</script>', '', html, flags=re.S)
    html = re.sub(r'<style id="fc-body-lock">.*?</style>', '', html, flags=re.S)
    styles = []
    for href in re.findall(r'<link[^>]*href="([^"]+\.css)"', html):
        css = (PAGE / href).resolve()
        if css.is_relative_to(ROOT) and css.exists():
            styles.append(css.read_text(encoding='utf-8'))
    html = re.sub(r'<link\b[^>]*>', '', html)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.route('**/*', lambda route: route.fulfill(status=200, content_type='text/html', body=html))
        page.goto('http://finance.test/')
        page.add_style_tag(content='\n'.join(styles))
        # Paleta clara usada pelo global-settings.js, sem carregar preferências reais.
        page.add_style_tag(content=':root { --sage:#4a7c59; --sage-2:#3a6447; --sage-light:#80a88a; --sage-pale:#eef4ef; --sage-border:#c5d8ca; --ink:#1a1a1a; --ink-60:#2d2d2d; --ink-35:#5a5a5a; --ink-12:#d0d0d0; --ink-06:#e8e8e8; --cream:#fff; --cream-2:#f8f8f8; --surface:#fff; --surface-2:#fafafa; --bg-body:#f0f2f1; }')
        page.evaluate('''() => {
          window.__fcPageToken = 'finance-test';
          window.fcPageListen = (target, name, fn) => target.addEventListener(name, fn);
          window.FarmaControlSettings = { API_BASE: 'http://finance.test' };
          window.correctionRequests = [];
          window.failCorrection = false;
          window.delayCorrection = false;
          window.amount = 150.75;
          window.fetch = async (url, options = {}) => {
            const parsed = new URL(url);
            let data = {ok:true}, status = 200;
            if (options.method === 'PUT') {
              correctionRequests.push(JSON.parse(options.body));
              if (delayCorrection) await new Promise(resolve => { window.releaseCorrection = resolve; });
              if (failCorrection) { data = {ok:false, mensagem:'O valor foi alterado por outro usuário.'}; status=409; }
              else amount = Number(JSON.parse(options.body).valor);
            } else if (parsed.pathname.endsWith('/transacoes')) {
              data.transacoes = [
                {id:12,descricao:'Despesa de teste',categoria_nome:'Outros',tipo:'despesa',valor:amount,
                 valor_exato:amount.toFixed(2),data_transacao:'2026-11-11 00:00:00',metodo_pagamento:'pix',status:'pago'},
                {id:13,descricao:'Venda vinculada',categoria_nome:'Vendas',tipo:'receita',valor:20,
                 data_transacao:'2026-11-11 00:00:00',metodo_pagamento:'pix',status:'pago',venda_id:8}];
            } else if (parsed.pathname.endsWith('/stats')) {
              data = {...data, despesas:amount, receitas:20, saldo:20-amount};
            } else if (parsed.pathname.endsWith('/categorias')) {
              data.categorias = [{id:2,nome:'Outros',tipo:'despesa',valor:amount}];
            } else if (parsed.pathname.endsWith('/fluxo')) {
              const start = parsed.searchParams.get('start_date'), end = parsed.searchParams.get('end_date');
              data = {...data,periodo:{inicio:start,fim:end},labels:['11/11'],dias:['2026-11-11'],receitas:[20],despesas:[amount]};
            }
            return {ok:status===200,status,json:async()=>data};
          };
        }''')
        page.add_script_tag(content=(PAGE / 'financeiro.js').read_text(encoding='utf-8'))
        edit = page.get_by_role('button', name='Editar valor da transação 12')
        edit.wait_for()
        assert page.locator('[data-edit-transaction="13"]').count() == 0
        page.get_by_role('button', name='Ver detalhes', exact=True).click()
        edit.click()
        assert page.locator('#edit-tx-value').input_value() == '150.75'
        assert '150,75' in page.locator('#edit-tx-before').input_value()
        page.locator('#edit-tx-value').fill('100.25')
        page.locator('#edit-tx-reason').fill('Valor digitado incorretamente')
        page.wait_for_function("getComputedStyle(document.querySelector('#modal-editar-transacao')).opacity === '1'")
        page.screenshot(path=str(OUT / 'editar-desktop.png'))
        page.evaluate('window.delayCorrection = true')
        page.get_by_role('button', name='Salvar correção', exact=True).click()
        assert page.locator('#btn-save-correcao').is_disabled()
        page.locator('#form-edit-transacao').dispatch_event('submit')
        assert len(page.evaluate('correctionRequests')) == 1
        page.evaluate('releaseCorrection()')
        page.wait_for_function("!document.querySelector('#modal-editar-transacao').classList.contains('open')")
        page.wait_for_function("document.querySelector('#kpi-despesas').textContent.includes('100,25')")
        page.wait_for_function("document.querySelector('#chart-despesas').textContent.includes('100,25')")
        page.wait_for_function("document.querySelector('#cat-list').textContent.includes('100,25')")
        assert page.evaluate('correctionRequests[0]') == {
            'valor':'100.25', 'valor_anterior':'150.75', 'motivo':'Valor digitado incorretamente'}
        page.evaluate('window.delayCorrection = false; window.failCorrection = true')
        edit.click()
        page.locator('#edit-tx-value').fill('90.10')
        page.locator('#edit-tx-reason').fill('Nova correção de teste')
        page.get_by_role('button', name='Salvar correção', exact=True).click()
        page.locator('#edit-tx-error').get_by_text('O valor foi alterado por outro usuário.').wait_for()
        assert not page.locator('#btn-save-correcao').is_disabled()
        page.set_viewport_size({'width':390,'height':844})
        page.wait_for_function("document.querySelector('.sidebar').getBoundingClientRect().right <= 0")
        assert page.locator('#btn-save-correcao').is_visible()
        assert page.locator('#form-edit-transacao').evaluate('el => el.getBoundingClientRect().right <= innerWidth')
        page.screenshot(path=str(OUT / 'editar-mobile.png'))
        assert not errors, errors
        browser.close()
    print('OK: edição, payload, duplo envio, conflito, totais/gráfico/detalhes e modal mobile (API simulada).')


if __name__ == '__main__':
    main()
