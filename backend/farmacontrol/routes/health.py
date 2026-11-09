# Guia de manutenção — Oferece a verificação de disponibilidade HTTP da aplicação.
# Consulte docs/DESENVOLVIMENTO.md para executar as verificações desta camada.
"""routes.health: responsabilidades extraídas da aplicação Flask."""

from datetime import datetime
from datetime import timezone
from farmacontrol.core import responses


# Verificação simples de que o servidor está rodando.
def health():
    """Verificação simples de que o servidor está rodando."""
    return responses.ok({"status": "online", "ts": datetime.now(timezone.utc).isoformat()})


# Liga URLs, métodos HTTP e nomes de endpoint à instância recebida.
# Alterar estes contratos exige revisar as telas e tests/fixtures/api_routes.json.
def register_routes(app):
    """Registra as URLs e nomes de endpoints existentes."""
    app.add_url_rule('/health', view_func=health, methods=['GET'])
