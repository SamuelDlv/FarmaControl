# Guia de manutenção — Aplica validação, autorização, cabeçalhos, auditoria e agendamento no ciclo HTTP.
# Consulte docs/desenvolvimento.md para executar as verificações desta camada.
"""middleware: responsabilidades extraídas da aplicação Flask."""

from farmacontrol.core import access
from farmacontrol.core import database
from farmacontrol.core import responses
from farmacontrol.services import email as email_service
from farmacontrol.services.audit import write_event
from farmacontrol.services.settings_notifications import schedule as schedule_notifications
from flask import current_app as app
from flask import g
from flask import request
from flask import session
import logging
import os
import pymysql.cursors
import secrets

log = logging.getLogger("farmacontrol")


# Filtra mutações antes da rota; autenticação também verifica origem e tentativas.
# Os limites de senha são em bytes UTF-8, coerentes com o limite do bcrypt.
def validar_entrada():
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    if request.path.startswith("/auth/"):
        origin = request.headers.get("Origin")
        if origin and origin not in {request.host_url.rstrip("/"), *app.config["ALLOWED_ORIGINS"]}:
            return responses.err("Origem da requisição não autorizada.", status=403)
        # Sair deve continuar possível mesmo após esgotar tentativas de login.
        # Origem, CSRF e auditoria do logout permanecem obrigatórios.
        if request.path != '/auth/logout':
            g.auth_attempts = app.extensions["auth_limiter"].check_with_status(request.remote_addr or "unknown")
            g.auth_limit_scope = 'ip'
            retry = g.auth_attempts["retry_after"]
            if retry:
                response = app.make_response(responses.err("Muitas tentativas. Aguarde antes de tentar novamente.", status=429))
                response.headers["Retry-After"] = str(retry)
                return response
            if request.path != '/auth/login':
                g.auth_attempts = app.extensions['auth_action_limiter'].check_with_status(
                    (request.remote_addr or 'unknown', request.endpoint))
                g.auth_limit_scope = 'acao'
                if g.auth_attempts['retry_after']:
                    return responses.err('Muitas solicitações desta operação. Aguarde antes de tentar novamente.', status=429)
    if request.is_json:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return responses.err("Envie um objeto JSON válido.")
        if request.path.startswith(("/auth/", "/admin/")):
            for key in ("nome", "sobrenome", "email", "role", "perfil", "status", "token", "convite_token", "password", "senha"):
                if key in data and data[key] is not None:
                    value = data[key]
                    if not isinstance(value, str):
                        return responses.err("Campo deve ser texto.", campo=key)
                    try:
                        size = len(value.encode("utf-8"))
                    except UnicodeEncodeError:
                        return responses.err("Texto inválido.", campo=key)
                    maximum = 72 if key in {"password", "senha"} else 512
                    if size > maximum:
                        return responses.err(f"Campo deve ter no máximo {maximum} bytes UTF-8.", campo=key)
    return None


def payload_grande(_error):
    return responses.err("Corpo da requisição excede o limite de 1 MiB.", status=413)


def security_headers(response):
    attempts = getattr(g, "auth_attempts", None)
    if attempts and (response.status_code == 429 or
                     (request.path == "/auth/login" and response.status_code == 401)):
        data = response.get_json()
        remaining = attempts["remaining"]
        wait = attempts["reset_after"] if remaining == 0 else 0
        data.update(tentativas_restantes=remaining, aguarde_segundos=wait)
        scope = getattr(g, 'auth_limit_scope', 'ip')
        data['limite_escopo'] = scope
        if remaining:
            noun = "tentativa disponível" if remaining == 1 else "tentativas disponíveis"
            data["mensagem"] += f" Restam {remaining} {noun} antes do bloqueio temporário."
        else:
            minutes, seconds = divmod(wait, 60)
            label = {'conta': 'Limite de falhas desta conta atingido. ',
                     'ip': 'Limite de autenticação deste IP atingido. ',
                     'acao': 'Limite de solicitações desta operação atingido. '}[scope]
            data["mensagem"] = (label +
                                f"Aguarde {minutes:02d}:{seconds:02d} para tentar novamente.")
            response.headers["Retry-After"] = str(wait)
        response.set_data(app.json.dumps(data))
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "frame-ancestors 'none'; object-src 'none'; base-uri 'self'"
    if request.path.startswith(access.PROTECTED_API_PREFIXES + ("/auth/",)):
        response.headers["Cache-Control"] = "no-store"
    if app.config["APP_ENV"] == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    return response


# Combina sessão válida, permissão do módulo e proteção CSRF nas mutações.
# Ocultar botões no frontend não substitui estas verificações do servidor.
def proteger_api():
    """Exige sessao assinada, perfil autorizado e token anti-CSRF nas mutacoes."""
    path = request.path
    if path == "/configuracoes/visual" or request.method == "OPTIONS" or not path.startswith(access.PROTECTED_API_PREFIXES):
        return None
    failure = access.validar_sessao()
    if failure is not None:
        return failure
    usuario_id = g.usuario_id
    perfil = g.usuario_perfil
    permissoes = g.usuario_permissoes
    modulo = access.modulo_da_rota(path)
    escrita = request.method not in {'GET', 'HEAD', 'OPTIONS'}
    if path == '/admin/logs':
        modulo = 'log'
    permitido = access.pode_acessar_modulo(perfil, permissoes, modulo, escrita=escrita)
    if not permitido:
        log.warning("Acesso negado: usuario=%s perfil=%s rota=%s", usuario_id, perfil, path)
        return responses.err("Seu perfil nao tem permissao para acessar este recurso.", status=403)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        recebido = request.headers.get("X-CSRF-Token", "")
        esperado = session.get("csrf_token", "")
        if not esperado or not secrets.compare_digest(recebido.encode(), esperado.encode()):
            return responses.err("Requisicao invalida. Atualize a pagina e tente novamente.", status=403)
    g.usuario_id = usuario_id
    g.usuario_perfil = perfil
    g.usuario_permissoes = permissoes
    return None


def auditar_consultas(response):
    # Mutações já foram auditadas atomicamente no commit. Não grava arquivos,
    # polling visual público, preflight ou a própria leitura do histórico.
    if (getattr(g, "usuario_id", None) and not getattr(g, "audit_written", False)
            and request.method == "GET" and request.path != "/admin/logs"
            and response.status_code < 400):
        try:
            write_event(database.get_db(), response.status_code)
            database.get_db().commit()
        except pymysql.MySQLError as exc:
            database.get_db().rollback()
            log.error("Falha ao registrar consulta: %s", exc)
            return app.make_response(responses.err("Não foi possível registrar a consulta no log.", status=503))
    return response


def check_scheduled_notifications(response):
    if (not app.testing and response.status_code < 400 and request.method == 'GET'
            and request.path == '/dashboard/stats' and getattr(g, 'usuario_id', None)):
        if all(os.getenv(k) for k in ('BREVO_SMTP_LOGIN', 'BREVO_SMTP_PASSWORD', 'BREVO_SENDER_EMAIL')):
            schedule_notifications(app._get_current_object(), database.get_db, email_service.enviar_email_brevo)
    return response

