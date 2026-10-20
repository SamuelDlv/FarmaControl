"""Controles de entrada e contenção local, sem acesso ao banco."""
import hashlib
import hmac
import math
import threading
import time


def credential_stamp(secret, password_hash):
    """Vincula o cookie à credencial sem publicar seu hash bcrypt."""
    return hmac.new(secret.encode(), password_hash.encode(), hashlib.sha256).hexdigest()


class AuthLimiter:
    """Janela fixa por IP/processo; memória limitada e acesso sincronizado.

    Em múltiplos workers, complementar no proxy com limite compartilhado.
    Cabeçalhos enviados pelo cliente nunca são usados como identidade.
    """
    def __init__(self, limit=20, window=300, capacity=4096):
        self.limit, self.window, self.capacity = limit, window, capacity
        self.entries = {}
        self.lock = threading.Lock()

    def check(self, ip):
        now = time.monotonic()
        with self.lock:
            self.entries = {key: value for key, value in self.entries.items() if value[0] > now}
            end, count = self.entries.get(ip, (now + self.window, 0))
            if ip not in self.entries and len(self.entries) >= self.capacity:
                return max(1, math.ceil(min(v[0] for v in self.entries.values()) - now))
            if count >= self.limit:
                return max(1, math.ceil(end - now))
            self.entries[ip] = (end, count + 1)
            return 0
