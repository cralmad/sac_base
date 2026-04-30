import base64
import binascii
import os

import requests
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from pages.cad_cliente.models import Cliente
from pages.filial.models import Filial
from pages.filial.services import get_filiais_escrita_queryset, obter_filial_escrita
from pages.motorista.models import Motorista
from sac_base.coercion import parse_date, parse_decimal, parse_int
from sac_base.form_validador import SchemaValidator
from sac_base.http_json import json_method_not_allowed
from sac_base.permissions_utils import build_action_permissions
from sac_base.sisvar_builders import (
    build_error_payload,
    build_form_response,
    build_form_state,
    build_records_response,
    build_sisvar_payload,
    build_success_payload,
)

from .models import ESTADO_CHOICES, INCIDENCIA_CHOICE, INCIDENCIA_ORIG_CHOICE, INCIDENCIA_TIPO_CHOICES, MOTIVO_CHOICES, ORIGEM_CHOICES, PERIODO_CHOICES, TIPO_CHOICES, Devolucao, Incidencia, Pedido, TentativaEntrega
from .serializers import (
    build_pedido_extra_payload,
    serialize_devolucao,
    serialize_incidencia,
    serialize_pedido_form,
    serialize_tentativa,
)
from .services.importador_csv import importar_csv
from .services.pedido_form import apply_prev_entrega_range_filters, persistir_pedido_cadastro


PERMISSOES_PEDIDO = {
    "acessar": "pedidos.view_pedido",
    "consultar": "pedidos.view_pedido",
    "incluir": "pedidos.add_pedido",
    "editar": "pedidos.change_pedido",
    "excluir": "pedidos.delete_pedido",
    "importar": "pedidos.add_pedido",
}


def _build_campos_pedido_iniciais():
    agora = timezone.localtime(timezone.now()).strftime("%Y-%m-%dT%H:%M")
    return {
        "id": None,
        "filial_id": None,
        "origem": "MANUAL",
        "id_vonzu": "",
        "pedido": "",
        "tipo": "ENTREGA",
        "criado": agora,
        "atualizacao": agora,
        "prev_entrega": "",
        "dt_entrega": "",
        "estado": "",
        "volume": "",
        "volume_conf": 0,
        "nome_dest": "",
        "email_dest": "",
        "fone_dest": "",
        "fone_dest2": "",
        "endereco_dest": "",
        "codpost_dest": "",
        "cidade_dest": "",
        "obs": "",
        "obs_rota": "",
        "cliente_id": None,
        "motorista_id": None,
        "peso": "",
        "expresso": False,
    }


def _listar_clientes_ativos():
    return [
        {"id": c.id, "codigo": c.codigo or "", "nome": c.nome}
        for c in Cliente.objects.filter(is_deleted=False).order_by("nome")[:1000]
    ]


def _listar_motoristas_filial(filial_id):
    if not filial_id:
        return []
    return [
        {"id": m.id, "codigo": m.codigo or "", "nome": m.nome}
        for m in Motorista.objects.filter(is_deleted=False, filial_id=filial_id).order_by("nome")
    ]


def listar_filiais_escrita(usuario):
    return [
        {"id": f.id, "codigo": f.codigo, "nome": f.nome}
        for f in get_filiais_escrita_queryset(usuario).order_by("nome")
    ]


@permission_required(PERMISSOES_PEDIDO["acessar"], raise_exception=True)
def pedidos_importacao_view(request):
    usuario = getattr(request, "user", None)
    acoes_permitidas = build_action_permissions(usuario, PERMISSOES_PEDIDO)

    if request.method == "GET":
        request.sisvar_extra = build_sisvar_payload(
            permissions={"pedido": acoes_permitidas},
            datasets={"filiais_escrita": listar_filiais_escrita(usuario)},
        )
        return render(request, "pedidos.html")

    return json_method_not_allowed()


@permission_required(PERMISSOES_PEDIDO["acessar"], raise_exception=True)
def pedidos_view(request):
    return pedidos_cadastro_view(request)


