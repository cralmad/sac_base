import logging

from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import render

from pages.agenda.constants import CATEGORIA_CHOICES, DIAS_SEMANA_AGENDA, MODO_EVENTO_CHOICES, RECORRENCIA_CHOICES
from pages.agenda.models import AgendaManual
from pages.agenda.services.agenda_manual import (
    campos_iniciais_agenda,
    confirmar_ocorrencia,
    materializar_ocorrencia,
    montar_linha_cons_agenda_manual,
    salvar_agenda_manual,
    serializar_agenda_manual,
)
from pages.agenda.services.agenda_materializacao_orquestrador import (
    listar_tipos_materializacao,
    obter_schema_materializacao,
)
from pages.agenda.views import PERMISSOES_AGENDA_MANUAL
from pages.filial.services import get_filiais_escrita_queryset
from sac_base.coercion import parse_date, parse_int
from sac_base.form_validador import SchemaValidator
from sac_base.http_json import json_method_not_allowed
from sac_base.permissions_utils import build_action_permissions, permission_denied_response
from sac_base.sisvar_builders import (
    build_error_payload,
    build_form_response,
    build_form_state,
    build_records_response,
    build_sisvar_payload,
    build_success_payload,
)

logger = logging.getLogger(__name__)

NOME_FORM = "cadAgendaManual"
NOME_FORM_CONS = "consAgendaManual"


def _schema_base():
    return {
        NOME_FORM: {
            "titulo": {"required": True, "type": "string", "maxlength": 200},
            "categoria": {"required": True, "type": "string"},
            "modo_evento": {"required": True, "type": "string"},
            "data_ancora": {"required": True, "type": "string"},
            "recorrencia": {"required": True, "type": "string"},
            "intervalo": {"required": True, "type": "integer"},
        },
        NOME_FORM_CONS: {
            "titulo_cons": {"type": "string", "maxlength": 200},
            "categoria_cons": {"type": "string"},
            "modo_evento_cons": {"type": "string"},
            "ativa_cons": {"type": "string"},
            "id_selecionado": {"type": "integer"},
        },
    }


@permission_required(PERMISSOES_AGENDA_MANUAL["acessar"], raise_exception=True)
def agenda_manual_view(request):
    usuario = getattr(request, "user", None)
    acoes = build_action_permissions(usuario, PERMISSOES_AGENDA_MANUAL)
    filial_ativa = getattr(request, "filial_ativa", None)
    filial_id = str(filial_ativa.id) if filial_ativa else ""

    if request.method == "GET":
        request.sisvar_extra = build_sisvar_payload(
            schema=_schema_base(),
            forms={
                NOME_FORM: build_form_state(
                    estado="novo" if acoes.get("incluir") else "visualizar",
                    campos=campos_iniciais_agenda(filial_id=filial_id),
                ),
                NOME_FORM_CONS: build_form_state(
                    campos={
                        "titulo_cons": "",
                        "categoria_cons": "",
                        "modo_evento_cons": "",
                        "ativa_cons": "",
                        "id_selecionado": None,
                    },
                ),
            },
            permissions={"agenda": acoes},
            datasets={
                "categorias": [{"value": v, "label": l} for v, l in CATEGORIA_CHOICES],
                "modos_evento": [{"value": v, "label": l} for v, l in MODO_EVENTO_CHOICES],
                "recorrencias": [{"value": v, "label": l} for v, l in RECORRENCIA_CHOICES],
                "tipos_materializacao": listar_tipos_materializacao(usuario),
                "dias_semana_agenda": [{"value": v, "label": l} for v, l in DIAS_SEMANA_AGENDA],
                "filial_ativa_id": filial_id,
            },
        )
        return render(request, "agenda_manual.html")

    if request.method != "POST":
        return json_method_not_allowed(["GET", "POST"])

    data = request.sisvar_front or {}
    form = data.get("form", {}).get(NOME_FORM, {})
    campos = form.get("campos", {})
    estado = form.get("estado", "")

    if estado == "novo" and not acoes.get("incluir"):
        return permission_denied_response("Sem permissão para incluir.")
    if estado == "editar" and not acoes.get("editar"):
        return permission_denied_response("Sem permissão para editar.")

    validator = SchemaValidator(_schema_base()[NOME_FORM])
    if not validator.validate(campos):
        erros = [f"{c} - {', '.join(e)}" for c, e in validator.get_errors().items()]
        return JsonResponse(build_error_payload(erros), status=400)

    try:
        registro = salvar_agenda_manual(usuario=usuario, campos=campos, estado=estado)
    except ValidationError as exc:
        msgs = exc.messages if hasattr(exc, "messages") else [str(exc)]
        return JsonResponse(build_error_payload(msgs), status=400)
    except Exception as exc:
        logger.error(exc, exc_info=True)
        return JsonResponse(build_error_payload("Falha ao salvar agenda."), status=500)

    return JsonResponse(
        build_form_response(
            form_id=NOME_FORM,
            estado="editar",
            campos=serializar_agenda_manual(registro),
            mensagem="Registro salvo com sucesso.",
        )
    )


