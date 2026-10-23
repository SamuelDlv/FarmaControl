"""Entrada local e WSGI do backend FarmaControl."""

from farmacontrol import create_app

app = create_app()


if __name__ == "__main__":
    if app.config["APP_ENV"] == "production":
        raise RuntimeError("Em produção, inicie app:app com um servidor WSGI atrás de HTTPS.")
    app.run(host="127.0.0.1", debug=app.config["DEBUG"], port=5000)
