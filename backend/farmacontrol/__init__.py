"""Criação e composição da aplicação Flask do FarmaControl."""

import logging
import os

from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS

from farmacontrol.core.paths import BACKEND_DIR
from farmacontrol.core.runtime_config import runtime_config
from farmacontrol.core.security import AuthLimiter


def create_app():
    """Carrega o ambiente e registra rotas e middlewares sem conectar ao banco."""
    load_dotenv(BACKEND_DIR / ".env")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    app = Flask("app", root_path=str(BACKEND_DIR))
    app.config.update(runtime_config(os.environ))
    if app.config["EPHEMERAL_SECRET"]:
        logging.getLogger("farmacontrol").warning(
            "SECRET_KEY ausente ou fraca: chave temporária local; sessões expiram ao reiniciar."
        )
    if app.config["ALLOWED_ORIGINS"]:
        CORS(app, origins=app.config["ALLOWED_ORIGINS"], supports_credentials=True,
             allow_private_network=False)
    app.extensions["auth_limiter"] = AuthLimiter()

    from farmacontrol.core.database import close_db
    from farmacontrol import middleware
    from farmacontrol.routes import (
        admin, alertas, auth, catalogo, clientes, compras, configuracoes,
        dashboard, estoque, financeiro, fornecedores, frontend, health,
        receitas, relatorios, vendas,
    )

    app.teardown_appcontext(close_db)
    app.before_request(middleware.validar_entrada)
    app.before_request(middleware.proteger_api)
    app.register_error_handler(413, middleware.payload_grande)
    # Flask executa after_request na ordem inversa à do registro.
    app.after_request(middleware.security_headers)
    app.after_request(middleware.auditar_consultas)
    app.after_request(middleware.check_scheduled_notifications)

    for routes in (
        health, auth, admin, clientes, catalogo, fornecedores, estoque,
        compras, vendas, receitas, alertas, configuracoes, dashboard,
        relatorios, frontend, financeiro,
    ):
        routes.register_routes(app)
    return app
