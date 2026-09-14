"""
FARMAControl — Backend API (Flask + MariaDB)
══════════════════════════════════════════════

Sistema de gestão para farmácias com IA preditiva.

ARQUITETURA:
├── Flask App: Servidor HTTP RESTful
├── Database: MariaDB/MySQL via PyMySQL (connection pooling)
├── Auth: JWT-free (sessão via localStorage no frontend)
├── CORS: Habilitado para desenvolvimento local
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
├── GET  /estoque                → Produtos com paginação
├── POST /estoque                → Criar produto
├── PUT  /estoque/<id>           → Editar produto
├── DELETE /estoque/<id>         → Excluir produto
├── GET  /usuarios               → Lista de usuários
├── POST /usuarios               → Criar usuário
├── POST /auth/login             → Autenticar
├── POST /auth/register          → Cadastrar novo usuário
└── GET  /configuracoes          → Configurações do usuário
"""

import os
import re
import logging
from datetime import datetime, timezone

import bcrypt
import pymysql
import pymysql.cursors
from dotenv import load_dotenv
from flask import Flask, jsonify, request, g, send_from_directory
from flask_cors import CORS

# ─────────────────────────────────────────────
#  Configuração inicial
# ─────────────────────────────────────────────
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("farmacontrol")

app = Flask(__name__)
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if os.getenv("FLASK_DEBUG", "false").lower() == "true":
        SECRET_KEY = "dev-only-change-me"
    else:
        raise RuntimeError("SECRET_KEY deve ser definida no ambiente.")
app.config["SECRET_KEY"] = SECRET_KEY

# CORS — aceita as origens definidas em .env; "*" libera qualquer origem local conhecida
# (útil ao abrir o HTML direto no navegador ou em Live Server de outra porta)
_origins_raw = os.getenv("ALLOWED_ORIGINS", "*")
_parsed = [o.strip() for o in _origins_raw.split(",") if o.strip()]
if '*' in _parsed:
    ALLOWED_ORIGINS = [
        'http://localhost:5000',
        'http://127.0.0.1:5000',
        'http://localhost:5500',
        'http://127.0.0.1:5500',
        'http://localhost:5501',
        'http://localhost:3000',
        'http://localhost:5173',
        'http://localhost:8000',
        'http://localhost:8080',
        'http://127.0.0.1:3000',
        'http://127.0.0.1:5173',
        'http://127.0.0.1:5501',
        'null',  # páginas abertas direto como arquivo (file://)
    ]
else:
    ALLOWED_ORIGINS = _parsed
CORS(app,
     origins=ALLOWED_ORIGINS,
     supports_credentials=True,
     expose_headers=['Content-Type', 'Authorization'])

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


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt(BCRYPT_ROUNDS)).decode()


def verificar_senha(senha: str, hash_: str) -> bool:
    return bcrypt.checkpw(senha.encode(), hash_.encode())


def registrar_acesso(cursor, usuario_id: int, sucesso: bool, motivo: str | None = None):
    """Grava log de tentativa de acesso."""
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
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

    db = get_db()
    try:
        with db.cursor() as cur:
            # E-mail já cadastrado?
            cur.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
            if cur.fetchone():
                return err("Este e-mail já está cadastrado.", campo="email", status=409)

            # Resolve perfil_id
            cur.execute("SELECT id FROM perfis WHERE slug = %s", (role,))
            perfil = cur.fetchone()
            if not perfil:
                return err("Perfil não encontrado no sistema.", campo="role")

            senha_hash = hash_senha(senha)

            cur.execute(
                """
                INSERT INTO usuarios (nome, sobrenome, email, senha_hash, perfil_id, status)
                VALUES (%s, %s, %s, %s, %s, 'pendente')
                """,
                (nome, sobrenome, email, senha_hash, perfil["id"]),
            )
            db.commit()

        log.info("Novo cadastro pendente: %s (%s)", email, role)
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
        db.rollback()
        log.error("Erro DB no cadastro: %s", exc)
        return err("Erro interno. Tente novamente em instantes.", status=500)


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

    if not EMAIL_RE.match(email):
        return err("Informe um e-mail válido.", campo="email")
    if not senha:
        return err("Informe sua senha.", campo="password")

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
                db.commit()
                return err("E-mail ou senha incorretos.", status=401)

            # Conta pendente
            if usuario["status"] == "pendente":
                registrar_acesso(cur, usuario["id"], sucesso=False, motivo="cadastro pendente")
                db.commit()
                return err(
                    "Seu cadastro ainda está sendo analisado. "
                    "Aguarde a aprovação da equipe responsável.",
                    status=403,
                )

            # Conta rejeitada
            if usuario["status"] == "rejeitado":
                registrar_acesso(cur, usuario["id"], sucesso=False, motivo="cadastro rejeitado")
                db.commit()
                return err(
                    "Seu cadastro foi recusado. "
                    "Entre em contato com o administrador do sistema.",
                    status=403,
                )

            # ── Login bem-sucedido ───────────────────
            cur.execute(
                "UPDATE usuarios SET ultimo_login = NOW() WHERE id = %s",
                (usuario["id"],),
            )
            registrar_acesso(cur, usuario["id"], sucesso=True)
            db.commit()

        log.info("Login OK: %s (%s)", email, usuario["perfil"])
        return ok(
            {
                "mensagem": f"Bem-vindo, {usuario['nome']}!",
                "usuario": {
                    "id":          usuario["id"],
                    "nome":        usuario["nome"],
                    "sobrenome":   usuario["sobrenome"],
                    "email":       usuario["email"],
                    "perfil":      usuario["perfil"],
                    "perfil_nome": usuario["perfil_nome"],
                },
            }
        )

    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB no login: %s", exc)
        return err("Erro interno. Tente novamente em instantes.", status=500)


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
    """
    Lista os últimos registros de atividade do sistema (log de acessos)
    com o nome do usuário, a ação realizada e os detalhes. Usado pelo
    painel de Usuários do proprietário.
    Query params: limit (opcional, padrão 10)
    """
    limit = request.args.get("limit", "10")
    try:
        limit = max(1, min(100, int(limit)))
    except (TypeError, ValueError):
        limit = 10

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT l.id,
                       CONCAT(u.nome, ' ', COALESCE(u.sobrenome, '')) AS usuario_nome,
                       l.sucesso,
                       l.motivo_falha,
                       l.criado_em
                FROM   log_acessos l
                JOIN   usuarios u ON u.id = l.usuario_id
                ORDER  BY l.criado_em DESC
                LIMIT  %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

        logs = []
        for row in rows:
            nome = (row.get("usuario_nome") or "").strip() or "Usuário"
            logs.append(
                {
                    "id": row["id"],
                    "usuario_nome": nome,
                    "acao": "fez login no sistema" if row["sucesso"] else "falhou ao entrar",
                    "detalhes": (row.get("motivo_falha") or "") or ("acesso realizado com sucesso" if row["sucesso"] else ""),
                    "criado_em": row["criado_em"].isoformat() if isinstance(row["criado_em"], datetime) else str(row["criado_em"]),
                }
            )

        return ok({"logs": logs})

    except pymysql.MySQLError as exc:
        log.error("Erro DB ao listar logs: %s", exc)
        return err("Erro interno.", status=500)


