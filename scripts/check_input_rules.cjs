/* Guia de manutenção — Verificador de input rules: confira pré-requisitos, argumentos e cenários antes de executar.
 * Os resultados cobrem os cenários descritos neste arquivo; mocks não comprovam integração real.
 */
/* Cenários de edição no Chrome; executados por check_navigation.cjs --input-rules. */
const assert = require('node:assert/strict');

module.exports = async function checkInputRules({ evaluate, send, origin }) {
  let checks = 0;
  const equal = (actual, expected, message) => { assert.equal(actual, expected, message); checks++; };
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
  // Prepara a página usada pelo cenário de teste e expõe os controles necessários às asserções.
  async function page(name) {
    await send('Page.navigate', { url: origin + '/pages/sistema/' + name + '/' + name + '.html' });
    for (let i = 0; i < 60; i++) {
      if (await evaluate(`location.pathname.endsWith('/${name}/${name}.html') && document.readyState === 'complete'`)) return;
      await pause(100);
    }
    throw new Error('Página não carregou: ' + name);
  }
  async function focus(selector, value = '') {
    await evaluate(`(() => {
      const input = document.querySelector(${JSON.stringify(selector)});
      for (let el = input; el; el = el.parentElement) {
        el.style.display = 'block'; el.style.visibility = 'visible';
      }
      input.value = ${JSON.stringify(value)};
      input.focus(); input.dispatchEvent(new FocusEvent('focusin', { bubbles: true }));
    })()`);
  }
  const value = selector => evaluate(`document.querySelector(${JSON.stringify(selector)}).value`);
  async function type(text) {
    for (const key of text) {
      await send('Input.dispatchKeyEvent', { type: 'keyDown', key, text: key });
      await send('Input.dispatchKeyEvent', { type: 'keyUp', key });
    }
  }
  async function paste(selector, text, drop = false) {
    await evaluate(`(() => {
      const input = document.querySelector(${JSON.stringify(selector)});
      const data = new DataTransfer(); data.setData('text/plain', ${JSON.stringify(text)});
      input.dispatchEvent(${drop ? "new DragEvent('drop', {dataTransfer:data" : "new ClipboardEvent('paste', {clipboardData:data"}, bubbles:true, cancelable:true}));
    })()`);
  }
  // Todos os campos numéricos reais, inclusive os que não possuíam min.
  for (const name of ['estoque', 'dashboard', 'vencimentos', 'relatorios', 'financeiro', 'configuracoes', 'compras']) {
    await page(name);
    const count = await evaluate(`(() => {
      const inputs = [...document.querySelectorAll('input[type="number"]')];
      for (const input of inputs) {
        input.disabled = false;
        input.dispatchEvent(new FocusEvent('focusin', {bubbles:true}));
        for (const key of ['-', '+', 'e', 'E', 'a']) {
          const event = new KeyboardEvent('keydown', {key, bubbles:true, cancelable:true});
          input.dispatchEvent(event);
          if (!event.defaultPrevented) throw new Error(input.id + ': tecla ' + key);
        }
        if (Number(input.min) < 0 || input.min === '') throw new Error(input.id + ': mínimo');
      }
      return inputs.length;
    })()`);
    assert(count > 0, name + ': campos numéricos encontrados'); checks += count;
  }
  await page('estoque');
  await focus('#sup-cnpj'); await type('00abc1234560001999');
  equal(await value('#sup-cnpj'), '00123456000199', 'CNPJ: somente 14 dígitos e zeros iniciais');
  await focus('#sup-cnpj'); await paste('#sup-cnpj', '00.123.456/0001-99');
  equal(await value('#sup-cnpj'), '00123456000199', 'Colagem de CNPJ formatado');
  await focus('#sup-cnpj'); await paste('#sup-cnpj', 'ABC123');
  equal(await value('#sup-cnpj'), '', 'Colagem de letras rejeitada');
  await focus('#sup-cnpj', '00123456000199');
  await evaluate("document.querySelector('#sup-cnpj').setSelectionRange(2, 5)");
  await paste('#sup-cnpj', '987');
  equal(await value('#sup-cnpj'), '00987456000199', 'Substituir seleção preserva o restante do documento');
  await focus('#sup-cnpj', '123');
  equal(await evaluate("document.querySelector('#sup-cnpj').checkValidity()"), false, 'CNPJ incompleto');
  await focus('#add-qty'); await type('-1e2.3');
  equal(await value('#add-qty'), '123', 'Quantidade inteira, sem sinal ou expoente');
  await focus('#add-qty', '7'); await paste('#add-qty', '-5');
  equal(await value('#add-qty'), '7', 'Colagem negativa não se transforma em positivo');
  await paste('#add-qty', '-8', true);
  equal(await value('#add-qty'), '7', 'Arrastar negativo é rejeitado');
  await paste('#add-qty', '1.5');
  equal(await value('#add-qty'), '7', 'Quantidade fracionária rejeitada');
  await focus('#add-custo');
  await type('12,345');
  equal(await value('#add-custo'), '12.34', 'Preço limitado a centavos');
  await focus('#add-custo'); await paste('#add-custo', '12,34');
  equal(await value('#add-custo'), '12.34', 'Colagem de preço com vírgula');
  await focus('#add-custo'); await send('Input.insertText', {text:'-9'});
  equal(await value('#add-custo'), '', 'Inserção por teclado virtual rejeita negativo');
  await focus('#sup-telefone'); await type('(11) abc99999-9999');
  equal(await value('#sup-telefone'), '(11) 99999-9999', 'Telefone aceita máscara e rejeita letras');
  await focus('#sup-email'); await type('a b@example.com');
  equal(await value('#sup-email'), 'ab@example.com', 'E-mail sem espaços');
  await focus('#add-nome'); await type('Vitamina B12 - 500mg');
  equal(await value('#add-nome'), 'Vitamina B12 - 500mg', 'Nome de produto aceita letras e números');
  // Exercita a renderização e os listeners reais dos itens criados dinamicamente.
  await page('compras');
  await evaluate("cmpItens = [{id:'teste-campo'}]; renderCmpItem(cmpItens[0]);");
  await focus('[data-field="quantidade"]'); await type('-4e2.1');
  equal(await value('[data-field="quantidade"]'), '421', 'Campo dinâmico protegido');
  equal(await evaluate('cmpItens[0].quantidade'), '421', 'Modelo recebe apenas a quantidade válida');
  await focus('[data-field="preco_unitario"]'); await paste('[data-field="preco_unitario"]', '4,50');
  equal(await evaluate('cmpItens[0].preco_unitario'), '4.50', 'Modelo recebe preço com vírgula normalizado');
  return { checks };
};
