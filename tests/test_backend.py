"""Regressões de contratos HTTP com banco simulado; qualquer conexão real falha."""
import json
import os
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
with patch("pymysql.connect", side_effect=AssertionError("Banco real proibido nos testes")), \
        patch("dotenv.load_dotenv"), patch.dict(os.environ, {
            "APP_ENV": "test", "APP_DEBUG": "false", "COOKIE_SECURE": "false",
            "SECRET_KEY": "chave-isolada-de-testes-com-32-caracteres",
            "ALLOWED_ORIGINS": "", "SESSION_HOURS": "8",
        }):
    import app as api


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.block_db = patch("pymysql.connect", side_effect=AssertionError("Banco real proibido"))
        self.block_db.start()
        self.addCleanup(self.block_db.stop)
        api.app.config.update(TESTING=True, SECRET_KEY="somente-testes", SESSION_COOKIE_SECURE=False)
        api.auth_limiter = api.AuthLimiter()
        self.client = api.app.test_client()
        self.cur = Mock()
        self.cur.__enter__ = Mock(return_value=self.cur)
        self.cur.__exit__ = Mock(return_value=False)
        self.cur.fetchone.return_value = {"senha_hash": "hash-simulado", "status": "aprovado", "perfil": "proprietario", "id": 3, "tipo": "receita"}
        self.cur.fetchall.return_value = []
        self.cur.lastrowid = 8
        self.db = Mock()
        self.db.cursor.return_value = self.cur
        self.get_db = patch.object(api, "get_db", return_value=self.db)
        self.get_db.start()
        self.addCleanup(self.get_db.stop)
        self.profile_permissions = {}
        self.permissions_reader = patch.object(
            api,
            "permissoes_efetivas",
            side_effect=lambda _cursor, profile: set(self.profile_permissions.get(profile, ())),
        )
        self.permissions_reader.start()
        self.addCleanup(self.permissions_reader.stop)

    def login_session(self, perfil="proprietario"):
        with self.client.session_transaction() as sess:
            sess["usuario_id"] = 42
            sess["credential_stamp"] = api.credential_stamp(api.app.config["SECRET_KEY"], "hash-simulado")
            sess["perfil"] = perfil
            sess["csrf_token"] = "teste-csrf"
        self.cur.fetchone.return_value = {"senha_hash": "hash-simulado", "status": "aprovado", "perfil": perfil, "id": 3, "tipo": "receita"}
        default_modules = {
            "proprietario": api.PERMISSION_MODULES,
            "admin": api.PERMISSION_MODULES,
            "farmaceutico": ("dashboard", "estoque", "vencimentos", "relatorios", "compras"),
            "atendente": ("dashboard", "estoque"),
            "visualizador": ("dashboard", "estoque", "vencimentos", "relatorios"),
            "compras": ("dashboard", "estoque", "vencimentos", "relatorios", "compras"),
            "ti": api.PERMISSION_MODULES,
        }
        self.profile_permissions = default_modules

    def test_health_does_not_query_database(self):
        self.assertEqual(self.client.get("/health").json["status"], "online")
        self.db.cursor.assert_not_called()

    def test_removed_forecast_is_unavailable(self):
        self.login_session()
        self.assertNotIn("previsao", api.PERMISSION_MODULES)
        for path in (
            "/previsao/reposicao",
            "/pages/sistema/previsao/previsao.html",
            "/pages/proprietario/previsao/previsao.html",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_removed_forecast_permission_is_rejected(self):
        self.login_session()
        response = self.client.put(
            "/admin/perfis/permissoes",
            json={"perfis": {"compras": ["previsao"]}},
            headers={"X-CSRF-Token": "teste-csrf"},
        )
        self.assertEqual(response.status_code, 400)

    def test_all_protected_routes_require_session(self):
        for rule in api.app.url_map.iter_rules():
            if not rule.rule.startswith(api.PROTECTED_API_PREFIXES) or rule.rule == "/configuracoes/visual":
                continue
            path = rule.rule
            import re
            path = re.sub(r"<int:\w+>", "1", path)
            path = re.sub(r"<string:\w+>", "tema", path)
            for method in rule.methods - {"HEAD", "OPTIONS"}:
                with self.subTest(path=path, method=method):
                    self.assertEqual(self.client.open(path, method=method).status_code, 401)

    def test_inventory_read_and_write_permissions_remain_distinct(self):
        self.login_session("visualizador")
        self.assertEqual(self.client.get("/estoque").status_code, 200)
        # A permissão de módulo libera leitura e escrita; a validação do
        # payload continua responsável pelo HTTP 400.
        self.assertEqual(self.client.post("/estoque", json={}, headers={"X-CSRF-Token": "teste-csrf"}).status_code, 403)

    def test_root_purchase_and_supplier_permissions(self):
        for route in ("/compras", "/fornecedores", "/compras/1", "/fornecedores/1"):
            for method in ("GET", "POST", "PUT", "DELETE"):
                with self.subTest(route=route, method=method):
                    self.assertEqual(api.roles_permitidos(route, method), api.INVENTORY_ROLES)
        self.assertEqual(api.roles_permitidos("/compras-falso", "GET"), set())
        self.assertEqual(api.roles_permitidos("/fornecedores-falso", "GET"), set())

    def test_root_lists_are_accessible_to_expected_roles(self):
        for role in api.INVENTORY_ROLES:
            for route in ("/compras", "/fornecedores"):
                with self.subTest(role=role, route=route):
                    self.assertEqual(api.modulo_da_rota(route), "compras")
                    modules = {
                        "proprietario": api.PERMISSION_MODULES,
                        "admin": api.PERMISSION_MODULES,
                        "farmaceutico": ("compras",),
                        "compras": ("compras",),
                        "ti": api.PERMISSION_MODULES,
                    }[role]
                    self.assertIn("compras", modules)

    def test_persisted_permission_controls_api_access(self):
        self.login_session("atendente")
        self.profile_permissions["atendente"] = {"dashboard"}
        self.assertEqual(self.client.get("/estoque").status_code, 403)

    def test_csrf_rejected_before_mutation(self):
        self.login_session()
        response = self.client.post("/estoque", json={})
        self.assertEqual(response.status_code, 403)
        self.db.commit.assert_not_called()

    def test_revoked_account_clears_session(self):
        self.login_session()
        self.cur.fetchone.return_value = {"status": "rejeitado", "perfil": "proprietario"}
        self.assertEqual(self.client.get("/estoque").status_code, 401)
        with self.client.session_transaction() as sess:
            self.assertNotIn("usuario_id", sess)

    def test_role_change_is_read_from_database(self):
        self.login_session()
        self.cur.fetchone.return_value = {"senha_hash": "hash-simulado", "status": "aprovado", "perfil": "atendente"}
        self.assertEqual(self.client.get("/financeiro/stats").status_code, 403)

    def test_database_failure_in_session_validation(self):
        self.login_session()
        self.cur.execute.side_effect = api.pymysql.OperationalError("simulado")
        self.assertEqual(self.client.get("/estoque").status_code, 503)

    def test_logout_requires_csrf_and_clears_cookie_session(self):
        self.login_session()
        self.assertEqual(self.client.post("/auth/logout").status_code, 403)
        self.assertEqual(self.client.post("/auth/logout", headers={"X-CSRF-Token": "teste-csrf"}).status_code, 200)
        self.assertEqual(self.client.get("/estoque").status_code, 401)

    def test_invalid_login_clears_previous_session(self):
        self.login_session()
        self.assertEqual(self.client.post("/auth/login", json={"email": "invalido"}).status_code, 400)
        self.assertEqual(self.client.get("/estoque").status_code, 401)

    def test_static_alias_content_and_cache(self):
        self.login_session()
        for extension, mime in (("html", "text/html"), ("css", "text/css"), ("js", "javascript")):
            path = f"dashboard/dashboard.{extension}"
            canonical = self.client.get("/pages/sistema/" + path)
            legacy = self.client.get("/pages/proprietario/" + path)
            self.assertEqual(canonical.status_code, 200)
            self.assertEqual(canonical.data, legacy.data)
            self.assertEqual(canonical.headers["Cache-Control"], "no-store" if extension == "html" else "no-cache")
            self.assertIn(mime, canonical.content_type)

    def test_static_missing_and_traversal(self):
        for path in ("/pages/sistema/../app.py", "/pages/sistema/missing.html", "/../backend/app.py", "/.env"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_all_html_css_js_assets_are_served(self):
        self.login_session()
        for path in (ROOT / "frontend/src").rglob("*"):
            if path.suffix not in {".html", ".css", ".js", ".ico", ".png"}:
                continue
            with self.subTest(path=path):
                response = self.client.get("/" + path.relative_to(ROOT / "frontend/src").as_posix())
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data, path.read_bytes())

    def test_financial_date_is_validated_and_parameterized(self):
        self.login_session()
        value = "2026-10-06"
        response = self.client.post("/financeiro/transacoes", json={
            "tipo": "receita", "categoria_id": 3, "descricao": "Teste", "valor": 12.5,
            "data_transacao": value, "metodo_pagamento": "pix"
        }, headers={"X-CSRF-Token": "teste-csrf"})
        self.assertEqual(response.status_code, 201)
        inserts = [(args[0], args[1]) for args, _ in self.cur.execute.call_args_list if "INSERT INTO financeiro_transacoes" in args[0]]
        self.assertEqual(len(inserts), 1)
        sql, params = inserts[0]
        self.assertNotIn(value, sql)
        self.assertIn("2026-10-06 00:00:00", params)

    def test_financial_invalid_date_returns_json_error(self):
        self.login_session()
        response = self.client.post("/financeiro/transacoes", json={
            "tipo": "receita", "categoria_id": 3, "descricao": "Teste", "valor": 12.5,
            "data_transacao": "2026-10-06'); SELECT 'teste", "metodo_pagamento": "pix"
        }, headers={"X-CSRF-Token": "teste-csrf"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json["ok"])
        self.assertFalse(any("INSERT INTO financeiro_transacoes" in args[0] for args, _ in self.cur.execute.call_args_list))

    def test_financial_invalid_values_return_json_error(self):
        self.login_session()
        for value in ("abc", "NaN", "Infinity", -1, 0, None, {}, []):
            with self.subTest(value=value):
                response = self.client.post("/financeiro/transacoes", json={
                    "tipo": "receita", "categoria_id": 3, "descricao": "Teste", "valor": value,
                    "metodo_pagamento": "pix"
                }, headers={"X-CSRF-Token": "teste-csrf"})
                self.assertEqual(response.status_code, 400)
                self.assertFalse(response.json["ok"])
        self.db.commit.assert_not_called()

    def test_stock_accepts_numeric_supplier(self):
        self.login_session()
        # Session lookup then product lookup: product must be created.
        self.cur.fetchone.side_effect = [{"senha_hash": "hash-simulado", "status": "aprovado", "perfil": "proprietario"}, None, {"id": 7}]
        response = self.client.post("/estoque", json={
            "produto_nome": "Teste", "produto_fornecedor_id": 7,
            "quantidade": 2, "data_validade": "2027-01-01"
        }, headers={"X-CSRF-Token": "teste-csrf"})
        self.assertEqual(response.status_code, 201)
        inserts = [args[1] for args, _ in self.cur.execute.call_args_list if "INSERT INTO produtos" in args[0]]
        self.assertEqual(inserts[0][11], 7)
        self.db.commit.assert_called_once()

    def test_stock_failure_rolls_back(self):
        self.login_session()
        self.cur.execute.side_effect = [None, api.pymysql.OperationalError("simulado")]
        response = self.client.post("/estoque", json={
            "produto_id": 2, "quantidade": 1, "data_validade": "2027-01-01"
        }, headers={"X-CSRF-Token": "teste-csrf"})
        self.assertEqual(response.status_code, 500)
        self.db.rollback.assert_called_once()
        self.db.commit.assert_not_called()

    def test_financial_categories_filter_the_category_type(self):
        self.login_session()
        with patch.object(api, "_fin_tables_exist", return_value=True):
            response = self.client.get("/financeiro/categorias?tipo=despesa&days=30")
        self.assertEqual(response.status_code, 200)
        query, params = next(call.args for call in self.cur.execute.call_args_list if "WHERE fc.tipo = %s" in call.args[0])
        self.assertIn("WHERE fc.tipo = %s", query)
        self.assertEqual(params, (30, "despesa"))

    def test_financial_read_failure_is_not_reported_as_empty_data(self):
        self.login_session()
        # A primeira consulta é a validação da sessão executada pelo middleware.
        self.cur.execute.side_effect = [None, api.pymysql.OperationalError("simulado")]
        with patch.object(api, "_fin_tables_exist", return_value=True):
            response = self.client.get("/financeiro/transacoes")
        self.assertEqual(response.status_code, 500)
        self.assertFalse(response.json["ok"])

    def test_cashflow_includes_each_calendar_day_and_current_day_total(self):
        self.login_session()
        self.cur.fetchall.return_value = [{
            'dia': date(2026, 10, 12), 'receitas': 27.56, 'despesas': 0,
        }]
        with patch.object(api, '_fin_tables_exist', return_value=True):
            response = self.client.get('/financeiro/fluxo?start_date=2026-10-10&end_date=2026-10-12')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['dias'], ['2026-10-10', '2026-10-11', '2026-10-12'])
        self.assertEqual(response.json['receitas'], [0.0, 0.0, 27.56])
        self.assertEqual(response.json['despesas'], [0.0, 0.0, 0.0])

    def test_stock_history_is_not_deleted_with_lot(self):
        self.login_session()
        self.cur.fetchone.side_effect = [
            {"senha_hash": "hash-simulado", "status": "aprovado", "perfil": "proprietario"},
            {"id": 8}, {"id": 1},
        ]
        response = self.client.delete("/estoque/8", headers={"X-CSRF-Token": "teste-csrf"})
        self.assertEqual(response.status_code, 409)
        self.assertFalse(any("DELETE FROM movimentacoes_estoque" in args[0] for args, _ in self.cur.execute.call_args_list))
        self.db.commit.assert_not_called()

    def test_stock_movement_filters_are_validated(self):
        self.login_session()
        response = self.client.get("/movimentacoes-estoque?tipo=invalido")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["campo"], "tipo")
        queries = [args[0] for args, _ in self.cur.execute.call_args_list]
        self.assertFalse(any("FROM   movimentacoes_estoque" in query for query in queries))

    def test_negative_stock_adjustment_cannot_cross_zero(self):
        self.login_session()
        self.cur.fetchall.return_value = [{"id": 8, "produto_id": 2, "quantidade": 3}]
        response = self.client.post("/movimentacoes-estoque", json={
            "estoque_id": 8, "tipo_movimentacao": "ajuste", "quantidade": -4,
        }, headers={"X-CSRF-Token": "teste-csrf"})
        self.assertEqual(response.status_code, 400)
        self.db.commit.assert_not_called()


    def test_stock_report_counts_outgoing_units_and_current_stock(self):
        self.login_session()
        self.cur.fetchone.side_effect = [
            {"senha_hash": "hash-simulado", "status": "aprovado", "perfil": "proprietario"},
            {"unidades": 100, "valor": 250.0, "alertas": 2, "zerados": 1},
            {"saidas": 12000, "entradas": 500, "valor_saidas": 30000,
             "valor_entradas": 1250, "dias_operacao": 10, "descartados": 2},
            {"inicio": "2026-10-01", "fim": "2026-10-10"},
        ]
        response = self.client.get("/relatorios/estoque")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['kpis'], {
            'total_saidas': 12000, 'valor_estoque': 250.0,
            'itens_alerta': 2, 'giro_estoque': 120.0,
        })
        self.assertEqual(response.json['resumo']['entradas'], 500)
        queries = [args[0] for args, _ in self.cur.execute.call_args_list]
        self.assertFalse(any('LIMIT 1000' in query for query in queries))
        self.assertTrue(any("me.tipo_movimentacao='saida'" in query and 'SUM(me.quantidade)' in query for query in queries))

    def test_report_rejects_invalid_period(self):
        self.login_session()
        self.assertEqual(self.client.get('/relatorios/estoque?periodo=invalid').status_code, 400)

    def test_movements_pagination_preserves_filters_and_reports_total(self):
        self.login_session()
        self.cur.fetchone.side_effect = [
            {'senha_hash': 'hash-simulado', 'status': 'aprovado', 'perfil': 'proprietario'}, {'total': 11391},
        ]
        response = self.client.get('/movimentacoes-estoque?periodo=year&limite=10&offset=1000&busca=creme&tipo=saida')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['total'], 11391)
        calls = self.cur.execute.call_args_list
        query, params = next(args for args, _ in calls if 'OFFSET %s' in args[0])
        self.assertIn('me.id DESC', query)
        self.assertEqual(params, ('saida', '%creme%', 10, 1000))

    def test_purchase_list_serializes_order_date_as_iso(self):
        from datetime import datetime
        self.login_session()
        self.cur.fetchall.side_effect = [[{'id': 1, 'data_pedido': datetime(2026, 10, 7), 'valor_total': 12}], []]
        response = self.client.get('/compras')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['compras'][0]['data_pedido'], '2026-10-07T00:00:00')

    def test_financial_categories_separate_paid_and_pending(self):
        self.login_session()
        self.cur.fetchall.return_value = [{'id': 2, 'nome': 'Despesas', 'tipo': 'despesa',
                                          'valor': 50, 'pendente': 75, 'qtd': 2}]
        with patch.object(api, '_fin_tables_exist', return_value=True):
            response = self.client.get('/financeiro/categorias?tipo=despesa&days=30')
        self.assertEqual(response.json['categorias'][0]['valor'], 50)
        self.assertEqual(response.json['categorias'][0]['pendente'], 75)
        queries = [args[0] for args, _ in self.cur.execute.call_args_list]
        self.assertTrue(any('DATE_SUB(CURDATE()' in query for query in queries))

    def test_successful_login_sets_session_without_exposing_hash(self):
        self.cur.fetchone.return_value = {
            "id": 42, "nome": "Teste", "sobrenome": "Local", "email": "teste@example.com",
            "senha_hash": "hash-simulado", "status": "aprovado",
            "perfil": "proprietario", "perfil_nome": "Proprietário",
        }
        with patch.object(api, "verificar_senha", return_value=True):
            response = self.client.post("/auth/login", json={"email": "teste@example.com", "password": "simulada"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("senha_hash", response.json["usuario"])
        self.assertTrue(response.json["csrf_token"])
        with self.client.session_transaction() as sess:
            self.assertEqual(sess["usuario_id"], 42)
            self.assertEqual(sess["csrf_token"], response.json["csrf_token"])
            self.assertFalse(sess.permanent)
        self.db.commit.assert_called_once()

    def test_login_logout_login_accepts_same_password_and_renews_csrf(self):
        self.cur.fetchone.return_value = {
            "id": 42, "nome": "Teste", "sobrenome": "Local", "email": "teste@example.com",
            "senha_hash": "hash-simulado", "status": "aprovado",
            "perfil": "proprietario", "perfil_nome": "Proprietário",
        }
        credentials = {"email": "teste@example.com", "password": "simulada"}
        with patch.object(api, "verificar_senha", return_value=True):
            first = self.client.post("/auth/login", json=credentials)
            self.assertEqual(first.status_code, 200)
            logout = self.client.post("/auth/logout", headers={
                "X-CSRF-Token": first.json["csrf_token"],
            })
            self.assertEqual(logout.status_code, 200)
            with self.client.session_transaction() as sess:
                self.assertNotIn("usuario_id", sess)
            second = self.client.post("/auth/login", json=credentials)
            self.assertEqual(second.status_code, 200)
            self.assertNotEqual(first.json["csrf_token"], second.json["csrf_token"])
            with self.client.session_transaction() as sess:
                self.assertEqual(sess["usuario_id"], 42)

    def test_remember_access_creates_a_persistent_session(self):
        self.cur.fetchone.return_value = {
            "id": 42, "nome": "Teste", "sobrenome": "Local", "email": "teste@example.com",
            "senha_hash": "hash-simulado", "status": "aprovado",
            "perfil": "proprietario", "perfil_nome": "Proprietário",
        }
        with patch.object(api, "verificar_senha", return_value=True):
            response = self.client.post("/auth/login", json={
                "email": "teste@example.com", "password": "simulada", "remember": True,
            })
        self.assertEqual(response.status_code, 200)
        self.assertIn("Expires=", response.headers["Set-Cookie"])
        with self.client.session_transaction() as sess:
            self.assertTrue(sess.permanent)

    def test_login_rejects_non_boolean_remember_access(self):
        response = self.client.post("/auth/login", json={
            "email": "teste@example.com", "password": "simulada", "remember": "true",
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["campo"], "remember")
        self.db.cursor.assert_not_called()

    def test_registration_still_requires_both_legal_consents(self):
        response = self.client.post("/auth/register", json={
            "nome": "Teste", "sobrenome": "Local", "email": "teste@example.com",
            "role": "atendente", "password": "senha-simulada", "accepts_terms": True,
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["campo"], "legal")
        self.db.cursor.assert_not_called()

    def test_retired_visual_preferences_cannot_be_saved(self):
        self.login_session()
        for key in ('tema', 'tema_efetivo'):
            for method, path, payload in (
                ('POST', '/configuracoes', {'chave': key, 'valor': 'escuro'}),
                ('PUT', '/configuracoes/' + key, {'valor': 'escuro'}),
            ):
                with self.subTest(method=method, key=key):
                    response = self.client.open(path, method=method, json=payload,
                                                headers={'X-CSRF-Token': 'teste-csrf'})
                    self.assertEqual(response.status_code, 410)
                    self.assertFalse(response.json['ok'])
            self.assertEqual(self.client.get('/configuracoes/' + key).status_code, 410)
        self.db.commit.assert_not_called()

    def test_old_database_preferences_do_not_reappear_in_settings(self):
        self.login_session()
        self.cur.fetchall.return_value = [
            {'chave': 'tema', 'valor': 'escuro'},
            {'chave': 'tema_efetivo', 'valor': 'escuro'},
            {'chave': 'cor_destaque', 'valor': '#2e6da4'},
        ]
        response = self.client.get('/configuracoes')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['configuracoes'],
                         [{'chave': 'cor_destaque', 'valor': '#2e6da4'}])

    def test_registration_uses_migrated_legal_table_without_runtime_ddl(self):
        self.cur.fetchone.side_effect = [None, {"id": 2}]
        with patch.dict(os.environ, {
            "BREVO_SMTP_LOGIN": "", "BREVO_SMTP_PASSWORD": "", "BREVO_SENDER_EMAIL": "",
        }):
            response = self.client.post("/auth/register", json={
                "nome": "Teste", "sobrenome": "Local", "email": "teste@example.com",
                "role": "atendente", "password": "senha-simulada",
                "accepts_terms": True, "accepts_privacy": True,
            })
        self.assertEqual(response.status_code, 201)
        queries = [args[0] for args, _ in self.cur.execute.call_args_list]
        self.assertFalse(any("CREATE TABLE" in query for query in queries))
        self.assertTrue(any("INSERT INTO aceites_legais" in query for query in queries))

    def test_brevo_smtp_uses_tls_and_credentials_from_environment(self):
        smtp = Mock()
        smtp_context = Mock()
        smtp_context.__enter__ = Mock(return_value=smtp)
        smtp_context.__exit__ = Mock(return_value=False)
        with patch.dict(os.environ, {
            "BREVO_SMTP_HOST": "smtp-relay.brevo.com", "BREVO_SMTP_PORT": "587",
            "BREVO_SMTP_LOGIN": "login@smtp-brevo.com", "BREVO_SMTP_PASSWORD": "segredo",
            "BREVO_SENDER_EMAIL": "remetente@example.com", "BREVO_SENDER_NAME": "FarmaControl",
        }), patch.object(api.smtplib, "SMTP", return_value=smtp_context) as smtp_class:
            self.assertTrue(api.enviar_email_brevo("destinatario@example.com", "Assunto", "<p>Teste</p>"))
        smtp_class.assert_called_once_with("smtp-relay.brevo.com", 587, timeout=10)
        smtp.starttls.assert_called_once()
        smtp.login.assert_called_once_with("login@smtp-brevo.com", "segredo")
        smtp.send_message.assert_called_once()
        mensagem = smtp.send_message.call_args.args[0]
        corpo_html = mensagem.get_body(preferencelist=("html",)).get_content()
        self.assertIn("FarmaControl", corpo_html)
        self.assertIn("background:#14532d", corpo_html)

    def test_alert_resolution_uses_authenticated_user(self):
        self.login_session()
        self.cur.fetchone.side_effect = [
            {"senha_hash": "hash-simulado", "status": "aprovado", "perfil": "proprietario"}, {"id": 9},
        ]
        response = self.client.put("/alertas/9", json={
            "status": "resolvido", "resolvido_por_usuario_id": 999,
        }, headers={"X-CSRF-Token": "teste-csrf"})
        self.assertEqual(response.status_code, 200)
        update = next(args for args, _ in self.cur.execute.call_args_list if "UPDATE alertas SET" in args[0])
        self.assertIn(42, update[1])
        self.assertNotIn(999, update[1])

    def test_admin_invite_does_not_create_account_or_assume_legal_consent(self):
        self.login_session()
        self.cur.fetchone.side_effect = [
            {"senha_hash": "hash-simulado", "status": "aprovado", "perfil": "proprietario"}, None, {"id": 2},
        ]
        with patch.object(api, "enviar_email_brevo", return_value=True) as send_mail:
            response = self.client.post("/admin/convites", json={
                "nome": "Pessoa", "sobrenome": "Convidada", "email": "convite@example.com", "role": "atendente",
            }, headers={"X-CSRF-Token": "teste-csrf"})
        self.assertEqual(response.status_code, 201)
        queries = [args[0] for args, _ in self.cur.execute.call_args_list]
        self.assertTrue(any("INSERT INTO convites_cadastro" in query for query in queries))
        self.assertFalse(any("INSERT INTO usuarios" in query for query in queries))
        send_mail.assert_called_once()

    def test_account_without_operational_history_removes_legal_acceptance_before_delete(self):
        self.login_session()
        self.cur.fetchone.side_effect = [
            {"senha_hash": "hash-simulado", "status": "aprovado", "perfil": "proprietario"}, {"id": 9},
        ]
        response = self.client.delete("/admin/usuarios/9", headers={"X-CSRF-Token": "teste-csrf"})
        self.assertEqual(response.status_code, 200)
        queries = [args[0] for args, _ in self.cur.execute.call_args_list]
        self.assertIn("DELETE FROM aceites_legais WHERE usuario_id = %s", queries)
        self.assertIn("DELETE FROM usuarios WHERE id = %s", queries)

    def test_password_reset_request_sends_link_without_storing_plain_token(self):
        self.cur.fetchone.return_value = {"id": 9, "nome": "Pessoa"}
        with patch.object(api, "enviar_email_brevo", return_value=True) as send_mail:
            response = self.client.post("/auth/recuperar-senha", json={"email": "pessoa@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["ok"])
        update = next(args for args, _ in self.cur.execute.call_args_list if "UPDATE usuarios" in args[0])
        self.assertNotIn("redefinir-senha.html?token=", update[1][0])
        send_mail.assert_called_once()
        self.assertIn("redefinir-senha.html?token=", send_mail.call_args.args[2])

    def test_password_reset_invalidates_token_after_updating_password(self):
        self.cur.fetchone.return_value = {"id": 9}
        response = self.client.post("/auth/redefinir-senha", json={"token": "segredo", "password": "nova-senha"})
        self.assertEqual(response.status_code, 200)
        update = next(args for args, _ in self.cur.execute.call_args_list if "SET senha_hash" in args[0])
        self.assertIn("token_reset = NULL", update[0])
        self.assertNotEqual(update[1][0], "nova-senha")

    def test_log_access_is_fixed_for_only_three_roles(self):
        for role in api.PERFIS_VALIDOS:
            self.login_session(role)
            # Even a forged/persisted module permission cannot grant this log.
            self.profile_permissions[role] = {"usuarios", "log"}
            response = self.client.get("/admin/logs")
            self.assertEqual(response.status_code, 200 if role in api.ADMIN_ROLES else 403)

    def test_log_filters_combine_with_cursor_and_brasilia_day_boundaries(self):
        from datetime import datetime
        self.login_session()
        response = self.client.get('/admin/logs?usuario_id=42&data_inicio=2026-10-09&data_fim=2026-10-09&antes=90')
        self.assertEqual(response.status_code, 200)
        query, params = self.cur.execute.call_args.args
        self.assertIn('id < %s AND usuario_id = %s AND criado_em >= %s AND criado_em < %s', query)
        self.assertEqual(params, (90, 42, datetime(2026, 10, 9, 3), datetime(2026, 10, 10, 3), 51))

    def test_log_rejects_invalid_filters(self):
        self.login_session()
        for query in ('usuario_id=-1', 'usuario_id=1 OR 1=1', 'data_inicio=2026-02-30',
                      'data_inicio=2026-10-10&data_fim=2026-10-09', 'data_fim=9999-12-31'):
            with self.subTest(query=query):
                self.assertEqual(self.client.get('/admin/logs?' + query).status_code, 400)

    def test_log_filter_users_come_from_preserved_history(self):
        self.login_session()
        self.cur.fetchall.side_effect = [[{'id': 9, 'nome': 'Autor removido'}], []]
        response = self.client.get('/admin/logs?incluir_usuarios=1')
        self.assertEqual(response.json['usuarios'], [{'id': 9, 'nome': 'Autor removido'}])
        queries = [call.args[0] for call in self.cur.execute.call_args_list]
        self.assertTrue(any('GROUP BY l.usuario_id' in query and 'FROM log_atividades' in query
                            and 'FROM usuarios u' in query and 'UNION ALL' in query for query in queries))

    def test_log_rejects_future_date_with_clear_message(self):
        from datetime import datetime, timedelta, timezone
        self.login_session()
        tomorrow = (datetime.now(timezone(timedelta(hours=-3))) + timedelta(days=1)).date().isoformat()
        for key in ('data_inicio', 'data_fim'):
            response = self.client.get(f'/admin/logs?{key}={tomorrow}')
            self.assertEqual(response.status_code, 400)
            self.assertIn('datas futuras', response.json['mensagem'])

    def test_log_empty_filtered_result_is_explicit(self):
        self.login_session()
        response = self.client.get('/admin/logs?usuario_id=9&data_inicio=2000-01-01&data_fim=2000-01-01')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['logs'], [])
        self.assertIsNone(response.json['proximo'])
        self.assertEqual(response.json['filtros']['usuario_id'], '9')

    def test_log_has_no_write_endpoint(self):
        self.login_session()
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            response = self.client.open("/admin/logs", method=method, headers={"X-CSRF-Token": "teste-csrf"})
            self.assertEqual(response.status_code, 405)

    def test_log_cursor_and_read_do_not_generate_more_logs(self):
        self.login_session()
        self.cur.fetchall.return_value = [
            {"id": 8, "criado_em": "2026-10-09T15:00:00+00:00"},
            {"id": 7, "criado_em": "2026-10-09T14:00:00+00:00"},
        ]
        response = self.client.get("/admin/logs?limit=1&antes=9")
        self.assertEqual(response.json["proximo"], 8)
        self.assertEqual(len(response.json["logs"]), 1)
        self.assertEqual(self.cur.execute.call_args.args[1], (9, 2))
        self.db.commit.assert_not_called()
        self.assertEqual(self.client.get("/admin/logs?antes=invalid").status_code, 400)

    def test_audit_failure_rolls_back_business_change(self):
        self.login_session()
        def execute(query, *args):
            if "INSERT INTO log_atividades" in query:
                raise api.pymysql.OperationalError("audit unavailable")
        self.cur.execute.side_effect = execute
        response = self.client.post("/categorias-produto", json={"nome": "Teste"}, headers={"X-CSRF-Token": "teste-csrf"})
        self.assertEqual(response.status_code, 500)
        self.db.rollback.assert_called()
        self.db.commit.assert_not_called()

    def test_audit_uses_session_actor_and_excludes_secrets(self):
        self.login_session()
        response = self.client.post("/categorias-produto", json={
            "nome": "Teste", "usuario_id": 99, "senha": "segredo", "token": "token-secreto",
        }, headers={"X-CSRF-Token": "teste-csrf"})
        self.assertEqual(response.status_code, 201)
        event = next(call.args[1] for call in self.cur.execute.call_args_list if "INSERT INTO log_atividades" in call.args[0])
        self.assertEqual(event[0], 42)
        self.assertNotIn("segredo", str(event))
        self.assertNotIn("token-secreto", str(event))
        self.db.commit.assert_called_once()

    def test_logout_is_audited_before_session_is_cleared(self):
        self.login_session()
        self.client.post("/auth/logout", headers={"X-CSRF-Token": "teste-csrf"})
        event = next(call.args[1] for call in self.cur.execute.call_args_list if "INSERT INTO log_atividades" in call.args[0])
        self.assertEqual(event[0], 42)
        self.assertEqual(event[3], "Saiu do sistema")

    def test_route_contract_matches_original_snapshot(self):
        original = json.loads((ROOT / "tests/fixtures/api_routes.json").read_text(encoding="utf-8"))
        expected = {(r["method"], r["path"], r["function"]) for r in original}
        actual = {(method, rule.rule, rule.endpoint) for rule in api.app.url_map.iter_rules()
                  for method in rule.methods - {"HEAD", "OPTIONS"} if rule.endpoint != "static"}
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
