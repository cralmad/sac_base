import logging

from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import render

from pages.filial.services import get_filiais_escrita_queryset
from pages.filial.models import Filial
from pages.financeiro.models import RegistroFinanceiro, RegistroFinanceiroTipo
from pages.financeiro.services.registro_manual import (
    cancelar_registro_manual,
    campos_iniciais_registro,
    listar_contrapartes,
    listar_filiais_escrita,
    listar_planos_nivel4,
    salvar_registro_manual,
    serializar_registro,
)
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

PERMISSOES_REGISTRO_FINANCEIRO = {
    "acessar": "financeiro.view_registrofinanceiro",
    "consultar": "financeiro.view_registrofinanceiro",
    "incluir": "financeiro.add_registrofinanceiro",
    "editar": "financeiro.change_registrofinanceiro",
    "excluir": "financeiro.delete_registrofinanceiro",
}


@permission_required(PERMISSOES_REGISTRO_FINANCEIRO["acessar"], raise_exception=True)
def registro_manual_view(request):
    nome_form = "cadRegistroFinanceiro"
    nome_form_cons = "consRegistroFinanceiro"
    usuario = getattr(request, "user", None)
    acoes = build_action_permissions(usuario, PERMISSOES_REGISTRO_FINANCEIRO)
    schema = {
        nome_form: {
            "id": {"type": "integer", "required": False, "value": None},
            "filial_id": {"type": "string", "required": True, "value": ""},
            "tipo": {"type": "string", "required": True, "value": RegistroFinanceiroTipo.ENTRADA},
            "contraparte_tipo": {"type": "string", "required": False, "value": ""},
            "contraparte_id": {"type": "string", "required": False, "value": ""},
            "plano_contas_id": {"type": "string", "required": True, "value": ""},
            "valor": {"type": "string", "required": True, "value": ""},
            "observacao": {"type": "string", "maxlength": 1000, "required": False, "value": ""},
            "status": {"type": "string", "required": False, "value": "aberto"},
        },
        nome_form_cons: {
            "filial_cons": {"type": "string", "required": False, "value": ""},
            "tipo_cons": {"type": "string", "required": False, "value": ""},
            "plano_cons": {"type": "string", "required": False, "value": ""},
            "status_cons": {"type": "string", "required": False, "value": ""},
            "id_selecionado": {"type": "integer", "required": False, "value": None},
        },
    }
    if request.method == "GET":
        filiais_escrita = listar_filiais_escrita(usuario)
        filial_ativa = getattr(request, "filial_ativa", None)
        filial_ativa_id = str(filial_ativa.id) if filial_ativa else ""
        total_filiais_cadastradas = Filial.objects.filter(ativa=True).count()
        bloquear_filial_select = len(filiais_escrita) <= 1 or total_filiais_cadastradas <= 1
        campos_form = campos_iniciais_registro()
        campos_form["filial_id"] = filial_ativa_id
        contraparte = listar_contrapartes()
        request.sisvar_extra = build_sisvar_payload(
            schema=schema,
            forms={
                nome_form: build_form_state(
                    estado="novo" if acoes["incluir"] else "visualizar",
                    campos=campos_form,
                ),
                nome_form_cons: build_form_state(
                    campos={
                        "filial_cons": filial_ativa_id,
                        "tipo_cons": "",
                        "plano_cons": "",
                        "status_cons": "",
                        "id_selecionado": None,
                    }
                ),
            },
            permissions={"financeiro": acoes},
            datasets={
                "filiais_escrita": filiais_escrita,
                "planos_nivel4": listar_planos_nivel4(),
                "tipos_registro_financeiro": [
                    {"value": val, "label": label}
                    for val, label in RegistroFinanceiroTipo.choices
                    if val != RegistroFinanceiroTipo.TRANSFERENCIA
                ],
                "contraparte_tipos": contraparte["tipos"],
                "contrapartes_por_tipo": contraparte["por_tipo"],
                "filial_ativa_id": filial_ativa_id,
                "bloquear_filial_select": bloquear_filial_select,
            },
        )
        return render(request, "financeiro_registro_manual.html")

    data_front = request.sisvar_front
    form = data_front.get("form", {}).get(nome_form, {})
    campos = form.get("campos", {})
    estado = form.get("estado", "")
    if estado == "novo" and not acoes["incluir"]:
        return permission_denied_response("Você não possui permissão para incluir registro financeiro.")
    if estado == "editar" and not acoes["editar"]:
        return permission_denied_response("Você não possui permissão para editar registro financeiro.")
    validator = SchemaValidator(schema[nome_form])
    if not validator.validate(campos):
        erros = [f"{campo} - {', '.join(msgs)}" for campo, msgs in validator.get_errors().items()]
        return JsonResponse(build_error_payload(erros), status=400)
    filiais_ids = list(get_filiais_escrita_queryset(usuario).values_list("id", flat=True))
    try:
        registro = salvar_registro_manual(
            usuario=usuario,
            campos=campos,
            estado=estado,
            filiais_escrita_ids=filiais_ids,
        )
    except ValidationError as exc:
        mensagens = exc.messages if hasattr(exc, "messages") else [str(exc)]
        return JsonResponse(build_error_payload(mensagens), status=422)
    except Exception as exc:
        logger.error(exc, exc_info=True)
        return JsonResponse(build_error_payload("Falha ao salvar registro financeiro."), status=500)
    return JsonResponse(
        build_form_response(
            form_id=nome_form,
            estado="visualizar",
            update=None,
            campos=serializar_registro(registro),
            mensagem_sucesso="Registro financeiro salvo com sucesso!",
        )
    )