@permission_required(PERMISSOES_PEDIDO["acessar"], raise_exception=True)
def pedidos_cadastro_view(request):
    nome_form = "cadPedido"
    nome_cons = "consPedido"
    usuario = getattr(request, "user", None)
    acoes = build_action_permissions(usuario, PERMISSOES_PEDIDO)

    schema = {
        nome_form: {
            "filial_id": {"type": "string", "required": True, "value": ""},
            "origem": {"type": "string", "required": True, "value": "MANUAL"},
            "id_vonzu": {"type": "string", "required": True, "value": ""},
            "pedido": {"type": "string", "maxlength": 100, "required": False, "value": ""},
            "tipo": {"type": "string", "required": True, "value": "ENTREGA"},
            "criado": {"type": "string", "required": True, "value": ""},
            "atualizacao": {"type": "string", "required": True, "value": ""},
            "prev_entrega": {"type": "string", "required": False, "value": ""},
            "dt_entrega": {"type": "string", "required": False, "value": ""},
            "estado": {"type": "string", "required": False, "value": ""},
            "volume": {"type": "string", "required": False, "value": ""},
            "volume_conf": {"type": "string", "required": False, "value": "0"},
            "nome_dest": {"type": "string", "required": False, "value": ""},
            "email_dest": {"type": "string", "required": False, "value": ""},
            "fone_dest": {"type": "string", "required": False, "value": ""},
            "fone_dest2": {"type": "string", "required": False, "value": ""},
            "endereco_dest": {"type": "string", "required": False, "value": ""},
            "codpost_dest": {"type": "string", "required": False, "value": ""},
            "cidade_dest": {"type": "string", "required": False, "value": ""},
            "obs": {"type": "string", "required": False, "value": ""},
            "obs_rota": {"type": "string", "required": False, "value": ""},
            "cliente_id": {"type": "string", "required": False, "value": ""},
            "motorista_id": {"type": "string", "required": False, "value": ""},
            "peso": {"type": "string", "required": False, "value": ""},
            "expresso": {"type": "boolean", "required": False, "value": False},
        },
        nome_cons: {
            "filial_cons": {"type": "string", "required": False, "value": ""},
            "origem_cons": {"type": "string", "required": False, "value": ""},
            "pedido_cons": {"type": "string", "required": False, "value": ""},
            "id_vonzu_cons": {"type": "string", "required": False, "value": ""},
            "estado_cons": {"type": "string", "required": False, "value": ""},
            "id_selecionado": {"type": "integer", "required": False, "value": None},
        },
    }

    if request.method == "GET":
        request.sisvar_extra = build_sisvar_payload(
            schema=schema,
            forms={
                nome_form: build_form_state(
                    estado="novo" if acoes["incluir"] else "visualizar",
                    campos=_build_campos_pedido_iniciais(),
                ),
                nome_cons: build_form_state(
                    campos={
                        "filial_cons": "",
                        "origem_cons": "",
                        "pedido_cons": "",
                        "id_vonzu_cons": "",
                        "estado_cons": "",
                        "id_selecionado": None,
                    },
                ),
            },
            permissions={"pedido": acoes},
            options={
                "tipos": [{"value": k, "label": v} for k, v in TIPO_CHOICES],
                "estados": [{"value": k, "label": v} for k, v in ESTADO_CHOICES],
                "origens": [{"value": k, "label": v} for k, v in ORIGEM_CHOICES],
                "clientes": _listar_clientes_ativos(),
                "periodos_mov": [{"value": k, "label": v} for k, v in PERIODO_CHOICES],
                "motivos_dev": [{"value": k, "label": v} for k, v in MOTIVO_CHOICES],
            },
            datasets={"filiais_escrita": listar_filiais_escrita(usuario)},
        )
        return render(request, "pedidos_cadastro.html")

    data_front = request.sisvar_front
    form = data_front.get("form", {}).get(nome_form, {})
    campos = form.get("campos", {})
    estado_form = form.get("estado", "")

    if estado_form == "novo" and not acoes["incluir"]:
        return JsonResponse(build_error_payload("Você não possui permissão para incluir pedidos."), status=403)
    if estado_form == "editar" and not acoes["editar"]:
        return JsonResponse(build_error_payload("Você não possui permissão para editar pedidos."), status=403)

    validator = SchemaValidator(schema[nome_form])
    if not validator.validate(campos):
        erros = [f"{k} - {', '.join(v)}" for k, v in validator.get_errors().items()]
        return JsonResponse(build_error_payload(erros), status=400)

    filial = obter_filial_escrita(campos.get("filial_id"), usuario)
    if not filial:
        return JsonResponse(build_error_payload("Filial inválida ou sem vínculo de escrita."), status=403)

    pedido, err = persistir_pedido_cadastro(usuario, estado_form, campos, filial)
    if err:
        payload, status = err
        return JsonResponse(payload, status=status)

    return JsonResponse(build_form_response(
        form_id=nome_form,
        estado="visualizar",
        campos=serialize_pedido_form(pedido),
        extra_payload=build_pedido_extra_payload(pedido),
        mensagem_sucesso="Pedido salvo com sucesso!",
    ))


