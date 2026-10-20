(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const user = JSON.parse(sessionStorage.getItem('farmacontrol_usuario') || 'null');
  if (!user) {
    location.replace('../../acesso/acesso.html');
    return;
  }
  if (!['proprietario', 'admin', 'farmaceutico', 'atendente', 'ti'].includes(user.perfil)) {
    location.replace('../dashboard/dashboard.html');
    return;
  }
  $('user-name').textContent = user.nome || 'Usuário';
  $('user-role').textContent = {
    proprietario: 'Proprietário',
    admin: 'Gerente / Administrador',
    farmaceutico: 'Farmacêutico',
    atendente: 'Atendente',
    ti: 'TI / Suporte'
  }[user.perfil];
  $('user-avatar').textContent = (user.nome || 'U').slice(0, 2).toUpperCase();
  const money = n => Number(n).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  const esc = value =>
    String(value ?? '').replace(
      /[&<>"']/g,
      c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]
    );
  const norm = value =>
    String(value || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, ' ')
      .trim();
  const activeIngredient = p => String(p.principio_ativo || p.nome_generico || '').trim();
  let relatedIngredient = '';
  let products = [],
    cart = [],
    selected = new Set(),
    limit = 24,
    busy = false,
    uncertain = false,
    loaded = false;
  const total = () =>
    cart.reduce(
      (sum, item) => sum + Math.round(Number(item.product.preco_venda) * 100) * item.qty,
      0
    ) / 100;
  const stock = p => p.lots.reduce((sum, l) => sum + Number(l.quantidade), 0);
  async function api(path, options) {
    const response = await fetch(window.FarmaControlSettings.API_BASE + path, options);
    const data = await response.json();
    if (!response.ok || !data.ok) {
      const error = new Error(
        response.status === 404
          ? 'O servidor está desatualizado. Reinicie o FarmaControl para carregar o catálogo.'
          : data.mensagem || 'Falha ao consultar o servidor.'
      );
      error.confirmed = true;
      throw error;
    }
    return data;
  }
  async function load() {
    if ($('atualizar').disabled) return;
    $('atualizar').disabled = true;
    $('pesquisar').disabled = true;
    try {
      const data = await api('/vendas/catalogo');
      const grouped = new Map();
      data.produtos.forEach(row => {
        if (!grouped.has(row.produto_id)) grouped.set(row.produto_id, { ...row, lots: [] });
        if (row.estoque_id && Number(row.valido) && Number(row.quantidade) > 0)
          grouped.get(row.produto_id).lots.push(row);
      });
      products = [...grouped.values()];
      loaded = true;
      products.forEach(p =>
        p.lots.sort((a, b) => (a.data_validade || '9999').localeCompare(b.data_validade || '9999'))
      );
      cart = cart.map(item => ({
        ...item,
        product: grouped.get(item.product.produto_id) || { ...item.product, lots: [] }
      }));
      selected = new Set([...selected].filter(id => grouped.has(id)));
      $('status').textContent =
        'Preços e saldo atualizados às ' + new Date().toLocaleTimeString('pt-BR') + '.';
      render();
      renderCart();
    } catch (error) {
      $('status').textContent = error.message;
      if (!loaded) {
        $('contagem').textContent = 'Catálogo indisponível';
        $('resultados').textContent =
          'Não foi possível carregar os produtos. Tente pesquisar novamente após restabelecer a conexão.';
      }
    } finally {
      $('atualizar').disabled = false;
      $('pesquisar').disabled = false;
    }
  }
  function details(p) {
    return `<span class="tag">${p.tipo_produto === 'medicamento' ? 'Medicamento' : 'Outro produto'}</span><h3>${esc(p.nome)}</h3><p class="product-meta">${esc(p.fabricante || 'Fabricante não informado')}<br>${esc(activeIngredient(p) ? 'Princ\u00edpio ativo: ' + activeIngredient(p) : p.tipo_produto === 'medicamento' ? 'Princ\u00edpio ativo n\u00e3o cadastrado' : p.categoria || 'Sem categoria')}<br>Código: ${esc(p.codigo_barras || 'Não informado')}</p><strong class="price">${money(p.preco_venda)} <small>/ unidade</small></strong><p class="product-meta">${stock(p)} un. disponíveis${p.requer_receita ? ' · <span class="warning">Exige receita</span>' : ''}</p>`;
  }
  function render() {
    if (!loaded) return;
    const terms = norm($('busca').value).split(/\s+/).filter(Boolean);
    const filtered = products.filter(
      p =>
        (!relatedIngredient || norm(activeIngredient(p)) === relatedIngredient) &&
        (!$('tipo').value || p.tipo_produto === $('tipo').value) &&
        (!$('disponiveis').checked || stock(p) > 0) &&
        terms.every(t =>
          norm(
            [p.nome, activeIngredient(p), p.fabricante, p.codigo_barras, p.categoria].join(' ')
          ).includes(t)
        )
    );
    filtered.sort((a, b) =>
      $('ordem').value === 'preco'
        ? Number(a.preco_venda) - Number(b.preco_venda)
        : a.nome.localeCompare(b.nome, 'pt-BR')
    );
    $('contagem').textContent = filtered.length + ' produtos encontrados';
    $('resultados').innerHTML =
      filtered
        .slice(0, limit)
        .map(
          p =>
            `<article class="product-card">${details(p)}<div class="actions"><button data-add="${p.produto_id}" ${stock(p) <= 0 || Number(p.preco_venda) <= 0 ? 'disabled' : ''}>+ Adicionar 1 unidade</button><button data-select="${p.produto_id}" aria-pressed="${selected.has(p.produto_id)}">${selected.has(p.produto_id) ? '✓ Selecionado' : 'Comparar'}</button></div>${activeIngredient(p) ? `<button data-related="${p.produto_id}">Buscar mesmo princípio ativo</button>` : ''}</article>`
        )
        .join('') || '<p>Nenhum produto encontrado. Tente outro nome ou código.</p>';
    $('comparar').textContent = `Comparar selecionados (${selected.size}/3)`;
    $('comparar').disabled = selected.size < 2;
    $('mais').hidden = filtered.length <= limit;
  }
  function renderCart() {
    $('carrinho').innerHTML =
      cart
        .map(
          (item, i) =>
            `<div class="cart-line"><strong>${esc(item.product.nome)}</strong><span>${money(item.product.preco_venda)} / un.</span><div class="cart-controls"><button data-minus="${i}" aria-label="Diminuir ${esc(item.product.nome)}">−</button><span>${item.qty} un.</span><button data-plus="${i}" aria-label="Aumentar ${esc(item.product.nome)}">+</button><button class="remove" data-remove="${i}" aria-label="Remover ${esc(item.product.nome)}">Remover</button></div>${item.qty > stock(item.product) ? '<p class="warning">Saldo insuficiente. Revise a quantidade.</p>' : ''}</div>`
        )
        .join('') ||
      '<p class="muted">Adicione um produto para iniciar. Você também pode apenas consultar preços.</p>';
    $('total').textContent = money(total());
    $('unidades').textContent = cart.reduce((s, i) => s + i.qty, 0) + ' unidades';
    $('receita-wrap').hidden = !cart.some(i => i.product.requer_receita);
    $('revisar').disabled =
      busy || uncertain || !cart.length || cart.some(i => i.qty > stock(i.product));
    $('limpar').disabled = busy || uncertain || !cart.length;
  }
  function add(p) {
    if (busy || uncertain) return;
    const item = cart.find(i => i.product.produto_id === p.produto_id);
    if ((item?.qty || 0) >= stock(p)) {
      $('status').textContent = 'Quantidade disponível atingida.';
      return;
    }
    if (item) item.qty++;
    else cart.push({ product: p, qty: 1 });
    $('receita').checked = false;
    renderCart();
  }
  $('resultados').addEventListener('click', e => {
    const b = e.target.closest('button');
    if (!b) return;
    if (b.dataset.add) add(products.find(p => p.produto_id === Number(b.dataset.add)));
    if (b.dataset.select) {
      const id = Number(b.dataset.select);
      if (selected.has(id)) selected.delete(id);
      else if (selected.size < 3) selected.add(id);
      else $('status').textContent = 'Compare até três produtos por vez.';
      render();
    }
    if (b.dataset.related) {
      const ingredient = activeIngredient(
        products.find(p => p.produto_id === Number(b.dataset.related))
      );
      relatedIngredient = norm(ingredient);
      $('busca').value = ingredient;
      $('tipo').value = '';
      $('disponiveis').checked = false;
      limit = 24;
      render();
    }
  });
  $('carrinho').addEventListener('click', e => {
    const b = e.target.closest('button');
    if (!b || busy || uncertain) return;
    if (b.dataset.plus !== undefined) add(cart[Number(b.dataset.plus)].product);
    if (b.dataset.minus !== undefined) {
      const i = Number(b.dataset.minus);
      if (--cart[i].qty === 0) cart.splice(i, 1);
    }
    if (b.dataset.remove !== undefined) cart.splice(Number(b.dataset.remove), 1);
    renderCart();
  });
  ['busca', 'tipo', 'ordem', 'disponiveis'].forEach(id =>
    $(id).addEventListener('input', () => {
      if (id === 'busca') relatedIngredient = '';
      limit = 24;
      render();
    })
  );
  $('pesquisa').addEventListener('submit', async e => {
    e.preventDefault();
    limit = 24;
    if (!loaded) await load();
    else render();
  });
  $('busca').addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      e.preventDefault();
      $('pesquisa').requestSubmit();
    }
  });
  $('mais').onclick = () => {
    limit += 24;
    render();
  };
  $('atualizar').onclick = load;
  $('limpar').onclick = () => {
    if (confirm('Limpar os itens desta venda?')) {
      cart = [];
      $('receita').checked = false;
      renderCart();
    }
  };
  $('comparar').onclick = () => {
    $('comparacao-itens').innerHTML = products
      .filter(p => selected.has(p.produto_id))
      .map(p => `<article class="product-card">${details(p)}</article>`)
      .join('');
    $('comparacao').showModal();
  };
  document.querySelectorAll('[data-close]').forEach(
    b =>
      (b.onclick = () => {
        if (!busy) $(b.dataset.close).close();
      })
  );
  $('confirmacao').addEventListener('cancel', e => {
    if (busy) e.preventDefault();
  });
  $('revisar').onclick = () => {
    if ($('revisar').disabled) return;
    if (cart.some(i => i.product.requer_receita) && !$('receita').checked) {
      $('status').textContent = 'Confirme a conferência da receita para continuar.';
      $('receita').focus();
      return;
    }
    $('resumo').innerHTML =
      cart
        .map(
          i =>
            `<p>${i.qty} × ${esc(i.product.nome)} <strong>${money(Number(i.product.preco_venda) * i.qty)}</strong></p>`
        )
        .join('') +
      `<p><strong>Total: ${money(total())}</strong> · ${esc($('pagamento').selectedOptions[0].textContent)}</p>`;
    $('confirm-status').textContent = 'Confira itens e pagamento antes de concluir.';
    $('confirmacao').showModal();
  };
  $('concluir').onclick = async () => {
    if (busy || uncertain) return;
    busy = true;
    $('concluir').disabled = true;
    renderCart();
    const itens = [];
    cart.forEach(item => {
      let remaining = item.qty;
      item.product.lots.forEach(l => {
        const quantidade = Math.min(remaining, Number(l.quantidade));
        if (quantidade > 0)
          itens.push({
            estoque_id: l.estoque_id,
            quantidade,
            preco_unitario: item.product.preco_venda
          });
        remaining -= quantidade;
      });
    });
    try {
      const data = await api('/vendas/balcao', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          itens,
          tipo_pagamento: $('pagamento').value,
          receita_conferida: $('receita').checked
        })
      });
      cart = [];
      $('receita').checked = false;
      $('confirmacao').close();
      await load();
      $('status').textContent =
        `Venda #${data.id} concluída · ${money(data.valor_total)}. Estoque e financeiro atualizados.`;
      $('busca').focus();
    } catch (error) {
      uncertain = !error.confirmed;
      $('confirm-status').textContent = uncertain
        ? 'A conexão foi interrompida. Não repita a venda: peça ao responsável para conferir o histórico antes de iniciar outra.'
        : error.message + ' Volte e atualize preços e saldo antes de tentar novamente.';
    } finally {
      busy = false;
      $('concluir').disabled = uncertain;
      renderCart();
    }
  };
  document.addEventListener('keydown', e => {
    if (e.key === 'F2') {
      e.preventDefault();
      $('busca').focus();
      $('busca').select();
    }
    if (e.key === 'F8') {
      e.preventDefault();
      $('revisar').click();
    }
  });
  window.addEventListener('beforeunload', e => {
    if (cart.length || busy) {
      e.preventDefault();
      e.returnValue = '';
    }
  });
  load();
})();
