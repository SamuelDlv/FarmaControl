"""core.database: responsabilidades extraídas da aplicação Flask."""

from flask import g
import os
import pymysql.cursors


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


def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

