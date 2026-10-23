"""routes.frontend: responsabilidades extraídas da aplicação Flask."""

from farmacontrol.core import access
from farmacontrol.core import responses
from farmacontrol.core.paths import FRONTEND_DIR
from flask import current_app as app
from flask import g
from flask import redirect
import mimetypes
import os
import re


FRONTEND_ASSETS = str(FRONTEND_DIR)


FRONTEND_SRC = os.path.join(FRONTEND_ASSETS, 'pages', 'sistema')


PAGE_ASSET_EXTENSIONS = ('.html', '.css', '.js', '.png', '.jpg', '.jpeg', '.svg', '.woff', '.woff2', '.json')


def _serve_frontend_file(directory, filename, allowed_extensions=None):
    """Entrega estáticos com o mesmo MIME/cache das rotas canônica e legada.

    commonpath compara diretórios completos, evitando confundir uma pasta
    irmã de mesmo prefixo com um recurso dentro da raiz permitida.
    """
    safe = re.sub(r'[<>:"|?*]', '', filename)
    if not safe or '..' in safe:
        return responses.err('Recurso não disponível.', status=404)
    base = os.path.realpath(directory)
    target = os.path.realpath(os.path.join(base, safe))
    try:
        inside = os.path.commonpath((base, target)) == base
    except ValueError:
        inside = False  # Unidades diferentes no Windows não têm raiz comum.
    if not inside or not os.path.isfile(target):
        return responses.err('Recurso não encontrado.', status=404)
    if allowed_extensions and not safe.lower().endswith(allowed_extensions):
        return responses.err('Tipo de arquivo não suportado.', status=404)
    # Verifica o destino físico: a rota genérica e aliases de caminho também
    # precisam passar pela proteção, inclusive em sistemas sem case sensitivity.
    system_root = os.path.realpath(FRONTEND_SRC)
    protected_html = (target.lower().endswith('.html') and
                      os.path.commonpath((system_root, target)) == system_root)
    if protected_html:
        failure = access.validar_sessao()
        if failure is not None:
            response = app.make_response(failure)
            if response.status_code == 401:
                response = redirect('/pages/acesso/acesso.html')
            response.headers['Cache-Control'] = 'no-store'
            return response
        module = os.path.relpath(target, system_root).split(os.sep)[0]
        allowed = (g.usuario_perfil in access.ADMIN_ROLES if module == 'log' else
                   g.usuario_perfil in access.SALES_ROLES if module == 'vendas' else
                   module in g.usuario_permissoes)
        if not allowed:
            response = app.make_response(responses.err('Seu perfil nao tem permissao para acessar esta página.', status=403))
            response.headers['Cache-Control'] = 'no-store'
            return response
    mime, _ = mimetypes.guess_type(target)
    with open(target, 'rb') as fh:
        data = fh.read()
    resp = app.response_class(data, mimetype=mime or 'application/octet-stream')
    resp.headers['Cache-Control'] = (
        'no-store' if protected_html else
        'no-cache' if safe.lower().endswith(('.html', '.css', '.js'))
        else 'public, max-age=300'
    )
    return resp


def serve_sistema_page(filename):
    """Serve as telas compartilhadas por perfil nas duas URLs compatíveis."""
    return _serve_frontend_file(FRONTEND_SRC, filename, PAGE_ASSET_EXTENSIONS)


def serve_frontend_asset(filename):
    """Entrega utilitários, estilos, login e imagens relativos a frontend/src.

    Rotas de API mais específicas continuam tendo precedência sobre este
    caminho genérico; suas permissões são verificadas em proteger_api.
    """
    return _serve_frontend_file(FRONTEND_ASSETS, filename)


def register_routes(app):
    """Registra as URLs e nomes de endpoints existentes."""
    app.add_url_rule('/pages/proprietario/<path:filename>', view_func=serve_sistema_page)
    app.add_url_rule('/pages/sistema/<path:filename>', view_func=serve_sistema_page)
    app.add_url_rule('/<path:filename>', view_func=serve_frontend_asset)
