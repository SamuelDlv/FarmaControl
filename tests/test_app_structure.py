"""Regressões da composição modular, sem banco ou envio de e-mails reais."""

import os
from pathlib import Path
import runpy
import unittest
from unittest.mock import patch

import test_backend as base
from farmacontrol import create_app, middleware
from farmacontrol.core.paths import BACKEND_DIR, FRONTEND_DIR
from flask import g


class AppStructureTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "APP_ENV": "test", "APP_DEBUG": "false", "COOKIE_SECURE": "false",
            "SECRET_KEY": "chave-isolada-de-testes-com-32-caracteres",
            "ALLOWED_ORIGINS": "", "SESSION_HOURS": "8",
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.dotenv = patch("farmacontrol.load_dotenv")
        self.load_env = self.dotenv.start()
        self.addCleanup(self.dotenv.stop)
        self.db = patch("pymysql.connect", side_effect=AssertionError("Banco real proibido"))
        self.db.start()
        self.addCleanup(self.db.stop)

    def test_factories_keep_routes_and_isolate_session_and_rate_limiter(self):
        first, second = create_app(), create_app()
        self.assertEqual(str(first.url_map), str(second.url_map))
        self.assertIsNot(first.extensions["auth_limiter"], second.extensions["auth_limiter"])
        first.extensions["auth_limiter"].check_with_status("local")
        self.assertEqual(second.extensions["auth_limiter"].check_with_status("local")["remaining"],
                         first.extensions["auth_limiter"].check_with_status("other")["remaining"])
        first.config["SECRET_KEY"] = "outra-chave"
        self.assertNotEqual(first.secret_key, second.secret_key)
        self.assertEqual(second.test_client().get("/health").status_code, 200)

    def test_paths_and_frontend_work_from_another_working_directory(self):
        previous = Path.cwd()
        try:
            os.chdir(base.ROOT / "tests")
            app = create_app()
            response = app.test_client().get("/pages/acesso/acesso.html")
        finally:
            os.chdir(previous)
        self.load_env.assert_called_once_with(BACKEND_DIR / ".env")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, (FRONTEND_DIR / "pages/acesso/acesso.html").read_bytes())

    def test_local_entrypoint_preserves_server_options(self):
        with patch("flask.Flask.run") as run:
            runpy.run_path(str(BACKEND_DIR / "app.py"), run_name="__main__")
        run.assert_called_once_with(host="127.0.0.1", debug=False, port=5000)

    def test_production_entrypoint_still_requires_wsgi(self):
        with patch.dict(os.environ, {"APP_ENV": "production", "COOKIE_SECURE": "true"}), \
                patch("flask.Flask.run") as run:
            with self.assertRaisesRegex(RuntimeError, "WSGI"):
                runpy.run_path(str(BACKEND_DIR / "app.py"), run_name="__main__")
        run.assert_not_called()

    def test_notification_scheduler_receives_concrete_app_for_background_thread(self):
        app = create_app()
        with patch.dict(os.environ, {
            "BREVO_SMTP_LOGIN": "test", "BREVO_SMTP_PASSWORD": "test",
            "BREVO_SENDER_EMAIL": "test@example.com",
        }), patch.object(middleware, "schedule_notifications") as schedule:
            with app.test_request_context("/dashboard/stats"):
                g.usuario_id = 42
                middleware.check_scheduled_notifications(app.response_class(status=200))
            # Depois de sair do contexto, um LocalProxy não seria utilizável.
            scheduled_app = schedule.call_args.args[0]
            self.assertIs(scheduled_app, app)
            with scheduled_app.app_context():
                self.assertEqual(scheduled_app.name, "app")
