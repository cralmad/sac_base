from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from sac_base.http_json import json_method_not_allowed
from sac_base.sisvar_builders import build_error_payload, build_sisvar_payload, build_success_payload

from pages.pedidos.services.conferencia_enovo import aplicar_leituras_lote, preview_leitura_etiqueta

PERM_CONFERIR = "pedidos.conferir_etiqueta_enovo"


@login_required
@permission_required(PERM_CONFERIR, raise_exception=True)
@require_http_methods(["GET"])
def conferencia_enovo_view(request):
    request.sisvar_extra = build_sisvar_payload()
    return render(request, "conferencia_enovo.html")


@login_required
@permission_required(PERM_CONFERIR, raise_exception=True)
def conferencia_enovo_preview_view(request):
    if request.method != "POST":
        return json_method_not_allowed()
    filial = getattr(request, "filial_ativa", None)
    if not filial:
        return JsonResponse(build_error_payload("Filial ativa não encontrada."), status=422)
    body = request.sisvar_front or {}
    resultado, erro = preview_leitura_etiqueta(filial, body.get("codigo"))
    if erro:
        return JsonResponse(build_error_payload(erro), status=400)
    return JsonResponse(build_success_payload(extra_payload={"leitura": resultado}))


@login_required
@permission_required(PERM_CONFERIR, raise_exception=True)
def conferencia_enovo_salvar_view(request):
    if request.method != "POST":
        return json_method_not_allowed()
    filial = getattr(request, "filial_ativa", None)
    if not filial:
        return JsonResponse(build_error_payload("Filial ativa não encontrada."), status=422)
    body = request.sisvar_front or {}
    lote = aplicar_leituras_lote(filial, body.get("leituras"))
    if lote["todos_ok"]:
        n = len(lote["gravados"])
        return JsonResponse(build_success_payload(
            f"{n} conferência(s) gravada(s) com sucesso.",
            extra_payload=lote,
        ))
    if lote["gravados"]:
        msg = (
            f"Gravação parcial: {len(lote['gravados'])} ok, "
            f"{len(lote['erros'])} com erro. Nenhuma linha com erro foi confirmada."
        )
    else:
        primeiro = (lote["erros"][0]["mensagem"] if lote["erros"] else "Falha ao gravar.")
        msg = primeiro
    return JsonResponse(build_error_payload(msg) | lote, status=422)