@permission_required(PERMISSOES_PEDIDO["consultar"], raise_exception=True)
def pedidos_cadastro_cons_view(request):
    nome_form = "cadPedido"
    nome_cons = "consPedido"
    usuario = getattr(request, "user", None)
    filiais_ids = list(get_filiais_escrita_queryset(usuario).values_list("id", flat=True))

    if request.method != "POST":
        return json_method_not_allowed()

    campos = request.sisvar_front.get("form", {}).get(nome_cons, {}).get("campos", {})
    id_sel = campos.get("id_selecionado")

    if id_sel:
        pedido = Pedido.objects.filter(id=id_sel, filial_id__in=filiais_ids).first()
        if not pedido:
            return JsonResponse(build_error_payload("Pedido não encontrado."), status=404)
        return JsonResponse(build_form_response(
            form_id=nome_form,
            estado="visualizar",
            campos=serialize_pedido_form(pedido),
            extra_payload=build_pedido_extra_payload(pedido),
        ))

    qs = Pedido.objects.filter(filial_id__in=filiais_ids).select_related("filial", "cliente", "motorista").order_by("-atualizacao", "-id")
    if campos.get("filial_cons"):
        qs = qs.filter(filial_id=campos.get("filial_cons"))
    if campos.get("origem_cons"):
        qs = qs.filter(origem=campos.get("origem_cons"))
    if campos.get("pedido_cons"):
        qs = qs.filter(pedido__icontains=(campos.get("pedido_cons") or "").strip())
    if campos.get("id_vonzu_cons"):
        id_v = parse_int(campos.get("id_vonzu_cons"))
        if id_v is not None:
            qs = qs.filter(id_vonzu=id_v)
    if campos.get("estado_cons"):
        qs = qs.filter(estado=campos.get("estado_cons"))
    qs, date_erros = apply_prev_entrega_range_filters(qs, campos)
    if date_erros:
        return JsonResponse(build_error_payload(date_erros), status=400)

    registros = [
        {
            "id": p.id,
            "filial": f"{p.filial.codigo} - {p.filial.nome}",
            "origem": p.origem,
            "id_vonzu": p.id_vonzu,
            "pedido": p.pedido or "",
            "tipo": p.tipo,
            "estado": p.estado or "",
            "prev_entrega": p.prev_entrega.isoformat() if p.prev_entrega else "",
            "nome_dest": p.nome_dest or "",
            "cliente": p.cliente.nome if p.cliente_id else "",
            "motorista": p.motorista.nome if p.motorista_id else "",
        }
        for p in qs[:500]
    ]
    return JsonResponse(build_records_response(registros))


