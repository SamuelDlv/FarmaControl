"""core.access: responsabilidades extraídas da aplicação Flask."""

from farmacontrol.core import database
from farmacontrol.core import responses
from farmacontrol.core.security import credential_stamp
from flask import current_app as app
from flask import g
from flask import session
import logging
import pymysql.cursors
import re
import secrets

log = logging.getLogger("farmacontrol")


EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


PERFIS_VALIDOS = {"proprietario", "farmaceutico", "admin", "atendente", "compras", "ti", "visualizador"}


ALL_ROLES = PERFIS_VALIDOS


INVENTORY_ROLES = {"proprietario", "admin", "farmaceutico", "compras", "ti"}


REPORT_ROLES = {"proprietario", "admin", "farmaceutico", "compras", "ti"}


FINANCE_ROLES = {"proprietario", "admin", "ti"}


ADMIN_ROLES = {"proprietario", "admin", "ti"}


SALES_ROLES = {"proprietario", "admin", "farmaceutico", "atendente", "ti"}


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


def validar_sessao():
    """Valida a sessão e a conta no banco tanto para HTML quanto para APIs."""
    usuario_id = session.get("usuario_id")
    perfil = session.get("perfil")
    if not usuario_id or perfil not in PERFIS_VALIDOS:
        return responses.err("Sua sessao expirou. Entre novamente para continuar.", status=401)
    # A sessao e assinada, mas a conta pode ter sido bloqueada ou mudado de
    # perfil depois do login. A fonte de verdade continua sendo o banco.
    try:
        with database.get_db().cursor() as cur:
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
        return responses.err("Nao foi possivel validar sua sessao. Tente novamente.", status=503)
    if not usuario_atual or usuario_atual["status"] != "aprovado":
        session.clear()
        return responses.err("Sua conta nao possui mais acesso ao sistema.", status=401)
    stamp = session.get("credential_stamp", "")
    password_hash = usuario_atual.get("senha_hash")
    if (not isinstance(stamp, str) or not password_hash or not secrets.compare_digest(
            stamp, credential_stamp(app.config["SECRET_KEY"], password_hash))):
        session.clear()
        return responses.err("Sua credencial mudou. Entre novamente.", status=401)
    perfil = usuario_atual["perfil"]
    session["perfil"] = perfil
    g.usuario_id = usuario_id
    g.usuario_perfil = perfil
    g.usuario_permissoes = permissoes
    return None


PERMISSION_MODULES = (
    "dashboard", "estoque", "vencimentos", "relatorios",
    "compras", "financeiro", "usuarios", "configuracoes",
)


def require_profile_permissions_table(db):
    """Valida a migração permanente de permissões, sem alterar o schema em produção."""
    with db.cursor() as cur:
        cur.execute("SELECT 1 FROM perfil_permissoes LIMIT 1")

