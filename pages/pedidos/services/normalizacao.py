from pages.pedidos.models import ESTADO_CHOICES, ESTADO_ENOVO_PARA_CANONICO


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


def normalizar_estado_enovo(valor_enovo):
    """Converte o texto ENOVO ("Último Estado") para a chave canónica.

    Só aceita labels declarados no 5.º campo de ESTADO_DEFINITIONS.
    Retorna None se vazio ou não mapeado — a importação ENOVO deve abortar
    (sem gravar UNKNOWN).
    """
    if valor_enovo is None:
        return None
    label = str(valor_enovo).strip()
    if not label:
        return None
    return ESTADO_ENOVO_PARA_CANONICO.get(label)
