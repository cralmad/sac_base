"""Página de teste: embed iframe eNovoTMS + painel de debug."""

from __future__ import annotations

import json
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from pages.home.services.iframe_embed_probe import (
    HOSTS_PERMITIDOS,
    sondar_headers_url,
    validar_url_probe,
)
from sac_base.csp_middleware import build_csp
from sac_base.http_json import json_method_not_allowed
from sac_base.sisvar_builders import build_error_payload

URL_PADRAO = "https://3dboxportugal.enovotms.com/admin"
ORIGEM_PADRAO_FRAME = "https://3dboxportugal.enovotms.com"


def _acesso_teste_permitido(request) -> bool:
    """DEBUG local ou superutilizador (evitar expor em produção a utilizadores comuns)."""
    if settings.DEBUG:
        return True
    user = getattr(request, "user", None)
    return bool(user and user.is_authenticated and user.is_superuser)


@login_required
@require_http_methods(["GET"])
def iframe_embed_teste_view(request):
    if not _acesso_teste_permitido(request):
        return HttpResponseForbidden("Página de teste indisponível neste ambiente.")

    url_inicial = (request.GET.get("url") or URL_PADRAO).strip()
    url_ok, _erro = validar_url_probe(url_inicial)
    if not url_ok:
        url_inicial = URL_PADRAO

    parsed = urlparse(url_inicial)
    origem = f"{parsed.scheme}://{parsed.netloc}"

    context = {
        "url_inicial": url_inicial,
        "origem_frame": origem,
        "hosts_permitidos": sorted(HOSTS_PERMITIDOS),
        "url_probe": reverse("iframe_embed_probe"),
        "debug_modo": settings.DEBUG,
    }
    response = render(request, "iframe_embed_teste.html", context)
    # Sem isto, default-src 'self' bloqueia o iframe externo.
    response["Content-Security-Policy"] = build_csp(
        frame_src=f"'self' {origem} {ORIGEM_PADRAO_FRAME}"
    )
    return response


@login_required
def iframe_embed_probe_view(request):
    if not _acesso_teste_permitido(request):
        return JsonResponse(
            build_error_payload("Página de teste indisponível neste ambiente."),
            status=403,
        )
    if request.method != "POST":
        return json_method_not_allowed()

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return JsonResponse(build_error_payload("JSON inválido."), status=400)

    url = body.get("url") if isinstance(body, dict) else None
    if not isinstance(url, str):
        return JsonResponse(build_error_payload("Campo url inválido."), status=400)

    resultado = sondar_headers_url(url)
    if not resultado.get("ok"):
        return JsonResponse(
            {
                "success": False,
                "mensagem": resultado.get("erro") or "Falha no probe.",
                "resultado": resultado,
            },
            status=400,
        )

    return JsonResponse(
        {
            "success": True,
            "mensagem": "Probe concluído.",
            "resultado": resultado,
        }
    )