@app.get("/admin/pendentes")
def listar_pendentes():
    """
    Lista todos os cadastros aguardando análise.
    Em produção, proteja esta rota com autenticação de admin.
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


@app.put("/admin/usuarios/<int:usuario_id>")
def editar_usuario(usuario_id):
    """
    Atualiza dados de um usuário existente (nome, e-mail, perfil e senha).
    Em produção, proteja esta rota com autenticação de admin.
    Payload: { nome, email, perfil, senha, status }
    `status` aceita 'ativo' (aprovado) ou 'inativo' (rejeitado).
    """
    data = request.get_json(silent=True) or {}

    nome      = (data.get("nome") or "").strip()
    email     = (data.get("email") or "").strip().lower()
    role      = (data.get("perfil") or "").strip()
    senha     = data.get("senha")
    status    = data.get("status")  # 'ativo' ou 'inativo'

    if len(nome) < 2:
        return err("Nome deve ter pelo menos 2 caracteres.", campo="nome")
    if not EMAIL_RE.match(email):
        return err("Informe um e-mail válido.", campo="email")
    if role and role not in PERFIS_VALIDOS:
        return err("Perfil de acesso inválido.", campo="perfil")
    if status and status not in ("ativo", "inativo"):
        return err("Status inválido. Use 'ativo' ou 'inativo'.", campo="status")
    if senha is not None and len(senha) < 8:
        return err("A senha deve ter pelo menos 8 caracteres.", campo="senha")

    # Mapeia o status amigável para o valor real do banco
    status_db = {"ativo": "aprovado", "inativo": "rejeitado"}.get(status)

    db = get_db()
    try:
        with db.cursor() as cur:
            # E-mail já em uso por outro usuário?
            cur.execute("SELECT id FROM usuarios WHERE email = %s AND id != %s", (email, usuario_id))
            if cur.fetchone():
                return err("Este e-mail já está em uso por outro usuário.", campo="email", status=409)

            set_parts = ["nome = %s", "email = %s"]
            values = [nome, email]

            if role:
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
                set_parts.append("senha_hash = %s")
                values.append(hash_senha(senha))

            values.append(usuario_id)
            cur.execute(
                f"UPDATE usuarios SET {', '.join(set_parts)} WHERE id = %s",
                tuple(values),
            )
            db.commit()

        log.info("Usuário %s atualizado", usuario_id)
        return ok({"mensagem": "Usuário atualizado com sucesso."})

    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao editar usuário: %s", exc)
        return err("Erro interno. Tente novamente em instantes.", status=500)


# ── Admin: aprovar/rejeitar cadastro ─────────

@app.post("/admin/analisar-cadastro")
def analisar_cadastro():
    """
    Aprova ou rejeita um cadastro pendente.
    Em produção, proteja esta rota com autenticação de admin.
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
            cur.execute("SELECT id, status FROM usuarios WHERE id = %s", (usuario_id,))
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
                (usuario_id, None, decisao, motivo),
            )
            db.commit()

        log.info("Cadastro %s para usuário %s", decisao, usuario_id)
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
            db.commit()
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
            db.commit()
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
            db.commit()
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
            db.commit()
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
            db.commit()
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
            db.commit()
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
    nome = data.get("nome")
    nome_generico = data.get("nome_generico")
    descricao = data.get("descricao")
    fabricante = data.get("fabricante")
    preco_custo = data.get("preco_custo")
    preco_venda = data.get("preco_venda")
    codigo_barras = data.get("codigo_barras")
    categoria_id = data.get("categoria_id")
    requer_receita = data.get("requer_receita", False)
    ativo = data.get("ativo", True)

    if not nome or not preco_custo or not preco_venda:
        return err("Nome, preço de custo e preço de venda são obrigatórios.", status=400)
    if preco_custo <= 0 or preco_venda <= 0:
        return err("Preço de custo e venda devem ser maiores que zero.", status=400)

    db = get_db()
    try:
        with db.cursor() as cur:
            if categoria_id:
                cur.execute("SELECT id FROM categorias_produto WHERE id = %s", (categoria_id,))
                if not cur.fetchone():
                    return err("Categoria não encontrada.", campo="categoria_id", status=400)

            cur.execute(
                """
                INSERT INTO produtos (nome, nome_generico, descricao, fabricante, preco_custo, preco_venda, codigo_barras, categoria_id, requer_receita, ativo)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (nome, nome_generico, descricao, fabricante, preco_custo, preco_venda, codigo_barras, categoria_id, requer_receita, ativo)
            )
            db.commit()
            return ok({"mensagem": "Produto criado com sucesso.", "id": cur.lastrowid}, status=201)
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
    nome = data.get("nome")
    nome_generico = data.get("nome_generico")
    descricao = data.get("descricao")
    fabricante = data.get("fabricante")
    preco_custo = data.get("preco_custo")
    preco_venda = data.get("preco_venda")
    codigo_barras = data.get("codigo_barras")
    categoria_id = data.get("categoria_id")
    requer_receita = data.get("requer_receita", False)
    ativo = data.get("ativo", True)

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM produtos WHERE id = %s", (produto_id,))
            if not cur.fetchone():
                return err("Produto não encontrado.", status=404)

            if categoria_id:
                cur.execute("SELECT id FROM categorias_produto WHERE id = %s", (categoria_id,))
                if not cur.fetchone():
                    return err("Categoria não encontrada.", campo="categoria_id", status=400)

            cur.execute(
                """
                UPDATE produtos SET nome = %s, nome_generico = %s, descricao = %s, fabricante = %s, preco_custo = %s, preco_venda = %s, codigo_barras = %s, categoria_id = %s, requer_receita = %s, ativo = %s
                WHERE id = %s
                """,
                (nome, nome_generico, descricao, fabricante, preco_custo, preco_venda, codigo_barras, categoria_id, requer_receita, ativo, produto_id)
            )
            db.commit()
            return ok({"mensagem": "Produto atualizado com sucesso."})
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
            db.commit()
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
            db.commit()
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
            db.commit()
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
            db.commit()
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

@app.get("/estoque/<int:estoque_id>")
def get_item_estoque(estoque_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT e.*,
                       p.nome          AS produto_nome,
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
    usuario_id    = data.get("usuario_id")
    # Campos opcionais de produto (usados ao criar produto novo)
    produto_principio = (data.get("produto_principio") or "").strip()
    produto_categoria = data.get("produto_categoria_id")
    produto_custo     = data.get("produto_preco_custo") or 0.01
    produto_venda     = data.get("produto_preco_venda") or 0.01
    produto_fornecedor = data.get("produto_fornecedor_id")

    if not produto_id and not produto_nome:
        return err("Informe produto_id ou produto_nome.", status=400)
    if not quantidade or quantidade <= 0:
        return err("Quantidade deve ser maior que zero.", status=400)
    if not data_validade:
        return err("Data de validade é obrigatória.", status=400)
    if produto_fornecedor and not str(produto_fornecedor).isdigit():
        produto_fornecedor = None

    db = get_db()
    try:
        with db.cursor() as cur:
            # Resolve produto_id a partir do nome se não foi fornecido
            if not produto_id:
                cur.execute("SELECT id FROM produtos WHERE nome = %s LIMIT 1", (produto_nome,))
                prod = cur.fetchone()
                if prod:
                    produto_id = prod["id"]
                else:
                    # Cria produto mínimo
                    cur.execute(
                        """
                        INSERT INTO produtos (nome, nome_generico, preco_custo, preco_venda, categoria_id, fornecedor_id)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (produto_nome, produto_principio or None,
                         produto_custo, produto_venda, produto_categoria or None,
                         produto_fornecedor if produto_fornecedor and produto_fornecedor.isdigit() else None)
                    )
                    produto_id = cur.lastrowid
                    log.info("Produto criado automaticamente: %s (id=%s)", produto_nome, produto_id)

            cur.execute(
                """
                INSERT INTO estoque (produto_id, lote, quantidade, data_validade, localizacao)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (produto_id, lote, quantidade, data_validade, localizacao)
            )
            estoque_id = cur.lastrowid

            # Registra movimentação de entrada se usuario_id fornecido
            if usuario_id:
                cur.execute(
                    """
                    INSERT INTO movimentacoes_estoque
                           (estoque_id, usuario_id, tipo_movimentacao, quantidade, observacao)
                    VALUES (%s, %s, 'entrada', %s, %s)
                    """,
                    (estoque_id, usuario_id, quantidade, "Cadastro inicial de estoque")
                )

            db.commit()
            return ok({"mensagem": "Item de estoque criado com sucesso.",
                       "id": estoque_id, "produto_id": produto_id}, status=201)
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
    para atualizar o produto associado. Registra ajuste de movimentação se
    a quantidade mudar e usuario_id for fornecido.
    """
    data = request.get_json(silent=True) or {}
    produto_id        = data.get("produto_id")
    lote              = data.get("lote")
    quantidade        = data.get("quantidade")
    data_validade     = data.get("data_validade")
    localizacao       = data.get("localizacao")
    usuario_id        = data.get("usuario_id")
    # Campos do produto para atualizar
    produto_nome      = (data.get("produto_nome") or "").strip()
    produto_principio = (data.get("produto_principio") or "").strip()
    produto_custo     = data.get("produto_preco_custo")
    produto_fornecedor = data.get("produto_fornecedor_id")

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id, produto_id, quantidade FROM estoque WHERE id = %s", (estoque_id,))
            item_atual = cur.fetchone()
            if not item_atual:
                return err("Item de estoque não encontrado.", status=404)

            pid = produto_id or item_atual["produto_id"]

            # Atualiza campos do produto se fornecidos
            if produto_nome or produto_principio or produto_custo is not None:
                updates, vals = [], []
                if produto_nome:
                    updates.append("nome = %s")
                    vals.append(produto_nome)
                if produto_principio:
                    updates.append("nome_generico = %s")
                    vals.append(produto_principio)
                if produto_custo is not None:
                    updates.append("preco_custo = %s")
                    vals.append(produto_custo)
                if produto_fornecedor and str(produto_fornecedor).isdigit():
                    updates.append("fornecedor_id = %s")
                    vals.append(int(produto_fornecedor))
                elif produto_fornecedor in ("", None):
                    updates.append("fornecedor_id = NULL")
                if updates:
                    vals.append(pid)
                    cur.execute(
                        f"UPDATE produtos SET {', '.join(updates)} WHERE id = %s",
                        vals
                    )

            # Monta campos de estoque a atualizar
            campos, valores = [], []
            if produto_id is not None:
                campos.append("produto_id = %s"); valores.append(produto_id)
            if lote is not None:
                campos.append("lote = %s"); valores.append(lote)
            if quantidade is not None:
                campos.append("quantidade = %s"); valores.append(quantidade)
            if data_validade is not None:
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
            if usuario_id and quantidade is not None:
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

            db.commit()
            return ok({"mensagem": "Item de estoque atualizado com sucesso."})
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
            cur.execute("SELECT id FROM estoque WHERE id = %s", (estoque_id,))
            if not cur.fetchone():
                return err("Item de estoque não encontrado.", status=404)

            # A FK de movimentacoes_estoque é RESTRICT: registrar a baixa como
            # movimentação de saída e remover o histórico vinculado antes de excluir.
            cur.execute("DELETE FROM movimentacoes_estoque WHERE estoque_id = %s", (estoque_id,))
            cur.execute("DELETE FROM estoque WHERE id = %s", (estoque_id,))
            db.commit()
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
                ORDER  BY me.data_movimentacao DESC
                LIMIT  200
            """)
            movimentacoes = cur.fetchall()
        for row in movimentacoes:
            if row.get("data_movimentacao") and hasattr(row["data_movimentacao"], "isoformat"):
                row["data_movimentacao"] = row["data_movimentacao"].isoformat()
            if row.get("valor_unitario") is not None:
                row["valor_unitario"] = float(row["valor_unitario"])
        return ok({"movimentacoes": movimentacoes})
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
    usuario_id = data.get("usuario_id")
    tipo_movimentacao = data.get("tipo_movimentacao")
    quantidade = data.get("quantidade")
    observacao = data.get("observacao")

    if not estoque_id or not usuario_id or not tipo_movimentacao or not quantidade:
        return err("ID do estoque, ID do usuário, tipo de movimentação e quantidade são obrigatórios.", status=400)
    if quantidade <= 0:
        return err("Quantidade deve ser maior que zero.", status=400)
    if tipo_movimentacao not in ["entrada", "saida", "ajuste", "transferencia"]:
        return err("Tipo de movimentação inválido.", status=400)

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id, quantidade FROM estoque WHERE id = %s", (estoque_id,))
            item_estoque = cur.fetchone()
            if not item_estoque:
                return err("Item de estoque não encontrado.", campo="estoque_id", status=400)

            cur.execute("SELECT id FROM usuarios WHERE id = %s", (usuario_id,))
            if not cur.fetchone():
                return err("Usuário não encontrado.", campo="usuario_id", status=400)

            nova_quantidade_estoque = item_estoque["quantidade"]
            if tipo_movimentacao == "entrada":
                nova_quantidade_estoque += quantidade
            elif tipo_movimentacao == "saida":
                if nova_quantidade_estoque < quantidade:
                    return err("Quantidade em estoque insuficiente para saída.", status=400)
                nova_quantidade_estoque -= quantidade
            elif tipo_movimentacao == "ajuste":
                # Para ajuste, a quantidade pode ser positiva ou negativa, mas aqui simplificamos como entrada/saída
                # Uma implementação mais robusta permitiria definir a quantidade final ou um delta.
                # Por simplicidade, vamos tratar como entrada/saída dependendo do sinal da quantidade.
                if quantidade > 0:
                    nova_quantidade_estoque += quantidade
                else:
                    if nova_quantidade_estoque < abs(quantidade):
                        return err("Quantidade em estoque insuficiente para ajuste de saída.", status=400)
                    nova_quantidade_estoque += quantidade # quantidade é negativa, então subtrai
            elif tipo_movimentacao == "transferencia":
                # Transferência requer lógica mais complexa com outro estoque_id de destino
                # Por simplicidade, trataremos como saída do estoque atual.
                if nova_quantidade_estoque < quantidade:
                    return err("Quantidade em estoque insuficiente para transferência.", status=400)
                nova_quantidade_estoque -= quantidade

            cur.execute(
                "UPDATE estoque SET quantidade = %s WHERE id = %s",
                (nova_quantidade_estoque, estoque_id)
            )

            cur.execute(
                """
                INSERT INTO movimentacoes_estoque (estoque_id, usuario_id, tipo_movimentacao, quantidade, observacao)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (estoque_id, usuario_id, tipo_movimentacao, quantidade, observacao)
            )
            db.commit()
            return ok({"mensagem": "Movimentação de estoque criada com sucesso.", "id": cur.lastrowid}, status=201)
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
                    SELECT ic.*, p.nome AS produto_nome
                    FROM   itens_compra ic
                    JOIN   produtos p ON ic.produto_id = p.id
                    WHERE  ic.compra_id IN (%s)
                """ % (",".join(["%s"] * len(ids)),), tuple(ids))
                for item in cur2.fetchall():
                    itens_map.setdefault(item["compra_id"], []).append(item)
        for row in compras:
            for k in ("criado_em", "data_recebimento", "atualizado_em", "data_entrega_prevista"):
                if row.get(k) and hasattr(row[k], "isoformat"):
                    row[k] = row[k].isoformat()
            if row.get("valor_total") is not None:
                row["valor_total"] = float(row["valor_total"])
            row["itens"] = itens_map.get(row["id"], [])
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
    usuario_id = data.get("usuario_id")
    valor_total = data.get("valor_total")
    status = data.get("status", "pendente")
    itens = data.get("itens", []) # Lista de dicionários com produto_id, quantidade, preco_unitario, lote_recebido, data_validade_recebida

    if not fornecedor_id or not usuario_id or not valor_total:
        return err("Fornecedor, usuário e valor total são obrigatórios.", status=400)
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

            cur.execute("SELECT id FROM usuarios WHERE id = %s", (usuario_id,))
            if not cur.fetchone():
                return err("Usuário não encontrado.", campo="usuario_id", status=400)

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
                lote_recebido = item.get("lote_recebido")
                data_validade_recebida = item.get("data_validade_recebida")

                if not produto_id or not quantidade or not preco_unitario:
                    db.rollback()
                    return err("Dados incompletos para item de compra.", status=400)

                cur.execute("SELECT id FROM produtos WHERE id = %s", (produto_id,))
                if not cur.fetchone():
                    db.rollback()
                    return err(f"Produto com ID {produto_id} não encontrado.", status=400)

                cur.execute(
                    """
                    INSERT INTO itens_compra (compra_id, produto_id, quantidade, preco_unitario, lote_recebido, data_validade_recebida)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (compra_id, produto_id, quantidade, preco_unitario, lote_recebido, data_validade_recebida)
                )

                # Se a compra foi recebida, atualiza o estoque
                if status == "recebido":
                    cur.execute("SELECT id FROM estoque WHERE produto_id = %s AND lote = %s", (produto_id, lote_recebido))
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

            db.commit()
            return ok({"mensagem": "Compra criada com sucesso.", "id": compra_id}, status=201)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao criar compra: %s", exc)
        return err("Erro interno ao criar compra.", status=500)

