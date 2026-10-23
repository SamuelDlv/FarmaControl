"""
FARMAControl — Backend API (Flask + MariaDB)
══════════════════════════════════════════════

Sistema de gestão para farmácias.

ARQUITETURA:
├── Flask App: Servidor HTTP RESTful
├── Database: MariaDB/MySQL via PyMySQL (conexão por requisição)
├── Auth: cookie Flask assinado e HttpOnly; CSRF nas mutações
├── CORS: Somente origens explicitamente configuradas (mesma origem por padrão)
└── Logging: Console com timestamp e nível

ROTA DE ARQUIVOS:
├── frontend/     → Servido como static files
├── .env          → Configurações (DB_HOST, DB_USER, etc.)
├── schema.sql    → Schema do banco de dados
└── requirements.txt → Dependências Python

DEPENDÊNCIAS:
- flask: Framework web
- flask-cors: CORS middleware
- pymysql: Driver MySQL
- bcrypt: Hash de senhas
- python-dotenv: Carrega .env

ENDPOINTS PRINCIPAIS:
├── GET  /dashboard/stats        → KPIs do dashboard
├── GET  /financeiro/stats       → KPIs financeiros
├── GET  /financeiro/transacoes  → Tabela de transações
├── GET  /financeiro/fluxo       → Fluxo de caixa para gráfico
├── GET  /financeiro/categorias  → Lista de categorias
├── GET  /estoque                → Lotes; paginação feita no frontend
├── POST /estoque                → Criar produto
├── PUT  /estoque/<id>           → Editar produto
├── DELETE /estoque/<id>         → Excluir produto
├── GET  /admin/usuarios               → Lista de usuários
├── POST /auth/register          → Criar cadastro pendente
├── POST /auth/login             → Autenticar
├── POST /auth/register          → Cadastrar novo usuário
└── GET  /configuracoes          → Configurações globais do sistema
"""

import os
import re
import logging
import math
import mimetypes
import secrets
import html
import hashlib
import smtplib
import ssl
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from email.utils import formataddr
from decimal import Decimal, InvalidOperation

import bcrypt
import pymysql
import pymysql.cursors
from dotenv import load_dotenv
from flask import Flask, jsonify, request, g, session
from flask_cors import CORS
from runtime_config import runtime_config
from security import AuthLimiter, credential_stamp
from audit import commit_audit, write_event
from reporting import stock_report, PERIOD_START
from product_rules import normalize_product, validate_expiry, stock_product_data, save_product
from system_settings import read_settings, validate_settings, require_lot, require_usable_stock, active_alerts
from settings_notifications import schedule as schedule_notifications

# ─────────────────────────────────────────────
#  Configuração inicial
# ─────────────────────────────────────────────
# O servidor pode ser iniciado pela raiz do projeto ou pela pasta backend.
# Carregar pelo caminho deste arquivo evita perder DB_PASSWORD nesse primeiro caso.
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("farmacontrol")

app = Flask(__name__)
app.config.update(runtime_config(os.environ))
if app.config["EPHEMERAL_SECRET"]:
    log.warning("SECRET_KEY ausente ou fraca: chave temporária local; sessões expiram ao reiniciar.")
ALLOWED_ORIGINS = app.config["ALLOWED_ORIGINS"]
if ALLOWED_ORIGINS:
    CORS(app, origins=ALLOWED_ORIGINS, supports_credentials=True, allow_private_network=False)

BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", 12))

# ─────────────────────────────────────────────
#  Conexão com o banco
# ─────────────────────────────────────────────

def get_db() -> pymysql.connections.Connection:
    """Retorna (e armazena em g) a conexão do banco para a requisição atual."""
    if "db" not in g:
        g.db = pymysql.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 3306)),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "farmacontrol"),
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
            connect_timeout=5,
        )
    return g.db


@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PERFIS_VALIDOS = {"proprietario", "farmaceutico", "admin", "atendente", "compras", "ti", "visualizador"}


def ok(data: dict, status: int = 200):
    return jsonify({"ok": True, **data}), status


def err(mensagem: str, status: int = 400, campo: str | None = None):
    body = {"ok": False, "mensagem": mensagem}
    if campo:
        body["campo"] = campo
    return jsonify(body), status


# A interface pode ocultar modulos, mas somente esta camada decide o que uma
# sessao pode realmente consultar ou alterar.
ALL_ROLES = PERFIS_VALIDOS
INVENTORY_ROLES = {"proprietario", "admin", "farmaceutico", "compras", "ti"}
REPORT_ROLES = {"proprietario", "admin", "farmaceutico", "compras", "ti"}
FINANCE_ROLES = {"proprietario", "admin", "ti"}
ADMIN_ROLES = {"proprietario", "admin", "ti"}
SALES_ROLES = {"proprietario", "admin", "farmaceutico", "atendente", "ti"}

# Todos os cargos usam a mesma matriz persistida de módulos exibidos na tela
# Usuários. O PDV mantém acesso operacional fixo em SALES_ROLES.
EDITABLE_PROFILE_SLUGS = (
    "proprietario", "admin", "farmaceutico", "atendente",
    "visualizador", "compras", "ti",
)
READ_ONLY_PROFILE_SLUGS = {"visualizador"}


def roles_permitidos(path: str, method: str) -> set[str]:
    """Retorna os perfis permitidos para a rota de API solicitada."""
    read_only = method in {"GET", "HEAD", "OPTIONS"}
    if path.startswith("/dashboard/"):
        return ALL_ROLES
    if path.startswith("/admin/"):
        return ADMIN_ROLES
    if path.startswith("/financeiro/"):
        return FINANCE_ROLES
    if path.startswith("/relatorios/"):
        return REPORT_ROLES
    # A coleção e seus itens compartilham os perfis; a fronteira "/" impede
    # que nomes parecidos (como /compras-falso) recebam acesso por acidente.
    if path in {"/compras", "/fornecedores"} or path.startswith(("/compras/", "/fornecedores/")):
        return INVENTORY_ROLES
    if path.startswith(("/alertas", "/movimentacoes-estoque")):
        return INVENTORY_ROLES
    if path.startswith(("/estoque", "/produtos", "/categorias-produto")):
        return ALL_ROLES if read_only else INVENTORY_ROLES
    if path.startswith(("/clientes", "/vendas", "/receitas")):
        return SALES_ROLES
    if path.startswith("/configuracoes"):
        # Leitura e necessaria para aplicar o tema de qualquer usuario.
        return ALL_ROLES if read_only else {"proprietario", "ti"}
    return set()


def modulo_da_rota(path: str) -> str | None:
    """Associa uma rota protegida ao mesmo módulo exibido no menu."""
    if path.startswith("/dashboard/"):
        return "dashboard"
    if path.startswith("/admin/"):
        return "usuarios"
    if path.startswith("/financeiro/"):
        return "financeiro"
    if path.startswith("/relatorios/"):
        return "relatorios"
    if path in {"/compras", "/fornecedores"} or path.startswith(("/compras/", "/fornecedores/")):
        return "compras"
    if path.startswith("/alertas"):
        return "vencimentos"
    if path.startswith(("/estoque", "/movimentacoes-estoque", "/produtos", "/categorias-produto")):
        return "estoque"
    if path.startswith(("/clientes", "/vendas", "/receitas")):
        return "vendas"
    if path.startswith("/configuracoes"):
        return "configuracoes"
    return None


def permissoes_efetivas(cursor, perfil: str) -> set[str]:
    """Lê a matriz persistida de módulos do cargo informado."""
    if perfil not in EDITABLE_PROFILE_SLUGS:
        return set()
    cursor.execute(
        """SELECT pp.modulo FROM perfil_permissoes pp
           JOIN perfis p ON p.id = pp.perfil_id
           WHERE p.slug = %s AND pp.permitido = 1""",
        (perfil,),
    )
    return {row["modulo"] for row in cursor.fetchall()}


PROTECTED_API_PREFIXES = (
    "/admin/", "/clientes", "/categorias-produto", "/produtos", "/fornecedores",
    "/estoque", "/movimentacoes-estoque", "/compras", "/vendas", "/receitas",
    "/alertas", "/configuracoes", "/dashboard/", "/relatorios/",
    "/financeiro/",
)


auth_limiter = AuthLimiter()


@app.before_request
def validar_entrada():
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    if request.path.startswith("/auth/"):
        origin = request.headers.get("Origin")
        if origin and origin not in {request.host_url.rstrip("/"), *ALLOWED_ORIGINS}:
            return err("Origem da requisição não autorizada.", status=403)
        g.auth_attempts = auth_limiter.check_with_status(request.remote_addr or "unknown")
        retry = g.auth_attempts["retry_after"]
        if retry:
            response = app.make_response(err("Muitas tentativas. Aguarde antes de tentar novamente.", status=429))
            response.headers["Retry-After"] = str(retry)
            return response
    if request.is_json:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return err("Envie um objeto JSON válido.")
        if request.path.startswith(("/auth/", "/admin/")):
            for key in ("nome", "sobrenome", "email", "role", "perfil", "status", "token", "convite_token", "password", "senha"):
                if key in data and data[key] is not None:
                    value = data[key]
                    if not isinstance(value, str):
                        return err("Campo deve ser texto.", campo=key)
                    try:
                        size = len(value.encode("utf-8"))
                    except UnicodeEncodeError:
                        return err("Texto inválido.", campo=key)
                    maximum = 72 if key in {"password", "senha"} else 512
                    if size > maximum:
                        return err(f"Campo deve ter no máximo {maximum} bytes UTF-8.", campo=key)
    return None


@app.errorhandler(413)
def payload_grande(_error):
    return err("Corpo da requisição excede o limite de 1 MiB.", status=413)


@app.after_request
def security_headers(response):
    attempts = getattr(g, "auth_attempts", None)
    if attempts and (response.status_code == 429 or
                     (request.path == "/auth/login" and response.status_code == 401)):
        data = response.get_json()
        remaining = attempts["remaining"]
        wait = attempts["reset_after"] if remaining == 0 else 0
        data.update(tentativas_restantes=remaining, aguarde_segundos=wait)
        if remaining:
            noun = "tentativa disponível" if remaining == 1 else "tentativas disponíveis"
            data["mensagem"] += f" Restam {remaining} {noun} antes do bloqueio temporário."
        else:
            minutes, seconds = divmod(wait, 60)
            data["mensagem"] = ("Limite de tentativas atingido. "
                                f"Aguarde {minutes:02d}:{seconds:02d} para tentar novamente.")
            response.headers["Retry-After"] = str(wait)
        response.set_data(app.json.dumps(data))
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "frame-ancestors 'none'; object-src 'none'; base-uri 'self'"
    if request.path.startswith(PROTECTED_API_PREFIXES + ("/auth/",)):
        response.headers["Cache-Control"] = "no-store"
    if app.config["APP_ENV"] == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    return response


@app.before_request
def proteger_api():
    """Exige sessao assinada, perfil autorizado e token anti-CSRF nas mutacoes."""
    path = request.path
    # A tela de login conhece somente as preferencias visuais publicas.
    if path == "/configuracoes/visual" or request.method == "OPTIONS" or not path.startswith(PROTECTED_API_PREFIXES):
        return None
    usuario_id = session.get("usuario_id")
    perfil = session.get("perfil")
    if not usuario_id or perfil not in PERFIS_VALIDOS:
        return err("Sua sessao expirou. Entre novamente para continuar.", status=401)
    # A sessao e assinada, mas a conta pode ter sido bloqueada ou mudado de
    # perfil depois do login. A fonte de verdade continua sendo o banco.
    try:
        with get_db().cursor() as cur:
            cur.execute(
                """SELECT u.status, u.senha_hash, p.slug AS perfil
                   FROM usuarios u JOIN perfis p ON p.id = u.perfil_id
                   WHERE u.id = %s LIMIT 1""",
                (usuario_id,),
            )
            usuario_atual = cur.fetchone()
            permissoes = permissoes_efetivas(cur, usuario_atual["perfil"]) if usuario_atual else set()
    except pymysql.MySQLError as exc:
        log.error("Nao foi possivel validar sessao do usuario %s: %s", usuario_id, exc)
        return err("Nao foi possivel validar sua sessao. Tente novamente.", status=503)
    if not usuario_atual or usuario_atual["status"] != "aprovado":
        session.clear()
        return err("Sua conta nao possui mais acesso ao sistema.", status=401)
    stamp = session.get("credential_stamp", "")
    password_hash = usuario_atual.get("senha_hash")
    if (not isinstance(stamp, str) or not password_hash or not secrets.compare_digest(
            stamp, credential_stamp(app.config["SECRET_KEY"], password_hash))):
        session.clear()
        return err("Sua credencial mudou. Entre novamente.", status=401)
    perfil = usuario_atual["perfil"]
    session["perfil"] = perfil
    modulo = modulo_da_rota(path)
    # O Visualizador pode consultar exclusivamente; esta proteção não depende
    # do menu nem da configuração de módulos salva no banco.
    if perfil in READ_ONLY_PROFILE_SLUGS and request.method not in {"GET", "HEAD", "OPTIONS"}:
        return err("O perfil Visualizador possui acesso somente para consulta.", status=403)
    # PDV: acesso operacional fixo, também aplicado ao menu.
    permitido = perfil in SALES_ROLES if modulo == "vendas" else modulo in permissoes
    if path == "/admin/logs":
        permitido = perfil in ADMIN_ROLES
    if not permitido:
        log.warning("Acesso negado: usuario=%s perfil=%s rota=%s", usuario_id, perfil, path)
        return err("Seu perfil nao tem permissao para acessar este recurso.", status=403)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        recebido = request.headers.get("X-CSRF-Token", "")
        esperado = session.get("csrf_token", "")
        if not esperado or not secrets.compare_digest(recebido.encode(), esperado.encode()):
            return err("Requisicao invalida. Atualize a pagina e tente novamente.", status=403)
    g.usuario_id = usuario_id
    g.usuario_perfil = perfil
    g.usuario_permissoes = permissoes
    return None


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt(BCRYPT_ROUNDS)).decode()


def verificar_senha(senha: str, hash_: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode(), hash_.encode())
    except (ValueError, TypeError):
        return False


def registrar_acesso(cursor, usuario_id: int, sucesso: bool, motivo: str | None = None):
    """Grava log de tentativa de acesso."""
    g.audit_actor = usuario_id
    g.audit_description = "Entrou no sistema" if sucesso else "Falhou ao entrar: " + (motivo or "acesso negado")
    g.audit_status = 200 if sucesso else 401
    ip = request.remote_addr
    ua = request.headers.get("User-Agent", "")[:500]
    cursor.execute(
        """
        INSERT INTO log_acessos (usuario_id, ip, user_agent, sucesso, motivo_falha)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (usuario_id, ip, ua, int(sucesso), motivo),
    )


# ─────────────────────────────────────────────
#  Rotas de Autenticação
# ─────────────────────────────────────────────

@app.get("/health")
def health():
    """Verificação simples de que o servidor está rodando."""
    return ok({"status": "online", "ts": datetime.now(timezone.utc).isoformat()})


# ── Cadastro ────────────────────────────────

LEGAL_DOCUMENT_VERSION = "2026-10-05"
INVITE_EXPIRY_HOURS = 168
PASSWORD_RESET_EXPIRY_HOURS = 1


def hash_convite(token):
    """Armazena somente o hash do segredo presente no link de convite."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_token_recuperacao(token):
    """Não persiste o segredo presente no link de recuperação."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def montar_email_html(titulo, conteudo_html, acao_principal=None, acao_secundaria=None):
    """Monta o visual padrão dos e-mails transacionais do FarmaControl."""
    botoes = ""
    if acao_principal:
        texto, url = acao_principal
        botoes += (
            '<p style="margin:28px 0 18px;text-align:center;">'
            f'<a href="{html.escape(url, quote=True)}" '
            'style="display:inline-block;background:#166534;border-radius:8px;color:#ffffff;'
            'font-size:16px;font-weight:700;line-height:20px;padding:14px 24px;text-align:center;'
            'text-decoration:none;">'
            f'{html.escape(texto)}</a></p>'
        )
    if acao_secundaria:
        texto, url = acao_secundaria
        botoes += (
            '<p style="margin:0 0 8px;text-align:center;">'
            f'<a href="{html.escape(url, quote=True)}" '
            'style="color:#4b5563;font-size:14px;text-decoration:underline;">'
            f'{html.escape(texto)}</a></p>'
        )
    # Os convites legados já trazem seus links no conteúdo. Converte-os em
    # CTAs visuais para que continuem bonitos sem duplicar ou alterar URLs.
    contador_links = 0

    def estilizar_link(match):
        nonlocal contador_links
        contador_links += 1
        href, texto = match.groups()
        if contador_links == 1:
            estilo = (
                "display:inline-block;background:#166534;border:1px solid #166534;"
                "border-radius:8px;color:#ffffff;font-size:15px;font-weight:700;"
                "padding:12px 18px;text-decoration:none;"
            )
        else:
            estilo = (
                "display:inline-block;background:#ffffff;border:1px solid #9ca3af;"
                "border-radius:8px;color:#374151;font-size:15px;font-weight:700;"
                "padding:12px 18px;text-decoration:none;"
            )
        return f'<a href="{href}" style="{estilo}">{texto}</a>'

    conteudo_html = re.sub(
        r'<a href="([^"]+)">(.+?)</a>', estilizar_link, conteudo_html,
    ).replace("&nbsp;|&nbsp;", "&nbsp;")
    return f"""<!doctype html>
<html lang="pt-BR">
<body style="margin:0;padding:0;background:#f3f7f4;color:#1f2937;font-family:Arial,Helvetica,sans-serif;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;">{html.escape(titulo)}</div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f3f7f4;padding:32px 12px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:600px;background:#ffffff;border-radius:14px;overflow:hidden;">
        <tr><td style="background:#14532d;padding:24px 32px;color:#ffffff;font-size:23px;font-weight:700;letter-spacing:-0.4px;">FarmaControl</td></tr>
        <tr><td style="padding:34px 32px 28px;">
          <h1 style="margin:0 0 18px;color:#173321;font-size:25px;line-height:32px;">{html.escape(titulo)}</h1>
          <div style="color:#374151;font-size:16px;line-height:25px;">{conteudo_html}</div>
          {botoes}
        </td></tr>
        <tr><td style="border-top:1px solid #e5e7eb;padding:20px 32px;color:#6b7280;font-size:12px;line-height:18px;">
          Esta é uma mensagem automática do FarmaControl. Caso não reconheça esta solicitação, entre em contato com a equipe responsável.
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def enviar_email_brevo(destinatario, assunto, conteudo_html):
    """Envia e-mail transacional sem deixar indisponível o fluxo principal.

    A configuração vem exclusivamente do ambiente. Falhas no provedor são
    registradas sem incluir chave, destinatário ou conteúdo sensível nos logs.
    """
    host = os.getenv("BREVO_SMTP_HOST", "smtp-relay.brevo.com")
    porta = os.getenv("BREVO_SMTP_PORT", "587")
    login = os.getenv("BREVO_SMTP_LOGIN")
    senha = os.getenv("BREVO_SMTP_PASSWORD")
    remetente = os.getenv("BREVO_SENDER_EMAIL")
    nome_remetente = os.getenv("BREVO_SENDER_NAME", "FarmaControl")
    if not login or not senha or not remetente:
        log.info("E-mail transacional não enviado: SMTP da Brevo não configurado.")
        return False
    conteudo_html = montar_email_html(assunto, conteudo_html)
    try:
        mensagem = EmailMessage()
        mensagem["From"] = formataddr((nome_remetente, remetente))
        mensagem["To"] = destinatario
        mensagem["Subject"] = assunto
        mensagem.set_content("Abra este e-mail em um cliente compatível com HTML.")
        mensagem.add_alternative(conteudo_html, subtype="html")
        with smtplib.SMTP(host, int(porta), timeout=10) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(login, senha)
            smtp.send_message(mensagem)
        return True
    except (OSError, smtplib.SMTPException, ValueError) as exc:
        log.warning("Não foi possível enviar e-mail transacional pela Brevo: %s", exc)
    return False

@app.post("/auth/register")
def register():
    """
    Cria um novo usuário com status 'pendente'.
    O cadastro só se torna ativo após aprovação manual.
    """
    data = request.get_json(silent=True) or {}

    nome      = (data.get("nome") or "").strip()
    sobrenome = (data.get("sobrenome") or "").strip()
    email     = (data.get("email") or "").strip().lower()
    role      = (data.get("role") or "").strip()
    senha     = data.get("password") or ""
    aceita_termos = data.get("accepts_terms") is True
    aceita_privacidade = data.get("accepts_privacy") is True
    convite_token = (data.get("convite_token") or "").strip()
    convite_hash = None

    # Convites administrativos nunca assumem consentimento. O link assinado
    # recupera os dados definidos pelo administrador, e o convidado ainda
    # precisa escolher senha e aceitar os documentos legais nesta requisição.
    if convite_token:
        convite_hash = hash_convite(convite_token)
        try:
            with get_db().cursor() as cur:
                cur.execute("""
                    SELECT c.nome, c.sobrenome, c.email, p.slug AS perfil
                    FROM convites_cadastro c JOIN perfis p ON p.id = c.perfil_id
                    WHERE c.token_hash = %s AND c.status = 'pendente'
                      AND c.expira_em > NOW() FOR UPDATE
                """, (convite_hash,))
                convite = cur.fetchone()
            if not convite:
                return err("Este convite é inválido, já foi usado ou expirou.", campo="convite", status=410)
            nome, sobrenome, email, role = convite["nome"], convite["sobrenome"], convite["email"], convite["perfil"]
        except pymysql.MySQLError as exc:
            log.error("Erro ao validar convite: %s", exc)
            return err("Não foi possível validar o convite.", status=500)

    # ── Validações ──────────────────────────
    if len(nome) < 2:
        return err("Nome deve ter pelo menos 2 caracteres.", campo="nome")
    if len(sobrenome) < 2:
        return err("Sobrenome deve ter pelo menos 2 caracteres.", campo="sobrenome")
    if not EMAIL_RE.match(email):
        return err("Informe um e-mail válido.", campo="email")
    if role not in PERFIS_VALIDOS:
        return err("Perfil de acesso inválido.", campo="role")
    if len(senha) < 8:
        return err("A senha deve ter pelo menos 8 caracteres.", campo="password")
    if not aceita_termos or not aceita_privacidade:
        return err("É necessário aceitar os Termos de Uso e a Política de Privacidade.", campo="legal")

    db = None
    permissoes = set()
    try:
        db = get_db()
        with db.cursor() as cur:
            # E-mail já cadastrado?
            cur.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
            if cur.fetchone():
                return err("Este e-mail já está cadastrado.", campo="email", status=409)

            # Resolve perfil_id
            cur.execute("SELECT id, nome FROM perfis WHERE slug = %s", (role,))
            perfil = cur.fetchone()
            if not perfil:
                return err("Perfil não encontrado no sistema.", campo="role")
            permissoes = permissoes_efetivas(cur, role)

            senha_hash = hash_senha(senha)

            cur.execute(
                """
                INSERT INTO usuarios (nome, sobrenome, email, senha_hash, perfil_id, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (nome, sobrenome, email, senha_hash, perfil["id"], "aprovado" if convite_hash else "pendente"),
            )
            usuario_criado_id = cur.lastrowid
            cur.execute(
                """
                INSERT INTO aceites_legais (usuario_id, termos_versao, privacidade_versao, ip)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    usuario_criado_id,
                    LEGAL_DOCUMENT_VERSION,
                    LEGAL_DOCUMENT_VERSION,
                    (request.remote_addr or "")[:64],
                ),
            )
            if convite_hash:
                cur.execute("""
                    UPDATE convites_cadastro
                    SET status = 'aceito', respondido_em = NOW(), aceito_usuario_id = %s
                    WHERE token_hash = %s AND status = 'pendente' AND expira_em > NOW()
                """, (usuario_criado_id, convite_hash))
                if cur.rowcount != 1:
                    db.rollback()
                    return err("Este convite é inválido, já foi usado ou expirou.", status=410)
            g.audit_actor = usuario_criado_id
            commit_audit(db, cur.lastrowid)

        log.info("Novo cadastro pendente: %s (%s)", email, role)
        if convite_hash:
            session.clear()
            session.permanent = True
            session["usuario_id"] = usuario_criado_id
            session["credential_stamp"] = credential_stamp(app.config["SECRET_KEY"], senha_hash)
            session["perfil"] = role
            session["csrf_token"] = secrets.token_urlsafe(32)
            return ok({
                "mensagem": "Convite confirmado. Seu acesso já está liberado.",
                "csrf_token": session["csrf_token"],
                "usuario": {"id": usuario_criado_id, "nome": nome, "sobrenome": sobrenome,
                            "email": email, "perfil": role, "perfil_nome": perfil["nome"],
                            "permissoes": sorted(permissoes)},
            }, status=201)
        enviar_email_brevo(
            email,
            "Recebemos seu cadastro no FarmaControl",
            "<p>Recebemos seu cadastro. Ele será liberado após a análise da equipe responsável.</p>",
        )
        return ok(
            {
                "mensagem": (
                    "Cadastro realizado! Seu acesso será liberado após análise "
                    "da equipe responsável. Você receberá uma notificação."
                )
            },
            status=201,
        )

    except pymysql.MySQLError as exc:
        if db is not None:
            db.rollback()
        log.error("Erro DB no cadastro: %s", exc)
        return err("Erro interno. Tente novamente em instantes.", status=500)


