from django.contrib.auth.decorators import permission_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from django.core.exceptions import ValidationError

from pages.filial.models import UsuarioFilial
from pages.filial.services import get_filiais_escrita_queryset
from pages.logistica_config.models import ConfiguracaoLogistica
from pages.logistica_config.services.config_logistica import (
    build_campos_iniciais,
    listar_registros_consulta,
    obter_config_por_id,
    persistir_configuracao,
    serializar_config,
)
from pages.zona_entrega.views import listar_filiais_logisticas
from sac_base.coercion import parse_int
from sac_base.form_validador import SchemaValidator
from sac_base.permissions_utils import build_action_permissions, extract_validation_messages, permission_denied_response
from sac_base.sisvar_builders import (
    build_error_payload,
    build_form_response,
    build_form_state,
    build_records_response,
    build_sisvar_payload,
    build_success_payload,
)

PERMISSOES_CONFIG_LOGISTICA = {
    "acessar": "logistica_config.view_configuracaologistica",
    "consultar": "logistica_config.view_configuracaologistica",
    "incluir": "logistica_config.add_configuracaologistica",
    "editar": "logistica_config.change_configuracaologistica",
    "excluir": "logistica_config.delete_configuracaologistica",
}


@permission_required(PERMISSOES_CONFIG_LOGISTICA["acessar"], raise_exception=True)
@csrf_protect
@require_http_methods(["GET", "POST"])
def cadastro_config_logistica_view(request):
    template = "configuracao_logistica_cadastro.html"
    nome_form = "cadConfigLogistica"
    nome_form_cons = "consConfigLogistica"
    usuario = getattr(request, "user", None)
    acoes = build_action_permissions(usuario, PERMISSOES_CONFIG_LOGISTICA)

    schema = {
        nome_form: {
            "id": {"type": "integer", "required": False, "value": None},
            "filial_id": {"type": "string", "required": True, "value": ""},
            "pedidos_pesado": {"type": "integer", "required": True, "value": "0"},
            "pesado_reservado": {"type": "integer", "required": True, "value": "0"},
            "valor_unitario_pesado": {"type": "string", "required": True, "value": "0.00"},
            "pedidos_ligeiro": {"type": "integer", "required": True, "value": "0"},
            "ligeiro_reservado": {"type": "integer", "required": True, "value": "0"},
            "valor_unitario_ligeiro": {"type": "string", "required": True, "value": "0.00"},
            "valor_excedente": {"type": "string", "required": True, "value": "0.00"},
        },
        nome_form_cons: {
            "filial_cons": {"type": "string", "required": False, "value": ""},
            "id_selecionado": {"type": "integer", "required": False, "value": None},
        },
    }

    if request.method == "GET":
        request.sisvar_extra = build_sisvar_payload(
            schema=schema,
            forms={
                nome_form: build_form_state(
                    estado="novo" if acoes["incluir"] else "visualizar",
                    campos=build_campos_iniciais(),
                ),
                nome_form_cons: build_form_state(
                    campos={
                        "filial_cons": "",
                        "id_selecionado": None,
                    },
                ),
            },
            permissions={"logistica_config": acoes},
            datasets={"filiais_atuacao": listar_filiais_logisticas(usuario)},
        )
        return render(request, template)

    data_front = request.sisvar_front
    form = data_front.get("form", {}).get(nome_form, {})
    campos = form.get("campos", {})
    estado = form.get("estado", "")

    if estado == "novo" and not acoes["incluir"]:
        return permission_denied_response("Você não possui permissão para incluir configuração de logística.")
    if estado == "editar" and not acoes["editar"]:
        return permission_denied_response("Você não possui permissão para editar configuração de logística.")

    validator = SchemaValidator(schema[nome_form])
    if not validator.validate(campos):
        erros = [f"{k} - {', '.join(v)}" for k, v in validator.get_errors().items()]
        return JsonResponse(build_error_payload(erros), status=400)

    excecoes = campos.get("excecoes", [])
    if not isinstance(excecoes, list):
        return JsonResponse(build_error_payload("Lista de datas de exceção inválida."), status=400)

    excecoes_periodo = campos.get("excecoes_periodo", [])
    if not isinstance(excecoes_periodo, list):
        return JsonResponse(build_error_payload("Lista de períodos de exceção inválida."), status=400)

    try:
        config = persistir_configuracao(
            usuario,
            estado,
            {**campos, "excecoes": excecoes, "excecoes_periodo": excecoes_periodo},
        )
    except ValidationError as exc:
        return JsonResponse(build_error_payload(extract_validation_messages(exc)), status=422)

    return JsonResponse(
        build_form_response(
            form_id=nome_form,
            estado="visualizar",
            update=None,
            campos=serializar_config(config),
            mensagem_sucesso="Configuração de logística salva com sucesso!",
        )
    )


@permission_required(PERMISSOES_CONFIG_LOGISTICA["consultar"], raise_exception=True)
@require_http_methods(["POST"])
@csrf_protect
def cadastro_config_logistica_cons_view(request):
    nome_form = "cadConfigLogistica"
    nome_form_cons = "consConfigLogistica"

    data_front = request.sisvar_front
    form = data_front.get("form", {}).get(nome_form_cons, {})
    campos = form.get("campos", {})
    id_selecionado = campos.get("id_selecionado")
    usuario = getattr(request, "user", None)

    if id_selecionado:
        sid = parse_int(id_selecionado)
        if not sid:
            return JsonResponse(build_error_payload("Identificador inválido."), status=400)
        cfg = obter_config_por_id(usuario, sid)
        if not cfg:
            return JsonResponse(build_error_payload("Registro não encontrado."), status=404)
        return JsonResponse(
            build_form_response(
                form_id=nome_form,
                estado="visualizar",
                update=None,
                campos=serializar_config(cfg),
            )
        )

    filial_cons = campos.get("filial_cons")
    registros = listar_registros_consulta(usuario, filial_cons)
    return JsonResponse(build_records_response(registros))


@permission_required(PERMISSOES_CONFIG_LOGISTICA["acessar"], raise_exception=True)
@require_http_methods(["POST"])
@csrf_protect
def cadastro_config_logistica_del_view(request):
    nome_form = "cadConfigLogistica"
    usuario = getattr(request, "user", None)

    if not usuario or not usuario.has_perm(PERMISSOES_CONFIG_LOGISTICA["excluir"]):
        return permission_denied_response("Você não possui permissão para excluir configuração de logística.")

    raw_id = request.sisvar_front.get("form", {}).get(nome_form, {}).get("campos", {}).get("id")
    cfg_id = parse_int(raw_id)
    if not cfg_id:
        return JsonResponse(build_error_payload("Identificador inválido."), status=400)

    config = ConfiguracaoLogistica.objects.filter(id=cfg_id).select_related("filial").first()
    if not config:
        return JsonResponse(build_error_payload("Registro não encontrado."), status=404)

    if not usuario.is_superuser:
        possui = UsuarioFilial.objects.filter(
            usuario=usuario,
            filial=config.filial,
            ativo=True,
            pode_escrever=True,
        ).exists()
        if not possui:
            return JsonResponse(
                build_error_payload("Você não possui vínculo de escrita para esta matriz/filial."),
                status=403,
            )

    with transaction.atomic():
        config.delete()

    return JsonResponse(build_success_payload("Configuração de logística excluída com sucesso!"))
