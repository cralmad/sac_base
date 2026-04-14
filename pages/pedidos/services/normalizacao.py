from pages.pedidos.models import ESTADO_CHOICES


ESTADO_CHOICES_VALUES = {valor for valor, _label in ESTADO_CHOICES}

# Aliases para valores CSV que diferem da chave no modelo
# Inclui: normalização de acento e variantes conhecidas
ESTADO_ALIASES = {
    "danos_visíveis_embalagem": "danos_visiveis_embalagem",
    "danos_visiveis_embalagem": "danos_visiveis_embalagem",
}


def normalizar_estado(valor_csv):
    """Converte um valor CSV de estado para a chave canônica do modelo.

    O valor 'cancelled' é tratado como estado próprio (Cancelado), distinto
    de 'A' (Pedido Cancelado). Valores não reconhecidos retornam 'UNKNOWN'.
    """
    if not valor_csv:
        return "UNKNOWN"
    valor = valor_csv.strip()
    valor = ESTADO_ALIASES.get(valor, valor)
    if valor in ESTADO_CHOICES_VALUES:
        return valor
    return "UNKNOWN"
