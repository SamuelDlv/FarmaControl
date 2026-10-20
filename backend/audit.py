"""Auditoria transacional com campos permitidos, sem segredos ou dados clínicos."""
from flask import g, request, session

RESOURCES = {
    "estoque": "lote de estoque", "movimentacoes-estoque": "movimentação de estoque",
    "produtos": "produto", "categorias-produto": "categoria de produto",
    "compras": "compra", "fornecedores": "fornecedor", "clientes": "cliente",
    "vendas": "venda", "receitas": "receita", "alertas": "alerta",
    "configuracoes": "configuração", "usuarios": "usuário", "perfis": "permissões de perfil",
    "convites": "convite", "analisar-cadastro": "análise de cadastro",
    "financeiro": "financeiro", "dashboard": "dashboard", "relatorios": "relatório",
    "pendentes": "cadastros pendentes", "logs": "log",
}

# Lista explícita por recurso: nunca copie o payload inteiro para o histórico.
FIELDS = {
    "fornecedores": ("nome_fantasia", "razao_social"),
    "produtos": ("nome", "categoria_id", "tipo_produto", "preco_custo", "preco_venda", "estoque_minimo", "ativo"),
    "categorias-produto": ("nome",),
    "estoque": ("produto_id", "produto_nome", "lote", "quantidade", "data_validade", "localizacao"),
    "movimentacoes-estoque": ("estoque_id", "estoque_destino_id", "tipo_movimentacao", "quantidade"),
    "vendas": ("cliente_id", "status", "valor_total", "tipo_pagamento"),
    "compras": ("fornecedor_id", "status", "valor_total", "data_recebimento"),
    "financeiro": ("categoria_id", "tipo", "valor", "status", "metodo_pagamento", "data_vencimento"),
    "usuarios": ("perfil", "perfil_id", "status"),
    "analisar-cadastro": ("usuario_id", "decisao"),
    "alertas": ("tipo", "status", "resolvido", "estoque_id", "produto_id"),
}
ITEM_FIELDS = ("produto_id", "estoque_id", "quantidade", "preco_unitario", "desconto", "lote_vendido", "lote_recebido")


def safe_value(value):
    if value is None:
        return "não informado"
    if isinstance(value, (dict, list)):
        return "[valor estruturado omitido]"
    return " ".join(str(value).split())[:255]


def event_description(resource, data):
    method = request.method
    action = {"GET": "Consultou", "POST": "Cadastrou", "PUT": "Atualizou", "PATCH": "Atualizou", "DELETE": "Excluiu"}.get(method, "Acessou")
    description = f"{action} {RESOURCES.get(resource, resource)}"
    if method in {"POST", "PUT", "PATCH"}:
        if resource == "vendas" and data.get("status") != getattr(g, "audit_previous_status", None):
            description = {"concluida": "Concluiu venda", "cancelada": "Cancelou venda", "pendente": "Registrou venda pendente"}.get(data.get("status"), description)
        elif resource == "compras" and data.get("status") != getattr(g, "audit_previous_status", None):
            description = {"recebido": "Recebeu compra", "cancelado": "Cancelou compra"}.get(data.get("status"), description)
        elif resource == "movimentacoes-estoque":
            description = {"entrada": "Registrou entrada de estoque", "saida": "Registrou saída de estoque", "ajuste": "Ajustou estoque", "transferencia": "Transferiu estoque"}.get(data.get("tipo_movimentacao"), description)
        elif resource == "analisar-cadastro":
            description = "Aprovou cadastro" if data.get("decisao") == "aprovado" else "Rejeitou cadastro"
    return description


def write_event(db, status=200):
    actor = getattr(g, "audit_actor", None) or getattr(g, "usuario_id", None) or session.get("usuario_id")
    parts = request.path.strip("/").split("/")
    resource = parts[1] if parts[0] == "admin" and len(parts) > 1 else parts[0]
    payload = request.get_json(silent=True)
    data = payload if isinstance(payload, dict) else {}
    data = {**data, **getattr(g, "audit_values", {})}
    description = event_description(resource, data)
    if resource == "auth":
        description = {"login": "Entrou no sistema", "logout": "Saiu do sistema",
                       "register": "Criou cadastro", "recuperar-senha": "Solicitou recuperação de senha",
                       "redefinir-senha": "Redefiniu a senha", "convites": "Recusou convite"}.get(parts[1], "Ação de autenticação")
    description = getattr(g, "audit_description", description)
    # Somente a rota parametrizada: links de convite contêm tokens secretos.
    route = request.url_rule.rule if request.url_rule else "/"
    identifiers = [f"{key}={value}" for key, value in (request.view_args or {}).items() if key.endswith("_id") and isinstance(value, int)]
    entity_id = getattr(g, "audit_entity", None)
    if entity_id:
        identifiers.append(f"registro={entity_id}")
    lines = [f"{request.method} {route}" + (" · " + ", ".join(identifiers) if identifiers else "")]
    if request.method in {"POST", "PUT", "PATCH"}:
        for key in FIELDS.get(resource, ()):
            if key in data:
                lines.append(f"{key}: {safe_value(data[key])}")
        if resource in {"compras", "vendas"} and isinstance(data.get("itens"), list):
            lines.append(f"Itens: {len(data['itens'])}")
            for number, item in enumerate(data["itens"], 1):
                if isinstance(item, dict):
                    lines.append(f"Item {number}: " + "; ".join(f"{key}={safe_value(item[key])}" for key in ITEM_FIELDS if key in item))
        if resource == "configuracoes":
            # Valores de configuração podem conter credenciais. Registre só chaves conhecidas.
            from system_settings import KEYS
            keys = sorted(key for key in data if key in KEYS)
            key = (request.view_args or {}).get("chave") or data.get("chave")
            if isinstance(key, str) and key in KEYS:
                keys.append(key)
            lines.append("Configurações: " + ", ".join(keys))
        if resource == "perfis":
            for profile, modules in getattr(g, "audit_permissions", {}).items():
                lines.append(f"Perfil {profile}: " + (", ".join(sorted(modules)) or "sem módulos"))
    if getattr(g, "audit_previous_status", None) is not None:
        lines.append(f"Status anterior: {safe_value(g.audit_previous_status)}")
    details = "\n".join(lines)
    # MEDIUMTEXT comporta os itens de compras/vendas sem truncar o histórico.
    with db.cursor() as cur:
        cur.execute("""INSERT INTO log_atividades
            (usuario_id, usuario_nome, perfil, acao, detalhes, status_http)
            VALUES (%s, COALESCE((SELECT TRIM(CONCAT(nome, ' ', COALESCE(sobrenome, '')))
              FROM usuarios WHERE id = %s), 'Visitante'),
              COALESCE((SELECT p.slug FROM usuarios u JOIN perfis p ON p.id = u.perfil_id
              WHERE u.id = %s), ''), %s, %s, %s)""",
            (actor, actor, actor, description, details, status))


def commit_audit(db, entity_id=None):
    """A alteração e seu histórico são confirmados na mesma transação."""
    if request.method == "POST" and isinstance(entity_id, int) and entity_id > 0:
        g.audit_entity = entity_id
    if not getattr(g, "audit_written", False):
        write_event(db, getattr(g, "audit_status", 200))
    db.commit()
    g.audit_written = True
