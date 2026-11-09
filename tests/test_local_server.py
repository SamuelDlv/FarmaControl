"""Encerramento: conclui requisições, fecha conexões e isola a pasta no Windows."""

import os
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from unittest.mock import Mock, patch
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from flask import Flask, g
from farmacontrol.core.database import close_db
from farmacontrol.core.local_server import LocalServer, WindowsControl, control_name


class LocalServerTests(unittest.TestCase):
    def test_close_waits_for_request_and_database_teardown(self):
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        connection = Mock()
        app = Flask(__name__)
        app.teardown_appcontext(close_db)

        @app.get('/')
        def slow_request():
            g.db = connection
            entered.set()
            if not release.wait(5):
                raise RuntimeError('Teste não liberou a requisição')
            return 'concluida'

        server = LocalServer('127.0.0.1', 0, app)
        serving = threading.Thread(target=server.handle_request)
        results = []

        def request():
            with urlopen(f'http://127.0.0.1:{server.port}/', timeout=10) as response:
                results.append(response.read())

        client = threading.Thread(target=request)
        serving.start()
        client.start()
        closer = None
        try:
            self.assertTrue(entered.wait(5))
            serving.join(5)
            self.assertFalse(serving.is_alive())

            def close():
                server.server_close()
                finished.set()

            closer = threading.Thread(target=close)
            closer.start()
            self.assertFalse(finished.wait(0.2), 'Encerramento cortou a requisição ativa')
            connection.close.assert_not_called()
            release.set()
            self.assertTrue(finished.wait(5))
        finally:
            release.set()
            client.join(10)
            serving.join(5)
            if closer:
                closer.join(5)
            server.server_close()
        self.assertEqual(results, [b'concluida'])
        connection.close.assert_called_once()

    @unittest.skipUnless(os.name == 'nt', 'Eventos nativos do Windows')
    def test_batch_signals_only_this_project_and_waits_for_completion(self):
        root = Path(__file__).resolve().parents[1]
        control = WindowsControl()
        with patch('farmacontrol.core.local_server.control_name', return_value=control_name() + '-other'):
            other = WindowsControl()
        acknowledged = threading.Event()

        def acknowledge():
            for _ in range(100):
                if control.requested():
                    control.kernel.SetEvent(control.done)
                    acknowledged.set()
                    return
                if acknowledged.wait(0.1):
                    return

        responder = threading.Thread(target=acknowledge)
        responder.start()
        try:
            result = subprocess.run(['cmd.exe', '/c', str(root / 'Encerrar-FarmaControl.bat')],
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(acknowledged.is_set())
            self.assertIn('FarmaControl encerrado.', result.stdout)
            self.assertFalse(other.requested())
            with self.assertRaisesRegex(RuntimeError, 'execução'):
                WindowsControl()
        finally:
            acknowledged.set()
            responder.join(5)
            other.close()
            control.close()


if __name__ == '__main__':
    unittest.main()
