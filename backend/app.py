# Guia de manutenção — Entrada WSGI e inicialização local. As regras de negócio ficam no pacote farmacontrol.
# Importar este arquivo cria a aplicação; executar como programa inicia o servidor local.
# Consulte docs/desenvolvimento.md para executar as verificações desta camada.
"""Entrada local e WSGI do backend FarmaControl."""

from farmacontrol import create_app
from farmacontrol.core.local_server import run_local

app = create_app()


if __name__ == "__main__":
    if app.config["APP_ENV"] == "production":
        raise RuntimeError("Em produção, inicie app:app com um servidor WSGI atrás de HTTPS.")
    run_local(app)
