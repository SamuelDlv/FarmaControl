"""Validação de formato sem alterar documentos previamente armazenados."""
import re


def validate_cnpj(value):
    if not isinstance(value, str) or not re.fullmatch(
            r'(?:[0-9]{14}|[0-9]{2}\.[0-9]{3}\.[0-9]{3}/[0-9]{4}-[0-9]{2})', value):
        raise ValueError('Informe os 14 números do CNPJ.')


def validate_phone(value, limit=20):
    if value is None or value == '':
        return
    if (not isinstance(value, str) or len(value) > limit
            or not re.fullmatch(r'\+?[0-9 ()-]+', value)
            or not re.search(r'[0-9]', value)):
        raise ValueError('Informe um telefone válido, com números e pontuação de telefone.')


def validate_supplier(data):
    limits = {'nome_fantasia': 150, 'razao_social': 255, 'contato_nome': 100,
              'contato_email': 180, 'endereco': 255}
    for key, limit in limits.items():
        value = data.get(key)
        if value is not None and (not isinstance(value, str) or len(value) > limit):
            raise ValueError(f'{key}: informe um texto de até {limit} caracteres.')
    if not (data.get('nome_fantasia') or '').strip() or not (data.get('razao_social') or '').strip():
        raise ValueError('Nome fantasia e razão social são obrigatórios.')
    validate_cnpj(data.get('cnpj'))
    validate_phone(data.get('contato_telefone'))
    email = data.get('contato_email')
    if email and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        raise ValueError('Informe um e-mail válido para o fornecedor.')