@permission_required(PERMISSOES_PEDIDO["excluir"], raise_exception=True)
def pedidos_cadastro_del_view(request):
    if request.method != "POST":
        return json_method_not_allowed()
    usuario = getattr(request, "user", None)
    filiais_ids = list(get_filiais_escrita_queryset(usuario).values_list("id", flat=True))
    pedido_id = request.sisvar_front.get("form", {}).get("cadPedido", {}).get("campos", {}).get("id")
    pedido = Pedido.objects.filter(id=pedido_id, filial_id__in=filiais_ids).first()
    if not pedido:
        return JsonResponse(build_error_payload("Pedido não encontrado."), status=404)
    pedido.delete()
    return JsonResponse(build_success_payload("Pedido excluído com sucesso!"))


@permission_required(PERMISSOES_PEDIDO["consultar"], raise_exception=True)
def pedido_mov_list_view(request):
    if request.method != "POST":
        return json_method_not_allowed()
    filial_ativa = getattr(request, "filial_ativa", None)
    if not filial_ativa:
        return JsonResponse(build_error_payload("Filial ativa não encontrada."), status=403)
    pedido_id = request.sisvar_front.get("pedido_id")
    regs = TentativaEntrega.objects.filter(
        pedido_id=pedido_id, pedido__filial=filial_ativa
    ).select_related("motorista").order_by("-data_tentativa", "-id")
    return JsonResponse(build_records_response([serialize_tentativa(r) for r in regs]))


@permission_required(PERMISSOES_PEDIDO["editar"], raise_exception=True)
def pedido_mov_save_view(request):
    if request.method != "POST":
        return json_method_not_allowed()
    filial_ativa = getattr(request, "filial_ativa", None)
    if not filial_ativa:
        return JsonResponse(build_error_payload("Filial ativa não encontrada."), status=403)
    data = request.sisvar_front
    pedido_id = parse_int(data.get("pedido_id"))
    mov_id = parse_int(data.get("id"))
    pedido = Pedido.objects.filter(id=pedido_id, filial=filial_ativa).first()
    if not pedido:
        return JsonResponse(build_error_payload("Pedido não encontrado."), status=404)

    dt_tentativa = parse_date(data.get("data_tentativa"))
    if not dt_tentativa:
        return JsonResponse(build_error_payload("Data da tentativa é obrigatória."), status=400)

    carro = parse_int(data.get("carro"))
    motorista_id = parse_int(data.get("motorista_id"))
    periodo = (data.get("periodo") or "").strip().upper() or None

    if periodo and periodo not in {codigo for codigo, _ in PERIODO_CHOICES}:
        return JsonResponse(build_error_payload("Período inválido."), status=400)

    motorista = None
    if motorista_id is not None:
        motorista = Motorista.objects.filter(id=motorista_id, filial_id=pedido.filial_id, is_deleted=False).first()
        if not motorista:
            return JsonResponse(build_error_payload("Motorista inválido para a filial do pedido."), status=400)

    if mov_id:
        mov = TentativaEntrega.objects.filter(id=mov_id, pedido=pedido).first()
        if not mov:
            return JsonResponse(build_error_payload("Movimentação não encontrada."), status=404)
    else:
        mov = TentativaEntrega(pedido=pedido)

    mov.data_tentativa = dt_tentativa
    mov.estado = (data.get("estado") or "").strip() or None
    mov.carro = carro
    mov.motorista = motorista
    mov.periodo = periodo
    mov.dt_entrega = parse_date(data.get("dt_entrega"))
    mov.faturado = bool(data.get("faturado", False))
    mov.interno = bool(data.get("interno", False))
    mov.save()
    return JsonResponse(build_success_payload("Movimentação salva com sucesso!", extra_payload={"mov": serialize_tentativa(mov)}))


@permission_required(PERMISSOES_PEDIDO["excluir"], raise_exception=True)
def pedido_mov_del_view(request):
    if request.method != "POST":
        return json_method_not_allowed()
    filial_ativa = getattr(request, "filial_ativa", None)
    if not filial_ativa:
        return JsonResponse(build_error_payload("Filial ativa não encontrada."), status=403)
    mov_id = parse_int(request.sisvar_front.get("id"))
    mov = TentativaEntrega.objects.filter(id=mov_id, pedido__filial=filial_ativa).first()
    if not mov:
        return JsonResponse(build_error_payload("Movimentação não encontrada."), status=404)
    mov.delete()
    return JsonResponse(build_success_payload("Movimentação excluída com sucesso!"))


