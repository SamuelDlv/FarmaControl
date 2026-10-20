'use strict';
const API_BASE = window.FarmaControlSettings
  ? window.FarmaControlSettings.API_BASE
  : 'http://localhost:5000';
const params = new URLSearchParams(location.search),
  token = params.get('convite'),
  statusEl = document.getElementById('status'),
  form = document.getElementById('invite-form');
function fail(message) {
  statusEl.textContent = message;
  statusEl.className = 'error';
}
document.querySelectorAll('.eye-toggle').forEach(button => {
  button.addEventListener('click', () => {
    const input = document.getElementById(button.dataset.target);
    const isPassword = input.type === 'password';
    input.type = isPassword ? 'text' : 'password';
    button.querySelector('.eye-open').style.display = isPassword ? 'none' : '';
    button.querySelector('.eye-closed').style.display = isPassword ? '' : 'none';
    const label = isPassword ? 'Ocultar senha' : 'Mostrar senha';
    button.setAttribute('aria-label', label);
  });
});
async function main() {
  if (!token) return fail('Convite ausente.');
  if (params.get('recusar') === '1') {
    if (!confirm('Deseja recusar este convite? Nenhuma conta será criada.'))
      return fail('Convite não foi recusado.');
    const res = await fetch(`${API_BASE}/auth/convites/${encodeURIComponent(token)}/recusar`, {
        method: 'POST'
      }),
      data = await res.json();
    return res.ok && data.ok
      ? (statusEl.textContent = 'Convite recusado. Nenhuma conta foi criada.')
      : fail(data.mensagem || 'Não foi possível recusar o convite.');
  }
  const res = await fetch(`${API_BASE}/auth/convites/${encodeURIComponent(token)}`),
    data = await res.json();
  if (!res.ok || !data.ok) return fail(data.mensagem || 'Convite inválido ou expirado.');
  const c = data.convite;
  document.getElementById('nome').value = c.nome;
  document.getElementById('sobrenome').value = c.sobrenome;
  document.getElementById('email').value = c.email;
  document.getElementById('perfil').value = c.role;
  statusEl.textContent = 'Confira seus dados, defina sua senha e confirme os documentos legais.';
  form.hidden = false;
}
form.addEventListener('submit', async e => {
  e.preventDefault();
  const senha = document.getElementById('senha').value;
  if (senha !== document.getElementById('confirmar').value) return fail('As senhas não coincidem.');
  if (!document.getElementById('termos').checked || !document.getElementById('privacidade').checked)
    return fail('É necessário aceitar os Termos e a Política de Privacidade.');
  const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        password: senha,
        accepts_terms: true,
        accepts_privacy: true,
        convite_token: token
      })
    }),
    data = await res.json();
  if (!res.ok || !data.ok) return fail(data.mensagem || 'Não foi possível concluir o cadastro.');
  sessionStorage.setItem('farmacontrol_usuario', JSON.stringify(data.usuario));
  sessionStorage.setItem('farmacontrol_csrf', data.csrf_token);
  location.href = '../sistema/dashboard/dashboard.html';
});
main();
