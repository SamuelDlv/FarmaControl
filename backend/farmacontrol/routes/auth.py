"""routes.auth: responsabilidades extraídas da aplicação Flask."""

from farmacontrol.core import access
from farmacontrol.core import credentials
from farmacontrol.core import database
from farmacontrol.core import responses
from farmacontrol.core.security import credential_stamp
from farmacontrol.services import email as email_service
from farmacontrol.services.audit import commit_audit
from flask import current_app as app
from flask import g
from flask import request
from flask import session
import html
import logging
import os
import pymysql.cursors
import secrets

log = logging.getLogger("farmacontrol")


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
        convite_hash = credentials.hash_convite(convite_token)
        try:
            with database.get_db().cursor() as cur:
                cur.execute("""
                    SELECT c.nome, c.sobrenome, c.email, p.slug AS perfil
                    FROM convites_cadastro c JOIN perfis p ON p.id = c.perfil_id
                    WHERE c.token_hash = %s AND c.status = 'pendente'
                      AND c.expira_em > NOW() FOR UPDATE
                """, (convite_hash,))
                convite = cur.fetchone()
            if not convite:
                return responses.err("Este convite é inválido, já foi usado ou expirou.", campo="convite", status=410)
            nome, sobrenome, email, role = convite["nome"], convite["sobrenome"], convite["email"], convite["perfil"]
        except pymysql.MySQLError as exc:
            log.error("Erro ao validar convite: %s", exc)
            return responses.err("Não foi possível validar o convite.", status=500)

    # ── Validações ──────────────────────────
    if len(nome) < 2:
        return responses.err("Nome deve ter pelo menos 2 caracteres.", campo="nome")
    if len(sobrenome) < 2:
        return responses.err("Sobrenome deve ter pelo menos 2 caracteres.", campo="sobrenome")
    if not access.EMAIL_RE.match(email):
        return responses.err("Informe um e-mail válido.", campo="email")
    if role not in access.PERFIS_VALIDOS:
        return responses.err("Perfil de acesso inválido.", campo="role")
    if len(senha) < 8:
        return responses.err("A senha deve ter pelo menos 8 caracteres.", campo="password")
    if not aceita_termos or not aceita_privacidade:
        return responses.err("É necessário aceitar os Termos de Uso e a Política de Privacidade.", campo="legal")

    db = None
    permissoes = set()
    try:
        db = database.get_db()
        with db.cursor() as cur:
            # E-mail já cadastrado?
            cur.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
            if cur.fetchone():
                return responses.err("Este e-mail já está cadastrado.", campo="email", status=409)

            # Resolve perfil_id
            cur.execute("SELECT id, nome FROM perfis WHERE slug = %s", (role,))
            perfil = cur.fetchone()
            if not perfil:
                return responses.err("Perfil não encontrado no sistema.", campo="role")
            permissoes = access.permissoes_efetivas(cur, role)

            senha_hash = credentials.hash_senha(senha)

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
                    credentials.LEGAL_DOCUMENT_VERSION,
                    credentials.LEGAL_DOCUMENT_VERSION,
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
                    return responses.err("Este convite é inválido, já foi usado ou expirou.", status=410)
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
            return responses.ok({
                "mensagem": "Convite confirmado. Seu acesso já está liberado.",
                "csrf_token": session["csrf_token"],
                "usuario": {"id": usuario_criado_id, "nome": nome, "sobrenome": sobrenome,
                            "email": email, "perfil": role, "perfil_nome": perfil["nome"],
                            "permissoes": sorted(permissoes)},
            }, status=201)
        email_service.enviar_email_brevo(
            email,
            "Recebemos seu cadastro no FarmaControl",
            "<p>Recebemos seu cadastro. Ele será liberado após a análise da equipe responsável.</p>",
        )
        return responses.ok(
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
        return responses.err("Erro interno. Tente novamente em instantes.", status=500)


def solicitar_recuperacao_senha():
    """Envia um link de uso único sem revelar se o e-mail possui conta."""
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    resposta = {"mensagem": "Se houver uma conta com este e-mail, enviaremos um link para redefinir a senha."}
    if not access.EMAIL_RE.match(email):
        return responses.ok(resposta)

    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT id, nome FROM usuarios WHERE email = %s AND status = 'aprovado'",
                (email,),
            )
            usuario = cur.fetchone()
            if not usuario:
                return responses.ok(resposta)
            token = secrets.token_urlsafe(32)
            cur.execute(
                """UPDATE usuarios
                   SET token_reset = %s, token_expira_em = DATE_ADD(NOW(), INTERVAL %s HOUR)
                   WHERE id = %s""",
                (credentials.hash_token_recuperacao(token), credentials.PASSWORD_RESET_EXPIRY_HOURS, usuario["id"]),
            )
        g.audit_actor = usuario["id"]
        commit_audit(db, cur.lastrowid)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro ao solicitar recuperação de senha: %s", exc)
        return responses.err("Não foi possível processar a solicitação. Tente novamente.", status=500)

    base_url = os.getenv("APP_PUBLIC_URL", "http://localhost:5000").rstrip("/")
    link = f"{base_url}/pages/redefinir-senha/redefinir-senha.html?token={token}"
    nome = html.escape(usuario.get("nome") or "usuário")
    email_service.enviar_email_brevo(
        email,
        "Redefina sua senha do FarmaControl",
        f"<p>Olá, {nome}.</p><p>Recebemos uma solicitação para redefinir sua senha.</p>"
        f'<p><a href="{link}">Redefinir minha senha</a></p>'
        "<p>Por segurança, este link expira em 1 hora e pode ser usado apenas uma vez.</p>",
    )
    return responses.ok(resposta)


