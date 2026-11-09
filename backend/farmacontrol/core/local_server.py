# Guia de manutenção — Serve a instalação local e coordena o encerramento das requisições no Windows.
# Consulte docs/DESENVOLVIMENTO.md para executar as verificações desta camada.
"""Servidor local com encerramento cooperativo, sem controlar o serviço de banco."""

import ctypes
from ctypes import wintypes
import hashlib
import os

from werkzeug.debug import DebuggedApplication
from werkzeug.serving import ThreadedWSGIServer

from farmacontrol.core.paths import BACKEND_DIR


# Agrupa o estado e as operações de LocalServer.
class LocalServer(ThreadedWSGIServer):
    # Aguarda os handlers terminarem, incluindo commit/rollback e teardown do Flask.
    daemon_threads = False
    block_on_close = True
    timeout = 0.25


# O hash do caminho absoluto identifica esta cópia do projeto na sessão Windows.
# Mantenha a mesma normalização em stop_local_server.ps1 para evitar encerrar outra pasta.
def control_name():
    path = str((BACKEND_DIR / "app.py").resolve()).lower()
    digest = hashlib.sha256(path.encode("utf-8")).hexdigest()
    return "Local\\FarmaControl-" + digest


# Eventos restritos à sessão Windows e identificados pela pasta do projeto.
class WindowsControl:
    """Eventos restritos à sessão Windows e identificados pela pasta do projeto."""

    def __init__(self):
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL,
                                           wintypes.BOOL, wintypes.LPCWSTR]
        self.kernel.CreateEventW.restype = wintypes.HANDLE
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.WaitForSingleObject.restype = wintypes.DWORD
        self.kernel.SetEvent.argtypes = [wintypes.HANDLE]
        self.kernel.SetEvent.restype = wintypes.BOOL
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.handles = []
        try:
            self.stop = self._create(".Stop")
            self.done = self._create(".Done")
        except BaseException:
            self.close()
            raise

    def _create(self, suffix):
        handle = self.kernel.CreateEventW(None, True, False, control_name() + suffix)
        error = ctypes.get_last_error()
        if not handle:
            raise ctypes.WinError(error)
        self.handles.append(handle)
        if error == 183:  # ERROR_ALREADY_EXISTS: não reutilizar sinal de outra instância.
            raise RuntimeError("FarmaControl desta pasta já está em execução ou encerrando.")
        return handle

    def requested(self):
        result = self.kernel.WaitForSingleObject(self.stop, 0)
        if result == 0:
            return True
        if result != 258:  # WAIT_TIMEOUT
            raise ctypes.WinError(ctypes.get_last_error())
        return False

    def close(self):
        for handle in reversed(self.handles):
            self.kernel.CloseHandle(handle)
        self.handles.clear()


# Aguarda o sinal de parada sem matar processos nem interromper transações em andamento.
# O evento Done só é sinalizado depois de o servidor aguardar as threads das requisições.
def run_local(app):
    control = WindowsControl() if os.name == "nt" else None
    try:
        application = DebuggedApplication(app, evalex=True) if app.debug else app
        with LocalServer("127.0.0.1", 5000, application) as server:
            print("FarmaControl: http://127.0.0.1:5000 - Ctrl+C ou Encerrar-FarmaControl.bat",
                  flush=True)
            try:
                while control is None or not control.requested():
                    server.handle_request()
            except KeyboardInterrupt:
                pass
            finally:
                print("Encerrando: aguardando as requisicoes em andamento...", flush=True)
        # O context manager só retorna depois de fechar as threads das requisições.
    finally:
        if control is not None:
            control.kernel.SetEvent(control.done)
            control.close()