@permission_required(PERMISSOES_AGENDA_MANUAL["consultar"], raise_exception=True)
def agenda_manual_cons_view(request):
    if request.method != "POST":
        return json_method_not_allowed(["POST"])

    usuario = getattr(request, "user", None)
    filiais_ids = list(get_filiais_escrita_queryset(usuario).values_list("id", flat=True))
    data = request.sisvar_front or {}
    cons = data.get("form", {}).get(NOME_FORM_CONS, {}).get("campos", {})
    id_sel = parse_int(cons.get("id_selecionado"), context="form")
    if id_sel:
        registro = AgendaManual.objects.filter(id=id_sel, filial_id__in=filiais_ids).first()
        if not registro:
            return JsonResponse(build_error_payload("Regra de agenda não encontrada."), status=404)
        return JsonResponse(
            build_form_response(
                form_id=NOME_FORM,
                estado="visualizar",
                campos=serializar_agenda_manual(registro),
            )
        )

    titulo = (cons.get("titulo_cons") or "").strip()
    qs = AgendaManual.objects.filter(filial_id__in=filiais_ids).order_by("titulo", "id")
    if titulo:
        qs = qs.filter(titulo__icontains=titulo)
    if cons.get("categoria_cons"):
        qs = qs.filter(categoria=cons.get("categoria_cons"))
    if cons.get("modo_evento_cons"):
        qs = qs.filter(modo_evento=cons.get("modo_evento_cons"))
    ativa_cons = (cons.get("ativa_cons") or "").strip().lower()
    if ativa_cons == "true":
        qs = qs.filter(ativa=True)
    elif ativa_cons == "false":
        qs = qs.filter(ativa=False)

    registros = [montar_linha_cons_agenda_manual(r) for r in qs[:200]]
    return JsonResponse(build_records_response(registros=registros))


@permission_required(PERMISSOES_AGENDA_MANUAL["confirmar"], raise_exception=True)
def agenda_manual_confirmar_view(request):
    if request.method != "POST":
        return json_method_not_allowed(["POST"])

    filial = getattr(request, "filial_ativa", None)
    if not filial:
        return JsonResponse(build_error_payload("Filial ativa não definida."), status=403)

    body = request.sisvar_front or {}
    agenda_id = parse_int(body.get("agenda_manual_id"), context="form")
    dt = parse_date(body.get("data_ocorrencia"))
    if not agenda_id or not dt:
        return JsonResponse(build_error_payload("Informe agenda e data da ocorrência."), status=400)

    try:
        confirmar_ocorrencia(
            agenda_manual_id=agenda_id,
            data_ocorrencia=dt,
            filial_id=filial.id,
            usuario=request.user,
        )
    except ValidationError as exc:
        msgs = exc.messages if hasattr(exc, "messages") else [str(exc)]
        return JsonResponse(build_error_payload(msgs), status=400)

    return JsonResponse(build_success_payload("Ocorrência confirmada."))


@permission_required(PERMISSOES_AGENDA_MANUAL["materializar"], raise_exception=True)
def agenda_manual_materializar_view(request):
    if request.method != "POST":
        return json_method_not_allowed(["POST"])

    filial = getattr(request, "filial_ativa", None)
    if not filial:
        return JsonResponse(build_error_payload("Filial ativa não definida."), status=403)

    body = request.sisvar_front or {}
    agenda_id = parse_int(body.get("agenda_manual_id"), context="form")
    dt = parse_date(body.get("data_ocorrencia"))
    if not agenda_id or not dt:
        return JsonResponse(build_error_payload("Informe agenda e data da ocorrência."), status=400)

    override = body.get("payload_override") if isinstance(body.get("payload_override"), dict) else None

    try:
        materializar_ocorrencia(
            agenda_manual_id=agenda_id,
            data_ocorrencia=dt,
            filial_id=filial.id,
            usuario=request.user,
            payload_override=override,
        )
    except ValidationError as exc:
        msgs = exc.messages if hasattr(exc, "messages") else [str(exc)]
        return JsonResponse(build_error_payload(msgs), status=400)
    except Exception as exc:
        logger.error(exc, exc_info=True)
        return JsonResponse(build_error_payload("Falha ao materializar."), status=500)

    return JsonResponse(build_success_payload("Lançamento materializado com sucesso."))


@permission_required(PERMISSOES_AGENDA_MANUAL["acessar"], raise_exception=True)
def agenda_manual_schema_materializacao_view(request):
    if request.method != "POST":
        return json_method_not_allowed(["POST"])

    filial = getattr(request, "filial_ativa", None)
    if not filial:
        return JsonResponse(build_error_payload("Filial ativa não definida."), status=403)

    body = request.sisvar_front or {}
    tipo = (body.get("tipo_materializacao") or "").strip()
    if not tipo:
        return JsonResponse(build_error_payload("Informe o tipo de materialização."), status=400)

    try:
        payload = obter_schema_materializacao(
            tipo_materializacao=tipo,
            filial_id=filial.id,
            usuario=request.user,
        )
    except ValidationError as exc:
        msgs = exc.messages if hasattr(exc, "messages") else [str(exc)]
        return JsonResponse(build_error_payload(msgs), status=400)

    return JsonResponse({"success": True, **payload})
