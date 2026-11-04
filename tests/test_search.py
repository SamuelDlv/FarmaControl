"""Contratos de consulta: validação, parâmetros SQL, paginação e autorização."""
import unittest
from unittest.mock import patch
from werkzeug.datastructures import MultiDict
import pymysql
import test_backend as base
from farmacontrol.core.query import QueryError, query_int, search_text
from farmacontrol.routes import estoque, financeiro

api = base.api


class QueryHelpersTests(unittest.TestCase):
    def test_missing_is_different_from_empty_or_malformed(self):
        self.assertEqual(query_int({}, "n", default=10), 10)
        self.assertIsNone(query_int({}, "n"))
        for raw in ("", " ", "1.5", "abc", "1_000", "1 OR 1=1", "9" * 5000):
            with self.subTest(raw=raw[:20]), self.assertRaises(QueryError) as cm:
                query_int({"n": raw}, "n")
            self.assertEqual(cm.exception.campo, "n")

    def test_bounds_and_legacy_clamping_are_explicit(self):
        for raw, expected in ((" 2 ", 2), ("+3", 3), ("0", 0)):
            self.assertEqual(query_int({"n": raw}, "n", maximum=3), expected)
        for raw in ("-1", "4", "9223372036854775808"):
            with self.assertRaises(QueryError):
                query_int({"n": raw}, "n", maximum=3)
        self.assertEqual(query_int({"n": "-4"}, "n", minimum=1, maximum=100, clamp=True), 1)
        self.assertEqual(query_int({"n": "500"}, "n", minimum=1, maximum=100, clamp=True), 100)

    def test_search_preserves_internal_spaces_unicode_and_sql_characters(self):
        for value in ("ação", "AÇÃO", "A  B", "50%_'\\"):
            self.assertEqual(search_text({"busca": "  " + value + "  "}), value)
        self.assertEqual(search_text({"busca": " \t\n"}), "")
        self.assertEqual(search_text({}), "")
        self.assertEqual(len(search_text({"busca": "á" * 120})), 120)
        with self.assertRaises(QueryError):
            search_text({"busca": "á" * 121})

    def test_repeated_parameters_keep_werkzeug_first_value(self):
        self.assertEqual(query_int(MultiDict([("n", "2"), ("n", "3")]), "n"), 2)