@permission_required(PERMISSOES_PEDIDO["consultar"], raise_exception=True)
def pedido_dev_list_view(request):
    if request.method != "POST":
        return json_method_not_allowed()
    filial_ativa = getattr(request, "filial_ativa", None)
    if not filial_ativa:
        return JsonResponse(build_error_payload("Filial ativa não encontrada."), status=403)
    pedido_id = request.sisvar_front.get("pedido_id")
    regs = Devolucao.objects.filter(
        pedido_id=pedido_id, pedido__filial=filial_ativa
    ).order_by("-data", "-id")
    return JsonResponse(build_records_response([serialize_devolucao(r) for r in regs]))


@permission_required(PERMISSOES_PEDIDO["editar"], raise_exception=True)
def pedido_dev_save_view(request):
    if request.method != "POST":
        return json_method_not_allowed()
    filial_ativa = getattr(request, "filial_ativa", None)
    if not filial_ativa:
        return JsonResponse(build_error_payload("Filial ativa não encontrada."), status=403)
    data = request.sisvar_front
    pedido_id = parse_int(data.get("pedido_id"))
    dev_id = parse_int(data.get("id"))
    pedido = Pedido.objects.filter(id=pedido_id, filial=filial_ativa).first()
    if not pedido:
        return JsonResponse(build_error_payload("Pedido não encontrado."), status=404)

    dt_data = parse_date(data.get("data"))
    if not dt_data:
        return JsonResponse(build_error_payload("Data é obrigatória."), status=400)

    motivo = (data.get("motivo") or "").strip()
    if not motivo or motivo not in {codigo for codigo, _ in MOTIVO_CHOICES}:
        return JsonResponse(build_error_payload("Motivo inválido."), status=400)

    if dev_id:
        dev = Devolucao.objects.filter(id=dev_id, pedido=pedido).first()
        if not dev:
            return JsonResponse(build_error_payload("Devolução não encontrada."), status=404)
    else:
        dev = Devolucao(pedido=pedido)

    dev.data = dt_data
    dev.palete = parse_int(data.get("palete"))
    dev.volume = parse_int(data.get("volume"))
    dev.motivo = motivo
    dev.obs = (data.get("obs") or "").strip() or None
    dev.save()
    return JsonResponse(build_success_payload("Devolução salva com sucesso!", extra_payload={"dev": serialize_devolucao(dev)}))


@permission_required(PERMISSOES_PEDIDO["excluir"], raise_exception=True)
def pedido_dev_del_view(request):
    if request.method != "POST":
        return json_method_not_allowed()
    filial_ativa = getattr(request, "filial_ativa", None)
    if not filial_ativa:
        return JsonResponse(build_error_payload("Filial ativa não encontrada."), status=403)
    dev_id = parse_int(request.sisvar_front.get("id"))
    dev = Devolucao.objects.filter(id=dev_id, pedido__filial=filial_ativa).first()
    if not dev:
        return JsonResponse(build_error_payload("Devolução não encontrada."), status=404)
    # Excluir imagens do imgbb antes de remover o registro
    for foto in (dev.fotos or []):
        delete_url = foto.get("delete_url", "")
        if delete_url:
            try:
                requests.get(delete_url, timeout=10)
            except requests.RequestException:
                pass
    dev.delete()
    return JsonResponse(build_success_payload("Devolução excluída com sucesso!"))


# ─── Incidências ───────────────────────────────────────────────────────────────

_INCIDENCIA_TIPOS_VALIDOS = {v for v, _ in INCIDENCIA_TIPO_CHOICES}
_INCIDENCIA_ORIGENS_VALIDAS = {v for v, _ in INCIDENCIA_ORIG_CHOICE}


