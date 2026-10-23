"""routes.admin: responsabilidades extraídas da aplicação Flask."""

from datetime import datetime
from datetime import timedelta
from datetime import timezone
from farmacontrol.core import access
from farmacontrol.core import credentials
from farmacontrol.core import database
from farmacontrol.core import responses
from farmacontrol.services import email as email_service
from farmacontrol.services.audit import commit_audit
from flask import g
from flask import request
import html
import logging
import os
import pymysql.cursors
import re
import secrets

log = logging.getLogger("farmacontrol")


def listar_usuarios():
    """
    Lista todos os usuários do sistema para o painel administrativo.
    """
    db = database.get_db()
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

        return responses.ok({"usuarios": usuarios})

    except pymysql.MySQLError as exc:
        log.error("Erro DB ao listar usuários: %s", exc)
        return responses.err("Erro interno.", status=500)


def listar_logs():
    """Histórico somente para consulta, com paginação por cursor estável."""
    try:
        limit = max(1, min(100, int(request.args.get("limit", "50"))))
        before = int(request.args.get("antes", "0"))
        if before < 0:
            raise ValueError
    except (ValueError, TypeError):
        return responses.err("Paginação inválida.")
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
            return responses.err("Não é possível consultar atividades em datas futuras. Escolha uma data até hoje.")
        # O filtro usa o mesmo horário de Brasília exibido pela tela (UTC-3).
        if "data_inicio" in dates:
            conditions.append("criado_em >= %s")
            params.append(dates["data_inicio"] + timedelta(hours=3))
        if "data_fim" in dates:
            conditions.append("criado_em < %s")
            params.append(dates["data_fim"] + timedelta(days=1, hours=3))
    except (ValueError, TypeError, OverflowError):
        return responses.err("Informe um usuário válido e um período de datas válido.")
    search = request.args.get("busca", "").strip()
    activity = request.args.get("atividade", "")
    if len(search) > 120 or activity not in {"", "alteracoes", "consultas"}:
        return responses.err("Informe uma busca de até 120 caracteres e uma atividade válida.")
    if search:
        conditions.append("(LOCATE(%s, acao) > 0 OR LOCATE(%s, detalhes) > 0 OR LOCATE(%s, usuario_nome) > 0)")
        params.extend([search] * 3)
    if activity:
        conditions.append("detalhes " + ("NOT LIKE" if activity == "alteracoes" else "LIKE") + " %s")
        params.append("GET %")
    try:
        users = None
        with database.get_db().cursor() as cur:
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
        return responses.ok(result)
    except pymysql.MySQLError as exc:
        log.error("Erro ao consultar histórico: %s", exc)
        return responses.err("Não foi possível carregar o log. Verifique a migração 016.", status=503)


def listar_pendentes():
    """
    Lista todos os cadastros aguardando análise.
    A sessão, o perfil administrativo e o CSRF são verificados em proteger_api.
    """
    db = database.get_db()
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

        return responses.ok({"pendentes": pendentes})

    except pymysql.MySQLError as exc:
        log.error("Erro DB ao listar pendentes: %s", exc)
        return responses.err("Erro interno. Tente novamente em instantes.", status=500)


def listar_permissoes_perfis():
    db = database.get_db()
    try:
        access.require_profile_permissions_table(db)
        with db.cursor() as cur:
            cur.execute("""
                SELECT p.slug, p.nome, pp.modulo, pp.permitido
                FROM perfis p
                LEFT JOIN perfil_permissoes pp ON pp.perfil_id = p.id
                WHERE p.slug IN (%s, %s, %s, %s, %s, %s, %s)
                ORDER BY FIELD(p.slug, 'proprietario', 'admin', 'farmaceutico', 'atendente', 'visualizador', 'compras', 'ti'), pp.modulo
            """, access.EDITABLE_PROFILE_SLUGS)
            rows = cur.fetchall()
        profiles = {}
        for row in rows:
            profile = profiles.setdefault(row["slug"], {"slug": row["slug"], "nome": row["nome"], "permissoes": []})
            if row["modulo"] and row["permitido"]:
                profile["permissoes"].append(row["modulo"])
        return responses.ok({"perfis": list(profiles.values()), "modulos": list(access.PERMISSION_MODULES)})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro ao listar permissões de perfil: %s", exc)
        return responses.err("Não foi possível carregar as permissões.", status=500)