class SearchContractTests(unittest.TestCase):
    setUp = base.BackendTests.setUp
    login_session = base.BackendTests.login_session

    def movement_query(self):
        return next(call.args for call in self.cur.execute.call_args_list
                    if "OFFSET %s" in call.args[0])

    def test_movements_reject_invalid_values_instead_of_dropping_filters(self):
        self.login_session()
        cases = [("produto_id", v) for v in ("", "abc", "0", "-1")]
        cases += [("periodo_dias", v) for v in ("", "abc", "0", "3651")]
        cases += [("limite", v) for v in ("", "abc", "0", "-1", "5001")]
        cases += [("offset", v) for v in ("", "abc", "-1", "9223372036854775808")]
        cases += [("busca", "a" * 121)]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                self.cur.execute.reset_mock()
                response = self.client.get("/movimentacoes-estoque", query_string={field: value})
                self.assertEqual(response.status_code, 400, response.json)
                self.assertEqual(response.json["campo"], field)
                self.assertFalse(any("OFFSET %s" in c.args[0] for c in self.cur.execute.call_args_list))

    def test_movements_empty_search_omits_text_filter_and_count(self):
        self.login_session()
        response = self.client.get("/movimentacoes-estoque", query_string={"busca": "   "})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"ok": True, "movimentacoes": [], "limite": 1000, "offset": 0})
        sql, params = self.movement_query()
        self.assertNotIn("p.nome LIKE", sql)
        self.assertEqual(params, (1000, 0))
        self.assertFalse(any("COUNT(*)" in c.args[0] for c in self.cur.execute.call_args_list))

    def test_movements_combined_filters_bind_same_values_to_list_and_count(self):
        self.login_session()
        self.cur.fetchone.side_effect = [
            {"senha_hash": "hash-simulado", "status": "aprovado", "perfil": "proprietario"},
            {"total": 3},
        ]
        self.cur.fetchall.return_value = [{"id": 7}, {"id": 6}]
        term = "Ação %_' OR 1=1 --"
        response = self.client.get("/movimentacoes-estoque", query_string={
            "produto_id": 8, "tipo": "saida", "periodo_dias": 30,
            "periodo": "month", "busca": "  " + term + "  ", "limite": 2, "offset": 0})
        self.assertEqual(response.status_code, 200)
        sql, params = self.movement_query()
        self.assertIn("me.data_movimentacao DESC, me.id DESC", sql)
        self.assertNotIn(term, sql)
        self.assertEqual(params, (8, "saida", 30, "%" + term + "%", 2, 0))
        count_sql, count_params = next(c.args for c in self.cur.execute.call_args_list if "COUNT(*)" in c.args[0])
        self.assertEqual(count_params, params[:-2])
        self.assertEqual(sql.split("WHERE ", 1)[1].split("ORDER", 1)[0].strip(),
                         count_sql.split("WHERE ", 1)[1].strip())
        self.assertTrue(response.json["tem_mais"])
        self.assertEqual(response.json["proximo_offset"], 2)
        self.assertEqual(response.json["total"], 3)

    def test_movements_last_and_empty_pages_have_no_next_offset(self):
        self.login_session()
        for offset, total, rows in ((2, 3, [{"id": 5}]), (3, 3, []), (0, 0, [])):
            with self.subTest(offset=offset, total=total):
                self.cur.fetchone.side_effect = [
                    {"senha_hash": "hash-simulado", "status": "aprovado", "perfil": "proprietario"},
                    {"total": total}]
                self.cur.fetchall.return_value = rows
                response = self.client.get("/movimentacoes-estoque", query_string={"offset": offset, "limite": 2})
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.json["tem_mais"])
                self.assertIsNone(response.json["proximo_offset"])

    def test_movement_enum_filters_remain_allowlisted(self):
        self.login_session()
        for field in ("tipo", "periodo"):
            response = self.client.get("/movimentacoes-estoque", query_string={field: "DESC; DROP TABLE produtos"})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["campo"], field)

    def test_log_cursor_and_extra_row_keep_existing_contract(self):
        self.login_session()
        self.cur.fetchall.return_value = [{"id": 8}, {"id": 7}, {"id": 6}]
        response = self.client.get("/admin/logs?limit=2&antes=9")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([r["id"] for r in response.json["logs"]], [8, 7])
        self.assertEqual(response.json["proximo"], 7)
        self.assertEqual(response.json["limite"], 2)
        self.assertTrue(response.json["tem_mais"])
        sql, params = self.cur.execute.call_args.args
        self.assertIn("id < %s", sql)
        self.assertIn("ORDER BY id DESC", sql)
        self.assertNotIn("OFFSET", sql)
        self.assertEqual(params, (9, 3))
        self.cur.fetchall.return_value = [{"id": 6}]
        response = self.client.get("/admin/logs?limit=2&antes=7")
        self.assertEqual([r["id"] for r in response.json["logs"]], [6])
        self.assertIsNone(response.json["proximo"])
        self.assertFalse(response.json["tem_mais"])

    def test_log_empty_page_and_blank_search(self):
        self.login_session()
        response = self.client.get("/admin/logs?busca=%20%20")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["logs"], [])
        self.assertFalse(response.json["tem_mais"])
        self.assertIsNone(response.json["proximo"])
        self.assertNotIn("LOCATE", self.cur.execute.call_args.args[0])

    def test_log_literal_search_is_bound_without_like_conversion(self):
        self.login_session()
        term = "Ação %_'"
        response = self.client.get("/admin/logs", query_string={"busca": term})
        self.assertEqual(response.status_code, 200)
        sql, params = self.cur.execute.call_args.args
        self.assertNotIn(term, sql)
        self.assertIn("LOCATE", sql)
        self.assertEqual(params, (term, term, term, 51))

    def test_log_invalid_numeric_and_long_search_are_client_errors(self):
        self.login_session()
        for field, value in (("limit", ""), ("limit", "abc"), ("antes", ""),
                             ("antes", "-1"), ("antes", "abc"), ("busca", "a" * 121)):
            response = self.client.get("/admin/logs", query_string={field: value})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json["campo"], field)

    def test_legacy_limit_clamping_remains_for_logs_and_finance(self):
        self.login_session()
        with patch.object(financeiro, "_fin_tables_exist", return_value=True):
            for route, maximum in (("/admin/logs", 100), ("/financeiro/transacoes", 500)):
                for value, expected in (("-1", 1), ("0", 1), ("9999", maximum)):
                    response = self.client.get(route, query_string={"limit": value})
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json["limite"], expected)

    def test_finance_invalid_limit_fails_before_table_check(self):
        self.login_session()
        with patch.object(financeiro, "_fin_tables_exist") as check:
            for value in ("", "abc", "1.5"):
                response = self.client.get("/financeiro/transacoes", query_string={"limit": value})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json["campo"], "limit")
            check.assert_not_called()

    def test_finance_stable_order_and_legacy_days_fallback(self):
        self.login_session()
        with patch.object(financeiro, "_fin_tables_exist", return_value=True):
            response = self.client.get("/financeiro/transacoes?days=invalid&limit=5")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"ok": True, "transacoes": [], "limite": 5})
        sql, params = next(c.args for c in self.cur.execute.call_args_list
                           if "FROM financeiro_transacoes t" in c.args[0])
        self.assertIn("ORDER BY t.data_transacao DESC, t.id DESC", sql)
        self.assertEqual(params, (30, 5))

    def test_database_failures_are_not_successful_empty_lists(self):
        with api.app.test_request_context("/movimentacoes-estoque"):
            with patch.object(estoque.database, "get_db", side_effect=pymysql.OperationalError("offline")):
                response, status = estoque.get_movimentacoes_estoque()
                self.assertEqual(status, 500)
                self.assertFalse(response.json["ok"])
        self.login_session()
        def fail_domain(sql, *args):
            if "FROM log_atividades " in sql or "FROM financeiro_transacoes t" in sql:
                raise pymysql.OperationalError("offline")
        self.cur.execute.side_effect = fail_domain
        self.assertEqual(self.client.get("/admin/logs").status_code, 503)
        with patch.object(financeiro, "_fin_tables_exist", return_value=True):
            self.assertEqual(self.client.get("/financeiro/transacoes").status_code, 500)

    def test_search_does_not_bypass_authentication_or_log_permissions(self):
        for route in ("/admin/logs", "/movimentacoes-estoque", "/financeiro/transacoes"):
            self.assertEqual(self.client.get(route + "?busca=x").status_code, 401)
        self.login_session("farmaceutico")
        self.assertEqual(self.client.get("/admin/logs?busca=x").status_code, 403)

