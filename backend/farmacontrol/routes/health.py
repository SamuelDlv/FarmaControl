"""routes.health: responsabilidades extraídas da aplicação Flask."""

from datetime import datetime
from datetime import timezone
from farmacontrol.core import responses


def health():
    """Verificação simples de que o servidor está rodando."""
    return responses.ok({"status": "online", "ts": datetime.now(timezone.utc).isoformat()})


def register_routes(app):
    """Registra as URLs e nomes de endpoints existentes."""
    app.add_url_rule('/health', view_func=health, methods=['GET'])
