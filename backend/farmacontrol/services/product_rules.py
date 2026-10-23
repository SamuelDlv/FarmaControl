"""Regras comuns ao catálogo, cadastro de estoque e recebimento de compras."""
from datetime import date
from decimal import Decimal, InvalidOperation


def normalize_product(data, current=None):
    product = dict(current or {})
    product.update(data)
    product.setdefault("tipo_produto", "medicamento")
    product.setdefault("exige_validade", True)
    product.setdefault("requer_receita", False)
    product.setdefault("ativo", True)
    product.setdefault("estoque_minimo", 10)
    if product["tipo_produto"] not in ("medicamento", "outro"):
        raise ValueError("Tipo de produto inválido.")
    for field in ("exige_validade", "requer_receita", "ativo"):
        if product[field] not in (True, False, 0, 1):
            raise ValueError("Informe um valor booleano para " + field + ".")
    if product["tipo_produto"] == "medicamento":
        if not product["exige_validade"]:
            raise ValueError("Medicamentos devem exigir validade nos lotes.")
    else:
        if product["requer_receita"]:
            raise ValueError("Somente medicamentos podem exigir receita.")
        product["nome_generico"] = None
    name = product.get("nome")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 255:
        raise ValueError("Informe um nome de produto com até 255 caracteres.")
    product["nome"] = name.strip()
    for field in ("preco_custo", "preco_venda"):
        try:
            value = Decimal(str(product.get(field)))
        except InvalidOperation:
            raise ValueError("Informe preços válidos para custo e venda.") from None
        if not value.is_finite() or value <= 0 or value > Decimal("99999999.99"):
            raise ValueError("Preço de custo e venda devem ser maiores que zero.")
        product[field] = value.quantize(Decimal("0.01"))
        if product[field] <= 0:
            raise ValueError("O menor preço permitido é R$ 0,01.")
    minimum = product["estoque_minimo"]
    if isinstance(minimum, bool) or not isinstance(minimum, int) or not 0 <= minimum <= 4294967295:
        raise ValueError("Estoque mínimo deve ser um inteiro igual ou maior que zero.")
    for field, limit in (("codigo_barras", 50), ("nome_generico", 255), ("fabricante", 150)):
        value = product.get(field)
        if value is not None and (not isinstance(value, str) or len(value) > limit):
            raise ValueError("Valor inválido para " + field + ".")
        product[field] = value.strip() or None if value else None
    for field in ("categoria_id", "fornecedor_id"):
        value = product.get(field)
        if value in (None, ""):
            product[field] = None
        elif isinstance(value, bool) or not str(value).isdigit() or int(value) <= 0:
            raise ValueError("Referência inválida para " + field + ".")
        else:
            product[field] = int(value)
    product.setdefault("descricao", None)
    return product


def validate_expiry(value, product):
    if not value:
        if product.get("exige_validade", True):
            raise ValueError("Data de validade é obrigatória para este produto.")
        return None
    try:
        return date.fromisoformat(str(value)).isoformat()
    except (ValueError, TypeError):
        raise ValueError("Data de validade inválida; use AAAA-MM-DD.") from None


STOCK_PRODUCT_FIELDS = {
    "produto_nome": "nome", "produto_principio": "nome_generico",
    "produto_tipo": "tipo_produto", "produto_exige_validade": "exige_validade",
    "produto_requer_receita": "requer_receita", "produto_codigo_barras": "codigo_barras",
    "produto_categoria_id": "categoria_id", "produto_fornecedor_id": "fornecedor_id",
    "produto_preco_custo": "preco_custo", "produto_preco_venda": "preco_venda",
    "estoque_minimo": "estoque_minimo",
}


def stock_product_data(data):
    return {field: data[key] for key, field in STOCK_PRODUCT_FIELDS.items() if key in data}


PRODUCT_FIELDS = ("nome", "nome_generico", "descricao", "fabricante", "preco_custo",
                  "preco_venda", "codigo_barras", "categoria_id", "requer_receita",
                  "ativo", "estoque_minimo", "fornecedor_id", "tipo_produto", "exige_validade")


def save_product(cursor, product, product_id=None):
    # Todos os identificadores SQL vêm da lista fixa acima.
    for field, table in (("categoria_id", "categorias_produto"), ("fornecedor_id", "fornecedores")):
        if product.get(field):
            cursor.execute(f"SELECT id FROM {table} WHERE id = %s", (product[field],))
            if not cursor.fetchone():
                raise ValueError("Categoria ou fornecedor não encontrado.")
    values = [product.get(field) for field in PRODUCT_FIELDS]
    if product_id is None:
        cursor.execute(
            f"INSERT INTO produtos ({', '.join(PRODUCT_FIELDS)}) VALUES ({', '.join(['%s'] * len(values))})",
            values,
        )
        return cursor.lastrowid
    cursor.execute(
        f"UPDATE produtos SET {', '.join(field + ' = %s' for field in PRODUCT_FIELDS)} WHERE id = %s",
        values + [product_id],
    )
    return product_id