@app.put("/compras/<int:compra_id>")
def update_compra(compra_id):
    data = request.get_json(silent=True) or {}
    fornecedor_id = data.get("fornecedor_id")
    usuario_id = data.get("usuario_id")
    valor_total = data.get("valor_total")
    status = data.get("status")
    data_recebimento = data.get("data_recebimento")

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id, status, usuario_id, valor_total, fornecedor_id FROM compras WHERE id = %s", (compra_id,))
            compra_existente = cur.fetchone()
            if not compra_existente:
                return err("Compra não encontrada.", status=404)

            if fornecedor_id:
                cur.execute("SELECT id FROM fornecedores WHERE id = %s", (fornecedor_id,))
                if not cur.fetchone():
                    return err("Fornecedor não encontrado.", campo="fornecedor_id", status=400)

            if usuario_id:
                cur.execute("SELECT id FROM usuarios WHERE id = %s", (usuario_id,))
                if not cur.fetchone():
                    return err("Usuário não encontrado.", campo="usuario_id", status=400)

            if status and status not in ["pendente", "recebido", "cancelado"]:
                return err("Status de compra inválido.", status=400)

            # Lógica para atualizar estoque se o status mudar para 'recebido'
            if status == "recebido" and compra_existente["status"] != "recebido":
                cur.execute("SELECT produto_id, quantidade, lote_recebido, data_validade_recebida FROM itens_compra WHERE compra_id = %s", (compra_id,))
                itens_compra = cur.fetchall()
                # Usuário que confirma o recebimento: enviado no payload ou o dono da compra
                usuario_recebimento = usuario_id if usuario_id else compra_existente["usuario_id"]
                for item in itens_compra:
                    produto_id = item["produto_id"]
                    quantidade = item["quantidade"]
                    lote_recebido = item["lote_recebido"]
                    data_validade_recebida = item["data_validade_recebida"]

                    lote_estoque = lote_recebido or "SEM-LOTE"
                    cur.execute("SELECT id FROM estoque WHERE produto_id = %s AND lote = %s", (produto_id, lote_estoque))
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
            if usuario_id is not None:
                set_parts.append("usuario_id = %s"); params.append(usuario_id)
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
            db.commit()
            return ok({"mensagem": "Compra atualizada com sucesso."})
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
            db.commit()
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

