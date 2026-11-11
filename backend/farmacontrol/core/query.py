# Guia de manutenção — Valida parâmetros de consulta antes de compor paginação e pesquisas SQL.
# Consulte docs/desenvolvimento.md para executar as verificações desta camada.
"""Validação compartilhada de consultas; SQL e políticas ficam nas rotas."""

import re


# Erro de entrada convertido pela rota com core.responses.err.
class QueryError(ValueError):
    """Erro de entrada convertido pela rota com core.responses.err."""

    def __init__(self, campo, mensagem):
        super().__init__(mensagem)
        self.campo = campo


# Ausente usa default; vazio/inválido falha. Clamp é só para contratos legados.
def query_int(args, name, *, default=None, minimum=0,
              maximum=9223372036854775807, clamp=False):
    """Ausente usa default; vazio/inválido falha. Clamp é só para contratos legados."""
    if name not in args:
        return default
    raw = args[name].strip()
    if not re.fullmatch(r"[+-]?[0-9]+", raw):
        raise QueryError(name, f"{name} deve ser um número inteiro.")
    try:
        value = int(raw)
    except ValueError:
        raise QueryError(name, f"{name} deve ser um número inteiro.") from None
    if clamp:
        return min(maximum, max(minimum, value))
    if not minimum <= value <= maximum:
        raise QueryError(name, f"{name} deve estar entre {minimum} e {maximum}.")
    return value


# Remove espaços nas bordas; preserva Unicode, espaços internos e operadores.
def search_text(args, name="busca", *, maximum=120):
    """Remove espaços nas bordas; preserva Unicode, espaços internos e operadores."""
    value = args.get(name, "").strip()
    if len(value) > maximum:
        raise QueryError(name, f"{name} deve ter até {maximum} caracteres.")
    return value