@app.post("/auth/recuperar-senha")
def solicitar_recuperacao_senha():
    """Envia um link de uso único sem revelar se o e-mail possui conta."""
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    resposta = {"mensagem": "Se houver uma conta com este e-mail, enviaremos um link para redefinir a senha."}
    if not EMAIL_RE.match(email):
        return ok(resposta)

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT id, nome FROM usuarios WHERE email = %s AND status = 'aprovado'",
                (email,),
            )
            usuario = cur.fetchone()
            if not usuario:
                return ok(resposta)
            token = secrets.token_urlsafe(32)
            cur.execute(
                """UPDATE usuarios
                   SET token_reset = %s, token_expira_em = DATE_ADD(NOW(), INTERVAL %s HOUR)
                   WHERE id = %s""",
                (hash_token_recuperacao(token), PASSWORD_RESET_EXPIRY_HOURS, usuario["id"]),
            )
        g.audit_actor = usuario["id"]
        commit_audit(db, cur.lastrowid)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro ao solicitar recuperação de senha: %s", exc)
        return err("Não foi possível processar a solicitação. Tente novamente.", status=500)

    base_url = os.getenv("APP_PUBLIC_URL", "http://localhost:5000").rstrip("/")
    link = f"{base_url}/pages/redefinir-senha/redefinir-senha.html?token={token}"
    nome = html.escape(usuario.get("nome") or "usuário")
    enviar_email_brevo(
        email,
        "Redefina sua senha do FarmaControl",
        f"<p>Olá, {nome}.</p><p>Recebemos uma solicitação para redefinir sua senha.</p>"
        f'<p><a href="{link}">Redefinir minha senha</a></p>'
        "<p>Por segurança, este link expira em 1 hora e pode ser usado apenas uma vez.</p>",
    )
    return ok(resposta)


@app.post("/auth/redefinir-senha")
def redefinir_senha():
    """Define a senha por meio de token único, válido por tempo limitado."""
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    senha = data.get("password") or ""
    if len(senha) < 8:
        return err("A senha deve ter pelo menos 8 caracteres.", campo="password")
    if not token:
        return err("Este link de recuperação é inválido ou expirou.", status=410)

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """SELECT id FROM usuarios
                   WHERE token_reset = %s AND token_expira_em > NOW() FOR UPDATE""",
                (hash_token_recuperacao(token),),
            )
            usuario = cur.fetchone()
            if not usuario:
                return err("Este link de recuperação é inválido ou expirou.", status=410)
            cur.execute(
                """UPDATE usuarios
                   SET senha_hash = %s, token_reset = NULL, token_expira_em = NULL
                   WHERE id = %s""",
                (hash_senha(senha), usuario["id"]),
            )
        g.audit_actor = usuario["id"]
        commit_audit(db, cur.lastrowid)
        return ok({"mensagem": "Senha redefinida com sucesso. Você já pode entrar."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro ao redefinir senha: %s", exc)
        return err("Não foi possível redefinir a senha. Tente novamente.", status=500)


@app.get("/auth/convites/<string:token>")
def consultar_convite(token):
    """Permite à página de cadastro preencher apenas um convite ainda válido."""
    try:
        with get_db().cursor() as cur:
            cur.execute("""
                SELECT c.nome, c.sobrenome, c.email, p.slug AS role
                FROM convites_cadastro c JOIN perfis p ON p.id = c.perfil_id
                WHERE c.token_hash = %s AND c.status = 'pendente' AND c.expira_em > NOW()
            """, (hash_convite(token),))
            convite = cur.fetchone()
        if not convite:
            return err("Convite inválido, já utilizado ou expirado.", status=410)
        return ok({"convite": convite})
    except pymysql.MySQLError as exc:
        log.error("Erro ao consultar convite: %s", exc)
        return err("Não foi possível consultar o convite.", status=500)


@app.post("/auth/convites/<string:token>/recusar")
def recusar_convite(token):
    """Recusa um convite sem criar conta ou aceitar documentos legais."""
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                UPDATE convites_cadastro SET status = 'recusado', respondido_em = NOW()
                WHERE token_hash = %s AND status = 'pendente' AND expira_em > NOW()
            """, (hash_convite(token),))
            if not cur.rowcount:
                return err("Convite inválido, já utilizado ou expirado.", status=410)
        commit_audit(db, cur.lastrowid)
        return ok({"mensagem": "Convite recusado. Nenhuma conta foi criada."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro ao recusar convite: %s", exc)
        return err("Não foi possível recusar o convite.", status=500)


# ── Login ────────────────────────────────────

@app.post("/auth/login")
def login():
    """
    Autentica o usuário.
    Apenas usuários com status='aprovado' podem acessar o sistema.
    """
    data  = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    senha = data.get("password") or ""
    remember = data.get("remember", False)

    # Uma tentativa de trocar de conta nao pode manter a sessao anterior
    # ativa caso as novas credenciais sejam invalidas ou estejam pendentes.
    session.clear()

    if not EMAIL_RE.match(email):
        return err("Informe um e-mail válido.", campo="email")
    if not senha:
        return err("Informe sua senha.", campo="password")
    if not isinstance(remember, bool):
        return err("Valor de lembrar acesso inválido.", campo="remember")

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.nome, u.sobrenome, u.email,
                       u.senha_hash, u.status,
                       p.slug AS perfil, p.nome AS perfil_nome
                FROM   usuarios u
                JOIN   perfis   p ON p.id = u.perfil_id
                WHERE  u.email = %s
                LIMIT  1
                """,
                (email,),
            )
            usuario = cur.fetchone()

            # Usuário não encontrado — mensagem genérica (segurança)
            if not usuario:
                return err("E-mail ou senha incorretos.", status=401)

            # Verifica senha (timing-safe via bcrypt)
            senha_ok = verificar_senha(senha, usuario["senha_hash"])

            if not senha_ok:
                registrar_acesso(cur, usuario["id"], sucesso=False, motivo="senha incorreta")
                commit_audit(db, cur.lastrowid)
                return err("E-mail ou senha incorretos.", status=401)

            # Conta pendente
            if usuario["status"] == "pendente":
                registrar_acesso(cur, usuario["id"], sucesso=False, motivo="cadastro pendente")
                commit_audit(db, cur.lastrowid)
                return err(
                    "Seu cadastro ainda está sendo analisado. "
                    "Aguarde a aprovação da equipe responsável.",
                    status=403,
                )

            # Conta rejeitada
            if usuario["status"] == "rejeitado":
                registrar_acesso(cur, usuario["id"], sucesso=False, motivo="cadastro rejeitado")
                commit_audit(db, cur.lastrowid)
                return err(
                    "Seu cadastro foi recusado. "
                    "Entre em contato com o administrador do sistema.",
                    status=403,
                )

            # ── Login bem-sucedido ───────────────────
            permissoes = permissoes_efetivas(cur, usuario["perfil"])
            cur.execute(
                "UPDATE usuarios SET ultimo_login = NOW() WHERE id = %s",
                (usuario["id"],),
            )
            registrar_acesso(cur, usuario["id"], sucesso=True)
            commit_audit(db, cur.lastrowid)

        # Cookie assinado e HttpOnly: o cliente nao escolhe seu id/perfil.
        # Sem a opcao, o cookie expira ao fechar o navegador. Com ela marcada,
        # usa o prazo de PERMANENT_SESSION_LIFETIME configurado no ambiente.
        session.clear()
        session.permanent = remember
        session["usuario_id"] = usuario["id"]
        session["credential_stamp"] = credential_stamp(app.config["SECRET_KEY"], usuario["senha_hash"])
        session["perfil"] = usuario["perfil"]
        session["csrf_token"] = secrets.token_urlsafe(32)
        log.info("Login OK: %s (%s)", email, usuario["perfil"])
        return ok(
            {
                "mensagem": f"Bem-vindo, {usuario['nome']}!",
                "csrf_token": session["csrf_token"],
                "usuario": {
                    "id":          usuario["id"],
                    "nome":        usuario["nome"],
                    "sobrenome":   usuario["sobrenome"],
                    "email":       usuario["email"],
                    "perfil":      usuario["perfil"],
                    "perfil_nome": usuario["perfil_nome"],
                    # Ausência preserva o fallback visual dos perfis que não
                    # participam do editor; para os editáveis, inclusive uma
                    # lista vazia é uma decisão explícita.
                    "permissoes":  sorted(permissoes) if usuario["perfil"] in EDITABLE_PROFILE_SLUGS else None,
                },
            }
        )

    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB no login: %s", exc)
        return err("Erro interno. Tente novamente em instantes.", status=500)


@app.post("/auth/logout")
def logout():
    """Invalida a sessao atual no navegador."""
    esperado = session.get("csrf_token")
    recebido = request.headers.get("X-CSRF-Token", "")
    if esperado and not secrets.compare_digest(recebido.encode(), esperado.encode()):
        return err("Requisicao invalida.", status=403)
    if session.get("usuario_id"):
        try:
            commit_audit(get_db())
        except pymysql.MySQLError:
            get_db().rollback()
            return err("Não foi possível registrar a saída. Tente novamente.", status=503)
    session.clear()
    return ok({"mensagem": "Sessao encerrada."})


# ── Admin: listar pendentes ──────────────────

@app.get("/admin/usuarios")
def listar_usuarios():
    """
    Lista todos os usuários do sistema para o painel administrativo.
    """
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.nome, u.sobrenome, u.email, u.status,
                       p.slug AS perfil, p.nome AS perfil_nome,
                       u.ultimo_login AS ultimo_acesso, u.criado_em
                FROM   usuarios u
                JOIN   perfis   p ON p.id = u.perfil_id
                ORDER  BY u.nome ASC
                """
            )
            usuarios = cur.fetchall()

        # Serializa datas e formata nomes
        for row in usuarios:
            row["nome"] = f"{row['nome']} {row['sobrenome']}".strip()
            if isinstance(row.get("ultimo_acesso"), datetime):
                row["ultimo_acesso"] = row["ultimo_acesso"].isoformat()
            if isinstance(row.get("criado_em"), datetime):
                row["criado_em"] = row["criado_em"].isoformat()
            
            # Ajuste de status para o frontend
            # Backend: pendente, aprovado, rejeitado
            # Frontend espera: ativo, inativo, pendente
            if row["status"] == "aprovado":
                row["status"] = "ativo"
            elif row["status"] == "rejeitado":
                row["status"] = "inativo"

        return ok({"usuarios": usuarios})

    except pymysql.MySQLError as exc:
        log.error("Erro DB ao listar usuários: %s", exc)
        return err("Erro interno.", status=500)


@app.get("/admin/logs")
def listar_logs():
    """Histórico somente para consulta, com paginação por cursor estável."""
    try:
        limit = max(1, min(100, int(request.args.get("limit", "50"))))
        before = int(request.args.get("antes", "0"))
        if before < 0:
            raise ValueError
    except (ValueError, TypeError):
        return err("Paginação inválida.")
    conditions, params = [], []
    if before:
        conditions.append("id < %s")
        params.append(before)
    try:
        user_id = request.args.get("usuario_id", "")
        if user_id:
            if int(user_id) < 1:
                raise ValueError
            conditions.append("usuario_id = %s")
            params.append(int(user_id))
        dates = {}
        for key in ("data_inicio", "data_fim"):
            value = request.args.get(key, "")
            if value:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                    raise ValueError
                dates[key] = datetime.strptime(value, "%Y-%m-%d")
        if len(dates) == 2 and dates["data_inicio"] > dates["data_fim"]:
            raise ValueError
        today = datetime.now(timezone(timedelta(hours=-3))).date()
        if any(value.date() > today for value in dates.values()):
            return err("Não é possível consultar atividades em datas futuras. Escolha uma data até hoje.")
        # O filtro usa o mesmo horário de Brasília exibido pela tela (UTC-3).
        if "data_inicio" in dates:
            conditions.append("criado_em >= %s")
            params.append(dates["data_inicio"] + timedelta(hours=3))
        if "data_fim" in dates:
            conditions.append("criado_em < %s")
            params.append(dates["data_fim"] + timedelta(days=1, hours=3))
    except (ValueError, TypeError, OverflowError):
        return err("Informe um usuário válido e um período de datas válido.")
    search = request.args.get("busca", "").strip()
    activity = request.args.get("atividade", "")
    if len(search) > 120 or activity not in {"", "alteracoes", "consultas"}:
        return err("Informe uma busca de até 120 caracteres e uma atividade válida.")
    if search:
        conditions.append("(LOCATE(%s, acao) > 0 OR LOCATE(%s, detalhes) > 0 OR LOCATE(%s, usuario_nome) > 0)")
        params.extend([search] * 3)
    if activity:
        conditions.append("detalhes " + ("NOT LIKE" if activity == "alteracoes" else "LIKE") + " %s")
        params.append("GET %")
    try:
        users = None
        with get_db().cursor() as cur:
            if request.args.get("incluir_usuarios") == "1":
                # Todos os cadastros, mesmo sem atividade, e autores já excluídos.
                cur.execute("""SELECT u.id, TRIM(CONCAT(u.nome, ' ', COALESCE(u.sobrenome, ''))) AS nome
                               FROM usuarios u
                               UNION ALL
                               SELECT l.usuario_id AS id, MAX(l.usuario_nome) AS nome
                               FROM log_atividades l
                               WHERE l.usuario_id IS NOT NULL
                                 AND NOT EXISTS (SELECT 1 FROM usuarios u WHERE u.id = l.usuario_id)
                               GROUP BY l.usuario_id ORDER BY nome, id""")
                users = cur.fetchall()
            cur.execute(
                """SELECT id, usuario_id, usuario_nome, perfil, acao, detalhes, status_http, criado_em
                   FROM log_atividades """ + ("WHERE " + " AND ".join(conditions) + " " if conditions else "") +
                "ORDER BY id DESC LIMIT %s",
                tuple(params) + (limit + 1,),
            )
            rows = cur.fetchall()
        more = len(rows) > limit
        rows = rows[:limit]
        for row in rows:
            if isinstance(row.get("criado_em"), datetime):
                row["criado_em"] = row["criado_em"].replace(tzinfo=timezone.utc).isoformat()
        result = {"logs": rows, "proximo": rows[-1]["id"] if more else None,
                  "filtros": {key: request.args.get(key, "") for key in ("usuario_id", "data_inicio", "data_fim", "busca", "atividade")}}
        if users is not None:
            result["usuarios"] = users
        return ok(result)
    except pymysql.MySQLError as exc:
        log.error("Erro ao consultar histórico: %s", exc)
        return err("Não foi possível carregar o log. Verifique a migração 016.", status=503)


@app.after_request
def auditar_consultas(response):
    # Mutações já foram auditadas atomicamente no commit. Não grava arquivos,
    # polling visual público, preflight ou a própria leitura do histórico.
    if (getattr(g, "usuario_id", None) and not getattr(g, "audit_written", False)
            and request.method == "GET" and request.path != "/admin/logs"
            and response.status_code < 400):
        try:
            write_event(get_db(), response.status_code)
            get_db().commit()
        except pymysql.MySQLError as exc:
            get_db().rollback()
            log.error("Falha ao registrar consulta: %s", exc)
            return app.make_response(err("Não foi possível registrar a consulta no log.", status=503))
    return response


@app.get("/admin/pendentes")
def listar_pendentes():
    """
    Lista todos os cadastros aguardando análise.
    A sessão, o perfil administrativo e o CSRF são verificados em proteger_api.
    """
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.nome, u.sobrenome, u.email,
                       p.slug AS perfil, p.nome AS perfil_nome,
                       u.criado_em
                FROM   usuarios u
                JOIN   perfis   p ON p.id = u.perfil_id
                WHERE  u.status = 'pendente'
                ORDER  BY u.criado_em ASC
                """
            )
            pendentes = cur.fetchall()

        # Serializa datas
        for row in pendentes:
            if isinstance(row.get("criado_em"), datetime):
                row["criado_em"] = row["criado_em"].isoformat()

        return ok({"pendentes": pendentes})

    except pymysql.MySQLError as exc:
        log.error("Erro DB ao listar pendentes: %s", exc)
        return err("Erro interno. Tente novamente em instantes.", status=500)


PERMISSION_MODULES = (
    "dashboard", "estoque", "vencimentos", "relatorios",
    "compras", "financeiro", "usuarios", "configuracoes",
)


def require_profile_permissions_table(db):
    """Valida a migração permanente de permissões, sem alterar o schema em produção."""
    with db.cursor() as cur:
        cur.execute("SELECT 1 FROM perfil_permissoes LIMIT 1")