def atualizar_permissoes_perfis():
    data = request.get_json(silent=True) or {}
    changes = data.get("perfis")
    if not isinstance(changes, dict):
        return responses.err("Informe as permissões por perfil.", campo="perfis")
    invalid_profiles = set(changes) - set(access.EDITABLE_PROFILE_SLUGS)
    if invalid_profiles:
        return responses.err("Perfil inválido.", campo="perfis")
    for permissions in changes.values():
        if (not isinstance(permissions, list)
                or any(not isinstance(module, str) for module in permissions)
                or set(permissions) - set(access.PERMISSION_MODULES)):
            return responses.err("Módulo de permissão inválido.", campo="perfis")
    db = database.get_db()
    try:
        access.require_profile_permissions_table(db)
        with db.cursor() as cur:
            for slug, permissions in changes.items():
                cur.execute("SELECT id FROM perfis WHERE slug = %s", (slug,))
                profile = cur.fetchone()
                if not profile:
                    return responses.err("Perfil não encontrado.", campo="perfis", status=404)
                cur.execute("DELETE FROM perfil_permissoes WHERE perfil_id = %s", (profile["id"],))
                cur.executemany(
                    "INSERT INTO perfil_permissoes (perfil_id, modulo, permitido) VALUES (%s, %s, 1)",
                    [(profile["id"], module) for module in permissions],
                )
        g.audit_permissions = changes
        commit_audit(db)
        return responses.ok({"mensagem": "Permissões atualizadas com sucesso."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro ao atualizar permissões de perfil: %s", exc)
        return responses.err("Não foi possível salvar as permissões.", status=500)


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
        return responses.err("Nome deve ter pelo menos 2 caracteres.", campo="nome")
    if email is not None and not access.EMAIL_RE.match(email):
        return responses.err("Informe um e-mail válido.", campo="email")
    if role is not None and role not in access.PERFIS_VALIDOS:
        return responses.err("Perfil de acesso inválido.", campo="perfil")
    if status and status not in ("ativo", "inativo"):
        return responses.err("Status inválido. Use 'ativo' ou 'inativo'.", campo="status")
    if senha is not None and len(senha) < 8:
        return responses.err("A senha deve ter pelo menos 8 caracteres.", campo="senha")
    if nome is None and email is None and role is None and senha is None and status is None:
        return responses.err("Informe ao menos um campo para atualizar.")
    if usuario_id == g.usuario_id and status == "inativo":
        return responses.err("Você não pode desativar sua própria conta enquanto estiver conectado.", status=409)

    # Mapeia o status amigável para o valor real do banco
    status_db = {"ativo": "aprovado", "inativo": "rejeitado"}.get(status)

    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM usuarios WHERE id = %s", (usuario_id,))
            if not cur.fetchone():
                return responses.err("Usuário não encontrado.", status=404)
            # E-mail já em uso por outro usuário?
            if email is not None:
                cur.execute("SELECT id FROM usuarios WHERE email = %s AND id != %s", (email, usuario_id))
                if cur.fetchone():
                    return responses.err("Este e-mail já está em uso por outro usuário.", campo="email", status=409)

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
                    return responses.err("Perfil não encontrado no sistema.", campo="perfil")
                set_parts.append("perfil_id = %s")
                values.append(perfil["id"])

            if status_db:
                set_parts.append("status = %s")
                values.append(status_db)

            if senha is not None and senha:
                set_parts.extend(["senha_hash = %s", "token_reset = NULL", "token_expira_em = NULL"])
                values.append(credentials.hash_senha(senha))

            values.append(usuario_id)
            cur.execute(
                f"UPDATE usuarios SET {', '.join(set_parts)} WHERE id = %s",
                tuple(values),
            )
            commit_audit(db, cur.lastrowid)

        log.info("Usuário %s atualizado", usuario_id)
        return responses.ok({"mensagem": "Usuário atualizado com sucesso."})

    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao editar usuário: %s", exc)
        return responses.err("Erro interno. Tente novamente em instantes.", status=500)


def criar_convite():
    """Cria convite pendente e envia ao destinatário links de aceitar/recusar."""
    data = request.get_json(silent=True) or {}
    nome = (data.get("nome") or "").strip()
    sobrenome = (data.get("sobrenome") or "").strip()
    email = (data.get("email") or "").strip().lower()
    role = (data.get("role") or "").strip()
    if len(nome) < 2 or len(sobrenome) < 2:
        return responses.err("Informe nome e sobrenome.", campo="nome", status=400)
    if not access.EMAIL_RE.match(email):
        return responses.err("Informe um e-mail válido.", campo="email", status=400)
    if role not in access.PERFIS_VALIDOS or role == "proprietario":
        return responses.err("Perfil de convite inválido.", campo="role", status=400)

    token = secrets.token_urlsafe(32)
    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
            if cur.fetchone():
                return responses.err("Este e-mail já possui uma conta.", campo="email", status=409)
            cur.execute("SELECT id FROM perfis WHERE slug = %s", (role,))
            perfil = cur.fetchone()
            if not perfil:
                return responses.err("Perfil não encontrado.", campo="role", status=400)
            # Substitui convite pendente anterior para o mesmo e-mail, sem
            # expor nem reutilizar o token anterior.
            cur.execute("UPDATE convites_cadastro SET status = 'expirado', respondido_em = NOW() WHERE email = %s AND status = 'pendente'", (email,))
            cur.execute("""
                INSERT INTO convites_cadastro
                    (nome, sobrenome, email, perfil_id, convidado_por_usuario_id, token_hash, expira_em)
                VALUES (%s, %s, %s, %s, %s, %s, DATE_ADD(NOW(), INTERVAL %s HOUR))
            """, (nome, sobrenome, email, perfil["id"], g.usuario_id, credentials.hash_convite(token), credentials.INVITE_EXPIRY_HOURS))
        commit_audit(db, cur.lastrowid)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro ao criar convite: %s", exc)
        return responses.err("Não foi possível criar o convite.", status=500)

    base_url = os.getenv("APP_PUBLIC_URL", "http://localhost:5000").rstrip("/")
    aceitar_url = f"{base_url}/pages/convite/convite.html?convite={token}"
    recusar_url = f"{base_url}/pages/convite/convite.html?convite={token}&recusar=1"
    nome_seguro = html.escape(nome)
    enviado = email_service.enviar_email_brevo(
        email,
        "Convite para o FarmaControl",
        f"""<p>Olá, {nome_seguro}.</p>
        <p>Você recebeu um convite para criar seu acesso ao FarmaControl.</p>
        <p><a href=\"{aceitar_url}\">Aceitar convite</a> &nbsp;|&nbsp; <a href=\"{recusar_url}\">Recusar convite</a></p>
        <p>O convite expira em 7 dias. Ao aceitar, você definirá sua senha e confirmará os documentos legais.</p>""",
    )
    if not enviado:
        return responses.err("O convite foi salvo, mas o e-mail não pôde ser enviado. Verifique o SMTP da Brevo antes de reenviar.", status=503)
    return responses.ok({"mensagem": "Convite enviado por e-mail. A conta será criada somente se a pessoa aceitar os documentos legais.", "email": email}, status=201)


def excluir_usuario(usuario_id):
    """Remove uma conta sem permitir a autoexclusao da sessao atual."""
    if usuario_id == g.usuario_id:
        return responses.err("Voce nao pode excluir a propria conta enquanto estiver conectado.", status=409)

    db = database.get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM usuarios WHERE id = %s", (usuario_id,))
            if not cur.fetchone():
                return responses.err("Usuario nao encontrado.", status=404)
            # Aceites pertencem exclusivamente à conta. Ao excluir uma conta
            # sem histórico operacional, remove-se também esse dado pessoal;
            # movimentações e documentos operacionais continuam protegidos
            # pelas demais FKs RESTRICT.
            cur.execute("DELETE FROM aceites_legais WHERE usuario_id = %s", (usuario_id,))
            cur.execute("DELETE FROM usuarios WHERE id = %s", (usuario_id,))
            commit_audit(db, cur.lastrowid)
        log.info("Usuario %s excluido por %s", usuario_id, g.usuario_id)
        return responses.ok({"mensagem": "Conta excluida com sucesso."})
    except pymysql.IntegrityError:
        db.rollback()
        return responses.err(
            "Esta conta possui movimentacoes ou documentos vinculados e nao pode ser excluida. "
            "Desative a conta para preservar o historico.",
            status=409,
        )
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao excluir usuario %s: %s", usuario_id, exc)
        return responses.err("Erro interno ao excluir a conta.", status=500)


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
        return responses.err("ID do usuário inválido.", campo="usuario_id")
    if decisao not in ["aprovado", "rejeitado"]:
        return responses.err("Decisão inválida. Use 'aprovado' ou 'rejeitado'.", campo="decisao")

    db = database.get_db()
    try:
        with db.cursor() as cur:
            # Verifica se o usuário existe e está pendente
            cur.execute("SELECT id, nome, email, status FROM usuarios WHERE id = %s", (usuario_id,))
            usuario = cur.fetchone()
            if not usuario:
                return responses.err("Usuário não encontrado.", status=404)
            if usuario["status"] not in ("pendente", "aprovado", "rejeitado"):
                return responses.err("O cadastro deste usuário não pode ser analisado.", status=400)

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
        email_service.enviar_email_brevo(usuario["email"], assunto, corpo)
        return responses.ok({"mensagem": f"Cadastro {decisao} com sucesso."})

    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao analisar cadastro: %s", exc)
        return responses.err("Erro interno. Tente novamente em instantes.", status=500)


def register_routes(app):
    """Registra as URLs e nomes de endpoints existentes."""
    app.add_url_rule('/admin/usuarios', view_func=listar_usuarios, methods=['GET'])
    app.add_url_rule('/admin/logs', view_func=listar_logs, methods=['GET'])
    app.add_url_rule('/admin/pendentes', view_func=listar_pendentes, methods=['GET'])
    app.add_url_rule('/admin/perfis/permissoes', view_func=listar_permissoes_perfis, methods=['GET'])
    app.add_url_rule('/admin/perfis/permissoes', view_func=atualizar_permissoes_perfis, methods=['PUT'])
    app.add_url_rule('/admin/usuarios/<int:usuario_id>', view_func=editar_usuario, methods=['PUT'])
    app.add_url_rule('/admin/convites', view_func=criar_convite, methods=['POST'])
    app.add_url_rule('/admin/usuarios/<int:usuario_id>', view_func=excluir_usuario, methods=['DELETE'])
    app.add_url_rule('/admin/analisar-cadastro', view_func=analisar_cadastro, methods=['POST'])
