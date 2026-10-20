(() => {
  'use strict';
  const user = JSON.parse(sessionStorage.getItem('farmacontrol_usuario') || 'null');
  if (!user) {
    window.location.replace('../../acesso/acesso.html');
    return;
  }
  if (!['proprietario', 'admin', 'ti'].includes(user.perfil)) {
    window.location.replace('../dashboard/dashboard.html');
    return;
  }
  const roles = {
    proprietario: 'Proprietário',
    admin: 'Gerente / Administrador',
    ti: 'TI / Suporte',
    farmaceutico: 'Farmacêutico',
    atendente: 'Atendente',
    compras: 'Compras',
    visualizador: 'Visualizador'
  };
  const name = `${user.nome || ''} ${user.sobrenome || ''}`.trim();
  document.getElementById('user-name').textContent = name || 'Usuário';
  document.getElementById('user-role').textContent = roles[user.perfil];
  document.getElementById('user-avatar').textContent = name
    .split(/\s+/)
    .map(part => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();
  const status = document.getElementById('log-status');
  const rows = document.getElementById('log-rows');
  const previous = document.getElementById('anterior');
  const next = document.getElementById('proxima');
  const refresh = document.getElementById('atualizar');
  const filters = document.getElementById('log-filters');
  const userFilter = document.getElementById('filtro-usuario');
  const startFilter = document.getElementById('filtro-inicio');
  const endFilter = document.getElementById('filtro-fim');
  const searchFilter = document.getElementById('filtro-busca');
  const activityFilter = document.getElementById('filtro-atividade');
  function todayInBrasilia() {
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'America/Sao_Paulo',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    }).formatToParts(new Date());
    const value = type => parts.find(part => part.type === type).value;
    return `${value('year')}-${value('month')}-${value('day')}`;
  }
  startFilter.max = endFilter.max = todayInBrasilia();
  let appliedFilters = new URLSearchParams({ atividade: activityFilter.value }),
    usersLoaded = false;
  let cursors = [0],
    index = 0,
    nextCursor = null,
    loading = false;
  function showEmpty(message, error = false) {
    rows.replaceChildren();
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = 6;
    td.className = 'log-empty';
    td.textContent = message;
    tr.appendChild(td);
    rows.appendChild(tr);
    status.textContent = message;
    status.dataset.error = String(error);
    nextCursor = null;
    cursors = [0];
    index = 0;
    previous.disabled = next.disabled = true;
    document.getElementById('pagina').textContent = 'Página 1';
  }
  async function load(target = index, reset = false, proposedFilters = appliedFilters) {
    if (loading) return;
    loading = true;
    previous.disabled = next.disabled = refresh.disabled = true;
    Array.from(filters.elements).forEach(element => {
      element.disabled = true;
    });
    status.textContent = 'Carregando atividades…';
    status.dataset.error = 'false';
    try {
      const cursor = reset ? 0 : cursors[target];
      const params = new URLSearchParams(proposedFilters);
      params.set('limit', '50');
      params.set('antes', cursor);
      if (!usersLoaded || reset) params.set('incluir_usuarios', '1');
      const response = await fetch(`${window.FarmaControlSettings.API_BASE}/admin/logs?${params}`);
      const data = await response.json();
      if (!response.ok || !data.ok)
        throw new Error(data.mensagem || 'Não foi possível carregar o log.');
      if (!data.filtros || (params.has('incluir_usuarios') && !Array.isArray(data.usuarios))) {
        throw new Error(
          'O serviço de Log precisa ser atualizado. Reinicie o FarmaControl e tente novamente.'
        );
      }
      if (reset) cursors = [0];
      appliedFilters = new URLSearchParams(proposedFilters);
      if (Array.isArray(data.usuarios)) {
        const selected = userFilter.value;
        userFilter.replaceChildren(new Option('Todos os usuários', ''));
        data.usuarios.forEach(person =>
          userFilter.add(new Option(`${person.nome} (#${person.id})`, person.id))
        );
        userFilter.value = selected;
        usersLoaded = true;
      }
      index = target;
      nextCursor = data.proximo;
      rows.replaceChildren();
      for (const entry of data.logs) {
        const tr = document.createElement('tr');
        const date = new Date(entry.criado_em);
        const values = [
          Number.isNaN(date.getTime())
            ? '—'
            : date.toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo' }),
          `${entry.usuario_nome}${entry.usuario_id ? ` (#${entry.usuario_id})` : ''}`,
          roles[entry.perfil] || '—',
          entry.acao,
          entry.detalhes,
          entry.status_http >= 400 ? 'Não realizada' : 'Realizada'
        ];
        for (const [column, value] of values.entries()) {
          const td = document.createElement('td');
          if (column === 4) {
            const details = document.createElement('details');
            const summary = document.createElement('summary');
            summary.textContent = `Ver detalhes · Evento #${entry.id}`;
            const content = document.createElement('div');
            content.className = 'log-details';
            content.textContent = value || '—';
            details.append(summary, content);
            td.appendChild(details);
          } else {
            td.textContent = value || '—';
          }
          tr.appendChild(td);
        }
        rows.appendChild(tr);
      }
      status.textContent = data.logs.length
        ? `${data.logs.length} atividades nesta página · Horário de Brasília`
        : 'Nenhuma atividade encontrada para os filtros selecionados.';
      if (!data.logs.length) showEmpty('Nenhuma atividade encontrada. Altere ou limpe os filtros.');
      document.getElementById('pagina').textContent = `Página ${index + 1}`;
    } catch (error) {
      if (error.name !== 'AbortError') showEmpty(error.message, true);
    } finally {
      loading = false;
      previous.disabled = index === 0;
      next.disabled = !nextCursor;
      refresh.disabled = false;
      Array.from(filters.elements).forEach(element => {
        element.disabled = false;
      });
    }
  }
  refresh.addEventListener('click', () => load(0, true));
  filters.addEventListener('submit', event => {
    event.preventDefault();
    const today = todayInBrasilia();
    startFilter.max = endFilter.max = today;
    if (startFilter.value > today || endFilter.value > today) {
      showEmpty(
        'Não é possível consultar atividades em datas futuras. Escolha uma data até hoje.',
        true
      );
      (startFilter.value > today ? startFilter : endFilter).focus();
      return;
    }
    if (!startFilter.checkValidity() || !endFilter.checkValidity()) {
      showEmpty('Informe uma data válida para consultar as atividades.', true);
      return;
    }
    if (startFilter.value && endFilter.value && startFilter.value > endFilter.value) {
      showEmpty('A data final deve ser igual ou posterior à data inicial.', true);
      endFilter.focus();
      return;
    }
    const values = new URLSearchParams();
    if (searchFilter.value.trim()) values.set('busca', searchFilter.value.trim());
    if (activityFilter.value) values.set('atividade', activityFilter.value);
    if (userFilter.value) values.set('usuario_id', userFilter.value);
    if (startFilter.value) values.set('data_inicio', startFilter.value);
    if (endFilter.value) values.set('data_fim', endFilter.value);
    load(0, true, values);
  });
  document.getElementById('limpar-filtros').addEventListener('click', () => {
    filters.reset();
    activityFilter.value = '';
    load(0, true, new URLSearchParams());
  });
  previous.addEventListener('click', () => load(index - 1));
  next.addEventListener('click', () => {
    cursors[index + 1] = nextCursor;
    load(index + 1);
  });
  load();
})();