@permission_required(PERMISSOES_PEDIDO["consultar"], raise_exception=True)
def pedido_inc_list_view(request):
    if request.method != "POST":
        return json_method_not_allowed()
    filial_ativa = getattr(request, "filial_ativa", None)
    if not filial_ativa:
        return JsonResponse(build_error_payload("Filial ativa não encontrada."), status=403)
    pedido_id = request.sisvar_front.get("pedido_id")
    regs = (
        Incidencia.objects
        .filter(pedido_id=pedido_id, pedido__filial=filial_ativa)
        .select_related("motorista")
        .order_by("-data", "-id")
    )
    return JsonResponse(build_records_response([serialize_incidencia(r) for r in regs]))


@permission_required(PERMISSOES_PEDIDO["editar"], raise_exception=True)
def pedido_inc_save_view(request):
    if request.method != "POST":
        return json_method_not_allowed()
    filial_ativa = getattr(request, "filial_ativa", None)
    if not filial_ativa:
        return JsonResponse(build_error_payload("Filial ativa não encontrada."), status=403)
    data = request.sisvar_front
    pedido_id = parse_int(data.get("pedido_id"))
    inc_id = parse_int(data.get("id"))
    pedido = Pedido.objects.filter(id=pedido_id, filial=filial_ativa).first()
    if not pedido:
        return JsonResponse(build_error_payload("Pedido não encontrado."), status=404)

    dt_data = parse_date(data.get("data"))
    if not dt_data:
        return JsonResponse(build_error_payload("Data é obrigatória."), status=400)

    origem = (data.get("origem") or "").strip()
    if not origem or origem not in _INCIDENCIA_ORIGENS_VALIDAS:
        return JsonResponse(build_error_payload("Origem inválida."), status=400)

    tipo = (data.get("tipo") or "").strip()
    if not tipo or tipo not in _INCIDENCIA_TIPOS_VALIDOS:
        return JsonResponse(build_error_payload("Tipo inválido."), status=400)

    # Validar que tipo é compatível com a origem escolhida
    filtro_origem = next(
        (f for v, f in INCIDENCIA_CHOICE if v == tipo), None
    )
    if filtro_origem is not None and filtro_origem != "" and filtro_origem != origem.lower():
        return JsonResponse(build_error_payload("Tipo incompatível com a origem selecionada."), status=400)

    motorista_id = None
    if origem.lower() == "filial":
        motorista_id = parse_int(data.get("motorista_id"))

    if inc_id:
        inc = Incidencia.objects.filter(id=inc_id, pedido=pedido).first()
        if not inc:
            return JsonResponse(build_error_payload("Incidência não encontrada."), status=404)
    else:
        inc = Incidencia(pedido=pedido)

    inc.data = dt_data
    inc.origem = origem
    inc.tipo = tipo
    inc.artigo = (data.get("artigo") or "").strip() or None
    inc.valor = parse_decimal(data.get("valor"))
    inc.motorista_id = motorista_id
    inc.obs = (data.get("obs") or "").strip() or None
    inc.save()
    return JsonResponse(build_success_payload(
        "Incidência salva com sucesso!",
        extra_payload={"inc": serialize_incidencia(inc)},
    ))


@permission_required(PERMISSOES_PEDIDO["excluir"], raise_exception=True)
def pedido_inc_del_view(request):
    if request.method != "POST":
        return json_method_not_allowed()
    filial_ativa = getattr(request, "filial_ativa", None)
    if not filial_ativa:
        return JsonResponse(build_error_payload("Filial ativa não encontrada."), status=403)
    inc_id = parse_int(request.sisvar_front.get("id"))
    inc = Incidencia.objects.filter(id=inc_id, pedido__filial=filial_ativa).first()
    if not inc:
        return JsonResponse(build_error_payload("Incidência não encontrada."), status=404)
    inc.delete()
    return JsonResponse(build_success_payload("Incidência excluída com sucesso!"))


_IMGBB_MAX_BYTES = 2 * 1024 * 1024  # 2 MB