@permission_required(PERMISSOES_REGISTRO_FINANCEIRO["consultar"], raise_exception=True)
def registro_manual_cons_view(request):
    if request.method != "POST":
        return json_method_not_allowed(["POST"])
    nome_form = "cadRegistroFinanceiro"
    nome_form_cons = "consRegistroFinanceiro"
    usuario = getattr(request, "user", None)
    filiais_ids = list(get_filiais_escrita_queryset(usuario).values_list("id", flat=True))
    campos = request.sisvar_front.get("form", {}).get(nome_form_cons, {}).get("campos", {})
    id_sel = campos.get("id_selecionado")
    if id_sel:
        registro = RegistroFinanceiro.objects.filter(id=id_sel, filial_id__in=filiais_ids).first()
        if not registro:
            return JsonResponse(build_error_payload("Registro financeiro não encontrado."), status=404)
        return JsonResponse(
            build_form_response(
                form_id=nome_form,
                estado="visualizar",
                update=None,
                campos=serializar_registro(registro),
            )
        )
    queryset = RegistroFinanceiro.objects.filter(filial_id__in=filiais_ids).select_related("filial", "plano_contas")
    if campos.get("filial_cons"):
        queryset = queryset.filter(filial_id=campos.get("filial_cons"))
    if campos.get("tipo_cons"):
        queryset = queryset.filter(tipo=campos.get("tipo_cons"))
    if campos.get("plano_cons"):
        queryset = queryset.filter(plano_contas_id=campos.get("plano_cons"))
    if campos.get("status_cons"):
        queryset = queryset.filter(status=campos.get("status_cons"))
    registros = [
        {
            "id": r.id,
            "filial": f"{r.filial.codigo} - {r.filial.nome}",
            "tipo": r.tipo,
            "plano": f"{r.plano_contas.codigo} - {r.plano_contas.nome}",
            "valor": str(r.valor),
            "valor_rest": str(r.valor_rest),
            "status": r.status,
        }
        for r in queryset.order_by("-id")[:300]
    ]
    return JsonResponse(build_records_response(registros))


@permission_required(PERMISSOES_REGISTRO_FINANCEIRO["excluir"], raise_exception=True)
def registro_manual_cancelar_view(request):
    if request.method != "POST":
        return json_method_not_allowed(["POST"])
    usuario = getattr(request, "user", None)
    filiais_ids = list(get_filiais_escrita_queryset(usuario).values_list("id", flat=True))
    registro_id = (
        request.sisvar_front.get("form", {})
        .get("cadRegistroFinanceiro", {})
        .get("campos", {})
        .get("id")
    )
    try:
        cancelar_registro_manual(usuario=usuario, registro_id=registro_id, filiais_escrita_ids=filiais_ids)
    except ValidationError as exc:
        mensagens = exc.messages if hasattr(exc, "messages") else [str(exc)]
        return JsonResponse(build_error_payload(mensagens), status=422)
    except Exception as exc:
        logger.error(exc, exc_info=True)
        return JsonResponse(build_error_payload("Falha ao cancelar registro financeiro."), status=500)
    return JsonResponse(build_success_payload("Registro financeiro cancelado com sucesso!"))
