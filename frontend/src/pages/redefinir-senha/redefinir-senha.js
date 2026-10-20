'use strict';

const API_BASE = window.FarmaControlSettings
  ? window.FarmaControlSettings.API_BASE
  : 'http://localhost:5000';
const token = new URLSearchParams(location.search).get('token');
const form = document.getElementById('reset-form');
const message = document.getElementById('message');
const passwordInput = document.getElementById('password');
document.getElementById('toggle-password').addEventListener('click', () => {
  const showing = passwordInput.type === 'text';
  passwordInput.type = showing ? 'password' : 'text';
  document.querySelector('.eye-open').style.display = showing ? '' : 'none';
  document.querySelector('.eye-closed').style.display = showing ? 'none' : '';
  document
    .getElementById('toggle-password')
    .setAttribute('aria-label', showing ? 'Mostrar senha' : 'Ocultar senha');
});
if (!token) {
  form.hidden = true;
  message.textContent = 'Este link de recuperação é inválido.';
  message.className = 'reset-message error';
}
form.addEventListener('submit', async event => {
  event.preventDefault();
  const password = document.getElementById('password').value;
  const button = form.querySelector('button');
  button.disabled = true;
  message.textContent = '';
  try {
    const response = await fetch(`${API_BASE}/auth/redefinir-senha`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, password })
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.mensagem);
    form.hidden = true;
    message.textContent = 'Senha redefinida. Redirecionando para o acesso…';
    message.className = 'reset-message success';
    setTimeout(() => (location.href = '../acesso/acesso.html'), 1800);
  } catch (error) {
    message.textContent = error.message || 'Não foi possível redefinir a senha.';
    message.className = 'reset-message error';
  } finally {
    button.disabled = false;
  }
});