@app.post("/vendas")
def create_venda():
    data = request.get_json(silent=True) or {}
    cliente_id = data.get("cliente_id")
    usuario_id = data.get("usuario_id")
    valor_total = data.get("valor_total")
    tipo_pagamento = data.get("tipo_pagamento")
    status = data.get("status", "pendente")
    itens = data.get("itens", []) # Lista de dicionários com produto_id, quantidade, preco_unitario, desconto, lote_vendido

    if not usuario_id or not valor_total or not tipo_pagamento:
        return err("Usuário, valor total e tipo de pagamento são obrigatórios.", status=400)
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

            cur.execute("SELECT id FROM usuarios WHERE id = %s", (usuario_id,))
            if not cur.fetchone():
                return err("Usuário não encontrado.", campo="usuario_id", status=400)

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
                lote_vendido = item.get("lote_vendido")

                if not produto_id or not quantidade or not preco_unitario:
                    db.rollback()
                    return err("Dados incompletos para item de venda.", status=400)

                cur.execute("SELECT id FROM produtos WHERE id = %s", (produto_id,))
                if not cur.fetchone():
                    db.rollback()
                    return err(f"Produto com ID {produto_id} não encontrado.", status=400)

                # Verifica e atualiza estoque
                if status == "concluida":
                    cur.execute("SELECT id, quantidade FROM estoque WHERE produto_id = %s AND lote = %s", (produto_id, lote_vendido))
                    estoque_item = cur.fetchone()
                    if not estoque_item or estoque_item["quantidade"] < quantidade:
                        db.rollback()
                        return err(f"Estoque insuficiente para o produto {produto_id} no lote {lote_vendido}.", status=400)

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

            db.commit()
            return ok({"mensagem": "Venda criada com sucesso.", "id": venda_id}, status=201)
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao criar venda: %s", exc)
        return err("Erro interno ao criar venda.", status=500)