@permission_required(PERMISSOES_PEDIDO["editar"], raise_exception=True)
def pedido_dev_foto_add_view(request):
    """Recebe base64 comprimida do frontend, faz upload no imgbb e persiste metadados."""
    if request.method != "POST":
        return json_method_not_allowed()

    filial_ativa = getattr(request, "filial_ativa", None)
    if not filial_ativa:
        return JsonResponse(build_error_payload("Filial ativa não encontrada."), status=403)

    data = request.sisvar_front
    dev_id = parse_int(data.get("dev_id"))
    imagem_b64 = data.get("imagem_b64", "")

    if not dev_id or not imagem_b64:
        return JsonResponse(build_error_payload("Dados insuficientes."), status=400)

    dev = Devolucao.objects.filter(id=dev_id, pedido__filial=filial_ativa).first()
    if not dev:
        return JsonResponse(build_error_payload("Devolução não encontrada."), status=404)

    # Validar tamanho do base64 (raw bytes estimados)
    try:
        raw_bytes = base64.b64decode(imagem_b64, validate=True)
    except (binascii.Error, TypeError):
        return JsonResponse(build_error_payload("Imagem inválida."), status=400)

    if len(raw_bytes) > _IMGBB_MAX_BYTES:
        return JsonResponse(
            build_error_payload("A imagem excede 2 MB mesmo após compressão."), status=400
        )

    api_key = os.environ.get("IMGBB_API_KEY", "")
    if not api_key:
        return JsonResponse(
            build_error_payload("Serviço de imagens não configurado."), status=500
        )

    try:
        resp = requests.post(
            "https://api.imgbb.com/1/upload",
            data={"key": api_key, "image": imagem_b64},
            timeout=30,
        )
        resp.raise_for_status()
        resultado = resp.json()
    except requests.RequestException:
        return JsonResponse(
            build_error_payload("Falha de rede ao enviar imagem para o serviço de hospedagem."), status=502
        )
    except ValueError:
        return JsonResponse(
            build_error_payload("Resposta inválida do serviço de imagens."), status=502
        )

    if not resultado.get("success"):
        return JsonResponse(build_error_payload("O serviço de hospedagem recusou a imagem."), status=502)

    img_data = resultado["data"]
    nova_foto = {
        "id": img_data["id"],
        "url": img_data["url"],
        "thumb_url": img_data.get("thumb", {}).get("url", img_data["url"]),
        "delete_url": img_data.get("delete_url", ""),
    }

    fotos = list(dev.fotos or [])
    fotos.append(nova_foto)
    dev.fotos = fotos
    dev.save(update_fields=["fotos"])

    foto_publica = {
        "id": nova_foto["id"],
        "url": nova_foto["url"],
        "thumb_url": nova_foto["thumb_url"],
    }
    return JsonResponse(build_success_payload("Foto adicionada.", extra_payload={"foto": foto_publica}))


@permission_required(PERMISSOES_PEDIDO["editar"], raise_exception=True)
def pedido_dev_foto_del_view(request):
    """Remove uma foto da devolução e notifica o imgbb via delete_url."""
    if request.method != "POST":
        return json_method_not_allowed()

    filial_ativa = getattr(request, "filial_ativa", None)
    if not filial_ativa:
        return JsonResponse(build_error_payload("Filial ativa não encontrada."), status=403)

    data = request.sisvar_front
    dev_id = parse_int(data.get("dev_id"))
    imgbb_id = (data.get("imgbb_id") or "").strip()

    if not dev_id or not imgbb_id:
        return JsonResponse(build_error_payload("Dados insuficientes."), status=400)

    dev = Devolucao.objects.filter(id=dev_id, pedido__filial=filial_ativa).first()
    if not dev:
        return JsonResponse(build_error_payload("Devolução não encontrada."), status=404)

    fotos = list(dev.fotos or [])
    alvo = next((f for f in fotos if f.get("id") == imgbb_id), None)
    if not alvo:
        return JsonResponse(build_error_payload("Foto não encontrada."), status=404)

    # Tenta excluir no imgbb (falha silenciosa — registro local é sempre removido)
    delete_url = alvo.get("delete_url", "")
    if delete_url:
        try:
            requests.get(delete_url, timeout=10)
        except requests.RequestException:
            pass

    dev.fotos = [f for f in fotos if f.get("id") != imgbb_id]
    dev.save(update_fields=["fotos"])

    return JsonResponse(build_success_payload("Foto removida."))


