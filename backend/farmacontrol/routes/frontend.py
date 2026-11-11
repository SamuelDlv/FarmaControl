# Guia de manutenção — Entrega arquivos estáticos e protege o HTML das telas internas no servidor.
# Consulte docs/desenvolvimento.md para executar as verificações desta camada.
"""routes.frontend: responsabilidades extraídas da aplicação Flask."""

from farmacontrol.core import access
from farmacontrol.core import responses
from farmacontrol.core.paths import FRONTEND_DIR
from flask import current_app as app
from flask import g
from flask import redirect
from flask import session
import mimetypes
import os
import re
import json


FRONTEND_ASSETS = str(FRONTEND_DIR)


FRONTEND_SRC = os.path.join(FRONTEND_ASSETS, 'pages', 'sistema')


PAGE_ASSET_EXTENSIONS = ('.html', '.css', '.js', '.png', '.jpg', '.jpeg', '.svg', '.woff', '.woff2', '.json')


# Entrega estáticos com o mesmo MIME/cache das rotas canônica e legada.
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
        allowed = access.pode_acessar_modulo(g.usuario_perfil, g.usuario_permissoes, module)
        if not allowed:
            response = app.make_response(responses.err('Seu perfil nao tem permissao para acessar esta página.', status=403))
            response.headers['Cache-Control'] = 'no-store'
            return response
    mime, _ = mimetypes.guess_type(target)
    with open(target, 'rb') as fh:
        data = fh.read()
    if protected_html:
        modules = ('estoque', 'vencimentos', 'compras', 'financeiro', 'usuarios', 'configuracoes', 'vendas')
        context = {
            'id': g.usuario_id, 'perfil': g.usuario_perfil,
            'permissoes': sorted(g.usuario_permissoes),
            'modulos_escrita': [m for m in modules if access.pode_acessar_modulo(
                g.usuario_perfil, g.usuario_permissoes, m, escrita=True)],
            'pagina_inicial': access.pagina_inicial(g.usuario_perfil, g.usuario_permissoes),
            'csrf_token': session.get('csrf_token'),
        }
        # JSON inerte, revalidado a cada HTML; não depende do cache da aba.
        payload = json.dumps(context, ensure_ascii=True).replace('<', '\\u003c')
        tag = f'<script type="application/json" id="fc-session-context">{payload}</script>'
        data = data.replace(b'<head>', ('<head>' + tag).encode('utf-8'), 1)
    resp = app.response_class(data, mimetype=mime or 'application/octet-stream')
    resp.headers['Cache-Control'] = (
        'no-store' if protected_html else
        'no-cache' if safe.lower().endswith(('.html', '.css', '.js'))
        else 'public, max-age=300'
    )
    return resp


# Serve as telas compartilhadas por perfil nas duas URLs compatíveis.
def serve_sistema_page(filename):
    """Serve as telas compartilhadas por perfil nas duas URLs compatíveis."""
    return _serve_frontend_file(FRONTEND_SRC, filename, PAGE_ASSET_EXTENSIONS)


# Entrega utilitários, estilos, login e imagens relativos a frontend/src.
def serve_frontend_asset(filename):
    """Entrega utilitários, estilos, login e imagens relativos a frontend/src.

    Rotas de API mais específicas continuam tendo precedência sobre este
    caminho genérico; suas permissões são verificadas em proteger_api.
    """
    return _serve_frontend_file(FRONTEND_ASSETS, filename)


# Liga URLs, métodos HTTP e nomes de endpoint à instância recebida.
# Alterar estes contratos exige revisar as telas e tests/fixtures/api_routes.json.
def register_routes(app):
    """Registra as URLs e nomes de endpoints existentes."""
    app.add_url_rule('/pages/proprietario/<path:filename>', view_func=serve_sistema_page)
    app.add_url_rule('/pages/sistema/<path:filename>', view_func=serve_sistema_page)
    app.add_url_rule('/<path:filename>', view_func=serve_frontend_asset)
