"""Relatório logística por motorista × data e modal financeiro mod_finan."""

import logging

from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods, require_POST

from pages.filial.services import get_filiais_escrita_queryset
from pages.pedidos.services.relatorio_logistica_motorista import (
    executar_salvar_mod_finan,
    montar_relatorio_logistica_motorista,
    montar_sisvar_relatorio_logistica_motorista_get,
)
from pages.pedidos.services.relatorio_logistica_motorista_gsheets import (
    executar_envio_gsheets_logistica_motorista,
)
from sac_base.coercion import parse_date, parse_int
from sac_base.form_validador import SchemaValidator
from sac_base.permissions_utils import build_action_permissions, permission_denied_response
logger = logging.getLogger(__name__)

PERMISSOES_REL_LOG_MOTORISTA = {
    "acessar": "pedidos.view_tentativaentrega",
}

PERMISSOES_MOD_FINAN = {
    **PERMISSOES_REL_LOG_MOTORISTA,
    "lancar": "financeiro.add_registrofinanceiro",
}


@login_required
@permission_required(PERMISSOES_REL_LOG_MOTORISTA["acessar"], raise_exception=True)
@csrf_protect
@require_http_methods(["GET", "POST"])
def relatorio_logistica_motorista_view(request):
    if request.method == "GET":
        request.sisvar_extra = montar_sisvar_relatorio_logistica_motorista_get(
            request=request,
            acoes_relatorio=build_action_permissions(request.user, PERMISSOES_REL_LOG_MOTORISTA),
            acoes_mod_finan=build_action_permissions(request.user, PERMISSOES_MOD_FINAN),
        )
        return render(request, "relatorio_logistica_motorista.html")

    filial_ativa = getattr(request, "filial_ativa", None)
    if not filial_ativa:
        return JsonResponse({"success": False, "mensagem": "Selecione uma filial ativa."}, status=403)

    data = request.sisvar_front or {}
    filtros = data.get("filtros", {})
    data_inicio = parse_date(filtros.get("data_inicio"))
    data_fim = parse_date(filtros.get("data_fim"))
    raw_mot = filtros.get("motoristas", [])
    motorista_ids = []
    if isinstance(raw_mot, list):
        motorista_ids = [int(x) for x in raw_mot if str(x).isdigit()]

    if not data_inicio or not data_fim:
        return JsonResponse({"success": False, "mensagem": "Informe data inicial e data final."}, status=400)

    try:
        payload = montar_relatorio_logistica_motorista(
            filial_ativa=filial_ativa,
            data_inicio=data_inicio,
            data_fim=data_fim,
            motorista_ids=motorista_ids or None,
        )
    except ValidationError as exc:
        msgs = list(exc.messages) if hasattr(exc, "messages") else [str(exc)]
        return JsonResponse({"success": False, "mensagem": msgs[0] if msgs else "Validação falhou."}, status=400)

    return JsonResponse({"success": True, **payload})


@login_required
@permission_required(PERMISSOES_REL_LOG_MOTORISTA["acessar"], raise_exception=True)
@csrf_protect
@require_POST
def relatorio_logistica_motorista_mod_finan_view(request):
    if not request.user.has_perm(PERMISSOES_MOD_FINAN["lancar"]):
        return permission_denied_response("Você não possui permissão para lançar registro financeiro.")

    filial_ativa = getattr(request, "filial_ativa", None)
    if not filial_ativa:
        return JsonResponse({"success": False, "mensagem": "Selecione uma filial ativa."}, status=403)

    schema = {
        "motorista_id": {"type": "integer", "required": True, "value": None},
        "data_tentativa": {"type": "string", "required": True, "value": ""},
        "valor": {"type": "string", "required": True, "value": ""},
        "observacao": {"type": "string", "maxlength": 1000, "required": False, "value": ""},
    }
    raw = request.sisvar_front or {}
    campos = raw.get("mod_finan") if isinstance(raw.get("mod_finan"), dict) else raw
    validator = SchemaValidator(schema)
    if not validator.validate(campos):
        erros = [f"{k} - {', '.join(v)}" for k, v in validator.get_errors().items()]
        return JsonResponse({"success": False, "mensagem": erros[0] if erros else "Dados inválidos."}, status=400)

    mid = parse_int(campos.get("motorista_id"), context="form")
    if not mid:
        return JsonResponse({"success": False, "mensagem": "Motorista é obrigatório para o lançamento."}, status=400)

    data_tt = parse_date(campos.get("data_tentativa"))
    if not data_tt:
        return JsonResponse({"success": False, "mensagem": "Data da tentativa inválida."}, status=400)

    filiais_ids = list(get_filiais_escrita_queryset(request.user).values_list("id", flat=True))
    try:
        executar_salvar_mod_finan(
            usuario=request.user,
            filial_ativa=filial_ativa,
            motorista_id=mid,
            data_tentativa=data_tt,
            valor=str(campos.get("valor") or "").strip(),
            observacao=str(campos.get("observacao") or ""),
            filiais_escrita_ids=filiais_ids,
        )
    except ValidationError as exc:
        msgs = list(exc.messages) if hasattr(exc, "messages") else [str(exc)]
        return JsonResponse({"success": False, "mensagem": msgs[0] if msgs else "Validação falhou."}, status=422)
    except Exception as exc:
        logger.error(exc, exc_info=True)
        return JsonResponse({"success": False, "mensagem": "Falha ao salvar registro financeiro."}, status=500)

    return JsonResponse({"success": True, "mensagem": "Registro financeiro salvo com sucesso!"})


@login_required
@permission_required(PERMISSOES_REL_LOG_MOTORISTA["acessar"], raise_exception=True)
@csrf_protect
@require_POST
def relatorio_logistica_motorista_gsheets_view(request):
    filial_ativa = getattr(request, "filial_ativa", None)
    if not filial_ativa:
        return JsonResponse({"success": False, "mensagem": "Selecione uma filial ativa."}, status=403)

    data = request.sisvar_front or {}
    filtros = data.get("filtros", {})
    data_inicio = parse_date(filtros.get("data_inicio"))
    data_fim = parse_date(filtros.get("data_fim"))
    raw_mot = filtros.get("motoristas", [])
    motorista_ids = []
    if isinstance(raw_mot, list):
        motorista_ids = [int(x) for x in raw_mot if str(x).isdigit()]

    if not data_inicio or not data_fim:
        return JsonResponse(
            {"success": False, "mensagem": "Informe data inicial e data final."},
            status=400,
        )

    try:
        resultado = executar_envio_gsheets_logistica_motorista(
            filial_ativa,
            data_inicio=data_inicio,
            data_fim=data_fim,
            motorista_ids=motorista_ids or None,
        )
    except ValidationError as exc:
        msgs = list(exc.messages) if hasattr(exc, "messages") else [str(exc)]
        return JsonResponse(
            {"success": False, "mensagem": msgs[0] if msgs else "Validação falhou."},
            status=400,
        )
    except Exception as exc:
        logger.error(exc, exc_info=True)
        return JsonResponse(
            {"success": False, "mensagem": "Falha ao enviar dados ao Google Sheets."},
            status=500,
        )

    return JsonResponse({"success": True, **resultado})
