# Guia de manutenção — Implementa revogação de credenciais e limite de tentativas em memória.
# Consulte docs/DESENVOLVIMENTO.md para executar as verificações desta camada.
"""Controles de entrada e contenção local, sem acesso ao banco."""
import hashlib
import hmac
import math
import threading
import time


# Vincula o cookie à credencial sem publicar seu hash bcrypt.
def credential_stamp(secret, password_hash):
    """Vincula o cookie à credencial sem publicar seu hash bcrypt."""
    return hmac.new(secret.encode(), password_hash.encode(), hashlib.sha256).hexdigest()


# Janela fixa por IP/processo; memória limitada e acesso sincronizado.
class AuthLimiter:
    """Janela fixa por IP/processo; memória limitada e acesso sincronizado.

    Em múltiplos workers, complementar no proxy com limite compartilhado.
    Cabeçalhos enviados pelo cliente nunca são usados como identidade.
    """
    def __init__(self, limit=5, window=300, capacity=4096):
        self.limit, self.window, self.capacity = limit, window, capacity
        self.entries = {}
        self.lock = threading.Lock()

    def check(self, ip):
        return self.check_with_status(ip)["retry_after"]

    # Consome uma tentativa e devolve os limites da mesma operação atômica.
    def check_with_status(self, ip):
        """Consome uma tentativa e devolve os limites da mesma operação atômica."""
        # O relógio monotônico mede duração sem sofrer ajustes do relógio civil.
        # O lock cobre limpeza, leitura e incremento para não perder tentativas
        # quando requisições simultâneas chegam ao mesmo processo.
        now = time.monotonic()
        with self.lock:
            self.entries = {key: value for key, value in self.entries.items() if value[0] > now}
            end, count = self.entries.get(ip, (now + self.window, 0))
            # Ao atingir a capacidade, recuse novas identidades temporariamente:
            # desalojar uma entrada ativa permitiria contornar o limite existente.
            if ip not in self.entries and len(self.entries) >= self.capacity:
                retry = max(1, math.ceil(min(v[0] for v in self.entries.values()) - now))
                return {"remaining": 0, "reset_after": retry, "retry_after": retry}
            if count >= self.limit:
                retry = max(1, math.ceil(end - now))
                return {"remaining": 0, "reset_after": retry, "retry_after": retry}
            self.entries[ip] = (end, count + 1)
            return {"remaining": self.limit - count - 1,
                    "reset_after": max(1, math.ceil(end - now)), "retry_after": 0}
