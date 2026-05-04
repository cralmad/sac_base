"""
De-para estático: ContentType da origem de negócio -> regras de lançamento.

O domínio (service de pedidos, etc.) faz merge com overrides na chamada ao FinanceiroService.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.contrib.contenttypes.models import ContentType


@dataclass(frozen=True)
class RegraLancamentoOrigem:
    """Uma linha de mapeamento origem -> título financeiro."""

    tipo: str  # RegistroFinanceiroTipo value
    plano_contas_codigo: str
    campo_fk_modelo_origem: str | None
    valor_attr: str


def _ct(app_label: str, model: str) -> ContentType:
    return ContentType.objects.get(app_label=app_label, model=model.lower())


def obter_regras_default(content_type_id: int) -> list[RegraLancamentoOrigem]:
    regras = REGISTRY_POR_CONTENT_TYPE_ID.get(content_type_id)
    if not regras:
        return []
    return list(regras)


REGISTRY_POR_CONTENT_TYPE_ID: dict[int, tuple[RegraLancamentoOrigem, ...]] = {}


def registrar_content_type_natural_key(
    app_label: str,
    model: str,
    regras: tuple[RegraLancamentoOrigem, ...],
) -> None:
    ct = _ct(app_label, model)
    REGISTRY_POR_CONTENT_TYPE_ID[ct.id] = regras


def popular_registry_padrao() -> None:
    """Idempotente: hooks de integração podem registrar Pedido etc. após migrations."""
    try:
        ct_pedido = _ct("pedidos", "pedido")
    except ContentType.DoesNotExist:
        return
    if ct_pedido.id not in REGISTRY_POR_CONTENT_TYPE_ID:
        REGISTRY_POR_CONTENT_TYPE_ID[ct_pedido.id] = ()


def merge_regras(
    content_type_id: int,
    overrides: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Default do registry ou lista `overrides` quando o cérebro envia regras completas."""
    defaults = [r.__dict__.copy() for r in obter_regras_default(content_type_id)]
    if overrides:
        return overrides
    return defaults
