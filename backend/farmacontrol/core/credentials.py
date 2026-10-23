"""core.credentials: responsabilidades extraídas da aplicação Flask."""

from flask import g
from flask import request
import bcrypt
import hashlib
import os


BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", 12))


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


LEGAL_DOCUMENT_VERSION = "2026-10-05"


INVITE_EXPIRY_HOURS = 168


PASSWORD_RESET_EXPIRY_HOURS = 1


def hash_convite(token):
    """Armazena somente o hash do segredo presente no link de convite."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_token_recuperacao(token):
    """Não persiste o segredo presente no link de recuperação."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