@app.put("/vendas/<int:venda_id>")
def update_venda(venda_id):
    data = request.get_json(silent=True) or {}
    cliente_id = data.get("cliente_id")
    usuario_id = data.get("usuario_id")
    valor_total = data.get("valor_total")
    tipo_pagamento = data.get("tipo_pagamento")
    status = data.get("status")

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id, status FROM vendas WHERE id = %s", (venda_id,))
            venda_existente = cur.fetchone()
            if not venda_existente:
                return err("Venda não encontrada.", status=404)

            if cliente_id:
                cur.execute("SELECT id FROM clientes WHERE id = %s", (cliente_id,))
                if not cur.fetchone():
                    return err("Cliente não encontrado.", campo="cliente_id", status=400)

            if usuario_id:
                cur.execute("SELECT id FROM usuarios WHERE id = %s", (usuario_id,))
                if not cur.fetchone():
                    return err("Usuário não encontrado.", campo="usuario_id", status=400)

            if tipo_pagamento and tipo_pagamento not in ["dinheiro", "cartao_credito", "cartao_debito", "pix"]:
                return err("Tipo de pagamento inválido.", status=400)
            if status and status not in ["concluida", "cancelada", "pendente"]:
                return err("Status de venda inválido.", status=400)

            # Lógica para atualizar estoque se o status mudar para 'concluida' e antes não era
            if status == "concluida" and venda_existente["status"] != "concluida":
                cur.execute("SELECT produto_id, quantidade, lote_vendido FROM itens_venda WHERE venda_id = %s", (venda_id,))
                itens_venda = cur.fetchall()
                for item in itens_venda:
                    produto_id = item["produto_id"]
                    quantidade = item["quantidade"]
                    lote_vendido = item["lote_vendido"]

                    cur.execute("SELECT id, quantidade FROM estoque WHERE produto_id = %s AND lote = %s", (produto_id, lote_vendido))
                    estoque_item = cur.fetchone()
                    if not estoque_item or estoque_item["quantidade"] < quantidade:
                        db.rollback()
                        return err(f"Estoque insuficiente para o produto {produto_id} no lote {lote_vendido}.", status=400)

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
                UPDATE vendas SET cliente_id = %s, usuario_id = %s, valor_total = %s, tipo_pagamento = %s, status = %s
                WHERE id = %s
                """,
                (cliente_id, usuario_id, valor_total, tipo_pagamento, status, venda_id)
            )
            db.commit()
            return ok({"mensagem": "Venda atualizada com sucesso."})
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
            db.commit()
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

            db.commit()
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
            db.commit()
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
            db.commit()
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
            db.commit()
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
    resolvido_por_usuario_id = data.get("resolvido_por_usuario_id")

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
            if resolvido_por_usuario_id: update_fields.append("resolvido_por_usuario_id = %s"); update_values.append(resolvido_por_usuario_id)
            if status == "resolvido" and "resolvido_em" not in update_fields:
                update_fields.append("resolvido_em = NOW()");

            if not update_fields:
                return err("Nenhum dado para atualizar.", status=400)

            query = f"UPDATE alertas SET {', '.join(update_fields)} WHERE id = %s"
            cur.execute(query, (*update_values, alerta_id))
            db.commit()
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
            db.commit()
            return ok({"mensagem": "Alerta excluído com sucesso."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao excluir alerta: %s", exc)
        return err("Erro interno ao excluir alerta.", status=500)



def ensure_configuracoes_table(db):
    """Garante a tabela de configurações para ambientes existentes sem migração aplicada."""
    with db.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS configuracoes_sistema (
              chave VARCHAR(120) PRIMARY KEY,
              valor TEXT NULL,
              descricao VARCHAR(255) NULL,
              criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
            """
        )
    db.commit()

# ─────────────────────────────────────────────
#  Rotas para Configurações do Sistema
# ─────────────────────────────────────────────

@app.get("/configuracoes")
def get_configuracoes():
    db = get_db()
    try:
        ensure_configuracoes_table(db)
        with db.cursor() as cur:
            cur.execute("SELECT * FROM configuracoes_sistema")
            configuracoes = cur.fetchall()
        return ok({"configuracoes": configuracoes})
    except pymysql.MySQLError as exc:
        log.error("Erro DB ao buscar configurações: %s", exc)
        return err("Erro interno ao buscar configurações.", status=500)