def redefinir_senha():
    """Define a senha por meio de token único, válido por tempo limitado."""
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    senha = data.get("password") or ""
    if len(senha) < 8:
        return responses.err("A senha deve ter pelo menos 8 caracteres.", campo="password")
    if not token:
        return responses.err("Este link de recuperação é inválido ou expirou.", status=410)

    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """SELECT id FROM usuarios
                   WHERE token_reset = %s AND token_expira_em > NOW() FOR UPDATE""",
                (credentials.hash_token_recuperacao(token),),
            )
            usuario = cur.fetchone()
            if not usuario:
                return responses.err("Este link de recuperação é inválido ou expirou.", status=410)
            cur.execute(
                """UPDATE usuarios
                   SET senha_hash = %s, token_reset = NULL, token_expira_em = NULL
                   WHERE id = %s""",
                (credentials.hash_senha(senha), usuario["id"]),
            )
        g.audit_actor = usuario["id"]
        commit_audit(db, cur.lastrowid)
        return responses.ok({"mensagem": "Senha redefinida com sucesso. Você já pode entrar."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro ao redefinir senha: %s", exc)
        return responses.err("Não foi possível redefinir a senha. Tente novamente.", status=500)


def consultar_convite(token):
    """Permite à página de cadastro preencher apenas um convite ainda válido."""
    try:
        with database.get_db().cursor() as cur:
            cur.execute("""
                SELECT c.nome, c.sobrenome, c.email, p.slug AS role
                FROM convites_cadastro c JOIN perfis p ON p.id = c.perfil_id
                WHERE c.token_hash = %s AND c.status = 'pendente' AND c.expira_em > NOW()
            """, (credentials.hash_convite(token),))
            convite = cur.fetchone()
        if not convite:
            return responses.err("Convite inválido, já utilizado ou expirado.", status=410)
        return responses.ok({"convite": convite})
    except pymysql.MySQLError as exc:
        log.error("Erro ao consultar convite: %s", exc)
        return responses.err("Não foi possível consultar o convite.", status=500)


def recusar_convite(token):
    """Recusa um convite sem criar conta ou aceitar documentos legais."""
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                UPDATE convites_cadastro SET status = 'recusado', respondido_em = NOW()
                WHERE token_hash = %s AND status = 'pendente' AND expira_em > NOW()
            """, (credentials.hash_convite(token),))
            if not cur.rowcount:
                return responses.err("Convite inválido, já utilizado ou expirado.", status=410)
        commit_audit(db, cur.lastrowid)
        return responses.ok({"mensagem": "Convite recusado. Nenhuma conta foi criada."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro ao recusar convite: %s", exc)
        return responses.err("Não foi possível recusar o convite.", status=500)


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

    if not access.EMAIL_RE.match(email):
        return responses.err("Informe um e-mail válido.", campo="email")
    if not senha:
        return responses.err("Informe sua senha.", campo="password")
    if not isinstance(remember, bool):
        return responses.err("Valor de lembrar acesso inválido.", campo="remember")

    db = database.get_db()
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
                return responses.err("E-mail ou senha incorretos.", status=401)

            # Verifica senha (timing-safe via bcrypt)
            senha_ok = credentials.verificar_senha(senha, usuario["senha_hash"])

            if not senha_ok:
                credentials.registrar_acesso(cur, usuario["id"], sucesso=False, motivo="senha incorreta")
                commit_audit(db, cur.lastrowid)
                return responses.err("E-mail ou senha incorretos.", status=401)

            # Conta pendente
            if usuario["status"] == "pendente":
                credentials.registrar_acesso(cur, usuario["id"], sucesso=False, motivo="cadastro pendente")
                commit_audit(db, cur.lastrowid)
                return responses.err(
                    "Seu cadastro ainda está sendo analisado. "
                    "Aguarde a aprovação da equipe responsável.",
                    status=403,
                )

            # Conta rejeitada
            if usuario["status"] == "rejeitado":
                credentials.registrar_acesso(cur, usuario["id"], sucesso=False, motivo="cadastro rejeitado")
                commit_audit(db, cur.lastrowid)
                return responses.err(
                    "Seu cadastro foi recusado. "
                    "Entre em contato com o administrador do sistema.",
                    status=403,
                )

            # ── Login bem-sucedido ───────────────────
            permissoes = access.permissoes_efetivas(cur, usuario["perfil"])
            cur.execute(
                "UPDATE usuarios SET ultimo_login = NOW() WHERE id = %s",
                (usuario["id"],),
            )
            credentials.registrar_acesso(cur, usuario["id"], sucesso=True)
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
        return responses.ok(
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
                    "permissoes":  sorted(permissoes) if usuario["perfil"] in access.EDITABLE_PROFILE_SLUGS else None,
                },
            }
        )

    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB no login: %s", exc)
        return responses.err("Erro interno. Tente novamente em instantes.", status=500)


def logout():
    """Invalida a sessao atual no navegador."""
    esperado = session.get("csrf_token")
    recebido = request.headers.get("X-CSRF-Token", "")
    if esperado and not secrets.compare_digest(recebido.encode(), esperado.encode()):
        return responses.err("Requisicao invalida.", status=403)
    if session.get("usuario_id"):
        try:
            commit_audit(database.get_db())
        except pymysql.MySQLError:
            database.get_db().rollback()
            return responses.err("Não foi possível registrar a saída. Tente novamente.", status=503)
    session.clear()
    return responses.ok({"mensagem": "Sessao encerrada."})


def register_routes(app):
    """Registra as URLs e nomes de endpoints existentes."""
    app.add_url_rule('/auth/register', view_func=register, methods=['POST'])
    app.add_url_rule('/auth/recuperar-senha', view_func=solicitar_recuperacao_senha, methods=['POST'])
    app.add_url_rule('/auth/redefinir-senha', view_func=redefinir_senha, methods=['POST'])
    app.add_url_rule('/auth/convites/<string:token>', view_func=consultar_convite, methods=['GET'])
    app.add_url_rule('/auth/convites/<string:token>/recusar', view_func=recusar_convite, methods=['POST'])
    app.add_url_rule('/auth/login', view_func=login, methods=['POST'])
    app.add_url_rule('/auth/logout', view_func=logout, methods=['POST'])
