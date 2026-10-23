"""core.responses: responsabilidades extraídas da aplicação Flask."""

from flask import jsonify


def ok(data: dict, status: int = 200):
    return jsonify({"ok": True, **data}), status


def err(mensagem: str, status: int = 400, campo: str | None = None):
    body = {"ok": False, "mensagem": mensagem}
    if campo:
        body["campo"] = campo
    return jsonify(body), status

