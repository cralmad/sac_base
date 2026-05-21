import logging

from django.contrib.auth.decorators import permission_required
from django.http import JsonResponse
from django.shortcuts import render

from pages.agenda.services.relatorio_previsibilidade import (
    montar_sisvar_relatorio_previsibilidade_get,
    parse_filtros_relatorio,
    validar_e_montar_relatorio,
)
from pages.agenda.views import PERMISSOES_AGENDA_MANUAL, PERMISSOES_RELATORIO
from pages.filial.services import get_filiais_escrita_queryset
from sac_base.http_json import json_method_not_allowed
from sac_base.permissions_utils import build_action_permissions
from sac_base.sisvar_builders import build_error_payload

logger = logging.getLogger(__name__)


def _prefixo_app(request) -> str:
    script = (request.META.get("SCRIPT_NAME") or "").rstrip("/")
    return f"{script}/app" if script else "/app"


@permission_required(PERMISSOES_RELATORIO["acessar"], raise_exception=True)
def relatorio_previsibilidade_view(request):
    usuario = getattr(request, "user", None)
    acoes_rel = build_action_permissions(usuario, PERMISSOES_RELATORIO)
    acoes_agenda = build_action_permissions(usuario, PERMISSOES_AGENDA_MANUAL)
    if request.method == "GET":
        request.sisvar_extra = montar_sisvar_relatorio_previsibilidade_get(
            usuario=usuario,
            request=request,
            acoes_agenda={**acoes_agenda, **acoes_rel},
        )
        return render(request, "agenda_relatorio_previsibilidade.html")

    if request.method != "POST":
        return json_method_not_allowed(["GET", "POST"])

    filial = getattr(request, "filial_ativa", None)
    if not filial:
        return JsonResponse(build_error_payload("Filial ativa não definida."), status=403)

    filiais_ids = set(get_filiais_escrita_queryset(usuario).values_list("id", flat=True))
    if filial.id not in filiais_ids:
        return JsonResponse(build_error_payload("Sem permissão para a filial ativa."), status=403)

    data = request.sisvar_front or {}
    filtros = data.get("filtros") if isinstance(data.get("filtros"), dict) else {}
    dt_ini, dt_fim, err = parse_filtros_relatorio(filtros)
    if err:
        return JsonResponse(build_error_payload(err), status=400)

    try:
        payload, erro = validar_e_montar_relatorio(
            data_inicio=dt_ini,
            data_fim=dt_fim,
            filial_id=filial.id,
            usuario=usuario,
            prefixo_app=_prefixo_app(request),
            pode_confirmar=acoes_agenda.get("confirmar", False),
            pode_materializar=acoes_agenda.get("materializar", False),
        )
    except Exception as exc:
        logger.error(exc, exc_info=True)
        return JsonResponse({"success": False, "mensagem": "Falha ao gerar relatório."}, status=500)

    if erro:
        return JsonResponse(build_error_payload(erro), status=400)
    return JsonResponse(payload)
