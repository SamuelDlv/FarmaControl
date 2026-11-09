/* Restrições de edição compartilhadas, inclusive para campos criados em modais. */
(() => {
  'use strict';
  const previous = new WeakMap();

  function kind(input) {
    if (!input || input.tagName !== 'INPUT' || input.disabled || input.readOnly) return '';
    return input.dataset.inputKind || (input.type === 'number' ? 'number' :
      input.type === 'email' ? 'email' : '');
  }

  function decimals(input) {
    const step = input.getAttribute('step') || '1';
    return step === 'any' ? 20 : (step.split('.')[1] || '').length;
  }

  function allowed(input, value) {
    if (input.maxLength >= 0 && value.length > input.maxLength) return false;
    switch (kind(input)) {
      case 'digits': return /^[0-9]*$/.test(value);
      case 'phone': return /^\+?[0-9 ()-]*$/.test(value);
      case 'email': return !/\s/.test(value);
      case 'number': return new RegExp(decimals(input) ?
        '^[0-9]*(?:[.,][0-9]{0,' + decimals(input) + '})?$' : '^[0-9]*$').test(value);
      default: return true;
    }
  }

  function prepare(input) {
    const rule = kind(input);
    if (rule === 'number') {
      if (!input.hasAttribute('min') || Number(input.min) < 0) input.min = '0';
      input.inputMode = decimals(input) ? 'decimal' : 'numeric';
    } else if (rule === 'digits') {
      input.inputMode = 'numeric';
      // Valores antigos podem vir formatados do servidor.
      if (/^[0-9]{2}\.[0-9]{3}\.[0-9]{3}\/[0-9]{4}-[0-9]{2}$/.test(input.value)) {
        input.value = input.value.replace(/[^0-9]/g, '');
      }
    }
    if (rule) previous.set(input, allowed(input, input.value) ? input.value : '');
  }

  function candidate(input, text) {
    if (input.selectionStart == null) return null; // type=number não expõe o cursor.
    return input.value.slice(0, input.selectionStart) + text + input.value.slice(input.selectionEnd);
  }

  document.addEventListener('focusin', event => prepare(event.target), true);
  document.addEventListener('keydown', event => {
    const input = event.target;
    if (!kind(input) || event.ctrlKey || event.metaKey || event.altKey || event.key.length !== 1) return;
    if (!allowed(input, event.key) ||
        (candidate(input, event.key) !== null && !allowed(input, candidate(input, event.key)))) {
      event.preventDefault();
    }
  }, true);
  document.addEventListener('beforeinput', event => {
    const input = event.target;
    if (!kind(input) || !event.data || !event.inputType.startsWith('insert')) return;
    const value = candidate(input, event.data);
    if (!allowed(input, event.data) || (value !== null && !allowed(input, value))) event.preventDefault();
  }, true);

  function transfer(event) {
    const input = event.target;
    const rule = kind(input);
    if (!rule) return;
    let text = (event.clipboardData || event.dataTransfer)?.getData('text/plain');
    if (text == null) return;
    event.preventDefault();
    text = text.trim();
    // Aceitar documentos formatados, sem converter texto arbitrário ou sinais negativos.
    if (rule === 'digits' && /^(?:[0-9]+|[0-9]{2}\.[0-9]{3}\.[0-9]{3}\/[0-9]{4}-[0-9]{2})$/.test(text)) {
      text = text.replace(/[^0-9]/g, '');
    }
    if (!allowed(input, text)) return;
    const value = candidate(input, text) ?? text;
    if (!allowed(input, value)) return;
    if (input.selectionStart == null) input.value = value.replace(',', '.');
    else input.setRangeText(text, input.selectionStart, input.selectionEnd, 'end');
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }
  document.addEventListener('paste', transfer, true);
  document.addEventListener('drop', transfer, true);
  document.addEventListener('input', event => {
    const input = event.target;
    if (!kind(input)) return;
    if (!allowed(input, input.value) || input.validity.badInput) {
      input.value = previous.get(input) || '';
    }
    previous.set(input, input.value);
  }, true);

  function initialize() {
    document.querySelectorAll('input').forEach(prepare);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize);
  else initialize();
})();