@app.get("/configuracoes/<string:chave>")
def get_configuracao(chave):
    db = get_db()
    try:
        ensure_configuracoes_table(db)
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

    if not chave or not valor:
        return err("Chave e valor são obrigatórios.", status=400)

    db = get_db()
    try:
        ensure_configuracoes_table(db)
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO configuracoes_sistema (chave, valor, descricao)
                VALUES (%s, %s, %s)
                """,
                (chave, valor, descricao)
            )
            db.commit()
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
    data = request.get_json(silent=True) or {}
    valor     = data.get("valor")
    descricao = data.get("descricao")

    db = get_db()
    try:
        ensure_configuracoes_table(db)
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
            db.commit()
            return ok({"mensagem": "Configuração salva com sucesso."})
    except pymysql.MySQLError as exc:
        db.rollback()
        log.error("Erro DB ao salvar configuração: %s", exc)
        return err("Erro interno ao salvar configuração.", status=500)

@app.delete("/configuracoes/<string:chave>")
def delete_configuracao(chave):
    db = get_db()
    try:
        ensure_configuracoes_table(db)
        with db.cursor() as cur:
            cur.execute("SELECT chave FROM configuracoes_sistema WHERE chave = %s", (chave,))
            if not cur.fetchone():
                return err("Configuração não encontrada.", status=404)

            cur.execute("DELETE FROM configuracoes_sistema WHERE chave = %s", (chave,))
            db.commit()
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
                WHERE  e.quantidade > 0
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
                SELECT p.nome, 
                       COALESCE(cp.nome, 'Sem Categoria') as categoria,
                       e.lote, 
                       e.quantidade, 
                       COALESCE(p.estoque_minimo, 10) AS estoque_minimo, 
                       e.data_validade,
                       CASE 
                         WHEN e.quantidade <= 0 THEN 'crit'
                         WHEN e.quantidade <= COALESCE(p.estoque_minimo, 10) THEN 'crit'
                         ELSE 'low'
                       END as status_classe
                FROM   estoque e
                JOIN   produtos p ON e.produto_id = p.id
                LEFT JOIN categorias_produto cp ON p.categoria_id = cp.id
                WHERE  e.quantidade <= COALESCE(p.estoque_minimo, 10) * 1.5
                ORDER  BY e.quantidade ASC
                LIMIT 10
            """)
            produtos_criticos = cur.fetchall()
            for row in produtos_criticos:
                if row.get("data_validade") and hasattr(row["data_validade"], "isoformat"):
                    row["data_validade"] = row["data_validade"].isoformat()

        return ok({
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
    db = get_db()
    try:
        with db.cursor() as cur:
            # KPIs
            cur.execute("SELECT COUNT(*) AS total FROM estoque WHERE quantidade > 0")
            total_saidas = cur.fetchone()["total"] or 0

            cur.execute("""
                SELECT COALESCE(SUM(e.quantidade * p.preco_custo), 0) AS valor
                FROM estoque e JOIN produtos p ON e.produto_id = p.id
            """)
            valor_estoque = float(cur.fetchone()["valor"] or 0)

            cur.execute("""
                SELECT COUNT(*) AS total FROM estoque e JOIN produtos p ON e.produto_id = p.id
                WHERE e.quantidade <= COALESCE(p.estoque_minimo, 10)
            """)
            itens_alerta = cur.fetchone()["total"] or 0

            cur.execute("""
                SELECT COUNT(*) AS total FROM estoque
                WHERE data_validade < DATE_ADD(CURDATE(), INTERVAL 60 DAY) AND quantidade > 0
            """)
            vencendo = cur.fetchone()["total"] or 0

            # Giro de estoque (saídas últimos 30 dias / valor médio estoque)
            cur.execute("""
                SELECT COALESCE(SUM(me.quantidade), 0) AS saidas
                FROM movimentacoes_estoque me
                WHERE me.tipo_movimentacao = 'saida'
                  AND me.data_movimentacao >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            """)
            saidas_30 = float(cur.fetchone()["saidas"] or 0)
            giro = round(saidas_30 / max(total_saidas, 1), 2)

            # Listagem por categoria
            cur.execute("""
                SELECT cp.nome AS categoria,
                       COUNT(DISTINCT e.produto_id) AS qtd_produtos,
                       SUM(e.quantidade) AS qtd_total,
                       SUM(e.quantidade * p.preco_custo) AS valor_total
                FROM   estoque e
                JOIN   produtos p ON e.produto_id = p.id
                LEFT JOIN categorias_produto cp ON p.categoria_id = cp.id
                GROUP  BY cp.id, cp.nome
                ORDER  BY valor_total DESC
            """)
            por_categoria = cur.fetchall()
            for row in por_categoria:
                if row.get("valor_total"):
                    row["valor_total"] = float(row["valor_total"])

            # Top produtos por valor em estoque
            cur.execute("""
                SELECT p.nome,
                       SUM(e.quantidade) AS quantidade,
                       COALESCE(SUM(e.quantidade * p.preco_custo), 0) AS valor_total
                FROM   estoque e
                JOIN   produtos p ON e.produto_id = p.id
                WHERE  e.quantidade > 0
                GROUP  BY p.id, p.nome
                ORDER  BY valor_total DESC
                LIMIT  10
            """)
            top_produtos = cur.fetchall()
            for row in top_produtos:
                row["quantidade"] = int(row["quantidade"] or 0)
                row["valor_total"] = float(row["valor_total"] or 0)

        return ok({
            "kpis": {
                "total_saidas":  int(total_saidas),
                "valor_estoque": round(valor_estoque, 2),
                "itens_alerta":  int(itens_alerta),
                "giro_estoque":  giro,
            },
            "por_categoria": por_categoria,
            "top_produtos":   top_produtos,
        })
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
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM compras")
            total_pedidos = cur.fetchone()["total"] or 0

            cur.execute("""
                SELECT COALESCE(SUM(valor_total), 0) AS valor FROM compras
                WHERE status = 'recebido'
            """)
            valor_comprado = float(cur.fetchone()["valor"] or 0)

            cur.execute("SELECT COUNT(*) AS total FROM compras WHERE status = 'pendente'")
            pendentes = cur.fetchone()["total"] or 0

            # Fornecedores ativos por perfil de compra
            cur.execute("SELECT COUNT(DISTINCT id) AS total FROM fornecedores WHERE ativo = TRUE")
            fornecedores = cur.fetchone()["total"] or 0

            # Fornecedores com pedidos registrados (usados nas compras)
            cur.execute("""
                SELECT f.id, f.nome_fantasia, f.cnpj, COUNT(c.id) AS total_pedidos,
                       COALESCE(SUM(c.valor_total), 0) AS valor_total
                FROM   fornecedores f
                JOIN   compras c ON c.fornecedor_id = f.id
                GROUP  BY f.id, f.nome_fantasia, f.cnpj
                ORDER  BY total_pedidos DESC
            """)
            fornecedores_rank = cur.fetchall()
            for row in fornecedores_rank:
                row["valor_total"] = float(row["valor_total"] or 0)
                row["total_pedidos"] = int(row["total_pedidos"] or 0)

            # Pedidos por categoria (classificação por fornecedor)
            cur.execute("""
                SELECT DATE_FORMAT(c.data_pedido, '%Y-%m') AS mes,
                       COUNT(*) AS total,
                       COALESCE(SUM(c.valor_total), 0) AS valor
                FROM   compras c
                WHERE  c.data_pedido >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
                GROUP  BY mes
                ORDER  BY mes ASC
            """)
            evolucao = cur.fetchall()
            for row in evolucao:
                row["total"] = int(row["total"] or 0)
                row["valor"] = float(row["valor"] or 0)

            # Categorias mais compradas (via categorias de produtos dos itens)
            cur.execute("""
                SELECT COALESCE(cp.nome, 'Sem Categoria') AS categoria,
                       COUNT(DISTINCT ic.compra_id) AS total_pedidos,
                       COALESCE(SUM(ic.quantidade * ic.preco_unitario), 0) AS valor
                FROM   itens_compra ic
                JOIN   produtos p        ON ic.produto_id = p.id
                LEFT JOIN categorias_produto cp ON p.categoria_id = cp.id
                JOIN   compras c         ON ic.compra_id = c.id
                WHERE  c.data_pedido >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
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


# ─────────────────────────────────────────────
#  Rota de Previsão de Reposición
# ─────────────────────────────────────────────

@app.get("/previsao/reposicao")
def previsao_reposicao():
    """
    Calcula previsão de reposición baseada no consumo médio diário dos
    últimos 30 dias e no estoque atual.
    Retorna lista de produtos com dias restantes estimados.
    """
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT p.id,
                       p.nome,
                       p.nome_generico,
                       COALESCE(p.estoque_minimo, 10) AS estoque_minimo,
                       SUM(e.quantidade)              AS estoque_atual,
                       COALESCE(
                           (
                               SELECT SUM(me.quantidade) / 30.0
                               FROM   movimentacoes_estoque me
                               JOIN   estoque e2 ON me.estoque_id = e2.id
                               WHERE  e2.produto_id = p.id
                                 AND  me.tipo_movimentacao = 'saida'
                                 AND  me.data_movimentacao >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                           ), 0
                       ) AS consumo_diario
                FROM   produtos p
                JOIN   estoque e ON e.produto_id = p.id
                WHERE  e.quantidade > 0
                GROUP  BY p.id, p.nome, p.nome_generico, p.estoque_minimo
                HAVING (SUM(e.quantidade) > 0) AND
                       ((COALESCE(
                           (SELECT SUM(me.quantidade) / 30.0
                            FROM   movimentacoes_estoque me
                            JOIN   estoque e2 ON me.estoque_id = e2.id
                            WHERE  e2.produto_id = p.id
                              AND  me.tipo_movimentacao = 'saida'
                              AND  me.data_movimentacao >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                           ), 0) > 0) OR
                        (SUM(e.quantidade) <= COALESCE(p.estoque_minimo, 10)))
                ORDER  BY (SUM(e.quantidade) / GREATEST(COALESCE(
                             (SELECT SUM(me.quantidade) / 30.0
                              FROM   movimentacoes_estoque me
                              JOIN   estoque e2 ON me.estoque_id = e2.id
                              WHERE  e2.produto_id = p.id
                                AND  me.tipo_movimentacao = 'saida'
                                AND  me.data_movimentacao >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                             ), 0), 0.01)) ASC
                LIMIT  50
            """)
            produtos = cur.fetchall()

        resultado = []
        for p in produtos:
            consumo = float(p["consumo_diario"] or 0)
            atual   = int(p["estoque_atual"] or 0)
            minimo  = int(p["estoque_minimo"] or 10)
            dias_restantes = round(atual / consumo, 1) if consumo > 0 else None
            resultado.append({
                "produto_id":      p["id"],
                "nome":            p["nome"],
                "nome_generico":   p["nome_generico"],
                "estoque_atual":   atual,
                "estoque_minimo":  minimo,
                "consumo_diario":  round(consumo, 2),
                "dias_restantes":  dias_restantes,
                "reposicao_urgente": atual <= minimo,
            })

        return ok({"previsao": resultado})
    except Exception as exc:  # noqa: BLE001
        log.exception("Erro ao calcular previsão de reposição: %s", exc)
        return err("Erro interno ao calcular previsão de reposição.", status=500)


FRONTEND_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend', 'src', 'pages', 'proprietario')

@app.route('/pages/proprietario/<path:filename>')
def serve_proprietario_page(filename):
    """Serve arquivos estáticos do frontend do proprietário.

    Permite abrir o sistema por http://localhost:5000 e mantém a navegação
    SPA (páginas trocadas via fetch) no mesmo origin da API — sem CORS e
    sem os flashes de recarga do browser.
    """
    safe = re.sub(r'[<>:"|?*]', '', filename)
    if not safe or '..' in safe:
        return err('Recurso não disponível.', status=404)
    base = os.path.realpath(FRONTEND_SRC)
    target = os.path.realpath(os.path.join(FRONTEND_SRC, safe))
    if not target.startswith(base) or not os.path.isfile(target):
        return err('Recurso não encontrado.', status=404)
    if not safe.lower().endswith(('.html', '.css', '.js', '.png', '.jpg', '.jpeg', '.svg', '.woff', '.woff2', '.json')):
        return err('Tipo de arquivo não suportado.', status=404)
    # Envio direto do conteúdo (send_from_directory não aceita diretório
    # absoluto fora do root_path do Flask) com MIME correto por extensão
    import mimetypes as _mimetypes
    mime, _ = _mimetypes.guess_type(target)
    with open(target, 'rb') as fh:
        data = fh.read()
    resp = app.response_class(data, mimetype=mime or 'application/octet-stream')
    # HTML das páginas nunca é cacheado pelo browser (é o conteúdo que o
    # SPA busca via fetch a cada navegação — precisa sempre revalidar).
    # CSS/JS/imagens podem ser cacheados por um período curto: o motor
    # SPA já mantém seu próprio cache em memória (cssTextCache/pageCache),
    # então isto só acelera reloads de aba/sessão nova.
    if safe.lower().endswith('.html'):
        resp.headers['Cache-Control'] = 'no-cache'
    else:
        resp.headers['Cache-Control'] = 'public, max-age=300'
    return resp

# Base para os estáticos compartilhados do frontend (utilitários, estilos, assets)
FRONTEND_ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend', 'src')

@app.route('/<path:filename>')
def serve_frontend_asset(filename):
    """Serve qualquer arquivo estático do frontend por URL absoluta.

    Necessário porque as páginas referenciam utilitários e estilos por
    caminho relativo (ex.: ../../../utils/global-settings.js); quando o
    sistema é aberto via http://localhost:5000, o browser resolve essas
    referências contra a raiz e esta rota as entrega. As rotas de API
    têm prioridade por especificidade.
    """
    safe = re.sub(r'[<>:"|?*]', '', filename)
    if not safe or '..' in safe:
        return err('Recurso não disponível.', status=404)
    base = os.path.realpath(FRONTEND_ASSETS)
    target = os.path.realpath(os.path.join(FRONTEND_ASSETS, safe))
    if not target.startswith(base) or not os.path.isfile(target):
        return err('Recurso não encontrado.', status=404)
    import mimetypes as _mimetypes
    mime, _ = _mimetypes.guess_type(target)
    with open(target, 'rb') as fh:
        data = fh.read()
    resp = app.response_class(data, mimetype=mime or 'application/octet-stream')
    if safe.lower().endswith('.html'):
        resp.headers['Cache-Control'] = 'no-cache'
    else:
        resp.headers['Cache-Control'] = 'public, max-age=300'
    return resp


def _fin_tables_exist():
    """Verifica se as tabelas de financeiro existem no banco."""
    try:
        db = get_db()
        with db.cursor() as cur:
            cur.execute("SHOW TABLES LIKE 'financeiro_transacoes'")
            return cur.fetchone() is not None
    except Exception:
        return False
# ═══════════════════════════════════════════════════════════════
#  Financeiro Routes
# ═══════════════════════════════════════════════════════════════

@app.get("/financeiro/stats")
def financeiro_stats():
    """Retorna KPIs financeiros para o período selecionado."""
    if not _fin_tables_exist():
        return jsonify({'ok': True, 'saldo': 0, 'receitas': 0, 'despesas': 0,
                        'ticket_medio': 0, 'delta_receitas': 0, 'delta_despesas': 0, 'spark': []})
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
                WHERE t.data_transacao >= DATE_SUB(NOW(), INTERVAL %s DAY)
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
                WHERE data_venda >= DATE_SUB(NOW(), INTERVAL %s DAY)
                  AND status = 'concluida'
            """, (days,))
            ticket = float(cur.fetchone()['ticket'] or 0)

            # Delta (comparação com período anterior)
            cur.execute("""
                SELECT COALESCE(SUM(CASE WHEN fc.tipo = 'receita' THEN t.valor ELSE 0 END), 0) AS receitas_ant
                FROM financeiro_transacoes t
                JOIN financeiro_categorias fc ON fc.id = t.categoria_id
                WHERE t.data_transacao BETWEEN DATE_SUB(NOW(), INTERVAL %s DAY)
                                           AND DATE_SUB(NOW(), INTERVAL %s DAY)
                  AND t.status = 'pago'
            """, (days * 2, days))
            receitas_ant = float(cur.fetchone()['receitas_ant'] or 0)
            delta_receitas = ((receitas - receitas_ant) / receitas_ant * 100) if receitas_ant > 0 else 0

            cur.execute("""
                SELECT COALESCE(SUM(CASE WHEN fc.tipo = 'despesa' THEN t.valor ELSE 0 END), 0) AS despesas_ant
                FROM financeiro_transacoes t
                JOIN financeiro_categorias fc ON fc.id = t.categoria_id
                WHERE t.data_transacao BETWEEN DATE_SUB(NOW(), INTERVAL %s DAY)
                                           AND DATE_SUB(NOW(), INTERVAL %s DAY)
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
                WHERE t.data_transacao >= DATE_SUB(NOW(), INTERVAL 14 DAY)
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
    except Exception as exc:
        log.error("Erro DB em financeiro/stats: %s", exc)
        return jsonify({'ok': True, 'saldo': 0, 'receitas': 0, 'despesas': 0,
                        'ticket_medio': 0, 'delta_receitas': 0, 'delta_despesas': 0, 'spark': []})


@app.get("/financeiro/fluxo")
def financeiro_fluxo():
    """Retorna dados para o gráfico de fluxo de caixa (receitas vs despesas por dia)."""
    if not _fin_tables_exist():
        return jsonify({'ok': True, 'labels': [], 'receitas': [], 'despesas': []})
    days = request.args.get('days', '7', type=int)
    if days not in (7, 30, 90):
        days = 7
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT DATE(t.data_transacao) AS dia,
                       SUM(CASE WHEN fc.tipo = 'receita' THEN t.valor ELSE 0 END) AS receitas,
                       SUM(CASE WHEN fc.tipo = 'despesa' THEN t.valor ELSE 0 END) AS despesas
                FROM financeiro_transacoes t
                JOIN financeiro_categorias fc ON fc.id = t.categoria_id
                WHERE t.data_transacao >= DATE_SUB(NOW(), INTERVAL %s DAY)
                  AND t.status = 'pago'
                GROUP BY DATE(t.data_transacao)
                ORDER BY dia ASC
            """, (days,))
            rows = cur.fetchall()

        labels = []
        receitas = []
        despesas = []
        for r in rows:
            labels.append(r['dia'].strftime('%d/%m') if r['dia'] else '—')
            receitas.append(float(r['receitas'] or 0))
            despesas.append(float(r['despesas'] or 0))

        return jsonify({'ok': True, 'labels': labels, 'receitas': receitas, 'despesas': despesas})
    except Exception as exc:
        log.error("Erro DB em financeiro/fluxo: %s", exc)
        return jsonify({'ok': True, 'labels': [], 'receitas': [], 'despesas': []})


@app.get("/financeiro/categorias")
def financeiro_categorias():
    """Retorna categorias financeiras com totais agrupados."""
    if not _fin_tables_exist():
        return jsonify({'ok': True, 'categorias': []})
    days = request.args.get('days', '30', type=int)
    tipo = request.args.get('tipo', None)
    db = get_db()
    try:
        with db.cursor() as cur:
            tipo_clause = "AND fc.tipo = %s" if tipo else ""
            params = (days,) + ((tipo,) if tipo else ())
            cur.execute(f"""
                SELECT fc.id, fc.nome, fc.tipo,
                       COALESCE(SUM(t.valor), 0) AS valor,
                       COUNT(t.id) AS qtd
                FROM financeiro_categorias fc
                LEFT JOIN financeiro_transacoes t ON t.categoria_id = fc.id
                    AND t.data_transacao >= DATE_SUB(NOW(), INTERVAL %s DAY)
                    AND t.status = 'pago'
                {tipo_clause}
                GROUP BY fc.id, fc.nome, fc.tipo
                ORDER BY valor DESC
            """, params)
            rows = cur.fetchall()

        categorias = [{'id': r['id'], 'nome': r['nome'], 'tipo': r['tipo'],
                       'valor': float(r['valor'] or 0), 'qtd': r['qtd']} for r in rows]

        return jsonify({'ok': True, 'categorias': categorias})
    except Exception as exc:
        log.error("Erro DB em financeiro/categorias: %s", exc)
        return jsonify({'ok': True, 'categorias': []})


@app.get("/financeiro/transacoes")
def financeiro_transacoes():
    """Retorna lista de transações do período."""
    if not _fin_tables_exist():
        return jsonify({'ok': True, 'transacoes': []})
    days = request.args.get('days', '30', type=int)
    if days not in (7, 30, 90):
        days = 30
    limit = request.args.get('limit', 50, type=int)
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT t.id, t.descricao, t.valor, t.data_transacao,
                       t.status, t.metodo_pagamento,
                       fc.tipo, fc.nome AS categoria_nome
                FROM financeiro_transacoes t
                JOIN financeiro_categorias fc ON fc.id = t.categoria_id
                WHERE t.data_transacao >= DATE_SUB(NOW(), INTERVAL %s DAY)
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
    except Exception as exc:
        log.error("Erro DB em financeiro/transacoes: %s", exc)
        return jsonify({'ok': True, 'transacoes': []})


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
    if not valor or float(valor) <= 0:
        return jsonify({'ok': False, 'mensagem': 'Informe um valor válido.'}), 400
    if metodo not in ('dinheiro', 'pix', 'cartao_credito', 'cartao_debito', 'boleto', 'transferencia'):
        return jsonify({'ok': False, 'mensagem': 'Método de pagamento inválido.'}), 400

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

            # Pega o primeiro usuário (temporário - em produção usar session)
            cur.execute("SELECT id FROM usuarios LIMIT 1")
            user = cur.fetchone()
            if not user:
                return jsonify({'ok': False, 'mensagem': 'Usuário não encontrado.'}), 404

            if data_transacao:
                cur.execute(
                    """
                    INSERT INTO financeiro_transacoes
                        (categoria_id, usuario_id, descricao, valor, data_transacao, metodo_pagamento, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'pago')
                    """,
                    (categoria_id, user['id'], descricao, float(valor), data_transacao, metodo),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO financeiro_transacoes
                        (categoria_id, usuario_id, descricao, valor, data_transacao, metodo_pagamento, status)
                    VALUES (%s, %s, %s, %s, NOW(), %s, 'pago')
                    """,
                    (categoria_id, user['id'], descricao, float(valor), metodo),
                )
            db.commit()

        log.info("Nova transação financeira: %s %s", tipo, descricao)
        return jsonify({'ok': True, 'mensagem': 'Transação registrada com sucesso.'}), 201
    except Exception as exc:
        db.rollback()
        log.error("Erro DB em create_transacao: %s", exc)
        return jsonify({'ok': False, 'mensagem': 'Erro ao salvar transação.'}), 400


if __name__ == "__main__":
    app.run(debug=True, port=5000)
