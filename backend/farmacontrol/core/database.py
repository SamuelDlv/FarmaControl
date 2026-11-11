# Guia de manutenção — Gerencia uma conexão MySQL por contexto Flask, com confirmação explícita.
# Consulte docs/desenvolvimento.md para executar as verificações desta camada.
"""core.database: responsabilidades extraídas da aplicação Flask."""

from flask import g
import os
import pymysql.cursors


# O cache em g pertence ao contexto atual: não compartilhe esta conexão entre threads.
# Autocommit fica desligado; a rota ou serviço decide quando confirmar ou desfazer.
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


# Remove a conexão do contexto e libera o recurso no teardown, inclusive após falhas.
# Fechar a conexão não substitui o commit explícito do fluxo de negócio.
def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