@app.get("/admin/perfis/permissoes")
def listar_permissoes_perfis():
    db = get_db()
    try:
        require_profile_permissions_table(db)
        with db.cursor() as cur:
            cur.execute("""
                SELECT p.slug, p.nome, pp.modulo, pp.permitido
                FROM perfis p
                LEFT JOIN perfil_permissoes pp ON pp.perfil_id = p.id
                WHERE p.slug IN (%s, %s, %s, %s, %s, %s, %s)
                ORDER BY FIELD(p.slug, 'proprietario', 'admin', 'farmaceutico', 'atendente', 'visualizador', 'compras', 'ti'), pp.modulo
            """, EDITABLE_PROFILE_SLUGS)
            rows = cur.fetchall()
        profiles = {}
        for row in rows:
            profile = profiles.setdefault(row["slug"], {"slug": row["slug"], "nome": row["nome"], "permissoes": []})
            if row["modulo"] and row["permitido"]:
                profile["permissoes"].append(row["modulo"])
        return ok({"perfis": list(profiles.values()), "modulos": list(PERMISSION_MODULES)})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro ao listar permissões de perfil: %s", exc)
        return err("Não foi possível carregar as permissões.", status=500)


@app.put("/admin/perfis/permissoes")
def atualizar_permissoes_perfis():
    data = request.get_json(silent=True) or {}
    changes = data.get("perfis")
    if not isinstance(changes, dict):
        return err("Informe as permissões por perfil.", campo="perfis")
    invalid_profiles = set(changes) - set(EDITABLE_PROFILE_SLUGS)
    if invalid_profiles:
        return err("Perfil inválido.", campo="perfis")
    for permissions in changes.values():
        if (not isinstance(permissions, list)
                or any(not isinstance(module, str) for module in permissions)
                or set(permissions) - set(PERMISSION_MODULES)):
            return err("Módulo de permissão inválido.", campo="perfis")
    db = get_db()
    try:
        require_profile_permissions_table(db)
        with db.cursor() as cur:
            for slug, permissions in changes.items():
                cur.execute("SELECT id FROM perfis WHERE slug = %s", (slug,))
                profile = cur.fetchone()
                if not profile:
                    return err("Perfil não encontrado.", campo="perfis", status=404)
                cur.execute("DELETE FROM perfil_permissoes WHERE perfil_id = %s", (profile["id"],))
                cur.executemany(
                    "INSERT INTO perfil_permissoes (perfil_id, modulo, permitido) VALUES (%s, %s, 1)",
                    [(profile["id"], module) for module in permissions],
                )
        g.audit_permissions = changes
        commit_audit(db)
        return ok({"mensagem": "Permissões atualizadas com sucesso."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro ao atualizar permissões de perfil: %s", exc)
        return err("Não foi possível salvar as permissões.", status=500)


@app.put("/admin/usuarios/<int:usuario_id>")
def editar_usuario(usuario_id):
    """
    Atualiza dados de um usuário existente (nome, e-mail, perfil e senha).
    A sessão, o perfil administrativo e o CSRF são verificados em proteger_api.
    Payload: { nome, email, perfil, senha, status }
    `status` aceita 'ativo' (aprovado) ou 'inativo' (rejeitado).
    """
    data = request.get_json(silent=True) or {}

    nome      = (data.get("nome") or "").strip() if "nome" in data else None
    email     = (data.get("email") or "").strip().lower() if "email" in data else None
    role      = (data.get("perfil") or "").strip() if "perfil" in data else None
    senha     = data.get("senha")
    status    = data.get("status")  # 'ativo' ou 'inativo'

    if nome is not None and len(nome) < 2:
        return err("Nome deve ter pelo menos 2 caracteres.", campo="nome")
    if email is not None and not EMAIL_RE.match(email):
        return err("Informe um e-mail válido.", campo="email")
    if role is not None and role not in PERFIS_VALIDOS:
        return err("Perfil de acesso inválido.", campo="perfil")
    if status and status not in ("ativo", "inativo"):
        return err("Status inválido. Use 'ativo' ou 'inativo'.", campo="status")
    if senha is not None and len(senha) < 8:
        return err("A senha deve ter pelo menos 8 caracteres.", campo="senha")
    if nome is None and email is None and role is None and senha is None and status is None:
        return err("Informe ao menos um campo para atualizar.")
    if usuario_id == g.usuario_id and status == "inativo":
        return err("Você não pode desativar sua própria conta enquanto estiver conectado.", status=409)

    # Mapeia o status amigável para o valor real do banco
    status_db = {"ativo": "aprovado", "inativo": "rejeitado"}.get(status)

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM usuarios WHERE id = %s", (usuario_id,))
            if not cur.fetchone():
                return err("Usuário não encontrado.", status=404)
            # E-mail já em uso por outro usuário?
            if email is not None:
                cur.execute("SELECT id FROM usuarios WHERE email = %s AND id != %s", (email, usuario_id))
                if cur.fetchone():
                    return err("Este e-mail já está em uso por outro usuário.", campo="email", status=409)

            set_parts = []
            values = []
            if nome is not None:
                set_parts.append("nome = %s")
                values.append(nome)
            if email is not None:
                set_parts.append("email = %s")
                values.append(email)

            if role is not None:
                cur.execute("SELECT id FROM perfis WHERE slug = %s", (role,))
                perfil = cur.fetchone()
                if not perfil:
                    return err("Perfil não encontrado no sistema.", campo="perfil")
                set_parts.append("perfil_id = %s")
                values.append(perfil["id"])

            if status_db:
                set_parts.append("status = %s")
                values.append(status_db)

            if senha is not None and senha:
                set_parts.extend(["senha_hash = %s", "token_reset = NULL", "token_expira_em = NULL"])
                values.append(hash_senha(senha))

            values.append(usuario_id)
            cur.execute(
                f"UPDATE usuarios SET {', '.join(set_parts)} WHERE id = %s",
                tuple(values),
            )
            commit_audit(db, cur.lastrowid)

        log.info("Usuário %s atualizado", usuario_id)
        return ok({"mensagem": "Usuário atualizado com sucesso."})

    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao editar usuário: %s", exc)
        return err("Erro interno. Tente novamente em instantes.", status=500)


# ── Admin: aprovar/rejeitar cadastro ─────────

@app.post("/admin/convites")
def criar_convite():
    """Cria convite pendente e envia ao destinatário links de aceitar/recusar."""
    data = request.get_json(silent=True) or {}
    nome = (data.get("nome") or "").strip()
    sobrenome = (data.get("sobrenome") or "").strip()
    email = (data.get("email") or "").strip().lower()
    role = (data.get("role") or "").strip()
    if len(nome) < 2 or len(sobrenome) < 2:
        return err("Informe nome e sobrenome.", campo="nome", status=400)
    if not EMAIL_RE.match(email):
        return err("Informe um e-mail válido.", campo="email", status=400)
    if role not in PERFIS_VALIDOS or role == "proprietario":
        return err("Perfil de convite inválido.", campo="role", status=400)

    token = secrets.token_urlsafe(32)
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
            if cur.fetchone():
                return err("Este e-mail já possui uma conta.", campo="email", status=409)
            cur.execute("SELECT id FROM perfis WHERE slug = %s", (role,))
            perfil = cur.fetchone()
            if not perfil:
                return err("Perfil não encontrado.", campo="role", status=400)
            # Substitui convite pendente anterior para o mesmo e-mail, sem
            # expor nem reutilizar o token anterior.
            cur.execute("UPDATE convites_cadastro SET status = 'expirado', respondido_em = NOW() WHERE email = %s AND status = 'pendente'", (email,))
            cur.execute("""
                INSERT INTO convites_cadastro
                    (nome, sobrenome, email, perfil_id, convidado_por_usuario_id, token_hash, expira_em)
                VALUES (%s, %s, %s, %s, %s, %s, DATE_ADD(NOW(), INTERVAL %s HOUR))
            """, (nome, sobrenome, email, perfil["id"], g.usuario_id, hash_convite(token), INVITE_EXPIRY_HOURS))
        commit_audit(db, cur.lastrowid)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro ao criar convite: %s", exc)
        return err("Não foi possível criar o convite.", status=500)

    base_url = os.getenv("APP_PUBLIC_URL", "http://localhost:5000").rstrip("/")
    aceitar_url = f"{base_url}/pages/convite/convite.html?convite={token}"
    recusar_url = f"{base_url}/pages/convite/convite.html?convite={token}&recusar=1"
    nome_seguro = html.escape(nome)
    enviado = enviar_email_brevo(
        email,
        "Convite para o FarmaControl",
        f"""<p>Olá, {nome_seguro}.</p>
        <p>Você recebeu um convite para criar seu acesso ao FarmaControl.</p>
        <p><a href=\"{aceitar_url}\">Aceitar convite</a> &nbsp;|&nbsp; <a href=\"{recusar_url}\">Recusar convite</a></p>
        <p>O convite expira em 7 dias. Ao aceitar, você definirá sua senha e confirmará os documentos legais.</p>""",
    )
    if not enviado:
        return err("O convite foi salvo, mas o e-mail não pôde ser enviado. Verifique o SMTP da Brevo antes de reenviar.", status=503)
    return ok({"mensagem": "Convite enviado por e-mail. A conta será criada somente se a pessoa aceitar os documentos legais.", "email": email}, status=201)

@app.delete("/admin/usuarios/<int:usuario_id>")
def excluir_usuario(usuario_id):
    """Remove uma conta sem permitir a autoexclusao da sessao atual."""
    if usuario_id == g.usuario_id:
        return err("Voce nao pode excluir a propria conta enquanto estiver conectado.", status=409)

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM usuarios WHERE id = %s", (usuario_id,))
            if not cur.fetchone():
                return err("Usuario nao encontrado.", status=404)
            # Aceites pertencem exclusivamente à conta. Ao excluir uma conta
            # sem histórico operacional, remove-se também esse dado pessoal;
            # movimentações e documentos operacionais continuam protegidos
            # pelas demais FKs RESTRICT.
            cur.execute("DELETE FROM aceites_legais WHERE usuario_id = %s", (usuario_id,))
            cur.execute("DELETE FROM usuarios WHERE id = %s", (usuario_id,))
            commit_audit(db, cur.lastrowid)
        log.info("Usuario %s excluido por %s", usuario_id, g.usuario_id)
        return ok({"mensagem": "Conta excluida com sucesso."})
    except pymysql.IntegrityError:
        db.rollback()
        return err(
            "Esta conta possui movimentacoes ou documentos vinculados e nao pode ser excluida. "
            "Desative a conta para preservar o historico.",
            status=409,
        )
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao excluir usuario %s: %s", usuario_id, exc)
        return err("Erro interno ao excluir a conta.", status=500)


@app.post("/admin/analisar-cadastro")
def analisar_cadastro():
    """
    Aprova ou rejeita um cadastro pendente.
    A sessão, o perfil administrativo e o CSRF são verificados em proteger_api.
    """
    data = request.get_json(silent=True) or {}
    usuario_id = data.get("usuario_id")
    decisao    = data.get("decisao") # 'aprovado' ou 'rejeitado'
    motivo     = data.get("motivo") # Opcional, para rejeição

    if not usuario_id or not isinstance(usuario_id, int):
        return err("ID do usuário inválido.", campo="usuario_id")
    if decisao not in ["aprovado", "rejeitado"]:
        return err("Decisão inválida. Use 'aprovado' ou 'rejeitado'.", campo="decisao")

    db = get_db()
    try:
        with db.cursor() as cur:
            # Verifica se o usuário existe e está pendente
            cur.execute("SELECT id, nome, email, status FROM usuarios WHERE id = %s", (usuario_id,))
            usuario = cur.fetchone()
            if not usuario:
                return err("Usuário não encontrado.", status=404)
            if usuario["status"] not in ("pendente", "aprovado", "rejeitado"):
                return err("O cadastro deste usuário não pode ser analisado.", status=400)

            # Atualiza o status do usuário
            cur.execute(
                "UPDATE usuarios SET status = %s WHERE id = %s",
                (decisao, usuario_id),
            )

            # Registra a análise
            cur.execute(
                """
                INSERT INTO analises_cadastro (usuario_id, analisado_por, decisao, motivo)
                VALUES (%s, %s, %s, %s)
                """,
                (usuario_id, g.usuario_id, decisao, motivo),
            )
            commit_audit(db, cur.lastrowid)

        log.info("Cadastro %s para usuário %s", decisao, usuario_id)
        nome_usuario = html.escape(usuario.get("nome") or "usuário")
        if decisao == "aprovado":
            assunto = "Seu acesso ao FarmaControl foi aprovado"
            corpo = f"<p>Olá, {nome_usuario}. Seu cadastro foi aprovado e seu acesso já está disponível.</p>"
        else:
            assunto = "Atualização sobre seu cadastro no FarmaControl"
            corpo = f"<p>Olá, {nome_usuario}. Seu cadastro não foi aprovado. Entre em contato com a equipe responsável para mais informações.</p>"
        enviar_email_brevo(usuario["email"], assunto, corpo)
        return ok({"mensagem": f"Cadastro {decisao} com sucesso."})

    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao analisar cadastro: %s", exc)
        return err("Erro interno. Tente novamente em instantes.", status=500)


# ─────────────────────────────────────────────
#  Rotas para Clientes
# ─────────────────────────────────────────────

@app.get("/clientes")
def get_clientes():
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM clientes")
            clientes = cur.fetchall()
        return ok({"clientes": clientes})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar clientes: %s", exc)
        return err("Erro interno ao buscar clientes.", status=500)

@app.get("/clientes/<int:cliente_id>")
def get_cliente(cliente_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM clientes WHERE id = %s", (cliente_id,))
            cliente = cur.fetchone()
            if not cliente:
                return err("Cliente não encontrado.", status=404)
        return ok({"cliente": cliente})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar cliente: %s", exc)
        return err("Erro interno ao buscar cliente.", status=500)

@app.post("/clientes")
def create_cliente():
    data = request.get_json(silent=True) or {}
    nome = data.get("nome")
    sobrenome = data.get("sobrenome")
    cpf = data.get("cpf")
    telefone = data.get("telefone")
    email = data.get("email")
    endereco = data.get("endereco")
    data_nascimento = data.get("data_nascimento")

    if not nome or not sobrenome:
        return err("Nome e sobrenome são obrigatórios.", status=400)

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO clientes (nome, sobrenome, cpf, telefone, email, endereco, data_nascimento)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (nome, sobrenome, cpf, telefone, email, endereco, data_nascimento)
            )
            commit_audit(db, cur.lastrowid)
            return ok({"mensagem": "Cliente criado com sucesso.", "id": cur.lastrowid}, status=201)
    except pymysql.IntegrityError as exc:
        db.rollback()
        if "Duplicate entry" in str(exc) and "cpf" in str(exc):
            return err("CPF já cadastrado.", campo="cpf", status=409)
        if "Duplicate entry" in str(exc) and "email" in str(exc):
            return err("Email já cadastrado.", campo="email", status=409)
        log.error("Erro DB ao criar cliente: %s", exc)
        return err("Erro interno ao criar cliente.", status=500)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao criar cliente: %s", exc)
        return err("Erro interno ao criar cliente.", status=500)

@app.put("/clientes/<int:cliente_id>")
def update_cliente(cliente_id):
    data = request.get_json(silent=True) or {}
    nome = data.get("nome")
    sobrenome = data.get("sobrenome")
    cpf = data.get("cpf")
    telefone = data.get("telefone")
    email = data.get("email")
    endereco = data.get("endereco")
    data_nascimento = data.get("data_nascimento")

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM clientes WHERE id = %s", (cliente_id,))
            if not cur.fetchone():
                return err("Cliente não encontrado.", status=404)

            cur.execute(
                """
                UPDATE clientes SET nome = %s, sobrenome = %s, cpf = %s, telefone = %s, email = %s, endereco = %s, data_nascimento = %s
                WHERE id = %s
                """,
                (nome, sobrenome, cpf, telefone, email, endereco, data_nascimento, cliente_id)
            )
            commit_audit(db, cur.lastrowid)
            return ok({"mensagem": "Cliente atualizado com sucesso."})
    except pymysql.IntegrityError as exc:
        db.rollback()
        if "Duplicate entry" in str(exc) and "cpf" in str(exc):
            return err("CPF já cadastrado para outro cliente.", campo="cpf", status=409)
        if "Duplicate entry" in str(exc) and "email" in str(exc):
            return err("Email já cadastrado para outro cliente.", campo="email", status=409)
        log.error("Erro DB ao atualizar cliente: %s", exc)
        return err("Erro interno ao atualizar cliente.", status=500)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao atualizar cliente: %s", exc)
        return err("Erro interno ao atualizar cliente.", status=500)

@app.delete("/clientes/<int:cliente_id>")
def delete_cliente(cliente_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM clientes WHERE id = %s", (cliente_id,))
            if not cur.fetchone():
                return err("Cliente não encontrado.", status=404)

            cur.execute("DELETE FROM clientes WHERE id = %s", (cliente_id,))
            commit_audit(db, cur.lastrowid)
            return ok({"mensagem": "Cliente excluído com sucesso."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao excluir cliente: %s", exc)
        return err("Erro interno ao excluir cliente.", status=500)


# ─────────────────────────────────────────────
#  Rotas para Categorias de Produtos
# ─────────────────────────────────────────────

@app.get("/categorias-produto")
def get_categorias_produto():
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM categorias_produto")
            categorias = cur.fetchall()
        return ok({"categorias": categorias})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar categorias de produto: %s", exc)
        return err("Erro interno ao buscar categorias de produto.", status=500)

@app.get("/categorias-produto/<int:categoria_id>")
def get_categoria_produto(categoria_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM categorias_produto WHERE id = %s", (categoria_id,))
            categoria = cur.fetchone()
            if not categoria:
                return err("Categoria de produto não encontrada.", status=404)
        return ok({"categoria": categoria})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar categoria de produto: %s", exc)
        return err("Erro interno ao buscar categoria de produto.", status=500)

@app.post("/categorias-produto")
def create_categoria_produto():
    data = request.get_json(silent=True) or {}
    nome = data.get("nome")
    descricao = data.get("descricao")

    if not nome:
        return err("Nome da categoria é obrigatório.", status=400)

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO categorias_produto (nome, descricao)
                VALUES (%s, %s)
                """,
                (nome, descricao)
            )
            commit_audit(db, cur.lastrowid)
            return ok({"mensagem": "Categoria de produto criada com sucesso.", "id": cur.lastrowid}, status=201)
    except pymysql.IntegrityError as exc:
        db.rollback()
        if "Duplicate entry" in str(exc) and "nome" in str(exc):
            return err("Nome da categoria já existe.", campo="nome", status=409)
        log.error("Erro DB ao criar categoria de produto: %s", exc)
        return err("Erro interno ao criar categoria de produto.", status=500)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao criar categoria de produto: %s", exc)
        return err("Erro interno ao criar categoria de produto.", status=500)

@app.put("/categorias-produto/<int:categoria_id>")
def update_categoria_produto(categoria_id):
    data = request.get_json(silent=True) or {}
    nome = data.get("nome")
    descricao = data.get("descricao")

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM categorias_produto WHERE id = %s", (categoria_id,))
            if not cur.fetchone():
                return err("Categoria de produto não encontrada.", status=404)

            cur.execute(
                """
                UPDATE categorias_produto SET nome = %s, descricao = %s
                WHERE id = %s
                """,
                (nome, descricao, categoria_id)
            )
            commit_audit(db, cur.lastrowid)
            return ok({"mensagem": "Categoria de produto atualizada com sucesso."})
    except pymysql.IntegrityError as exc:
        db.rollback()
        if "Duplicate entry" in str(exc) and "nome" in str(exc):
            return err("Nome da categoria já existe para outra categoria.", campo="nome", status=409)
        log.error("Erro DB ao atualizar categoria de produto: %s", exc)
        return err("Erro interno ao atualizar categoria de produto.", status=500)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao atualizar categoria de produto: %s", exc)
        return err("Erro interno ao atualizar categoria de produto.", status=500)

@app.delete("/categorias-produto/<int:categoria_id>")
def delete_categoria_produto(categoria_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM categorias_produto WHERE id = %s", (categoria_id,))
            if not cur.fetchone():
                return err("Categoria de produto não encontrada.", status=404)

            cur.execute("DELETE FROM categorias_produto WHERE id = %s", (categoria_id,))
            commit_audit(db, cur.lastrowid)
            return ok({"mensagem": "Categoria de produto excluída com sucesso."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao excluir categoria de produto: %s", exc)
        return err("Erro interno ao excluir categoria de produto.", status=500)


# ─────────────────────────────────────────────
#  Rotas para Produtos
# ─────────────────────────────────────────────

@app.get("/produtos")
def get_produtos():
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT p.*, cp.nome as categoria_nome FROM produtos p LEFT JOIN categorias_produto cp ON p.categoria_id = cp.id")
            produtos = cur.fetchall()
        return ok({"produtos": produtos})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar produtos: %s", exc)
        return err("Erro interno ao buscar produtos.", status=500)

@app.get("/produtos/<int:produto_id>")
def get_produto(produto_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT p.*, cp.nome as categoria_nome FROM produtos p LEFT JOIN categorias_produto cp ON p.categoria_id = cp.id WHERE p.id = %s", (produto_id,))
            produto = cur.fetchone()
            if not produto:
                return err("Produto não encontrado.", status=404)
        return ok({"produto": produto})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar produto: %s", exc)
        return err("Erro interno ao buscar produto.", status=500)

@app.post("/produtos")
def create_produto():
    data = request.get_json(silent=True) or {}
    try:
        product = normalize_product(data)
    except ValueError as exc:
        return err(str(exc), status=400)

    db = get_db()
    try:
        with db.cursor() as cur:
            if "estoque_minimo" not in data:
                product["estoque_minimo"] = int(read_settings(cur)["estoque_minimo_padrao"])
            product_id = save_product(cur, product)
            commit_audit(db, cur.lastrowid)
            return ok({"mensagem": "Produto criado com sucesso.", "id": product_id}, status=201)
    except ValueError as exc:
        db.rollback()
        return err(str(exc), status=400)
    except pymysql.IntegrityError as exc:
        db.rollback()
        if "Duplicate entry" in str(exc) and "codigo_barras" in str(exc):
            return err("Código de barras já cadastrado.", campo="codigo_barras", status=409)
        log.error("Erro DB ao criar produto: %s", exc)
        return err("Erro interno ao criar produto.", status=500)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao criar produto: %s", exc)
        return err("Erro interno ao criar produto.", status=500)

@app.put("/produtos/<int:produto_id>")
def update_produto(produto_id):
    data = request.get_json(silent=True) or {}

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM produtos WHERE id = %s FOR UPDATE", (produto_id,))
            current = cur.fetchone()
            if not current:
                return err("Produto não encontrado.", status=404)
            product = normalize_product(data, current)
            save_product(cur, product, produto_id)
            commit_audit(db, cur.lastrowid)
            return ok({"mensagem": "Produto atualizado com sucesso."})
    except ValueError as exc:
        db.rollback()
        return err(str(exc), status=400)
    except pymysql.IntegrityError as exc:
        db.rollback()
        if "Duplicate entry" in str(exc) and "codigo_barras" in str(exc):
            return err("Código de barras já cadastrado para outro produto.", campo="codigo_barras", status=409)
        log.error("Erro DB ao atualizar produto: %s", exc)
        return err("Erro interno ao atualizar produto.", status=500)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao atualizar produto: %s", exc)
        return err("Erro interno ao atualizar produto.", status=500)

@app.delete("/produtos/<int:produto_id>")
def delete_produto(produto_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM produtos WHERE id = %s", (produto_id,))
            if not cur.fetchone():
                return err("Produto não encontrado.", status=404)

            cur.execute("DELETE FROM produtos WHERE id = %s", (produto_id,))
            commit_audit(db, cur.lastrowid)
            return ok({"mensagem": "Produto excluído com sucesso."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao excluir produto: %s", exc)
        return err("Erro interno ao excluir produto.", status=500)


# ─────────────────────────────────────────────
#  Rotas para Fornecedores
# ─────────────────────────────────────────────

@app.get("/fornecedores")
def get_fornecedores():
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM fornecedores")
            fornecedores = cur.fetchall()
        return ok({"fornecedores": fornecedores})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar fornecedores: %s", exc)
        return err("Erro interno ao buscar fornecedores.", status=500)

@app.get("/fornecedores/<int:fornecedor_id>")
def get_fornecedor(fornecedor_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM fornecedores WHERE id = %s", (fornecedor_id,))
            fornecedor = cur.fetchone()
            if not fornecedor:
                return err("Fornecedor não encontrado.", status=404)
        return ok({"fornecedor": fornecedor})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar fornecedor: %s", exc)
        return err("Erro interno ao buscar fornecedor.", status=500)

@app.post("/fornecedores")
def create_fornecedor():
    data = request.get_json(silent=True) or {}
    nome_fantasia = data.get("nome_fantasia")
    razao_social = data.get("razao_social")
    cnpj = data.get("cnpj")
    contato_nome = data.get("contato_nome")
    contato_telefone = data.get("contato_telefone")
    contato_email = data.get("contato_email")
    endereco = data.get("endereco")

    if not nome_fantasia or not razao_social or not cnpj:
        return err("Nome fantasia, razão social e CNPJ são obrigatórios.", status=400)

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO fornecedores (nome_fantasia, razao_social, cnpj, contato_nome, contato_telefone, contato_email, endereco)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (nome_fantasia, razao_social, cnpj, contato_nome, contato_telefone, contato_email, endereco)
            )
            commit_audit(db, cur.lastrowid)
            return ok({"mensagem": "Fornecedor criado com sucesso.", "id": cur.lastrowid}, status=201)
    except pymysql.IntegrityError as exc:
        db.rollback()
        if "Duplicate entry" in str(exc) and "razao_social" in str(exc):
            return err("Razão social já cadastrada.", campo="razao_social", status=409)
        if "Duplicate entry" in str(exc) and "cnpj" in str(exc):
            return err("CNPJ já cadastrado.", campo="cnpj", status=409)
        log.error("Erro DB ao criar fornecedor: %s", exc)
        return err("Erro interno ao criar fornecedor.", status=500)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao criar fornecedor: %s", exc)
        return err("Erro interno ao criar fornecedor.", status=500)

@app.put("/fornecedores/<int:fornecedor_id>")
def update_fornecedor(fornecedor_id):
    data = request.get_json(silent=True) or {}
    nome_fantasia = data.get("nome_fantasia")
    razao_social = data.get("razao_social")
    cnpj = data.get("cnpj")
    contato_nome = data.get("contato_nome")
    contato_telefone = data.get("contato_telefone")
    contato_email = data.get("contato_email")
    endereco = data.get("endereco")

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM fornecedores WHERE id = %s", (fornecedor_id,))
            if not cur.fetchone():
                return err("Fornecedor não encontrado.", status=404)

            cur.execute(
                """
                UPDATE fornecedores SET nome_fantasia = %s, razao_social = %s, cnpj = %s, contato_nome = %s, contato_telefone = %s, contato_email = %s, endereco = %s
                WHERE id = %s
                """,
                (nome_fantasia, razao_social, cnpj, contato_nome, contato_telefone, contato_email, endereco, fornecedor_id)
            )
            commit_audit(db, cur.lastrowid)
            return ok({"mensagem": "Fornecedor atualizado com sucesso."})
    except pymysql.IntegrityError as exc:
        db.rollback()
        if "Duplicate entry" in str(exc) and "razao_social" in str(exc):
            return err("Razão social já cadastrada para outro fornecedor.", campo="razao_social", status=409)
        if "Duplicate entry" in str(exc) and "cnpj" in str(exc):
            return err("CNPJ já cadastrado para outro fornecedor.", campo="cnpj", status=409)
        log.error("Erro DB ao atualizar fornecedor: %s", exc)
        return err("Erro interno ao atualizar fornecedor.", status=500)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao atualizar fornecedor: %s", exc)
        return err("Erro interno ao atualizar fornecedor.", status=500)

@app.delete("/fornecedores/<int:fornecedor_id>")
def delete_fornecedor(fornecedor_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM fornecedores WHERE id = %s", (fornecedor_id,))
            if not cur.fetchone():
                return err("Fornecedor não encontrado.", status=404)

            cur.execute("DELETE FROM fornecedores WHERE id = %s", (fornecedor_id,))
            commit_audit(db, cur.lastrowid)
            return ok({"mensagem": "Fornecedor excluído com sucesso."})
    except pymysql.IntegrityError as exc:
        db.rollback()
        msg = str(exc)
        if "1451" in msg or "fk_compra_fornecedor" in msg:
            return err(
                "Este fornecedor não pode ser excluído porque possui pedidos de compra registrados. "
                "Exclua ou desvincule as compras antes, ou mantenha o fornecedor cadastrado para preservar o histórico.",
                status=409,
            )
        log.error("Erro DB ao excluir fornecedor: %s", exc)
        return err("Erro interno ao excluir fornecedor.", status=500)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao excluir fornecedor: %s", exc)
        return err("Erro interno ao excluir fornecedor.", status=500)


# ─────────────────────────────────────────────
#  Rotas para Estoque
# ─────────────────────────────────────────────

@app.get("/estoque")
def get_estoque():
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT e.*,
                       p.nome                        AS produto_nome,
                       p.tipo_produto, p.exige_validade, p.requer_receita,
                       p.preco_venda, p.categoria_id,
                       p.nome_generico               AS principio_ativo,
                       p.fabricante                  AS produto_fabricante,
                       COALESCE(p.preco_custo, 0)    AS preco_custo,
                       p.codigo_barras               AS produto_codigo_barras,
                       COALESCE(p.estoque_minimo, 0) AS estoque_minimo,
                       cp.nome                       AS categoria,
                       p.fornecedor_id               AS fornecedor_id,
                       f.nome_fantasia               AS fornecedor_nome,
                       COALESCE((
                           SELECT SUM(me.quantidade)
                           FROM   movimentacoes_estoque me
                           WHERE  me.estoque_id = e.id
                             AND  me.tipo_movimentacao = 'saida'
                             AND  me.data_movimentacao >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                       ), 0) AS saidas_30d
                FROM   estoque e
                JOIN   produtos p              ON e.produto_id   = p.id
                LEFT JOIN categorias_produto cp ON p.categoria_id = cp.id
                LEFT JOIN fornecedores f        ON p.fornecedor_id = f.id
                ORDER BY (e.data_validade IS NULL), e.data_validade ASC
            """)
            estoque = cur.fetchall()
        for row in estoque:
            for k in ("data_validade", "criado_em", "atualizado_em"):
                if row.get(k) and hasattr(row[k], "isoformat"):
                    row[k] = row[k].isoformat()
            for k in ("preco_custo", "saidas_30d"):
                if row.get(k) is not None:
                    row[k] = float(row[k])
        return ok({"estoque": estoque})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar estoque: %s", exc)
        return err("Erro interno ao buscar estoque.", status=500)

@app.get("/estoque/parametros")
def get_parametros_estoque():
    db = get_db()
    try:
        with db.cursor() as cur:
            settings = read_settings(cur)
        keys = ('estoque_minimo_padrao', 'estoque_maximo_padrao', 'ponto_reposicao',
                'controle_lote_obrigatorio', 'bloquear_produtos_vencidos', 'unidade_medida_padrao')
        return ok({'parametros': {key: settings[key] for key in keys}})
    except pymysql.MySQLError:
        return err('Erro ao carregar parâmetros de estoque.', status=500)


@app.get("/estoque/<int:estoque_id>")
def get_item_estoque(estoque_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT e.*,
                       p.nome          AS produto_nome,
                       p.tipo_produto, p.exige_validade, p.requer_receita,
                       p.preco_venda, p.categoria_id, p.fornecedor_id, p.estoque_minimo,
                       p.nome_generico AS produto_principio,
                       p.fabricante    AS produto_fabricante,
                       p.preco_custo   AS produto_preco_custo,
                       p.codigo_barras AS produto_codigo_barras,
                       cp.nome         AS produto_categoria
                FROM   estoque e
                JOIN   produtos p             ON e.produto_id   = p.id
                LEFT JOIN categorias_produto cp ON p.categoria_id = cp.id
                WHERE  e.id = %s
            """, (estoque_id,))
            item_estoque = cur.fetchone()
            if not item_estoque:
                return err("Item de estoque não encontrado.", status=404)
        for k in ("data_validade", "criado_em", "atualizado_em"):
            if item_estoque.get(k) and hasattr(item_estoque[k], "isoformat"):
                item_estoque[k] = item_estoque[k].isoformat()
        return ok({"item_estoque": item_estoque})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar item de estoque: %s", exc)
        return err("Erro interno ao buscar item de estoque.", status=500)

@app.post("/estoque")
def create_item_estoque():
    """
    Cria item de estoque. Aceita produto_id (int) OU produto_nome (str).
    Se produto_nome for enviado sem produto_id, tenta encontrar o produto pelo nome
    ou cria um novo produto com preco_custo e preco_venda padrão.
    """
    data = request.get_json(silent=True) or {}
    produto_id    = data.get("produto_id")
    produto_nome  = (data.get("produto_nome") or "").strip()
    lote          = (data.get("lote") or "").strip() or "SEM-LOTE"
    quantidade    = data.get("quantidade")
    data_validade = data.get("data_validade")
    localizacao   = data.get("localizacao")
    usuario_id    = g.usuario_id

    if not produto_id and not produto_nome:
        return err("Informe produto_id ou produto_nome.", status=400)
    if isinstance(quantidade, bool) or not isinstance(quantidade, int) or quantidade <= 0:
        return err("Quantidade deve ser maior que zero.", status=400)

    db = get_db()
    try:
        with db.cursor() as cur:
            if produto_id:
                cur.execute("SELECT * FROM produtos WHERE id = %s FOR UPDATE", (produto_id,))
                prod = cur.fetchone()
                if not prod:
                    return err("Produto não encontrado.", status=404)
            else:
                # Evita que itens homônimos sejam silenciosamente fundidos.
                cur.execute("SELECT id FROM produtos WHERE nome = %s LIMIT 1", (produto_nome,))
                if cur.fetchone():
                    return err("Já existe um produto com esse nome. Informe produto_id para adicionar um lote ao cadastro existente.", status=409)
                fields = stock_product_data(data)
                fields.setdefault("preco_custo", 0.01)
                fields.setdefault("preco_venda", 0.01)
                fields.setdefault("estoque_minimo", int(read_settings(cur)["estoque_minimo_padrao"]))
                prod = normalize_product(fields)
            require_lot(read_settings(cur), lote)
            data_validade = validate_expiry(data_validade, prod)
            if not produto_id:
                produto_id = save_product(cur, prod)

            cur.execute(
                """
                INSERT INTO estoque (produto_id, lote, quantidade, data_validade, localizacao)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (produto_id, lote, quantidade, data_validade, localizacao)
            )
            estoque_id = cur.lastrowid

            cur.execute(
                """
                INSERT INTO movimentacoes_estoque
                       (estoque_id, usuario_id, tipo_movimentacao, quantidade, observacao)
                VALUES (%s, %s, 'entrada', %s, %s)
                """,
                (estoque_id, usuario_id, quantidade, "Cadastro inicial de estoque")
            )

            g.audit_values = {"produto_id": produto_id}
            commit_audit(db, estoque_id)
            return ok({"mensagem": "Item de estoque criado com sucesso.",
                       "id": estoque_id, "produto_id": produto_id}, status=201)
    except ValueError as exc:
        db.rollback()
        return err(str(exc), status=400)
    except pymysql.IntegrityError as exc:
        db.rollback()
        if "Duplicate entry" in str(exc) and "uk_produto_lote" in str(exc):
            return err("Lote já cadastrado para este produto.", campo="lote", status=409)
        log.error("Erro DB ao criar item de estoque: %s", exc)
        return err("Erro interno ao criar item de estoque.", status=500)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao criar item de estoque: %s", exc)
        return err("Erro interno ao criar item de estoque.", status=500)

@app.put("/estoque/<int:estoque_id>")
def update_item_estoque(estoque_id):
    """
    Atualiza item de estoque. Aceita campos do produto (nome, principio, categoria)
    para atualizar o produto associado. Registra ajuste de movimentação com
    a autoria da sessão quando a quantidade muda.
    """
    data = request.get_json(silent=True) or {}
    produto_id        = data.get("produto_id")
    lote              = data.get("lote")
    quantidade        = data.get("quantidade")
    data_validade     = data.get("data_validade")
    localizacao       = data.get("localizacao")
    usuario_id        = g.usuario_id

    if quantidade is not None:
        if not isinstance(quantidade, int) or isinstance(quantidade, bool) or quantidade < 0:
            return err("Quantidade deve ser um número inteiro igual ou maior que zero.", campo="quantidade", status=400)

    db = get_db()
    try:
        with db.cursor() as cur:
            # O bloqueio protege o cálculo do ajuste contra outra baixa/entrada
            # concorrente no mesmo lote até o commit desta transação.
            cur.execute("SELECT id, produto_id, quantidade, data_validade FROM estoque WHERE id = %s FOR UPDATE", (estoque_id,))
            item_atual = cur.fetchone()
            if not item_atual:
                return err("Item de estoque não encontrado.", status=404)

            if lote is not None:
                require_lot(read_settings(cur), lote.strip())
            pid = produto_id or item_atual["produto_id"]

            cur.execute("SELECT * FROM produtos WHERE id = %s FOR UPDATE", (pid,))
            current = cur.fetchone()
            if not current:
                return err("Produto não encontrado.", status=404)
            product_fields = stock_product_data(data)
            product = normalize_product(product_fields, current)
            if "data_validade" in data or "exige_validade" in product_fields or produto_id is not None:
                data_validade = validate_expiry(data.get("data_validade", item_atual["data_validade"]), product)
            if product_fields:
                save_product(cur, product, pid)

            # Monta campos de estoque a atualizar
            campos, valores = [], []
            if produto_id is not None:
                campos.append("produto_id = %s"); valores.append(produto_id)
            if lote is not None:
                campos.append("lote = %s"); valores.append(lote.strip() or "SEM-LOTE")
            if quantidade is not None:
                campos.append("quantidade = %s"); valores.append(quantidade)
            if "data_validade" in data:
                campos.append("data_validade = %s"); valores.append(data_validade)
            if localizacao is not None:
                campos.append("localizacao = %s"); valores.append(localizacao)

            if campos:
                valores.append(estoque_id)
                cur.execute(
                    f"UPDATE estoque SET {', '.join(campos)} WHERE id = %s",
                    valores
                )

            # Registra ajuste de movimentação se quantidade mudou
            if quantidade is not None:
                delta = quantidade - item_atual["quantidade"]
                if delta != 0:
                    cur.execute(
                        """
                        INSERT INTO movimentacoes_estoque
                               (estoque_id, usuario_id, tipo_movimentacao, quantidade, observacao)
                        VALUES (%s, %s, 'ajuste', %s, %s)
                        """,
                        (estoque_id, usuario_id, abs(delta),
                         f"Ajuste manual: {'entrada' if delta > 0 else 'saída'} de {abs(delta)} unidades")
                    )

            commit_audit(db, cur.lastrowid)
            return ok({"mensagem": "Item de estoque atualizado com sucesso."})
    except ValueError as exc:
        db.rollback()
        return err(str(exc), status=400)
    except pymysql.IntegrityError as exc:
        db.rollback()
        if "Duplicate entry" in str(exc) and "uk_produto_lote" in str(exc):
            return err("Lote já cadastrado para este produto.", campo="lote", status=409)
        log.error("Erro DB ao atualizar item de estoque: %s", exc)
        return err("Erro interno ao atualizar item de estoque.", status=500)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao atualizar item de estoque: %s", exc)
        return err("Erro interno ao atualizar item de estoque.", status=500)

@app.delete("/estoque/<int:estoque_id>")
def delete_item_estoque(estoque_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM estoque WHERE id = %s FOR UPDATE", (estoque_id,))
            if not cur.fetchone():
                return err("Item de estoque não encontrado.", status=404)

            # Histórico de estoque é trilha de auditoria: um lote que já teve
            # movimentação não pode ser apagado silenciosamente.
            cur.execute("SELECT 1 FROM movimentacoes_estoque WHERE estoque_id = %s LIMIT 1", (estoque_id,))
            if cur.fetchone():
                return err("Não é possível excluir um item com movimentações. Zere o saldo por ajuste e mantenha o histórico.", status=409)
            cur.execute("DELETE FROM estoque WHERE id = %s", (estoque_id,))
            commit_audit(db, cur.lastrowid)
            return ok({"mensagem": "Item de estoque excluído com sucesso."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao excluir item de estoque: %s", exc)
        return err("Erro interno ao excluir item de estoque.", status=500)


# ─────────────────────────────────────────────
#  Rotas para Movimentações de Estoque
# ─────────────────────────────────────────────

@app.get("/estoque/<int:estoque_id>/historico")
def get_historico_estoque(estoque_id):
    """Retorna o histórico de movimentações de um item de estoque específico."""
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM estoque WHERE id = %s", (estoque_id,))
            if not cur.fetchone():
                return err("Item de estoque não encontrado.", status=404)
            cur.execute("""
                SELECT me.id, me.tipo_movimentacao, me.quantidade, me.observacao,
                       me.data_movimentacao,
                       u.nome AS usuario_nome
                FROM   movimentacoes_estoque me
                JOIN   usuarios u ON me.usuario_id = u.id
                WHERE  me.estoque_id = %s
                ORDER  BY me.data_movimentacao DESC
                LIMIT  50
            """, (estoque_id,))
            historico = cur.fetchall()
        for row in historico:
            if row.get("data_movimentacao") and hasattr(row["data_movimentacao"], "isoformat"):
                row["data_movimentacao"] = row["data_movimentacao"].isoformat()
        return ok({"historico": historico})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar histórico de estoque: %s", exc)
        return err("Erro interno ao buscar histórico de estoque.", status=500)

@app.get("/movimentacoes-estoque")
def get_movimentacoes_estoque():
    produto_id = request.args.get("produto_id", type=int)
    tipo = request.args.get("tipo")
    periodo_dias = request.args.get("periodo_dias", type=int)
    limite = request.args.get("limite", default=1000, type=int)
    offset = request.args.get('offset', default=0, type=int)
    period = request.args.get('periodo')
    search = request.args.get('busca', '').strip()
    if offset is None or offset < 0:
        return err('Página inválida.', campo='offset', status=400)
    if period is not None and period not in PERIOD_START:
        return err('Período inválido.', campo='periodo', status=400)
    tipos_validos = {"entrada", "saida", "ajuste", "transferencia"}
    if tipo and tipo not in tipos_validos:
        return err("Tipo de movimentação inválido.", campo="tipo", status=400)
    if produto_id is not None and produto_id <= 0:
        return err("Produto inválido.", campo="produto_id", status=400)
    if periodo_dias is not None and not 1 <= periodo_dias <= 3650:
        return err("Período deve estar entre 1 e 3650 dias.", campo="periodo_dias", status=400)
    if limite is None or not 1 <= limite <= 5000:
        return err("Limite deve estar entre 1 e 5000.", campo="limite", status=400)

    filtros, parametros = [], []
    if produto_id is not None:
        filtros.append("e.produto_id = %s")
        parametros.append(produto_id)
    if tipo:
        filtros.append("me.tipo_movimentacao = %s")
        parametros.append(tipo)
    if periodo_dias is not None:
        filtros.append("me.data_movimentacao >= DATE_SUB(CURDATE(), INTERVAL %s DAY)")
        parametros.append(periodo_dias)
    if period:
        filtros.append(f"me.data_movimentacao >= {PERIOD_START[period]} AND me.data_movimentacao < CURDATE() + INTERVAL 1 DAY")
    if search:
        filtros.append("p.nome LIKE %s")
        parametros.append('%' + search + '%')
    where = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT me.*, e.lote, p.nome AS produto_nome,
                       COALESCE(cp.nome, 'Sem Categoria') AS categoria,
                       COALESCE(p.preco_custo, 0) AS valor_unitario,
                       u.nome AS usuario_nome
                FROM   movimentacoes_estoque me
                JOIN   estoque e   ON me.estoque_id = e.id
                JOIN   produtos p  ON e.produto_id  = p.id
                LEFT JOIN categorias_produto cp ON p.categoria_id = cp.id
                JOIN   usuarios u  ON me.usuario_id = u.id
                {where}
                ORDER  BY me.data_movimentacao DESC, me.id DESC
                LIMIT  %s OFFSET %s
            """.format(where=where), (*parametros, limite, offset))
            movimentacoes = cur.fetchall()
            total = None
            if 'offset' in request.args:
                cur.execute(f"""SELECT COUNT(*) AS total FROM movimentacoes_estoque me
                    JOIN estoque e ON me.estoque_id=e.id JOIN produtos p ON e.produto_id=p.id
                    JOIN usuarios u ON me.usuario_id=u.id {where}""", tuple(parametros))
                total = int(cur.fetchone()['total'])
        for row in movimentacoes:
            if row.get("data_movimentacao") and hasattr(row["data_movimentacao"], "isoformat"):
                row["data_movimentacao"] = row["data_movimentacao"].isoformat()
            if row.get("valor_unitario") is not None:
                row["valor_unitario"] = float(row["valor_unitario"])
        return ok({"movimentacoes": movimentacoes, **({"total": total} if total is not None else {})})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar movimentações de estoque: %s", exc)
        return err("Erro interno ao buscar movimentações de estoque.", status=500)

@app.get("/movimentacoes-estoque/<int:movimentacao_id>")
def get_movimentacao_estoque(movimentacao_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT me.*, e.lote, p.nome as produto_nome, u.nome as usuario_nome FROM movimentacoes_estoque me JOIN estoque e ON me.estoque_id = e.id JOIN produtos p ON e.produto_id = p.id JOIN usuarios u ON me.usuario_id = u.id WHERE me.id = %s", (movimentacao_id,))
            movimentacao = cur.fetchone()
            if not movimentacao:
                return err("Movimentação de estoque não encontrada.", status=404)
        return ok({"movimentacao": movimentacao})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar movimentação de estoque: %s", exc)
        return err("Erro interno ao buscar movimentação de estoque.", status=500)

@app.post("/movimentacoes-estoque")
def create_movimentacao_estoque():
    data = request.get_json(silent=True) or {}
    estoque_id = data.get("estoque_id")
    usuario_id = g.usuario_id
    tipo_movimentacao = data.get("tipo_movimentacao")
    quantidade = data.get("quantidade")
    observacao = data.get("observacao")
    estoque_destino_id = data.get("estoque_destino_id")

    if not estoque_id or not tipo_movimentacao or not quantidade:
        return err("ID do estoque, tipo de movimentação e quantidade são obrigatórios.", status=400)
    if not isinstance(quantidade, int) or isinstance(quantidade, bool):
        return err("Quantidade deve ser um número inteiro.", campo="quantidade", status=400)
    if tipo_movimentacao not in ["entrada", "saida", "ajuste", "transferencia"]:
        return err("Tipo de movimentação inválido.", status=400)
    if tipo_movimentacao == "ajuste":
        if quantidade == 0:
            return err("Ajuste deve ser diferente de zero.", campo="quantidade", status=400)
    elif quantidade <= 0:
        return err("Quantidade deve ser maior que zero.", campo="quantidade", status=400)
    if tipo_movimentacao == "transferencia":
        if not isinstance(estoque_destino_id, int) or isinstance(estoque_destino_id, bool) or estoque_destino_id <= 0:
            return err("Informe o estoque de destino para a transferência.", campo="estoque_destino_id", status=400)
        if estoque_destino_id == estoque_id:
            return err("O estoque de destino deve ser diferente da origem.", campo="estoque_destino_id", status=400)

    db = get_db()
    try:
        with db.cursor() as cur:
            # Em transferências, a ordem fixa evita deadlock quando dois lotes
            # são transferidos simultaneamente em sentidos opostos.
            ids_bloqueio = sorted({estoque_id, estoque_destino_id}) if tipo_movimentacao == "transferencia" else [estoque_id]
            cur.execute(
                "SELECT id, produto_id, quantidade, lote, data_validade FROM estoque WHERE id IN (" + ", ".join(["%s"] * len(ids_bloqueio)) + ") FOR UPDATE",
                ids_bloqueio,
            )
            itens = {item["id"]: item for item in cur.fetchall()}
            item_estoque = itens.get(estoque_id)
            if not item_estoque:
                return err("Item de estoque não encontrado.", campo="estoque_id", status=400)
            item_destino = itens.get(estoque_destino_id) if tipo_movimentacao == "transferencia" else None
            if tipo_movimentacao == "transferencia" and not item_destino:
                return err("Item de estoque de destino não encontrado.", campo="estoque_destino_id", status=400)
            if tipo_movimentacao == "transferencia" and item_destino["produto_id"] != item_estoque["produto_id"]:
                return err("A transferência deve ocorrer entre lotes do mesmo produto.", campo="estoque_destino_id", status=400)

            settings = read_settings(cur)
            if tipo_movimentacao == 'saida':
                require_usable_stock(settings, item_estoque)
            elif tipo_movimentacao in ('entrada', 'transferencia'):
                require_lot(settings, item_estoque.get('lote'))
                if item_destino:
                    require_lot(settings, item_destino.get('lote'))
            nova_quantidade_estoque = item_estoque["quantidade"]
            if tipo_movimentacao == "entrada":
                nova_quantidade_estoque += quantidade
            elif tipo_movimentacao == "saida":
                if nova_quantidade_estoque < quantidade:
                    return err("Quantidade em estoque insuficiente para saída.", status=400)
                nova_quantidade_estoque -= quantidade
            elif tipo_movimentacao == "ajuste":
                if nova_quantidade_estoque + quantidade < 0:
                    return err("Quantidade em estoque insuficiente para ajuste de saída.", status=400)
                nova_quantidade_estoque += quantidade
            elif tipo_movimentacao == "transferencia":
                if nova_quantidade_estoque < quantidade:
                    return err("Quantidade em estoque insuficiente para transferência.", status=400)
                nova_quantidade_estoque -= quantidade

            cur.execute(
                "UPDATE estoque SET quantidade = %s WHERE id = %s",
                (nova_quantidade_estoque, estoque_id)
            )

            if tipo_movimentacao == "transferencia":
                cur.execute("UPDATE estoque SET quantidade = quantidade + %s WHERE id = %s", (quantidade, estoque_destino_id))

            cur.execute(
                """
                INSERT INTO movimentacoes_estoque (estoque_id, usuario_id, tipo_movimentacao, quantidade, observacao)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (estoque_id, usuario_id, tipo_movimentacao, quantidade, observacao)
            )
            if tipo_movimentacao == "transferencia":
                cur.execute(
                    """
                    INSERT INTO movimentacoes_estoque (estoque_id, usuario_id, tipo_movimentacao, quantidade, observacao)
                    VALUES (%s, %s, 'transferencia', %s, %s)
                    """,
                    (estoque_destino_id, usuario_id, quantidade, observacao or f"Transferência recebida do lote {estoque_id}"),
                )
            commit_audit(db, cur.lastrowid)
            return ok({"mensagem": "Movimentação de estoque criada com sucesso.", "id": cur.lastrowid}, status=201)
    except ValueError as exc:
        db.rollback()
        return err(str(exc), status=400)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao criar movimentação de estoque: %s", exc)
        return err("Erro interno ao criar movimentação de estoque.", status=500)


# ─────────────────────────────────────────────
#  Rotas para Compras
# ─────────────────────────────────────────────

@app.get("/compras")
def get_compras():
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT c.*,
                       f.nome_fantasia                     AS fornecedor_nome,
                       u.nome                           AS usuario_nome,
                       (
                           SELECT COUNT(*)
                           FROM   itens_compra ic
                           WHERE  ic.compra_id = c.id
                       )                                AS itens_count,
                       c.data_recebimento               AS data_entrega_prevista
                FROM   compras c
                LEFT JOIN fornecedores f ON c.fornecedor_id = f.id
                LEFT JOIN usuarios u    ON c.usuario_id    = u.id
                ORDER  BY c.criado_em DESC
            """)
            compras = cur.fetchall()
        # Carrega os itens de todas as compras em uma única consulta (N+1)
        ids = [c["id"] for c in compras]
        itens_map = {}
        if ids:
            with db.cursor() as cur2:
                cur2.execute("""
                    SELECT ic.*, p.nome AS produto_nome, p.exige_validade
                    FROM   itens_compra ic
                    JOIN   produtos p ON ic.produto_id = p.id
                    WHERE  ic.compra_id IN (%s)
                """ % (",".join(["%s"] * len(ids)),), tuple(ids))
                for item in cur2.fetchall():
                    itens_map.setdefault(item["compra_id"], []).append(item)
        for row in compras:
            for k in ("criado_em", "data_pedido", "data_recebimento", "atualizado_em", "data_entrega_prevista"):
                if row.get(k) and hasattr(row[k], "isoformat"):
                    row[k] = row[k].isoformat()
            if row.get("valor_total") is not None:
                row["valor_total"] = float(row["valor_total"])
            row["itens"] = itens_map.get(row["id"], [])
            for item in row["itens"]:
                if item.get("data_validade_recebida") and hasattr(item["data_validade_recebida"], "isoformat"):
                    item["data_validade_recebida"] = item["data_validade_recebida"].isoformat()
        return ok({"compras": compras})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar compras: %s", exc)
        return err("Erro interno ao buscar compras.", status=500)

@app.get("/compras/<int:compra_id>")
def get_compra(compra_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT c.*,
                       f.nome_fantasia AS fornecedor_nome,
                       u.nome          AS usuario_nome
                FROM   compras c
                LEFT JOIN fornecedores f ON c.fornecedor_id = f.id
                LEFT JOIN usuarios u    ON c.usuario_id    = u.id
                WHERE  c.id = %s
            """, (compra_id,))
            compra = cur.fetchone()
            if not compra:
                return err("Compra não encontrada.", status=404)
        for k in ("criado_em", "data_recebimento", "atualizado_em", "data_pedido"):
            if compra.get(k) and hasattr(compra[k], "isoformat"):
                compra[k] = compra[k].isoformat()
        # Busca itens da compra
        with db.cursor() as cur2:
            cur2.execute("""
                SELECT ic.*, p.nome AS produto_nome
                FROM   itens_compra ic
                JOIN   produtos p ON ic.produto_id = p.id
                WHERE  ic.compra_id = %s
            """, (compra_id,))
            compra["itens"] = cur2.fetchall()
        return ok({"compra": compra})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar compra: %s", exc)
        return err("Erro interno ao buscar compra.", status=500)

@app.post("/compras")
def create_compra():
    data = request.get_json(silent=True) or {}
    fornecedor_id = data.get("fornecedor_id")
    usuario_id = g.usuario_id
    valor_total = data.get("valor_total")
    status = data.get("status", "pendente")
    itens = data.get("itens", []) # Lista de dicionários com produto_id, quantidade, preco_unitario, lote_recebido, data_validade_recebida

    if not fornecedor_id or not valor_total:
        return err("Fornecedor e valor total são obrigatórios.", status=400)
    if valor_total <= 0:
        return err("Valor total deve ser maior que zero.", status=400)
    if status not in ["pendente", "recebido", "cancelado"]:
        return err("Status de compra inválido.", status=400)

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM fornecedores WHERE id = %s", (fornecedor_id,))
            if not cur.fetchone():
                return err("Fornecedor não encontrado.", campo="fornecedor_id", status=400)

            cur.execute(
                """
                INSERT INTO compras (fornecedor_id, usuario_id, valor_total, status)
                VALUES (%s, %s, %s, %s)
                """,
                (fornecedor_id, usuario_id, valor_total, status)
            )
            compra_id = cur.lastrowid

            for item in itens:
                produto_id = item.get("produto_id")
                quantidade = item.get("quantidade")
                preco_unitario = item.get("preco_unitario")
                lote_recebido = (item.get("lote_recebido") or "").strip() or "SEM-LOTE"
                data_validade_recebida = item.get("data_validade_recebida")

                if not produto_id or not quantidade or not preco_unitario:
                    db.rollback()
                    return err("Dados incompletos para item de compra.", status=400)

                cur.execute("SELECT id, exige_validade FROM produtos WHERE id = %s", (produto_id,))
                product = cur.fetchone()
                if not product:
                    db.rollback()
                    return err(f"Produto com ID {produto_id} não encontrado.", status=400)

                data_validade_recebida = validate_expiry(
                    data_validade_recebida, product if status == "recebido" else {"exige_validade": False})

                cur.execute(
                    """
                    INSERT INTO itens_compra (compra_id, produto_id, quantidade, preco_unitario, lote_recebido, data_validade_recebida)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (compra_id, produto_id, quantidade, preco_unitario, lote_recebido, data_validade_recebida)
                )

                # Se a compra foi recebida, atualiza o estoque
                if status == "recebido":
                    require_lot(read_settings(cur), lote_recebido)
                    cur.execute("SELECT id FROM estoque WHERE produto_id = %s AND lote = %s FOR UPDATE", (produto_id, lote_recebido))
                    estoque_item = cur.fetchone()
                    if estoque_item:
                        cur.execute("UPDATE estoque SET quantidade = quantidade + %s WHERE id = %s", (quantidade, estoque_item["id"]))
                    else:
                        cur.execute(
                            """
                            INSERT INTO estoque (produto_id, lote, quantidade, data_validade)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (produto_id, lote_recebido, quantidade, data_validade_recebida)
                        )
                    # Registrar movimentação de estoque
                    cur.execute(
                        """
                        INSERT INTO movimentacoes_estoque (estoque_id, usuario_id, tipo_movimentacao, quantidade, observacao)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (cur.lastrowid if not estoque_item else estoque_item["id"], usuario_id, "entrada", quantidade, f"Entrada por compra {compra_id}")
                    )

            g.audit_values = {"status": status}
            commit_audit(db, compra_id)
            return ok({"mensagem": "Compra criada com sucesso.", "id": compra_id}, status=201)
    except ValueError as exc:
        db.rollback()
        return err(str(exc), status=400)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao criar compra: %s", exc)
        return err("Erro interno ao criar compra.", status=500)

@app.put("/compras/<int:compra_id>")
def update_compra(compra_id):
    data = request.get_json(silent=True) or {}
    fornecedor_id = data.get("fornecedor_id")
    usuario_id = g.usuario_id
    valor_total = data.get("valor_total")
    status = data.get("status")
    data_recebimento = data.get("data_recebimento")

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id, status, usuario_id, valor_total, fornecedor_id FROM compras WHERE id = %s FOR UPDATE", (compra_id,))
            compra_existente = cur.fetchone()
            if not compra_existente:
                return err("Compra não encontrada.", status=404)

            if fornecedor_id:
                cur.execute("SELECT id FROM fornecedores WHERE id = %s", (fornecedor_id,))
                if not cur.fetchone():
                    return err("Fornecedor não encontrado.", campo="fornecedor_id", status=400)

            if status and status not in ["pendente", "recebido", "cancelado"]:
                return err("Status de compra inválido.", status=400)
            if status and status != compra_existente["status"] and compra_existente["status"] == "recebido":
                return err("Uma compra recebida não pode voltar de status; registre uma devolução de estoque para preservar a auditoria.", campo="status", status=409)

            # Lógica para atualizar estoque se o status mudar para 'recebido'
            if status == "recebido" and compra_existente["status"] != "recebido":
                cur.execute("SELECT id, produto_id, quantidade, lote_recebido, data_validade_recebida FROM itens_compra WHERE compra_id = %s", (compra_id,))
                itens_compra = cur.fetchall()
                recebimentos = data.get("itens_recebimento", [])
                if not isinstance(recebimentos, list):
                    raise ValueError("Informe uma lista de itens para recebimento.")
                recebimentos_por_id = {}
                ids_compra = {item["id"] for item in itens_compra}
                for recebido in recebimentos:
                    if not isinstance(recebido, dict) or recebido.get("id") not in ids_compra:
                        raise ValueError("Item de recebimento não pertence a esta compra.")
                    if recebido["id"] in recebimentos_por_id:
                        raise ValueError("Item de recebimento duplicado.")
                    recebimentos_por_id[recebido["id"]] = recebido
                # A confirmação é sempre atribuída à sessão que a executou.
                usuario_recebimento = g.usuario_id
                for item in itens_compra:
                    produto_id = item["produto_id"]
                    quantidade = item["quantidade"]
                    lote_recebido = item["lote_recebido"]
                    data_validade_recebida = item["data_validade_recebida"]
                    recebido = recebimentos_por_id.get(item["id"], {})
                    lote_recebido = recebido.get("lote_recebido", lote_recebido)
                    data_validade_recebida = recebido.get("data_validade_recebida", data_validade_recebida)

                    cur.execute("SELECT id, exige_validade FROM produtos WHERE id = %s", (produto_id,))
                    product = cur.fetchone()
                    data_validade_recebida = validate_expiry(data_validade_recebida, product or {})

                    lote_estoque = (lote_recebido or "").strip() or "SEM-LOTE"
                    require_lot(read_settings(cur), lote_estoque)
                    cur.execute("UPDATE itens_compra SET lote_recebido = %s, data_validade_recebida = %s WHERE id = %s",
                                (lote_estoque, data_validade_recebida, item["id"]))
                    cur.execute("SELECT id FROM estoque WHERE produto_id = %s AND lote = %s FOR UPDATE", (produto_id, lote_estoque))
                    estoque_item = cur.fetchone()
                    if estoque_item:
                        cur.execute("UPDATE estoque SET quantidade = quantidade + %s WHERE id = %s", (quantidade, estoque_item["id"]))
                    else:
                        cur.execute(
                            """
                            INSERT INTO estoque (produto_id, lote, quantidade, data_validade)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (produto_id, lote_estoque, quantidade, data_validade_recebida)
                        )
                    # Registrar movimentação de estoque
                    cur.execute(
                        """
                        INSERT INTO movimentacoes_estoque (estoque_id, usuario_id, tipo_movimentacao, quantidade, observacao)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (cur.lastrowid if not estoque_item else estoque_item["id"], usuario_recebimento, "entrada", quantidade, f"Entrada por compra {compra_id}")
                    )

            # Update parcial: somente os campos enviados pelo frontend são alterados,
            # mantendo os valores atuais para o que não foi informado (evita erro de NULL)
            if status and status == "recebido" and not data_recebimento:
                data_recebimento = "NOW()"
                use_now = True
            else:
                use_now = False

            set_parts = []
            params = []
            if fornecedor_id is not None:
                set_parts.append("fornecedor_id = %s"); params.append(fornecedor_id)
            if valor_total is not None:
                set_parts.append("valor_total = %s"); params.append(valor_total)
            if status is not None:
                set_parts.append("status = %s"); params.append(status)
            if use_now:
                set_parts.append("data_recebimento = NOW()")
            elif data_recebimento is not None:
                set_parts.append("data_recebimento = %s"); params.append(data_recebimento)

            if set_parts:
                params.append(compra_id)
                cur.execute(f"UPDATE compras SET {', '.join(set_parts)} WHERE id = %s", params)
            g.audit_previous_status = compra_existente["status"]
            commit_audit(db)
            return ok({"mensagem": "Compra atualizada com sucesso."})
    except ValueError as exc:
        db.rollback()
        return err(str(exc), status=400)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao atualizar compra: %s", exc)
        return err("Erro interno ao atualizar compra.", status=500)

@app.delete("/compras/<int:compra_id>")
def delete_compra(compra_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM compras WHERE id = %s", (compra_id,))
            if not cur.fetchone():
                return err("Compra não encontrada.", status=404)

            cur.execute("DELETE FROM compras WHERE id = %s", (compra_id,))
            commit_audit(db, cur.lastrowid)
            return ok({"mensagem": "Compra excluída com sucesso."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao excluir compra: %s", exc)
        return err("Erro interno ao excluir compra.", status=500)


# ─────────────────────────────────────────────
#  Rotas para Vendas
# ─────────────────────────────────────────────

@app.get("/vendas")
def get_vendas():
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT v.*, c.nome as cliente_nome, u.nome as usuario_nome FROM vendas v LEFT JOIN clientes c ON v.cliente_id = c.id LEFT JOIN usuarios u ON v.usuario_id = u.id")
            vendas = cur.fetchall()
        return ok({"vendas": vendas})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar vendas: %s", exc)
        return err("Erro interno ao buscar vendas.", status=500)


@app.get("/vendas/catalogo")
def catalogo_pdv():
    """Consulta comercial independente da permissão de edição de estoque."""
    try:
        with get_db().cursor() as cur:
            cur.execute("""SELECT p.id AS produto_id, p.nome, p.nome_generico,
                p.nome_generico AS principio_ativo,
                p.fabricante, p.codigo_barras, p.tipo_produto, p.requer_receita,
                p.preco_venda, c.nome AS categoria, e.id AS estoque_id,
                e.lote, e.quantidade, e.data_validade,
                (e.data_validade IS NULL OR e.data_validade >= CURDATE()) AS valido
                FROM produtos p LEFT JOIN categorias_produto c ON c.id=p.categoria_id
                LEFT JOIN estoque e ON e.produto_id=p.id WHERE p.ativo=1
                ORDER BY p.nome, e.data_validade""")
            rows = cur.fetchall()
        for row in rows:
            row['preco_venda'] = str(row['preco_venda'])
            if row.get('data_validade'):
                row['data_validade'] = row['data_validade'].isoformat()
        return ok({'produtos': rows})
    except pymysql.MySQLError:
        return err('Não foi possível consultar o catálogo.', status=503)


@app.post("/vendas/balcao")
def concluir_pdv():
    """Saldo, preço, receita e financeiro validados na mesma transação."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return err('Venda inválida.')
    items = data.get('itens')
    payment = data.get('tipo_pagamento')
    if payment not in {'dinheiro', 'pix', 'cartao_credito', 'cartao_debito'}:
        return err('Selecione a forma de pagamento.')
    if not isinstance(items, list) or not 1 <= len(items) <= 100:
        return err('Adicione de 1 a 100 lotes à venda.')
    seen = set()
    for item in items:
        if (not isinstance(item, dict) or type(item.get('estoque_id')) is not int
                or type(item.get('quantidade')) is not int
                or not 1 <= item['quantidade'] <= 100000
                or item['estoque_id'] in seen):
            return err('Quantidade ou lote inválido/duplicado.')
        seen.add(item['estoque_id'])
    db = get_db()
    try:
        with db.cursor() as cur:
            validated, total = [], Decimal('0.00')
            for item in sorted(items, key=lambda value: value['estoque_id']):
                cur.execute("""SELECT e.*, p.nome, p.preco_venda, p.requer_receita,
                    (e.data_validade IS NULL OR e.data_validade >= CURDATE()) AS valido
                    FROM estoque e JOIN produtos p ON p.id=e.produto_id
                    WHERE e.id=%s FOR UPDATE""", (item['estoque_id'],))
                row = cur.fetchone()
                if not row or not row['valido'] or row['quantidade'] < item['quantidade']:
                    raise ValueError('Saldo indisponível ou lote vencido. Atualize o catálogo e revise a venda.')
                price = Decimal(str(row['preco_venda']))
                quoted = Decimal(str(item.get('preco_unitario', 'NaN')))
                if not price.is_finite() or price <= 0 or not quoted.is_finite() or quoted != price:
                    raise ValueError('O preço mudou ou está inválido. Atualize o catálogo e revise a venda.')
                if row['requer_receita'] and data.get('receita_conferida') is not True:
                    raise ValueError('Confirme a conferência da receita antes de concluir.')
                total += price * item['quantidade']
                validated.append((row, item['quantidade'], price))
            if total > Decimal('9999999999.99'):
                raise ValueError('Total acima do limite permitido.')
            cur.execute("SELECT id FROM financeiro_categorias WHERE slug='venda_medicamentos' AND tipo='receita'")
            category = cur.fetchone()
            if not category:
                raise ValueError('Categoria financeira de vendas não configurada.')
            cur.execute("""INSERT INTO vendas (usuario_id, valor_total, tipo_pagamento, status)
                VALUES (%s,%s,%s,'concluida')""", (g.usuario_id, total, payment))
            sale_id = cur.lastrowid
            for row, qty, price in validated:
                cur.execute('UPDATE estoque SET quantidade=quantidade-%s WHERE id=%s', (qty, row['id']))
                cur.execute("""INSERT INTO itens_venda
                    (venda_id,produto_id,quantidade,preco_unitario,desconto,lote_vendido)
                    VALUES (%s,%s,%s,%s,0,%s)""", (sale_id,row['produto_id'],qty,price,row['lote']))
                cur.execute("""INSERT INTO movimentacoes_estoque
                    (estoque_id,usuario_id,tipo_movimentacao,quantidade,observacao)
                    VALUES (%s,%s,'saida',%s,%s)""", (row['id'],g.usuario_id,qty,f'Venda PDV {sale_id}'))
            cur.execute("""INSERT INTO financeiro_transacoes
                (categoria_id,usuario_id,venda_id,descricao,valor,status,metodo_pagamento)
                VALUES (%s,%s,%s,%s,%s,'pago',%s)""",
                (category['id'],g.usuario_id,sale_id,f'Venda PDV {sale_id}',total,payment))
            g.audit_values = {"status": "concluida", "valor_total": str(total), "itens": [
                {"produto_id": row["produto_id"], "estoque_id": row["id"],
                 "quantidade": qty, "preco_unitario": str(price), "lote_vendido": row["lote"]}
                for row, qty, price in validated]}
            commit_audit(db, sale_id)
        return ok({'id': sale_id, 'valor_total': str(total)}, status=201)
    except (ValueError, InvalidOperation) as exc:
        db.rollback()
        return err(str(exc) if isinstance(exc, ValueError) else 'Preço inválido.', status=409)
    except pymysql.MySQLError:
        db.rollback()
        log.exception('Falha ao concluir PDV')
        return err('Não foi possível concluir a venda.', status=503)

@app.get("/vendas/<int:venda_id>")
def get_venda(venda_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT v.*, c.nome as cliente_nome, u.nome as usuario_nome FROM vendas v LEFT JOIN clientes c ON v.cliente_id = c.id LEFT JOIN usuarios u ON v.usuario_id = u.id WHERE v.id = %s", (venda_id,))
            venda = cur.fetchone()
            if not venda:
                return err("Venda não encontrada.", status=404)
        return ok({"venda": venda})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar venda: %s", exc)
        return err("Erro interno ao buscar venda.", status=500)

def sync_venda_financeiro(cur, venda_id):
    """Mantém a receita vinculada na mesma transação da venda (inclusive na API antiga)."""
    cur.execute("SELECT id FROM financeiro_categorias WHERE slug='venda_medicamentos' AND tipo='receita'")
    category = cur.fetchone()
    if not category:
        raise ValueError('Categoria financeira de vendas não configurada.')
    cur.execute("""UPDATE financeiro_transacoes t JOIN vendas v ON v.id=t.venda_id
        SET t.valor=v.valor_total, t.metodo_pagamento=v.tipo_pagamento,
            t.status=CASE v.status WHEN 'concluida' THEN 'pago'
                WHEN 'cancelada' THEN 'cancelado' ELSE 'pendente' END,
            t.data_transacao=CASE WHEN v.status='concluida' THEN v.data_venda ELSE t.data_transacao END
        WHERE v.id=%s""", (venda_id,))
    cur.execute("""INSERT INTO financeiro_transacoes
        (categoria_id,usuario_id,venda_id,descricao,valor,data_transacao,status,metodo_pagamento)
        SELECT %s,v.usuario_id,v.id,CONCAT('Venda #',v.id),v.valor_total,v.data_venda,
            CASE v.status WHEN 'concluida' THEN 'pago'
                WHEN 'cancelada' THEN 'cancelado' ELSE 'pendente' END,v.tipo_pagamento
        FROM vendas v WHERE v.id=%s AND NOT EXISTS
            (SELECT 1 FROM financeiro_transacoes t WHERE t.venda_id=v.id)""",
        (category['id'], venda_id))


@app.post("/vendas")
def create_venda():
    data = request.get_json(silent=True) or {}
    cliente_id = data.get("cliente_id")
    usuario_id = g.usuario_id
    valor_total = data.get("valor_total")
    tipo_pagamento = data.get("tipo_pagamento")
    status = data.get("status", "pendente")
    itens = data.get("itens", []) # Lista de dicionários com produto_id, quantidade, preco_unitario, desconto, lote_vendido

    if not valor_total or not tipo_pagamento:
        return err("Valor total e tipo de pagamento são obrigatórios.", status=400)
    if valor_total <= 0:
        return err("Valor total deve ser maior que zero.", status=400)
    if tipo_pagamento not in ["dinheiro", "cartao_credito", "cartao_debito", "pix"]:
        return err("Tipo de pagamento inválido.", status=400)
    if status not in ["concluida", "cancelada", "pendente"]:
        return err("Status de venda inválido.", status=400)

    db = get_db()
    try:
        with db.cursor() as cur:
            if cliente_id:
                cur.execute("SELECT id FROM clientes WHERE id = %s", (cliente_id,))
                if not cur.fetchone():
                    return err("Cliente não encontrado.", campo="cliente_id", status=400)

            cur.execute(
                """
                INSERT INTO vendas (cliente_id, usuario_id, valor_total, tipo_pagamento, status)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (cliente_id, usuario_id, valor_total, tipo_pagamento, status)
            )
            venda_id = cur.lastrowid

            for item in itens:
                produto_id = item.get("produto_id")
                quantidade = item.get("quantidade")
                preco_unitario = item.get("preco_unitario")
                desconto = item.get("desconto", 0.00)
                lote_vendido = (item.get("lote_vendido") or "").strip() or "SEM-LOTE"

                if not produto_id or not quantidade or not preco_unitario:
                    db.rollback()
                    return err("Dados incompletos para item de venda.", status=400)

                cur.execute("SELECT id FROM produtos WHERE id = %s", (produto_id,))
                if not cur.fetchone():
                    db.rollback()
                    return err(f"Produto com ID {produto_id} não encontrado.", status=400)

                # Verifica e atualiza estoque
                if status == "concluida":
                    cur.execute("SELECT id, quantidade, lote, data_validade FROM estoque WHERE produto_id = %s AND lote = %s FOR UPDATE", (produto_id, lote_vendido))
                    estoque_item = cur.fetchone()
                    if not estoque_item or estoque_item["quantidade"] < quantidade:
                        db.rollback()
                        return err(f"Estoque insuficiente para o produto {produto_id} no lote {lote_vendido}.", status=400)

                    require_usable_stock(read_settings(cur), estoque_item)
                    cur.execute("UPDATE estoque SET quantidade = quantidade - %s WHERE id = %s", (quantidade, estoque_item["id"]))
                    # Registrar movimentação de estoque
                    cur.execute(
                        """
                        INSERT INTO movimentacoes_estoque (estoque_id, usuario_id, tipo_movimentacao, quantidade, observacao)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (estoque_item["id"], usuario_id, "saida", quantidade, f"Saída por venda {venda_id}")
                    )

                cur.execute(
                    """
                    INSERT INTO itens_venda (venda_id, produto_id, quantidade, preco_unitario, desconto, lote_vendido)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (venda_id, produto_id, quantidade, preco_unitario, desconto, lote_vendido)
                )

            sync_venda_financeiro(cur, venda_id)
            g.audit_values = {"status": status}
            commit_audit(db, venda_id)
            return ok({"mensagem": "Venda criada com sucesso.", "id": venda_id}, status=201)
    except ValueError as exc:
        db.rollback()
        return err(str(exc), status=400)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao criar venda: %s", exc)
        return err("Erro interno ao criar venda.", status=500)

@app.put("/vendas/<int:venda_id>")
def update_venda(venda_id):
    data = request.get_json(silent=True) or {}
    cliente_id = data.get("cliente_id")
    usuario_id = g.usuario_id
    valor_total = data.get("valor_total")
    tipo_pagamento = data.get("tipo_pagamento")
    status = data.get("status")

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id, status FROM vendas WHERE id = %s FOR UPDATE", (venda_id,))
            venda_existente = cur.fetchone()
            if not venda_existente:
                return err("Venda não encontrada.", status=404)

            if cliente_id:
                cur.execute("SELECT id FROM clientes WHERE id = %s", (cliente_id,))
                if not cur.fetchone():
                    return err("Cliente não encontrado.", campo="cliente_id", status=400)

            if tipo_pagamento and tipo_pagamento not in ["dinheiro", "cartao_credito", "cartao_debito", "pix"]:
                return err("Tipo de pagamento inválido.", status=400)
            if status and status not in ["concluida", "cancelada", "pendente"]:
                return err("Status de venda inválido.", status=400)
            if status and status != venda_existente["status"] and venda_existente["status"] == "concluida":
                return err("Uma venda concluída não pode voltar de status; registre uma devolução de estoque para preservar a auditoria.", campo="status", status=409)

            # Lógica para atualizar estoque se o status mudar para 'concluida' e antes não era
            if status == "concluida" and venda_existente["status"] != "concluida":
                cur.execute("SELECT produto_id, quantidade, lote_vendido FROM itens_venda WHERE venda_id = %s", (venda_id,))
                itens_venda = cur.fetchall()
                for item in itens_venda:
                    produto_id = item["produto_id"]
                    quantidade = item["quantidade"]
                    lote_vendido = item["lote_vendido"] or "SEM-LOTE"

                    cur.execute("SELECT id, quantidade, lote, data_validade FROM estoque WHERE produto_id = %s AND lote = %s FOR UPDATE", (produto_id, lote_vendido))
                    estoque_item = cur.fetchone()
                    if not estoque_item or estoque_item["quantidade"] < quantidade:
                        db.rollback()
                        return err(f"Estoque insuficiente para o produto {produto_id} no lote {lote_vendido}.", status=400)

                    require_usable_stock(read_settings(cur), estoque_item)
                    cur.execute("UPDATE estoque SET quantidade = quantidade - %s WHERE id = %s", (quantidade, estoque_item["id"]))
                    # Registrar movimentação de estoque
                    cur.execute(
                        """
                        INSERT INTO movimentacoes_estoque (estoque_id, usuario_id, tipo_movimentacao, quantidade, observacao)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (estoque_item["id"], usuario_id, "saida", quantidade, f"Saída por venda {venda_id}")
                    )

            cur.execute(
                """
                UPDATE vendas SET data_venda = CASE
                    WHEN status <> 'concluida' AND %s = 'concluida' THEN NOW() ELSE data_venda END,
                    cliente_id = %s, valor_total = %s, tipo_pagamento = %s, status = %s
                WHERE id = %s
                """,
                (status, cliente_id, valor_total, tipo_pagamento, status, venda_id)
            )
            sync_venda_financeiro(cur, venda_id)
            g.audit_previous_status = venda_existente["status"]
            commit_audit(db, venda_id)
            return ok({"mensagem": "Venda atualizada com sucesso."})
    except ValueError as exc:
        db.rollback()
        return err(str(exc), status=400)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao atualizar venda: %s", exc)
        return err("Erro interno ao atualizar venda.", status=500)

@app.delete("/vendas/<int:venda_id>")
def delete_venda(venda_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM vendas WHERE id = %s", (venda_id,))
            if not cur.fetchone():
                return err("Venda não encontrada.", status=404)

            cur.execute("DELETE FROM vendas WHERE id = %s", (venda_id,))
            commit_audit(db, cur.lastrowid)
            return ok({"mensagem": "Venda excluída com sucesso."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao excluir venda: %s", exc)
        return err("Erro interno ao excluir venda.", status=500)


# ─────────────────────────────────────────────
#  Rotas para Receitas
# ─────────────────────────────────────────────

@app.get("/receitas")
def get_receitas():
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT r.*, c.nome as cliente_nome FROM receitas r LEFT JOIN clientes c ON r.cliente_id = c.id")
            receitas = cur.fetchall()
        return ok({"receitas": receitas})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar receitas: %s", exc)
        return err("Erro interno ao buscar receitas.", status=500)

@app.get("/receitas/<int:receita_id>")
def get_receita(receita_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT r.*, c.nome as cliente_nome FROM receitas r LEFT JOIN clientes c ON r.cliente_id = c.id WHERE r.id = %s", (receita_id,))
            receita = cur.fetchone()
            if not receita:
                return err("Receita não encontrada.", status=404)
        return ok({"receita": receita})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar receita: %s", exc)
        return err("Erro interno ao buscar receita.", status=500)

@app.post("/receitas")
def create_receita():
    data = request.get_json(silent=True) or {}
    cliente_id = data.get("cliente_id")
    medico_nome = data.get("medico_nome")
    crm = data.get("crm")
    data_prescricao = data.get("data_prescricao")
    data_validade = data.get("data_validade")
    observacoes = data.get("observacoes")
    arquivo_receita_url = data.get("arquivo_receita_url")
    itens = data.get("itens", []) # Lista de dicionários com produto_id, quantidade, dosagem, instrucoes_uso

    if not cliente_id or not medico_nome or not crm or not data_prescricao:
        return err("Cliente, nome do médico, CRM e data da prescrição são obrigatórios.", status=400)

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM clientes WHERE id = %s", (cliente_id,))
            if not cur.fetchone():
                return err("Cliente não encontrado.", campo="cliente_id", status=400)

            cur.execute(
                """
                INSERT INTO receitas (cliente_id, medico_nome, crm, data_prescricao, data_validade, observacoes, arquivo_receita_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (cliente_id, medico_nome, crm, data_prescricao, data_validade, observacoes, arquivo_receita_url)
            )
            receita_id = cur.lastrowid

            for item in itens:
                produto_id = item.get("produto_id")
                quantidade = item.get("quantidade")
                dosagem = item.get("dosagem")
                instrucoes_uso = item.get("instrucoes_uso")

                if not produto_id or not quantidade:
                    db.rollback()
                    return err("Dados incompletos para item de receita.", status=400)

                cur.execute("SELECT id FROM produtos WHERE id = %s", (produto_id,))
                if not cur.fetchone():
                    db.rollback()
                    return err(f"Produto com ID {produto_id} não encontrado.", status=400)

                cur.execute(
                    """
                    INSERT INTO receitas_itens (receita_id, produto_id, quantidade, dosagem, instrucoes_uso)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (receita_id, produto_id, quantidade, dosagem, instrucoes_uso)
                )

            commit_audit(db, cur.lastrowid)
            return ok({"mensagem": "Receita criada com sucesso.", "id": receita_id}, status=201)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao criar receita: %s", exc)
        return err("Erro interno ao criar receita.", status=500)

@app.put("/receitas/<int:receita_id>")
def update_receita(receita_id):
    data = request.get_json(silent=True) or {}
    cliente_id = data.get("cliente_id")
    medico_nome = data.get("medico_nome")
    crm = data.get("crm")
    data_prescricao = data.get("data_prescricao")
    data_validade = data.get("data_validade")
    observacoes = data.get("observacoes")
    arquivo_receita_url = data.get("arquivo_receita_url")

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM receitas WHERE id = %s", (receita_id,))
            if not cur.fetchone():
                return err("Receita não encontrada.", status=404)

            if cliente_id:
                cur.execute("SELECT id FROM clientes WHERE id = %s", (cliente_id,))
                if not cur.fetchone():
                    return err("Cliente não encontrado.", campo="cliente_id", status=400)

            cur.execute(
                """
                UPDATE receitas SET cliente_id = %s, medico_nome = %s, crm = %s, data_prescricao = %s, data_validade = %s, observacoes = %s, arquivo_receita_url = %s
                WHERE id = %s
                """,
                (cliente_id, medico_nome, crm, data_prescricao, data_validade, observacoes, arquivo_receita_url, receita_id)
            )
            commit_audit(db, cur.lastrowid)
            return ok({"mensagem": "Receita atualizada com sucesso."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao atualizar receita: %s", exc)
        return err("Erro interno ao atualizar receita.", status=500)

@app.delete("/receitas/<int:receita_id>")
def delete_receita(receita_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM receitas WHERE id = %s", (receita_id,))
            if not cur.fetchone():
                return err("Receita não encontrada.", status=404)

            cur.execute("DELETE FROM receitas WHERE id = %s", (receita_id,))
            commit_audit(db, cur.lastrowid)
            return ok({"mensagem": "Receita excluída com sucesso."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao excluir receita: %s", exc)
        return err("Erro interno ao excluir receita.", status=500)


# ─────────────────────────────────────────────
#  Rotas para Alertas
# ─────────────────────────────────────────────

@app.get("/alertas")
def get_alertas():
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM alertas")
            alertas = cur.fetchall()
        return ok({"alertas": alertas})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar alertas: %s", exc)
        return err("Erro interno ao buscar alertas.", status=500)

@app.get("/alertas/<int:alerta_id>")
def get_alerta(alerta_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM alertas WHERE id = %s", (alerta_id,))
            alerta = cur.fetchone()
            if not alerta:
                return err("Alerta não encontrado.", status=404)
        return ok({"alerta": alerta})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar alerta: %s", exc)
        return err("Erro interno ao buscar alerta.", status=500)

@app.post("/alertas")
def create_alerta():
    data = request.get_json(silent=True) or {}
    tipo_alerta = data.get("tipo_alerta")
    referencia_id = data.get("referencia_id")
    mensagem = data.get("mensagem")
    status = data.get("status", "ativo")

    if not tipo_alerta or not mensagem:
        return err("Tipo de alerta e mensagem são obrigatórios.", status=400)
    if tipo_alerta not in ["vencimento", "estoque_baixo", "outros"]:
        return err("Tipo de alerta inválido.", status=400)

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO alertas (tipo_alerta, referencia_id, mensagem, status)
                VALUES (%s, %s, %s, %s)
                """,
                (tipo_alerta, referencia_id, mensagem, status)
            )
            commit_audit(db, cur.lastrowid)
            return ok({"mensagem": "Alerta criado com sucesso.", "id": cur.lastrowid}, status=201)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao criar alerta: %s", exc)
        return err("Erro interno ao criar alerta.", status=500)

@app.put("/alertas/<int:alerta_id>")
def update_alerta(alerta_id):
    data = request.get_json(silent=True) or {}
    tipo_alerta = data.get("tipo_alerta")
    referencia_id = data.get("referencia_id")
    mensagem = data.get("mensagem")
    status = data.get("status")

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM alertas WHERE id = %s", (alerta_id,))
            if not cur.fetchone():
                return err("Alerta não encontrado.", status=404)

            if tipo_alerta and tipo_alerta not in ["vencimento", "estoque_baixo", "outros"]:
                return err("Tipo de alerta inválido.", status=400)
            if status and status not in ["ativo", "resolvido"]:
                return err("Status de alerta inválido.", status=400)

            update_fields = []
            update_values = []
            if tipo_alerta: update_fields.append("tipo_alerta = %s"); update_values.append(tipo_alerta)
            if referencia_id: update_fields.append("referencia_id = %s"); update_values.append(referencia_id)
            if mensagem: update_fields.append("mensagem = %s"); update_values.append(mensagem)
            if status: update_fields.append("status = %s"); update_values.append(status)
            if status == "resolvido":
                # A autoria vem da sessão autenticada, nunca do corpo enviado
                # pelo cliente; a migração 007 fornece ambas as colunas.
                update_fields.append("resolvido_por_usuario_id = %s"); update_values.append(g.usuario_id)
                update_fields.append("resolvido_em = NOW()")
            elif status == "ativo":
                update_fields.append("resolvido_por_usuario_id = NULL")
                update_fields.append("resolvido_em = NULL")

            if not update_fields:
                return err("Nenhum dado para atualizar.", status=400)

            query = f"UPDATE alertas SET {', '.join(update_fields)} WHERE id = %s"
            cur.execute(query, (*update_values, alerta_id))
            commit_audit(db, cur.lastrowid)
            return ok({"mensagem": "Alerta atualizado com sucesso."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao atualizar alerta: %s", exc)
        return err("Erro interno ao atualizar alerta.", status=500)

@app.delete("/alertas/<int:alerta_id>")
def delete_alerta(alerta_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM alertas WHERE id = %s", (alerta_id,))
            if not cur.fetchone():
                return err("Alerta não encontrado.", status=404)

            cur.execute("DELETE FROM alertas WHERE id = %s", (alerta_id,))
            commit_audit(db, cur.lastrowid)
            return ok({"mensagem": "Alerta excluído com sucesso."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao excluir alerta: %s", exc)
        return err("Erro interno ao excluir alerta.", status=500)

# ─────────────────────────────────────────────
#  Rotas para Configurações do Sistema
# ─────────────────────────────────────────────

@app.get("/configuracoes/visual")
def get_configuracoes_visuais():
    """Preferencias seguras usadas pelo login antes de existir uma sessao."""
    chaves = ("cor_destaque", "densidade_interface", "animacoes_interface")
    db = get_db()
    try:
        with db.cursor() as cur:
            placeholders = ", ".join(["%s"] * len(chaves))
            cur.execute(
                f"SELECT chave, valor FROM configuracoes_sistema WHERE chave IN ({placeholders})",
                chaves,
            )
            configuracoes = cur.fetchall()
        return ok({"configuracoes": configuracoes})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar configuracoes visuais: %s", exc)
        return err("Erro interno ao buscar configuracoes visuais.", status=500)


@app.get("/configuracoes")
def get_configuracoes():
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM configuracoes_sistema")
            configuracoes = cur.fetchall()
        # Preferências aposentadas podem existir em instalações anteriores.
        configuracoes = [item for item in configuracoes if item["chave"] not in {"tema", "tema_efetivo"}]
        return ok({"configuracoes": configuracoes, "email_disponivel": all(os.getenv(k) for k in ("BREVO_SMTP_LOGIN", "BREVO_SMTP_PASSWORD", "BREVO_SENDER_EMAIL"))})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar configurações: %s", exc)
        return err("Erro interno ao buscar configurações.", status=500)

@app.put("/configuracoes")
def save_configuracoes():
    """Salva o formulário inteiro em uma única transação, incluindo auditoria."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return err("Informe as configurações para salvar.", status=400)
    db = get_db()
    try:
        with db.cursor() as cur:
            values = validate_settings(data.get('configuracoes'), read_settings(cur))
            for chave, valor in values.items():
                cur.execute("""INSERT INTO configuracoes_sistema (chave, valor, descricao)
                    VALUES (%s, %s, 'Configurações do sistema')
                    ON DUPLICATE KEY UPDATE valor = VALUES(valor)""", (chave, valor))
            commit_audit(db)
        return ok({"mensagem": "Configurações salvas com sucesso.", "valores": values})
    except ValueError as exc:
        db.rollback()
        return err(str(exc), status=400)
    except pymysql.MySQLError:
        db.rollback()
        log.exception("Erro ao salvar configurações")
        return err("Não foi possível salvar as configurações. Tente novamente.", status=500)


@app.get("/configuracoes/<string:chave>")
def get_configuracao(chave):
    if chave in {"tema", "tema_efetivo"}:
        return err("Esta preferência visual foi removida.", status=410)
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM configuracoes_sistema WHERE chave = %s", (chave,))
            configuracao = cur.fetchone()
            if not configuracao:
                return err("Configuração não encontrada.", status=404)
        return ok({"configuracao": configuracao})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar configuração: %s", exc)
        return err("Erro interno ao buscar configuração.", status=500)

@app.post("/configuracoes")
def create_configuracao():
    data = request.get_json(silent=True) or {}
    chave = data.get("chave")
    valor = data.get("valor")
    descricao = data.get("descricao")

    if chave in ("tema", "tema_efetivo"):
        return err("Esta preferência visual foi removida.", campo="chave", status=410)

    if not chave or not valor:
        return err("Chave e valor são obrigatórios.", status=400)

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO configuracoes_sistema (chave, valor, descricao)
                VALUES (%s, %s, %s)
                """,
                (chave, valor, descricao)
            )
            commit_audit(db, cur.lastrowid)
            return ok({"mensagem": "Configuração criada com sucesso."}, status=201)
    except pymysql.IntegrityError as exc:
        db.rollback()
        if "Duplicate entry" in str(exc) and "chave" in str(exc):
            return err("Chave de configuração já existe.", campo="chave", status=409)
        log.error("Erro DB ao criar configuração: %s", exc)
        return err("Erro interno ao criar configuração.", status=500)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao criar configuração: %s", exc)
        return err("Erro interno ao criar configuração.", status=500)

@app.put("/configuracoes/<string:chave>")
def update_configuracao(chave):
    """Atualiza ou cria (upsert) uma configuração do sistema."""
    if chave in {"tema", "tema_efetivo"}:
        return err("Esta preferência visual foi removida.", campo="chave", status=410)
    data = request.get_json(silent=True) or {}
    valor     = data.get("valor")
    descricao = data.get("descricao")

    db = get_db()
    try:
        with db.cursor() as cur:
            # INSERT ... ON DUPLICATE KEY UPDATE (upsert)
            cur.execute(
                """
                INSERT INTO configuracoes_sistema (chave, valor, descricao)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE valor = VALUES(valor),
                                        descricao = COALESCE(VALUES(descricao), descricao)
                """,
                (chave, valor, descricao)
            )
            commit_audit(db, cur.lastrowid)
            return ok({"mensagem": "Configuração salva com sucesso."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao salvar configuração: %s", exc)
        return err("Erro interno ao salvar configuração.", status=500)

@app.delete("/configuracoes/<string:chave>")
def delete_configuracao(chave):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT chave FROM configuracoes_sistema WHERE chave = %s", (chave,))
            if not cur.fetchone():
                return err("Configuração não encontrada.", status=404)

            cur.execute("DELETE FROM configuracoes_sistema WHERE chave = %s", (chave,))
            commit_audit(db, cur.lastrowid)
            return ok({"mensagem": "Configuração excluída com sucesso."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao excluir configuração: %s", exc)
        return err("Erro interno ao excluir configuração.", status=500)




# ─────────────────────────────────────────────
#  Rota de Estatísticas de Dashboard
# ─────────────────────────────────────────────

@app.get("/dashboard/stats")
def get_dashboard_stats():
    """Retorna estatísticas consolidadas para o dashboard do proprietário."""
    db = get_db()
    try:
        with db.cursor() as cur:
            # Total de itens distintos em estoque
            cur.execute("SELECT COUNT(*) AS total FROM estoque WHERE quantidade > 0")
            total_itens = cur.fetchone()["total"] or 0

            # Valor total em estoque (quantidade * preco_custo)
            cur.execute("""
                SELECT COALESCE(SUM(e.quantidade * p.preco_custo), 0) AS valor
                FROM   estoque e
                JOIN   produtos p ON e.produto_id = p.id
            """)
            valor_estoque = float(cur.fetchone()["valor"] or 0)

            # Itens com estoque crítico (quantidade <= estoque_minimo do produto)
            cur.execute("""
                SELECT COUNT(*) AS total
                FROM   estoque e
                JOIN   produtos p ON e.produto_id = p.id
                WHERE  e.quantidade >= 0
                  AND  e.quantidade <= COALESCE(p.estoque_minimo, 10)
            """)
            estoque_critico = cur.fetchone()["total"] or 0

            # Itens com estoque baixo (até 2x o mínimo, mas acima do crítico)
            cur.execute("""
                SELECT COUNT(*) AS total
                FROM   estoque e
                JOIN   produtos p ON e.produto_id = p.id
                WHERE  e.quantidade > COALESCE(p.estoque_minimo, 10)
                  AND  e.quantidade <= COALESCE(p.estoque_minimo, 10) * 2
            """)
            estoque_baixo = cur.fetchone()["total"] or 0

            # Itens vencidos
            cur.execute("""
                SELECT COUNT(*) AS total
                FROM   estoque
                WHERE  data_validade < CURDATE() AND quantidade > 0
                  AND  data_validade IS NOT NULL
            """)
            vencidos = cur.fetchone()["total"] or 0

            # Vencendo em até 30 dias
            cur.execute("""
                SELECT COUNT(*) AS total
                FROM   estoque
                WHERE  data_validade BETWEEN CURDATE()
                                         AND DATE_ADD(CURDATE(), INTERVAL 30 DAY)
                  AND  quantidade > 0
                  AND  data_validade IS NOT NULL
            """)
            vencendo_30 = cur.fetchone()["total"] or 0

            # Vencendo em até 60 dias
            cur.execute("""
                SELECT COUNT(*) AS total
                FROM   estoque
                WHERE  data_validade BETWEEN DATE_ADD(CURDATE(), INTERVAL 31 DAY)
                                         AND DATE_ADD(CURDATE(), INTERVAL 60 DAY)
                  AND  quantidade > 0
                  AND  data_validade IS NOT NULL
            """)
            vencendo_60 = cur.fetchone()["total"] or 0

            # Saídas hoje
            cur.execute("""
                SELECT COALESCE(SUM(quantidade), 0) AS total
                FROM   movimentacoes_estoque
                WHERE  tipo_movimentacao = 'saida'
                  AND  DATE(data_movimentacao) = CURDATE()
            """)
            saidas_hoje = int(cur.fetchone()["total"] or 0)

            # Entradas hoje
            cur.execute("""
                SELECT COALESCE(SUM(quantidade), 0) AS total
                FROM   movimentacoes_estoque
                WHERE  tipo_movimentacao = 'entrada'
                  AND  DATE(data_movimentacao) = CURDATE()
            """)
            entradas_hoje = int(cur.fetchone()["total"] or 0)

            # Total de compras pendentes
            cur.execute("SELECT COUNT(*) AS total FROM compras WHERE status = 'pendente'")
            compras_pendentes = cur.fetchone()["total"] or 0

            # Total de fornecedores ativos
            cur.execute("SELECT COUNT(*) AS total FROM fornecedores WHERE ativo = TRUE")
            fornecedores_ativos = cur.fetchone()["total"] or 0

            # Movimentações dos últimos 7 dias (entradas e saídas por dia)
            cur.execute("""
                SELECT DATE(data_movimentacao) AS dia,
                       tipo_movimentacao,
                       SUM(quantidade) AS total
                FROM   movimentacoes_estoque
                WHERE  data_movimentacao >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
                  AND  tipo_movimentacao IN ('entrada', 'saida')
                GROUP  BY dia, tipo_movimentacao
                ORDER  BY dia ASC
            """)
            movs_semana = cur.fetchall()
            for row in movs_semana:
                if row.get("dia") and hasattr(row["dia"], "isoformat"):
                    row["dia"] = row["dia"].isoformat()

            # Top 5 produtos mais movimentados (saídas nos últimos 30 dias)
            cur.execute("""
                SELECT p.nome AS produto_nome,
                       SUM(me.quantidade) AS total_saidas
                FROM   movimentacoes_estoque me
                JOIN   estoque e  ON me.estoque_id = e.id
                JOIN   produtos p ON e.produto_id  = p.id
                WHERE  me.tipo_movimentacao = 'saida'
                  AND  me.data_movimentacao >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                GROUP  BY p.id, p.nome
                ORDER  BY total_saidas DESC
                LIMIT  5
            """)
            top_produtos = cur.fetchall()

            # Produtos Críticos para a tabela do dashboard
            cur.execute("""
                SELECT e.id AS estoque_id, p.id AS produto_id, p.nome, 
                       COALESCE(cp.nome, 'Sem Categoria') as categoria,
                       e.lote, 
                       e.quantidade, 
                       COALESCE(p.estoque_minimo, 10) AS estoque_minimo, 
                       e.data_validade,
                       CASE 
                         WHEN e.quantidade <= COALESCE(p.estoque_minimo, 10)
                           OR (e.data_validade IS NOT NULL
                               AND e.data_validade <= CURDATE() + INTERVAL 30 DAY) THEN 'crit'
                         ELSE 'low'
                       END as status_classe
                FROM   estoque e
                JOIN   produtos p ON e.produto_id = p.id
                LEFT JOIN categorias_produto cp ON p.categoria_id = cp.id
                WHERE  e.quantidade <= COALESCE(p.estoque_minimo, 10) * 2
                   OR (e.data_validade IS NOT NULL
                       AND e.data_validade <= CURDATE() + INTERVAL 30 DAY)
                ORDER  BY CASE
                            WHEN e.data_validade IS NULL THEN 1
                            ELSE 0
                          END,
                          e.data_validade ASC,
                          e.quantidade ASC,
                          p.nome ASC
            """)
            produtos_criticos = cur.fetchall()
            for row in produtos_criticos:
                if row.get("data_validade") and hasattr(row["data_validade"], "isoformat"):
                    row["data_validade"] = row["data_validade"].isoformat()

            cur.execute("""
                SELECT e.id, p.nome, e.lote, e.quantidade, e.data_validade,
                       DATEDIFF(e.data_validade, CURDATE()) AS dias
                FROM estoque e JOIN produtos p ON p.id=e.produto_id
                WHERE e.quantidade > 0 AND e.data_validade BETWEEN CURDATE() AND CURDATE() + INTERVAL 60 DAY
                ORDER BY e.data_validade, p.nome, e.id
            """)
            vencimentos_proximos = cur.fetchall()
            for row in vencimentos_proximos:
                row['data_validade'] = row['data_validade'].isoformat()

            alertas_ativos = active_alerts(cur, read_settings(cur))

        return ok({
            "alertas_ativos": alertas_ativos,
            "kpis": {
                "total_itens":        int(total_itens),
                "valor_estoque":      round(valor_estoque, 2),
                "estoque_critico":    int(estoque_critico),
                "estoque_baixo":      int(estoque_baixo),
                "vencidos":           int(vencidos),
                "vencendo_30":        int(vencendo_30),
                "vencendo_60":        int(vencendo_60),
                "saidas_hoje":        saidas_hoje,
                "entradas_hoje":      entradas_hoje,
                "compras_pendentes":  int(compras_pendentes),
                "fornecedores_ativos": int(fornecedores_ativos),
            },
            "movimentacoes_semana": movs_semana,
            "top_produtos":         top_produtos,
            "produtos_criticos":    produtos_criticos,
            "vencimentos_proximos": vencimentos_proximos,
        })
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar estatísticas do dashboard: %s", exc)
        return err("Erro interno ao buscar estatísticas do dashboard.", status=500)


# ─────────────────────────────────────────────
#  Rota de Relatórios do Proprietário
# ─────────────────────────────────────────────

@app.get("/relatorios/estoque")
def relatorio_estoque():
    """Relatório completo de posição de estoque com KPIs e listagem."""
    period = request.args.get('periodo', 'month')
    if period not in PERIOD_START:
        return err('Período inválido.', campo='periodo', status=400)
    db = get_db()
    try:
        with db.cursor() as cur:
            report = stock_report(cur, period)
        return ok(report)
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao gerar relatório de estoque: %s", exc)
        return err("Erro interno ao gerar relatório de estoque.", status=500)


@app.get("/relatorios/vencimentos")
def relatorio_vencimentos():
    """Relatório de vencimentos com distribuição por faixa de prazo."""
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) AS total FROM estoque
                WHERE data_validade < CURDATE() AND quantidade > 0
            """)
            vencidos = cur.fetchone()["total"] or 0

            cur.execute("""
                SELECT COUNT(*) AS total FROM estoque
                WHERE data_validade BETWEEN CURDATE()
                                        AND DATE_ADD(CURDATE(), INTERVAL 30 DAY)
                  AND quantidade > 0
            """)
            ate_30 = cur.fetchone()["total"] or 0

            cur.execute("""
                SELECT COUNT(*) AS total FROM estoque
                WHERE data_validade BETWEEN DATE_ADD(CURDATE(), INTERVAL 31 DAY)
                                        AND DATE_ADD(CURDATE(), INTERVAL 60 DAY)
                  AND quantidade > 0
            """)
            ate_60 = cur.fetchone()["total"] or 0

            cur.execute("""
                SELECT COUNT(*) AS total FROM estoque
                WHERE data_validade > DATE_ADD(CURDATE(), INTERVAL 60 DAY)
                  AND quantidade > 0
            """)
            ok_count = cur.fetchone()["total"] or 0

        return ok({
            "kpis": {
                "vencidos": int(vencidos),
                "ate_30":   int(ate_30),
                "ate_60":   int(ate_60),
                "ok":       int(ok_count),
            }
        })
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao gerar relatório de vencimentos: %s", exc)
        return err("Erro interno ao gerar relatório de vencimentos.", status=500)


@app.get("/relatorios/compras")
def relatorio_compras():
    """Relatório de compras com KPIs e movimentações."""
    period = request.args.get('periodo', 'month')
    if period not in PERIOD_START:
        return err('Período inválido.', campo='periodo', status=400)
    scope = f"data_pedido >= {PERIOD_START[period]} AND data_pedido < CURDATE() + INTERVAL 1 DAY"
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS total FROM compras WHERE {scope}")
            total_pedidos = cur.fetchone()["total"] or 0

            cur.execute(f"""
                SELECT COALESCE(SUM(valor_total), 0) AS valor FROM compras
                WHERE status = 'recebido' AND {scope}
            """)
            valor_comprado = float(cur.fetchone()["valor"] or 0)

            cur.execute(f"SELECT COUNT(*) AS total FROM compras WHERE status = 'pendente' AND {scope}")
            pendentes = cur.fetchone()["total"] or 0

            # Fornecedores ativos por perfil de compra
            cur.execute("SELECT COUNT(DISTINCT id) AS total FROM fornecedores WHERE ativo = TRUE")
            fornecedores = cur.fetchone()["total"] or 0

            # Fornecedores com pedidos registrados (usados nas compras)
            cur.execute(f"""
                SELECT f.id, f.nome_fantasia, f.cnpj, COUNT(c.id) AS total_pedidos,
                       COALESCE(SUM(c.valor_total), 0) AS valor_total
                FROM   fornecedores f
                JOIN   compras c ON c.fornecedor_id = f.id
                WHERE {scope} AND c.status <> 'cancelado'
                GROUP  BY f.id, f.nome_fantasia, f.cnpj
                ORDER  BY valor_total DESC, f.id
            """)
            fornecedores_rank = cur.fetchall()
            for row in fornecedores_rank:
                row["valor_total"] = float(row["valor_total"] or 0)
                row["total_pedidos"] = int(row["total_pedidos"] or 0)

            # Pedidos por categoria (classificação por fornecedor)
            cur.execute(f"""
                SELECT DATE_FORMAT(c.data_pedido, '%Y-%m') AS mes,
                       COUNT(*) AS total,
                       COALESCE(SUM(c.valor_total), 0) AS valor
                FROM   compras c
                WHERE  {scope} AND c.status <> 'cancelado'
                GROUP  BY mes
                ORDER  BY mes ASC
            """)
            evolucao = cur.fetchall()
            for row in evolucao:
                row["total"] = int(row["total"] or 0)
                row["valor"] = float(row["valor"] or 0)

            # Categorias mais compradas (via categorias de produtos dos itens)
            cur.execute(f"""
                SELECT COALESCE(cp.nome, 'Sem Categoria') AS categoria,
                       COUNT(DISTINCT ic.compra_id) AS total_pedidos,
                       COALESCE(SUM(ic.quantidade * ic.preco_unitario), 0) AS valor
                FROM   itens_compra ic
                JOIN   produtos p        ON ic.produto_id = p.id
                LEFT JOIN categorias_produto cp ON p.categoria_id = cp.id
                JOIN   compras c         ON ic.compra_id = c.id
                WHERE  {scope} AND c.status <> 'cancelado'
                GROUP  BY cp.id, cp.nome
                ORDER  BY valor DESC
            """)
            categorias = cur.fetchall()
            for row in categorias:
                row["total_pedidos"] = int(row["total_pedidos"] or 0)
                row["valor"] = float(row["valor"] or 0)

        return ok({
            "kpis": {
                "total_pedidos":   int(total_pedidos),
                "valor_comprado":  round(valor_comprado, 2),
                "pedidos_pendentes": int(pendentes),
                "fornecedores_ativos": int(fornecedores),
            },
            "fornecedores": fornecedores_rank,
            "categorias":    categorias,
            "evolucao":      evolucao,
        })
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao gerar relatório de compras: %s", exc)
        return err("Erro interno ao gerar relatório de compras.", status=500)


# Caminhos físicos independem do diretório usado para iniciar o servidor.
FRONTEND_ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend', 'src')
FRONTEND_SRC = os.path.join(FRONTEND_ASSETS, 'pages', 'sistema')
PAGE_ASSET_EXTENSIONS = ('.html', '.css', '.js', '.png', '.jpg', '.jpeg', '.svg', '.woff', '.woff2', '.json')


def _serve_frontend_file(directory, filename, allowed_extensions=None):
    """Entrega estáticos com o mesmo MIME/cache das rotas canônica e legada.

    commonpath compara diretórios completos, evitando confundir uma pasta
    irmã de mesmo prefixo com um recurso dentro da raiz permitida.
    """
    safe = re.sub(r'[<>:"|?*]', '', filename)
    if not safe or '..' in safe:
        return err('Recurso não disponível.', status=404)
    base = os.path.realpath(directory)
    target = os.path.realpath(os.path.join(base, safe))
    try:
        inside = os.path.commonpath((base, target)) == base
    except ValueError:
        inside = False  # Unidades diferentes no Windows não têm raiz comum.
    if not inside or not os.path.isfile(target):
        return err('Recurso não encontrado.', status=404)
    if allowed_extensions and not safe.lower().endswith(allowed_extensions):
        return err('Tipo de arquivo não suportado.', status=404)
    mime, _ = mimetypes.guess_type(target)
    with open(target, 'rb') as fh:
        data = fh.read()
    resp = app.response_class(data, mimetype=mime or 'application/octet-stream')
    resp.headers['Cache-Control'] = (
        'no-cache' if safe.lower().endswith(('.html', '.css', '.js'))
        else 'public, max-age=300'
    )
    return resp


@app.route('/pages/sistema/<path:filename>')
@app.route('/pages/proprietario/<path:filename>')  # Mantém favoritos e links antigos.
def serve_sistema_page(filename):
    """Serve as telas compartilhadas por perfil nas duas URLs compatíveis."""
    return _serve_frontend_file(FRONTEND_SRC, filename, PAGE_ASSET_EXTENSIONS)


@app.route('/<path:filename>')
def serve_frontend_asset(filename):
    """Entrega utilitários, estilos, login e imagens relativos a frontend/src.

    Rotas de API mais específicas continuam tendo precedência sobre este
    caminho genérico; suas permissões são verificadas em proteger_api.
    """
    return _serve_frontend_file(FRONTEND_ASSETS, filename)


def _fin_tables_exist():
    """Verifica se as duas tabelas requeridas pelo módulo financeiro existem."""
    try:
        db = get_db()
        with db.cursor() as cur:
            cur.execute("SHOW TABLES LIKE 'financeiro_transacoes'")
            transacoes = cur.fetchone() is not None
            cur.execute("SHOW TABLES LIKE 'financeiro_categorias'")
            return transacoes and cur.fetchone() is not None
    except pymysql.MySQLError as exc:
        log.error("Erro ao verificar tabelas financeiras: %s", exc)
        return False
# ═══════════════════════════════════════════════════════════════
#  Financeiro Routes
# ═══════════════════════════════════════════════════════════════

@app.get("/financeiro/stats")
def financeiro_stats():
    """Retorna KPIs financeiros para o período selecionado."""
    if not _fin_tables_exist():
        return err('Tabelas financeiras não configuradas. Execute a migração 005_tabela_financeiro.sql', status=503)
    days = request.args.get('days', '30', type=int)
    if days not in (7, 30, 90):
        days = 30
    db = get_db()
    try:
        with db.cursor() as cur:
            # Receitas do período
            cur.execute("""
                SELECT COALESCE(SUM(CASE WHEN fc.tipo = 'receita' THEN t.valor ELSE 0 END), 0) AS receitas,
                       COALESCE(SUM(CASE WHEN fc.tipo = 'despesa' THEN t.valor ELSE 0 END), 0) AS despesas
                FROM financeiro_transacoes t
                JOIN financeiro_categorias fc ON fc.id = t.categoria_id
                WHERE t.data_transacao >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                  AND t.data_transacao < CURDATE() + INTERVAL 1 DAY
                  AND t.status = 'pago'
            """, (days,))
            row = cur.fetchone()
            receitas = float(row['receitas'] or 0)
            despesas = float(row['despesas'] or 0)
            saldo = receitas - despesas

            # Ticket médio (vendas do período)
            cur.execute("""
                SELECT AVG(valor_total) AS ticket
                FROM vendas
                WHERE data_venda >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                  AND data_venda < CURDATE() + INTERVAL 1 DAY
                  AND status = 'concluida'
            """, (days,))
            ticket = float(cur.fetchone()['ticket'] or 0)

            # Delta (comparação com período anterior)
            cur.execute("""
                SELECT COALESCE(SUM(CASE WHEN fc.tipo = 'receita' THEN t.valor ELSE 0 END), 0) AS receitas_ant
                FROM financeiro_transacoes t
                JOIN financeiro_categorias fc ON fc.id = t.categoria_id
                WHERE t.data_transacao >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                  AND t.data_transacao < DATE_SUB(CURDATE(), INTERVAL %s DAY)
                  AND t.status = 'pago'
            """, (days * 2, days))
            receitas_ant = float(cur.fetchone()['receitas_ant'] or 0)
            delta_receitas = ((receitas - receitas_ant) / receitas_ant * 100) if receitas_ant > 0 else 0

            cur.execute("""
                SELECT COALESCE(SUM(CASE WHEN fc.tipo = 'despesa' THEN t.valor ELSE 0 END), 0) AS despesas_ant
                FROM financeiro_transacoes t
                JOIN financeiro_categorias fc ON fc.id = t.categoria_id
                WHERE t.data_transacao >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                  AND t.data_transacao < DATE_SUB(CURDATE(), INTERVAL %s DAY)
                  AND t.status = 'pago'
            """, (days * 2, days))
            despesas_ant = float(cur.fetchone()['despesas_ant'] or 0)
            delta_despesas = ((despesas - despesas_ant) / despesas_ant * 100) if despesas_ant > 0 else 0

            # Sparkline data (últimos 14 pontos)
            cur.execute("""
                SELECT DATE(t.data_transacao) AS dia,
                       SUM(CASE WHEN fc.tipo = 'receita' THEN t.valor ELSE -t.valor END) AS liquido
                FROM financeiro_transacoes t
                JOIN financeiro_categorias fc ON fc.id = t.categoria_id
                WHERE t.data_transacao >= DATE_SUB(CURDATE(), INTERVAL 14 DAY)
                  AND t.data_transacao < CURDATE() + INTERVAL 1 DAY
                  AND t.status = 'pago'
                GROUP BY DATE(t.data_transacao)
                ORDER BY dia ASC
            """)
            spark = [float(r['liquido'] or 0) for r in cur.fetchall()]

        return jsonify({
            'ok': True,
            'saldo': saldo,
            'receitas': receitas,
            'despesas': despesas,
            'ticket_medio': ticket,
            'delta_receitas': delta_receitas,
            'delta_despesas': delta_despesas,
            'spark': spark
        })
    except pymysql.MySQLError as exc:
        log.error("Erro DB em financeiro/stats: %s", exc)
        return err('Erro interno ao consultar indicadores financeiros.', status=500)


@app.get("/financeiro/fluxo")
def financeiro_fluxo():
    """Retorna dados para o gráfico de fluxo de caixa (receitas vs despesas por dia)."""
    if not _fin_tables_exist():
        return err('Tabelas financeiras não configuradas. Execute a migração 005_tabela_financeiro.sql', status=503)
    days = request.args.get('days', '7', type=int)
    if days not in (7, 30, 90):
        days = 7
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    if bool(start_date) != bool(end_date):
        return err('Informe data inicial e final juntas.', campo='start_date', status=400)
    if start_date and end_date:
        try:
            start_day = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_day = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return err('Datas inválidas. Use o formato AAAA-MM-DD.', campo='start_date', status=400)
        if start_day > end_day:
            return err('A data inicial deve ser anterior à final.', campo='start_date', status=400)
    else:
        end_day = datetime.now().date()
        start_day = end_day - timedelta(days=days)
    db = get_db()
    try:
        with db.cursor() as cur:
            query = """
                SELECT DATE(t.data_transacao) AS dia,
                       SUM(CASE WHEN fc.tipo = 'receita' THEN t.valor ELSE 0 END) AS receitas,
                       SUM(CASE WHEN fc.tipo = 'despesa' THEN t.valor ELSE 0 END) AS despesas
                FROM financeiro_transacoes t
                JOIN financeiro_categorias fc ON fc.id = t.categoria_id
                WHERE t.data_transacao >= {start_clause}
                  AND t.data_transacao < {end_clause}
                  AND t.status = 'pago'
                GROUP BY DATE(t.data_transacao)
                ORDER BY dia ASC
            """
            if start_date and end_date:
                cur.execute(query.format(start_clause='%s', end_clause='DATE_ADD(%s, INTERVAL 1 DAY)'), (start_day, end_day))
            else:
                cur.execute(query.format(start_clause='DATE_SUB(CURDATE(), INTERVAL %s DAY)', end_clause='CURDATE() + INTERVAL 1 DAY'), (days,))
            rows = cur.fetchall()

        # O gráfico representa o calendário, e não apenas os dias que tiveram
        # movimento. Assim, a coluna de hoje já existe e cresce durante o dia.
        by_day = {r['dia']: r for r in rows if r.get('dia')}
        days_in_range = (end_day - start_day).days + 1
        calendar_days = [start_day + timedelta(days=offset) for offset in range(days_in_range)]
        labels = [day.strftime('%d/%m') for day in calendar_days]
        receitas = [float((by_day.get(day) or {}).get('receitas') or 0) for day in calendar_days]
        despesas = [float((by_day.get(day) or {}).get('despesas') or 0) for day in calendar_days]

        return jsonify({
            'ok': True,
            'labels': labels,
            'dias': [day.isoformat() for day in calendar_days],
            'receitas': receitas,
            'despesas': despesas,
            'periodo': {'inicio': start_day.isoformat(), 'fim': end_day.isoformat()},
        })
    except pymysql.MySQLError as exc:
        log.error("Erro DB em financeiro/fluxo: %s", exc)
        return err('Erro interno ao consultar fluxo de caixa.', status=500)


@app.get("/financeiro/categorias")
def financeiro_categorias():
    """Retorna categorias financeiras com totais agrupados."""
    if not _fin_tables_exist():
        return err('Tabelas financeiras não configuradas. Execute a migração 005_tabela_financeiro.sql', status=503)
    days = request.args.get('days', '30', type=int)
    tipo = request.args.get('tipo', None)
    if days not in (7, 30, 90):
        days = 30
    if tipo not in (None, 'receita', 'despesa'):
        return err('Tipo inválido.', campo='tipo', status=400)
    db = get_db()
    try:
        with db.cursor() as cur:
            tipo_clause = "WHERE fc.tipo = %s" if tipo else ""
            params = (days,) + ((tipo,) if tipo else ())
            cur.execute(f"""
                SELECT fc.id, fc.nome, fc.tipo,
                       COALESCE(SUM(IF(t.status='pago', t.valor, 0)), 0) AS valor,
                       COALESCE(SUM(IF(t.status='pendente', t.valor, 0)), 0) AS pendente,
                       COUNT(t.id) AS qtd
                FROM financeiro_categorias fc
                LEFT JOIN financeiro_transacoes t ON t.categoria_id = fc.id
                    AND t.data_transacao >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                    AND t.data_transacao < CURDATE() + INTERVAL 1 DAY
                    AND t.status IN ('pago', 'pendente')
                {tipo_clause}
                GROUP BY fc.id, fc.nome, fc.tipo
                ORDER BY valor DESC
            """, params)
            rows = cur.fetchall()

        categorias = [{'id': r['id'], 'nome': r['nome'], 'tipo': r['tipo'],
                       'valor': float(r['valor'] or 0), 'pendente': float(r.get('pendente') or 0), 'qtd': r['qtd']} for r in rows]

        return jsonify({'ok': True, 'categorias': categorias})
    except pymysql.MySQLError as exc:
        log.error("Erro DB em financeiro/categorias: %s", exc)
        return err('Erro interno ao consultar categorias financeiras.', status=500)


@app.get("/financeiro/transacoes")
def financeiro_transacoes():
    """Retorna lista de transações do período."""
    if not _fin_tables_exist():
        return err('Tabelas financeiras não configuradas. Execute a migração 005_tabela_financeiro.sql', status=503)
    days = request.args.get('days', '30', type=int)
    if days not in (7, 30, 90):
        days = 30
    limit = request.args.get('limit', 50, type=int)
    limit = min(max(limit, 1), 500)
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT t.id, t.descricao, t.valor, t.data_transacao,
                       t.status, t.metodo_pagamento,
                       fc.tipo, fc.nome AS categoria_nome
                FROM financeiro_transacoes t
                JOIN financeiro_categorias fc ON fc.id = t.categoria_id
                WHERE t.data_transacao >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                  AND t.data_transacao < CURDATE() + INTERVAL 1 DAY
                ORDER BY t.data_transacao DESC
                LIMIT %s
            """, (days, limit))
            rows = cur.fetchall()

        transacoes = [{
            'id': r['id'],
            'descricao': r['descricao'],
            'valor': float(r['valor']),
            'data_transacao': r['data_transacao'].strftime('%Y-%m-%d %H:%M:%S') if r['data_transacao'] else '—',
            'status': r['status'],
            'metodo_pagamento': r['metodo_pagamento'],
            'tipo': r['tipo'],
            'categoria_nome': r['categoria_nome']
        } for r in rows]

        return jsonify({'ok': True, 'transacoes': transacoes})
    except pymysql.MySQLError as exc:
        log.error("Erro DB em financeiro/transacoes: %s", exc)
        return err('Erro interno ao consultar transações financeiras.', status=500)


@app.post("/financeiro/transacoes")
def create_financeiro_transacao():
    """Cria uma nova transação financeira."""
    if not _fin_tables_exist():
        return jsonify({'ok': False, 'mensagem': 'Tabelas financeiras não configuradas. Execute a migração 005_tabela_financeiro.sql'}), 503
    data = request.get_json(silent=True) or {}
    tipo = (data.get('tipo') or '').strip().lower()
    categoria_id = data.get('categoria_id')
    descricao = (data.get('descricao') or '').strip()
    valor = data.get('valor')
    data_transacao = (data.get('data_transacao') or '').strip()
    metodo = (data.get('metodo_pagamento') or '').strip()

    if tipo not in ('receita', 'despesa'):
        return jsonify({'ok': False, 'mensagem': 'Tipo inválido.'}), 400
    if not categoria_id:
        return jsonify({'ok': False, 'mensagem': 'Selecione uma categoria.'}), 400
    if not descricao:
        return jsonify({'ok': False, 'mensagem': 'Informe uma descrição.'}), 400
    # Mantém números e strings numéricas aceitos pela API, mas impede que
    # conversões inválidas escapem como HTTP 500 ou levem NaN/Infinity ao SQL.
    try:
        valor = float(valor)
    except (TypeError, ValueError, OverflowError):
        return jsonify({'ok': False, 'mensagem': 'Informe um valor válido.'}), 400
    if not math.isfinite(valor) or valor <= 0:
        return jsonify({'ok': False, 'mensagem': 'Informe um valor válido.'}), 400
    if metodo not in ('dinheiro', 'pix', 'cartao_credito', 'cartao_debito', 'boleto', 'transferencia'):
        return jsonify({'ok': False, 'mensagem': 'Método de pagamento inválido.'}), 400
    if data_transacao:
        try:
            # O formulário envia somente a data; armazenamos o início desse dia
            # para que os agrupamentos de fluxo e categoria a considerem nele.
            data_transacao = datetime.strptime(data_transacao, '%Y-%m-%d').strftime('%Y-%m-%d 00:00:00')
        except ValueError:
            return jsonify({'ok': False, 'mensagem': 'Informe uma data válida no formato AAAA-MM-DD.'}), 400

    db = get_db()
    try:
        with db.cursor() as cur:
            # Verifica categoria
            cur.execute("SELECT id, tipo FROM financeiro_categorias WHERE id = %s", (categoria_id,))
            cat = cur.fetchone()
            if not cat:
                return jsonify({'ok': False, 'mensagem': 'Categoria não encontrada.'}), 404
            if cat['tipo'] != tipo:
                return jsonify({'ok': False, 'mensagem': 'Categoria não corresponde ao tipo.'}), 400

            # A data é um parâmetro, nunca um fragmento SQL. Ausência mantém
            # o horário do banco (NOW), como no contrato anterior.
            cur.execute("""
                INSERT INTO financeiro_transacoes (categoria_id, usuario_id, descricao, valor, data_transacao, metodo_pagamento, status)
                VALUES (%s, %s, %s, %s, COALESCE(%s, NOW()), %s, 'pago')
            """, (categoria_id, g.usuario_id, descricao, valor, data_transacao or None, metodo))
            commit_audit(db, cur.lastrowid)

        log.info("Nova transação financeira: %s %s", tipo, descricao)
        return jsonify({'ok': True, 'mensagem': 'Transação registrada com sucesso.'}), 201
    except Exception as exc:
        db.rollback()
        log.error("Erro DB em create_transacao: %s", exc)
        return jsonify({'ok': False, 'mensagem': 'Erro ao salvar transação.'}), 400


@app.after_request
def check_scheduled_notifications(response):
    if (not app.testing and response.status_code < 400 and request.method == 'GET'
            and request.path == '/dashboard/stats' and getattr(g, 'usuario_id', None)):
        if all(os.getenv(k) for k in ('BREVO_SMTP_LOGIN', 'BREVO_SMTP_PASSWORD', 'BREVO_SENDER_EMAIL')):
            schedule_notifications(app, get_db, enviar_email_brevo)
    return response


if __name__ == "__main__":
    if app.config["APP_ENV"] == "production":
        raise RuntimeError("Em produção, inicie app:app com um servidor WSGI atrás de HTTPS.")
    app.run(host="127.0.0.1", debug=app.config["DEBUG"], port=5000)


