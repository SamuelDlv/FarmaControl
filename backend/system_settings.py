"""Validação e leitura das preferências persistidas da farmácia."""
import re
from datetime import date

DEFAULTS = {
    'fuso_horario': 'America/Sao_Paulo', 'idioma': 'pt-BR', 'moeda': 'BRL',
    'alerta_estoque_minimo': 'true', 'alerta_vencimento': 'true',
    'alertas_pedidos_pendentes': 'true', 'notificacoes_email': 'false',
    'relatorio_semanal': 'false', 'prazo_vencimento': '30',
    'estoque_minimo_padrao': '10', 'estoque_maximo_padrao': '100',
    'ponto_reposicao': '20', 'metodo_custeio': 'PEPS',
    'unidade_medida_padrao': 'unidade', 'controle_lote_obrigatorio': 'false',
    'bloquear_produtos_vencidos': 'true',
}
BOOLEANS = {k for k, v in DEFAULTS.items() if v in ('true', 'false')} | {
    'animacoes_interface', 'sidebar_recolhida_padrao'}
ENUMS = {
    'fuso_horario': ('America/Sao_Paulo', 'America/Manaus', 'America/Belem'),
    'idioma': ('pt-BR', 'en-US', 'es'), 'moeda': ('BRL', 'USD'),
    'metodo_custeio': ('PEPS', 'UEPS', 'custo_medio'),
    'unidade_medida_padrao': ('unidade', 'caixa', 'frasco', 'blister'),
    'densidade_interface': ('normal', 'compacta', 'espacada'),
    'cor_destaque': ('#4a7c59', '#2e6da4', '#b87a1a', '#c03a3a', '#6b4fbb', '#1a7a6e'),
}
TEXT_LIMITS = {'nome_farmacia': 255, 'cnpj': 18, 'crf_responsavel': 100,
               'telefone': 30, 'endereco': 500, 'email_notificacao': 254}
NUMBERS = {'prazo_vencimento': (1, 365), 'estoque_minimo_padrao': (0, 1000000),
           'estoque_maximo_padrao': (1, 1000000), 'ponto_reposicao': (0, 1000000)}
KEYS = set(DEFAULTS) | BOOLEANS | set(ENUMS) | set(TEXT_LIMITS) | set(NUMBERS)


def read_settings(cursor):
    cursor.execute('SELECT chave, valor FROM configuracoes_sistema')
    settings = dict(DEFAULTS)
    for row in cursor.fetchall():
        key, value = row.get('chave'), row.get('valor')
        if not key or value is None:
            continue
        value = str(value)
        if key in NUMBERS:
            low, high = NUMBERS[key]
            if not value.isdigit() or not low <= int(value) <= high:
                continue
        if key in BOOLEANS and value not in ('true', 'false'):
            continue
        if key in ENUMS and value not in ENUMS[key]:
            continue
        settings[key] = value
    return settings


def require_lot(settings, lot):
    if settings['controle_lote_obrigatorio'] == 'true' and (not lot or lot == 'SEM-LOTE'):
        raise ValueError('Informe o número do lote: o controle por lote está habilitado.')


def require_usable_stock(settings, stock):
    require_lot(settings, stock.get('lote'))
    expiry = stock.get('data_validade')
    if (settings['bloquear_produtos_vencidos'] == 'true' and expiry
            and str(expiry)[:10] < date.today().isoformat()):
        raise ValueError('Saída bloqueada: o produto está vencido.')


def active_alerts(cursor, settings):
    alerts = []
    if settings['alerta_estoque_minimo'] == 'true':
        cursor.execute('''SELECT p.id, p.nome, COALESCE(SUM(e.quantidade), 0) AS quantidade,
            p.estoque_minimo FROM produtos p LEFT JOIN estoque e ON e.produto_id=p.id
            WHERE p.ativo=1 GROUP BY p.id, p.nome, p.estoque_minimo
            HAVING quantidade <= p.estoque_minimo ORDER BY p.nome''')
        for row in cursor.fetchall():
            alerts.append({'tipo': 'estoque_baixo', 'titulo': row['nome'],
                           'mensagem': f"Estoque: {row['quantidade']} · mínimo: {row['estoque_minimo']}"})
    if settings['alerta_vencimento'] == 'true':
        cursor.execute('''SELECT p.nome, e.lote, e.data_validade FROM estoque e
            JOIN produtos p ON p.id=e.produto_id WHERE e.quantidade > 0
            AND e.data_validade <= CURDATE() + INTERVAL %s DAY ORDER BY e.data_validade''',
            (int(settings['prazo_vencimento']),))
        for row in cursor.fetchall():
            alerts.append({'tipo': 'vencimento', 'titulo': row['nome'],
                           'mensagem': f"Lote {row['lote']} · validade: {row['data_validade']}"})
    if settings['alertas_pedidos_pendentes'] == 'true':
        cursor.execute("""SELECT id FROM compras WHERE status='pendente'
            AND data_pedido <= NOW() - INTERVAL 48 HOUR ORDER BY data_pedido""")
        for row in cursor.fetchall():
            alerts.append({'tipo': 'pedido_pendente', 'titulo': f"Pedido #{row['id']}",
                           'mensagem': 'Compra pendente há mais de 48 horas.'})
    return alerts


def validate_settings(values, current=None):
    if not isinstance(values, dict) or not values:
        raise ValueError('Informe as configurações para salvar.')
    clean = {}
    for key, value in values.items():
        if key not in KEYS:
            raise ValueError('Configuração desconhecida: ' + key)
        if isinstance(value, bool):
            value = 'true' if value else 'false'
        if not isinstance(value, (str, int)):
            raise ValueError('Valor inválido para ' + key)
        value = str(value).strip()
        if key in BOOLEANS and value not in ('true', 'false'):
            raise ValueError('Opção inválida para ' + key)
        if key in ENUMS and value not in ENUMS[key]:
            raise ValueError('Opção inválida para ' + key)
        if key in TEXT_LIMITS and len(value) > TEXT_LIMITS[key]:
            raise ValueError('Texto muito longo para ' + key)
        if key in NUMBERS:
            low, high = NUMBERS[key]
            if not re.fullmatch(r'\d+', value) or not low <= int(value) <= high:
                raise ValueError(f'{key}: informe um inteiro entre {low} e {high}.')
            value = str(int(value))
        if key == 'email_notificacao' and value and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('Informe um e-mail válido para alertas.')
        clean[key] = value
    merged = {**DEFAULTS, **(current or {}), **clean}
    if int(merged['estoque_minimo_padrao']) > int(merged['estoque_maximo_padrao']):
        raise ValueError('O estoque máximo deve ser maior ou igual ao mínimo.')
    if not int(merged['estoque_minimo_padrao']) <= int(merged['ponto_reposicao']) <= int(merged['estoque_maximo_padrao']):
        raise ValueError('O ponto de reposição deve ficar entre o estoque mínimo e o máximo.')
    if any(merged[k] == 'true' for k in ('notificacoes_email', 'relatorio_semanal')) and not merged.get('email_notificacao'):
        raise ValueError('Preencha o e-mail para ativar as notificações por e-mail.')
    return clean
