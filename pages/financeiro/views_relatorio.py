import logging

from django.contrib.auth.decorators import permission_required
from django.http import JsonResponse
from django.shortcuts import render

from pages.filial.services import get_filiais_escrita_queryset
from pages.financeiro.services.relatorio_registros import (
    executar_relatorio_registros,
    montar_sisvar_relatorio_registros_get,
)
from pages.financeiro.views import PERMISSOES_REGISTRO_FINANCEIRO
from sac_base.http_json import json_method_not_allowed
from sac_base.permissions_utils import build_action_permissions

logger = logging.getLogger(__name__)


def _prefixo_app_para_links(request) -> str:
    script = (request.META.get("SCRIPT_NAME") or "").rstrip("/")
    return f"{script}/app" if script else "/app"


@permission_required(PERMISSOES_REGISTRO_FINANCEIRO["acessar"], raise_exception=True)
def relatorio_registros_financeiros_view(request):
    usuario = getattr(request, "user", None)
    acoes = build_action_permissions(usuario, PERMISSOES_REGISTRO_FINANCEIRO)
    if request.method == "GET":
        request.sisvar_extra = montar_sisvar_relatorio_registros_get(
            usuario=usuario, request=request, acoes_financeiro=acoes
        )
        return render(request, "financeiro_relatorio_registros.html")

    if request.method != "POST":
        return json_method_not_allowed(["GET", "POST"])

    data = request.sisvar_front or {}
    filtros = data.get("filtros") if isinstance(data.get("filtros"), dict) else {}
    agrupamento = data.get("agrupamento") if isinstance(data.get("agrupamento"), dict) else {}
    filiais_ids = list(get_filiais_escrita_queryset(usuario).values_list("id", flat=True))
    try:
        payload = executar_relatorio_registros(
            filiais_escrita_ids=filiais_ids,
            filtros=filtros,
            agrupamento=agrupamento,
            prefixo_app_manual=_prefixo_app_para_links(request),
        )
    except Exception as exc:
        logger.error(exc, exc_info=True)
        return JsonResponse({"success": False, "mensagem": "Falha ao gerar relatório."}, status=500)
    if not payload.get("success"):
        return JsonResponse(payload, status=400)
    return JsonResponse(payload)
