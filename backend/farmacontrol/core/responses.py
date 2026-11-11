# Guia de manutenção — Mantém o contrato JSON de sucesso e erro consumido pelas telas.
# Consulte docs/desenvolvimento.md para executar as verificações desta camada.
"""core.responses: responsabilidades extraídas da aplicação Flask."""

from flask import jsonify


# Retorna a tupla resposta/status aceita pelo Flask. O envelope ok é usado
# pelas telas junto ao status HTTP para decidir sucesso e apresentar mensagens.
def ok(data: dict, status: int = 200):
    return jsonify({"ok": True, **data}), status


# campo é opcional e permite destacar o controle inválido no formulário.
# Envie mensagens públicas aqui; detalhes técnicos ficam no logger do backend.
def err(mensagem: str, status: int = 400, campo: str | None = None):
    body = {"ok": False, "mensagem": mensagem}
    if campo:
        body["campo"] = campo
    return jsonify(body), status

