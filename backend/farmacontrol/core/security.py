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


def login_account_key(secret, identity):
    """Identidade normalizada e opaca; o contador não armazena IDs/e-mails."""
    return credential_stamp(secret, 'login:' + identity.strip().lower())


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


class LoginFailureLimiter:
    """Falhas por conta, com reserva atômica das verificações em andamento.

    Sucesso limpa somente as falhas da conta. Reservas de outras requisições
    permanecem válidas: uma falha concorrente não desaparece por acidente.
    """
    def __init__(self, limit=5, window=300, capacity=4096):
        self.limit, self.window, self.capacity = limit, window, capacity
        self.entries = {}
        self.lock = threading.Lock()
        self.serial = 0

    def _expire(self, now):
        self.entries = {key: value for key, value in self.entries.items() if value['end'] > now}

    def _status(self, entry, now):
        failures = entry['failures'] if entry else 0
        wait = max(1, math.ceil(entry['end'] - now)) if entry else 0
        return {'remaining': self.limit - failures, 'reset_after': wait,
                'retry_after': wait if failures >= self.limit else 0}

    def begin(self, key):
        """Reserva uma verificação, sem registrá-la como senha incorreta."""
        now = time.monotonic()
        with self.lock:
            self._expire(now)
            entry = self.entries.get(key)
            if entry is None:
                if len(self.entries) >= self.capacity:
                    wait = max(1, math.ceil(min(e['end'] for e in self.entries.values()) - now))
                    return {'remaining': 0, 'reset_after': wait, 'retry_after': wait, 'ticket': None}
                entry = {'end': now + self.window, 'failures': 0, 'pending': set()}
                self.entries[key] = entry
            status = self._status(entry, now)
            if status['retry_after']:
                return {**status, 'ticket': None}
            if entry['failures'] + len(entry['pending']) >= self.limit:
                # Requisições simultâneas aguardam; não viram falhas de senha.
                return {'remaining': 0, 'reset_after': 1, 'retry_after': 1, 'ticket': None}
            self.serial += 1
            entry['pending'].add(self.serial)
            return {**status, 'ticket': self.serial}

    def finish(self, key, ticket, outcome=None):
        """Conclui uma reserva uma única vez; erros internos não consomem falhas."""
        now = time.monotonic()
        with self.lock:
            self._expire(now)
            entry = self.entries.get(key)
            if entry is None or ticket not in entry['pending']:
                return self._status(entry, now)
            entry['pending'].remove(ticket)
            if outcome == 'failure':
                entry['failures'] += 1
            elif outcome == 'success':
                entry['failures'] = 0
                entry['end'] = now + self.window
            status = self._status(entry, now)
            if not entry['failures'] and not entry['pending']:
                del self.entries[key]
            return status
