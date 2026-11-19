"""Tokens e URLs curtas do link público de avaliação (SMS-friendly)."""

from __future__ import annotations

import secrets

from django.conf import settings
from django.db import IntegrityError

from pages.pedidos.models import AvaliacaoPedido

TOKEN_BYTES = 9
TOKEN_MAX_LEN_CURTO = 16
TOKEN_LEN_UPGRADE = 40
_MAX_TENTATIVAS_TOKEN = 8


def gerar_token_opaco() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def token_precisa_upgrade(token: str | None) -> bool:
    if not token:
        return True
    if "." in token:
        return True
    return len(token) > TOKEN_LEN_UPGRADE


def garantir_token_para_envio(avaliacao: AvaliacaoPedido) -> AvaliacaoPedido:
    """Garante token opaco curto antes de montar o link para o cliente.

    Substitui JWT/tokens longos para o próximo envio nunca reutilizar URL gigante.
    """
    if not token_precisa_upgrade(avaliacao.token_publico):
        return avaliacao

    ultimo_erro: Exception | None = None
    for _ in range(_MAX_TENTATIVAS_TOKEN):
        candidato = gerar_token_opaco()
        avaliacao.token_publico = candidato
        try:
            avaliacao.save(update_fields=["token_publico", "updated_at"])
            return avaliacao
        except IntegrityError as exc:
            ultimo_erro = exc
            continue
    raise RuntimeError("Não foi possível gerar token_publico único para avaliação.") from ultimo_erro


def resolver_avaliacao_por_token(token: str) -> AvaliacaoPedido:
    return AvaliacaoPedido.objects.select_related("pedido").get(token_publico=token)


def montar_link_publico(request, token: str) -> str:
    base = (settings.APP_BASE_URL or "").rstrip("/")
    path = f"/a/{token}/"
    if base:
        return f"{base}{path}"
    if request is not None:
        return request.build_absolute_uri(path)
    return path