@permission_required(PERMISSOES_PEDIDO["consultar"], raise_exception=True)
def pedido_motoristas_view(request):
    if request.method != "POST":
        return json_method_not_allowed()
    filial_ativa = getattr(request, "filial_ativa", None)
    if not filial_ativa:
        return JsonResponse(build_error_payload("Filial ativa não encontrada."), status=403)
    filial_id = parse_int(request.sisvar_front.get("filial_id"))
    if filial_id != filial_ativa.id:
        return JsonResponse(build_error_payload("Filial inválida."), status=403)
    return JsonResponse(build_records_response(_listar_motoristas_filial(filial_ativa.id)))


@permission_required(PERMISSOES_PEDIDO["importar"], raise_exception=True)
def pedidos_importar_view(request):
    usuario = getattr(request, "user", None)

    if request.method != "POST":
        return json_method_not_allowed()

    arquivo = request.FILES.get("arquivo_csv")
    filial_id = request.POST.get("filial_id")
    verificar_volumes = request.POST.get("verificar_volumes") == "1"

    if not arquivo:
        return JsonResponse(build_error_payload("Arquivo CSV não enviado."), status=400)

    if not arquivo.name.lower().endswith(".csv"):
        return JsonResponse(build_error_payload("O arquivo deve ter extensão .csv."), status=400)

    filial = obter_filial_escrita(filial_id, usuario)
    if not filial:
        return JsonResponse(
            build_error_payload("Filial inválida ou sem permissão de escrita."), status=403
        )

    conteudo = arquivo.read()
    nome_arquivo = arquivo.name

    resultado = importar_csv(conteudo, filial, nome_arquivo)

    if not resultado["sucesso"]:
        return JsonResponse(
            {
                "success": False,
                "mensagens": {"erro": {"conteudo": resultado["erros"], "ignorar": False}},
            },
            status=422,
        )

    stats = resultado["stats"]
    resumo = (
        f"Importação concluída: {stats['criados']} criado(s), "
        f"{stats['atualizados']} atualizado(s), "
        f"{stats['sem_alteracao']} sem alteração, "
        f"{stats['tentativas']} tentativa(s) criada(s)."
    )
    if stats["avisos_fk"]:
        resumo += f" {stats['avisos_fk']} aviso(s) de FK — consulte o relatório."

    relatorio_url = None
    if verificar_volumes and resultado.get("dados_volumes"):
        request.session["relatorio_volumes"] = {
            "nome_arquivo": nome_arquivo,
            "dados": resultado["dados_volumes"],
        }
        relatorio_url = "/app/logistica/pedidos/relatorio-volumes/"

    return JsonResponse(
        {
            "success": True,
            "relatorio": resultado["relatorio"],
            "nome_relatorio": f"relatorio_{nome_arquivo.replace('.csv', '')}.txt",
            "stats": stats,
            "mensagens": {"sucesso": {"conteudo": [resumo], "ignorar": True}},
            "relatorio_volumes_url": relatorio_url,
        }
    )


@login_required
@permission_required(PERMISSOES_PEDIDO["importar"], raise_exception=True)
def pedidos_relatorio_volumes_view(request):
    dados_sessao = request.session.pop("relatorio_volumes", None)
    if not dados_sessao:
        return render(request, "relatorio_volumes.html", {"sem_dados": True})
    return render(request, "relatorio_volumes.html", {
        "nome_arquivo": dados_sessao.get("nome_arquivo", ""),
        "pedidos": dados_sessao.get("dados", []),
        "sem_dados": False,
    })
