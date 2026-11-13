"""Filtros e helpers do Relatório Gerencial de Pedidos."""

from __future__ import annotations

from sac_base.coercion import parse_decimal

PESO_OPS_COMPARACAO = frozenset({"gt", "lt", "eq"})
PESO_OP_SEM_PESO = "null"


def aplicar_filtro_peso(qs, peso_op, peso_valor_raw):
    """
    Aplica filtro de peso ao queryset de Pedido.

    Retorna (qs, mensagem_erro). mensagem_erro é None se OK.
    """
    op = str(peso_op or "").strip().lower()
    if not op:
        return qs, None

    if op == PESO_OP_SEM_PESO:
        return qs.filter(peso__isnull=True), None

    if op not in PESO_OPS_COMPARACAO:
        return qs, "Operador de peso inválido."

    raw = peso_valor_raw
    if isinstance(raw, str):
        raw = raw.strip()
    peso_valor = parse_decimal(raw, context="form")
    if peso_valor is None:
        return qs, "Informe um valor de peso válido para o filtro."

    if op == "gt":
        return qs.filter(peso__gt=peso_valor), None
    if op == "lt":
        return qs.filter(peso__lt=peso_valor), None
    return qs.filter(peso=peso_valor), None
