"""Configuração validável sem carregar Flask, .env ou acessar o banco."""
import secrets
from datetime import timedelta
from urllib.parse import urlsplit


def runtime_config(env):
    mode = env.get('APP_ENV', 'development').strip().lower()
    if mode not in {'development', 'production', 'test'}:
        raise ValueError('APP_ENV deve ser development, production ou test.')
    production = mode == 'production'

    def boolean(name, default):
        value = env.get(name, str(default)).strip().lower()
        if value not in {'true', 'false'}:
            raise ValueError(f'{name} deve ser true ou false.')
        return value == 'true'

    secret = env.get('SECRET_KEY', '').strip()
    weak = len(secret) < 32 or secret in {
        'dev-secret-insecuro', 'substitua-por-um-segredo-longo-e-aleatorio',
    }
    if production and weak:
        raise ValueError('Produção exige SECRET_KEY aleatória de pelo menos 32 caracteres.')
    ephemeral = weak
    if ephemeral:
        secret = secrets.token_hex(32)
    debug = boolean('APP_DEBUG', False)
    secure = boolean('COOKIE_SECURE', production)
    if production and (debug or not secure):
        raise ValueError('Produção exige APP_DEBUG=false e COOKIE_SECURE=true.')
    hours = int(env.get('SESSION_HOURS', '8'))
    if not 1 <= hours <= 168:
        raise ValueError('SESSION_HOURS deve estar entre 1 e 168.')

    origins = []
    for origin in env.get('ALLOWED_ORIGINS', '').split(','):
        origin = origin.strip()
        if not origin:
            continue
        parsed = urlsplit(origin)
        if (parsed.scheme not in {'http', 'https'} or not parsed.hostname
                or parsed.username or parsed.password or parsed.path
                or parsed.query or parsed.fragment or '*' in origin):
            raise ValueError('ALLOWED_ORIGINS aceita apenas origens HTTP(S) explícitas, sem caminho, * ou null.')
        if production and parsed.scheme != 'https':
            raise ValueError('Origens de produção devem usar HTTPS.')
        origins.append(origin)
    return {
        'MAX_CONTENT_LENGTH': 1024 * 1024,
        'APP_ENV': mode, 'DEBUG': debug, 'SECRET_KEY': secret,
        'EPHEMERAL_SECRET': ephemeral, 'ALLOWED_ORIGINS': origins,
        'PERMANENT_SESSION_LIFETIME': timedelta(hours=hours),
        'SESSION_COOKIE_HTTPONLY': True, 'SESSION_COOKIE_SAMESITE': 'Lax',
        'SESSION_COOKIE_SECURE': secure,
    }
