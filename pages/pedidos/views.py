from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from pages.cad_cliente.models import Cliente
from pages.filial.models import Filial, UsuarioFilial
from pages.motorista.models import Motorista
from sac_base.form_validador import SchemaValidator
from sac_base.permissions_utils import build_action_permissions
from sac_base.sisvar_builders import (
    build_error_payload,
    build_form_response,
    build_form_state,
    build_records_response,
    build_sisvar_payload,
    build_success_payload,
)

from .models import ESTADO_CHOICES, ORIGEM_CHOICES, PERIODO_CHOICES, TIPO_CHOICES, Pedido, TentativaEntrega
from .services.importador_csv import importar_csv


PERMISSOES_PEDIDO = {
    "acessar": "pedidos.view_pedido",
    "consultar": "pedidos.view_pedido",
    "incluir": "pedidos.add_pedido",
    "editar": "pedidos.change_pedido",
    "excluir": "pedidos.delete_pedido",
    "importar": "pedidos.add_pedido",
}

TRAVAS_IMPORTADOS = {"filial_id", "origem", "id_vonzu", "pedido", "tipo", "criado", "cliente_id"}


def _parse_int(valor):
    if valor in (None, ""):
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _parse_date(valor):
    if not valor:
        return None
    try:
        return datetime.strptime(str(valor), "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_datetime(valor):
    if not valor:
        return None
    texto = str(valor).strip()
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.strptime(texto, fmt)
            return timezone.make_aware(dt) if timezone.is_naive(dt) else dt
        except ValueError:
            continue
    return None


def _parse_decimal(valor):
    if valor in (None, ""):
        return None
    try:
        return Decimal(str(valor).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def _dt_to_local_input(dt):
    if not dt:
        return ""
    local = timezone.localtime(dt)
    return local.strftime("%Y-%m-%dT%H:%M")


def _serialize_pedido_form(pedido):
    return {
        "id": pedido.id,
        "filial_id": pedido.filial_id,
        "origem": pedido.origem,
        "id_vonzu": pedido.id_vonzu,
        "pedido": pedido.pedido or "",
        "tipo": pedido.tipo,
        "criado": _dt_to_local_input(pedido.criado),
        "atualizacao": _dt_to_local_input(pedido.atualizacao),
        "prev_entrega": pedido.prev_entrega.isoformat() if pedido.prev_entrega else "",
        "dt_entrega": pedido.dt_entrega.isoformat() if pedido.dt_entrega else "",
        "estado": pedido.estado or "",
        "volume": pedido.volume,
        "volume_conf": pedido.volume_conf,
        "nome_dest": pedido.nome_dest or "",
        "email_dest": pedido.email_dest or "",
        "fone_dest": pedido.fone_dest or "",
        "fone_dest2": pedido.fone_dest2 or "",
        "endereco_dest": pedido.endereco_dest or "",
        "codpost_dest": pedido.codpost_dest or "",
        "cidade_dest": pedido.cidade_dest or "",
        "obs": pedido.obs or "",
        "obs_rota": pedido.obs_rota or "",
        "cliente_id": pedido.cliente_id,
        "motorista_id": pedido.motorista_id,
        "peso": str(pedido.peso) if pedido.peso is not None else "",
        "expresso": pedido.expresso,
    }


def _serialize_tentativa(reg):
    return {
        "id": reg.id,
        "pedido_id": reg.pedido_id,
        "data_tentativa": reg.data_tentativa.isoformat() if reg.data_tentativa else "",
        "estado": reg.estado or "",
        "carro": reg.carro,
        "motorista_id": reg.motorista_id,
        "motorista_nome": reg.motorista.nome if reg.motorista_id else "",
        "periodo": reg.periodo or "",
        "faturado": reg.faturado,
        "interno": reg.interno,
        "dt_entrega": reg.dt_entrega.isoformat() if reg.dt_entrega else "",
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


def get_filiais_escrita_queryset(usuario):
    queryset = Filial.objects.filter(ativa=True, pais_atuacao__isnull=False).select_related("pais_atuacao")
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return queryset.none()
    if getattr(usuario, "is_superuser", False):
        return queryset
    return queryset.filter(
        usuarios_vinculados__usuario=usuario,
        usuarios_vinculados__ativo=True,
        usuarios_vinculados__pode_escrever=True,
    ).distinct()


def listar_filiais_escrita(usuario):
    return [
        {"id": f.id, "codigo": f.codigo, "nome": f.nome}
        for f in get_filiais_escrita_queryset(usuario).order_by("nome")
    ]


def obter_filial_escrita(filial_id, usuario):
    try:
        filial_id = int(filial_id)
    except (TypeError, ValueError):
        return None
    return get_filiais_escrita_queryset(usuario).filter(id=filial_id).first()


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

    return JsonResponse(build_error_payload("Método não permitido."), status=405)


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

    try:
        with transaction.atomic():
            if estado_form == "novo":
                pedido = Pedido(filial=filial)
                origem = "MANUAL"
            elif estado_form == "editar":
                pedido = Pedido.objects.filter(
                    id=campos.get("id"),
                    filial_id__in=list(get_filiais_escrita_queryset(usuario).values_list("id", flat=True)),
                ).first()
                if not pedido:
                    return JsonResponse(build_error_payload("Pedido não encontrado."), status=404)
                origem = pedido.origem
            else:
                return JsonResponse(build_error_payload("Estado inválido."), status=400)

            parsed = {
                "filial_id": filial.id,
                "origem": "MANUAL" if estado_form == "novo" else origem,
                "id_vonzu": _parse_int(campos.get("id_vonzu")),
                "pedido": (campos.get("pedido") or "").strip() or None,
                "tipo": (campos.get("tipo") or "ENTREGA").strip(),
                "criado": _parse_datetime(campos.get("criado")) or timezone.now(),
                "atualizacao": _parse_datetime(campos.get("atualizacao")) or timezone.now(),
                "prev_entrega": _parse_date(campos.get("prev_entrega")),
                "dt_entrega": _parse_date(campos.get("dt_entrega")),
                "estado": (campos.get("estado") or "").strip() or None,
                "volume": _parse_int(campos.get("volume")),
                "volume_conf": _parse_int(campos.get("volume_conf")) or 0,
                "nome_dest": (campos.get("nome_dest") or "").strip() or None,
                "email_dest": (campos.get("email_dest") or "").strip() or None,
                "fone_dest": (campos.get("fone_dest") or "").strip() or None,
                "fone_dest2": (campos.get("fone_dest2") or "").strip() or None,
                "endereco_dest": (campos.get("endereco_dest") or "").strip() or None,
                "codpost_dest": (campos.get("codpost_dest") or "").strip() or None,
                "cidade_dest": (campos.get("cidade_dest") or "").strip() or None,
                "obs": (campos.get("obs") or "").strip() or None,
                "obs_rota": (campos.get("obs_rota") or "").strip() or None,
                "cliente_id": _parse_int(campos.get("cliente_id")),
                "motorista_id": _parse_int(campos.get("motorista_id")),
                "peso": _parse_decimal(campos.get("peso")),
                "expresso": bool(campos.get("expresso", False)),
            }

            if estado_form == "editar" and pedido.origem == "IMPORTADO":
                for chave in TRAVAS_IMPORTADOS:
                    parsed[chave] = getattr(pedido, chave if chave != "filial_id" else "filial_id")

            if parsed["id_vonzu"] is None:
                return JsonResponse(build_error_payload("ID Vonzu é obrigatório e numérico."), status=400)

            for campo, valor in parsed.items():
                setattr(pedido, campo, valor)

            pedido.save()
    except Exception as exc:
        return JsonResponse(build_error_payload(str(exc)), status=422)

    return JsonResponse(build_form_response(
        form_id=nome_form,
        estado="visualizar",
        campos=_serialize_pedido_form(pedido),
        extra_payload={"registros_mov": [_serialize_tentativa(t) for t in pedido.tentativas.select_related("motorista").order_by("-data_tentativa", "-id")]},
        mensagem_sucesso="Pedido salvo com sucesso!",
    ))


@permission_required(PERMISSOES_PEDIDO["consultar"], raise_exception=True)
def pedidos_cadastro_cons_view(request):
    nome_form = "cadPedido"
    nome_cons = "consPedido"
    usuario = getattr(request, "user", None)
    filiais_ids = list(get_filiais_escrita_queryset(usuario).values_list("id", flat=True))

    if request.method != "POST":
        return JsonResponse(build_error_payload("Método não permitido."), status=405)

    campos = request.sisvar_front.get("form", {}).get(nome_cons, {}).get("campos", {})
    id_sel = campos.get("id_selecionado")

    if id_sel:
        pedido = Pedido.objects.filter(id=id_sel, filial_id__in=filiais_ids).first()
        if not pedido:
            return JsonResponse(build_error_payload("Pedido não encontrado."), status=404)
        return JsonResponse(build_form_response(
            form_id=nome_form,
            estado="visualizar",
            campos=_serialize_pedido_form(pedido),
            extra_payload={"registros_mov": [_serialize_tentativa(t) for t in pedido.tentativas.select_related("motorista").order_by("-data_tentativa", "-id")]},
        ))

    qs = Pedido.objects.filter(filial_id__in=filiais_ids).select_related("filial", "cliente", "motorista").order_by("-atualizacao", "-id")
    if campos.get("filial_cons"):
        qs = qs.filter(filial_id=campos.get("filial_cons"))
    if campos.get("origem_cons"):
        qs = qs.filter(origem=campos.get("origem_cons"))
    if campos.get("pedido_cons"):
        qs = qs.filter(pedido__icontains=(campos.get("pedido_cons") or "").strip())
    if campos.get("id_vonzu_cons"):
        id_v = _parse_int(campos.get("id_vonzu_cons"))
        if id_v is not None:
            qs = qs.filter(id_vonzu=id_v)
    if campos.get("estado_cons"):
        qs = qs.filter(estado=campos.get("estado_cons"))

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
        return JsonResponse(build_error_payload("Método não permitido."), status=405)
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
        return JsonResponse(build_error_payload("Método não permitido."), status=405)
    pedido_id = request.sisvar_front.get("pedido_id")
    regs = TentativaEntrega.objects.filter(pedido_id=pedido_id).select_related("motorista").order_by("-data_tentativa", "-id")
    return JsonResponse(build_records_response([_serialize_tentativa(r) for r in regs]))


@permission_required(PERMISSOES_PEDIDO["editar"], raise_exception=True)
def pedido_mov_save_view(request):
    if request.method != "POST":
        return JsonResponse(build_error_payload("Método não permitido."), status=405)
    data = request.sisvar_front
    pedido_id = _parse_int(data.get("pedido_id"))
    mov_id = _parse_int(data.get("id"))
    pedido = Pedido.objects.filter(id=pedido_id).first()
    if not pedido:
        return JsonResponse(build_error_payload("Pedido não encontrado."), status=404)

    dt_tentativa = _parse_date(data.get("data_tentativa"))
    if not dt_tentativa:
        return JsonResponse(build_error_payload("Data da tentativa é obrigatória."), status=400)

    carro = _parse_int(data.get("carro"))
    motorista_id = _parse_int(data.get("motorista_id"))
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
    mov.dt_entrega = _parse_date(data.get("dt_entrega"))
    mov.faturado = bool(data.get("faturado", False))
    mov.interno = bool(data.get("interno", False))
    mov.save()
    return JsonResponse(build_success_payload("Movimentação salva com sucesso!", extra_payload={"mov": _serialize_tentativa(mov)}))


@permission_required(PERMISSOES_PEDIDO["excluir"], raise_exception=True)
def pedido_mov_del_view(request):
    if request.method != "POST":
        return JsonResponse(build_error_payload("Método não permitido."), status=405)
    mov_id = _parse_int(request.sisvar_front.get("id"))
    mov = TentativaEntrega.objects.filter(id=mov_id).first()
    if not mov:
        return JsonResponse(build_error_payload("Movimentação não encontrada."), status=404)
    mov.delete()
    return JsonResponse(build_success_payload("Movimentação excluída com sucesso!"))


@permission_required(PERMISSOES_PEDIDO["consultar"], raise_exception=True)
def pedido_motoristas_view(request):
    if request.method != "POST":
        return JsonResponse(build_error_payload("Método não permitido."), status=405)
    filial_id = _parse_int(request.sisvar_front.get("filial_id"))
    return JsonResponse(build_records_response(_listar_motoristas_filial(filial_id)))


@permission_required(PERMISSOES_PEDIDO["importar"], raise_exception=True)
def pedidos_importar_view(request):
    usuario = getattr(request, "user", None)

    if request.method != "POST":
        return JsonResponse(build_error_payload("Método não permitido."), status=405)

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
