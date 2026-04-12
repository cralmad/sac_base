from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render

from pages.auditoria.models import AuditEvent
from pages.auditoria.utils import diff_snapshots, registrar_auditoria, snapshot_instance
from pages.filial.models import Filial, UsuarioFilial
from sac_base.form_validador import SchemaValidator
from sac_base.sisvar_builders import build_error_payload, build_form_response, build_form_state, build_records_response, build_sisvar_payload, build_success_payload

from .models import ZonaEntrega, ZonaEntregaExcecaoPostal, ZonaEntregaFaixaPostal


PERMISSOES_ZONA_ENTREGA = {
    "acessar": "zona_entrega.view_zonaentrega",
    "consultar": "zona_entrega.view_zonaentrega",
    "incluir": "zona_entrega.add_zonaentrega",
    "editar": "zona_entrega.change_zonaentrega",
    "excluir": "zona_entrega.delete_zonaentrega",
}


def obter_acoes_permitidas(usuario):
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return {acao: False for acao in PERMISSOES_ZONA_ENTREGA}

    return {
        acao: usuario.has_perm(codename)
        for acao, codename in PERMISSOES_ZONA_ENTREGA.items()
    }


def resposta_sem_permissao(mensagem, status=403):
    return JsonResponse(build_error_payload(mensagem), status=status)


def extrair_mensagens_validacao(exc):
    if hasattr(exc, "message_dict"):
        return [
            f"{campo} - {mensagem}"
            for campo, mensagens in exc.message_dict.items()
            for mensagem in mensagens
        ]

    if hasattr(exc, "messages"):
        return list(exc.messages)

    return [str(exc)]


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


def listar_filiais_logisticas(usuario):
    return [
        {
            "id": filial.id,
            "codigo": filial.codigo,
            "nome": filial.nome,
            "pais_atuacao_id": filial.pais_atuacao_id,
            "pais_atuacao_sigla": filial.pais_atuacao.sigla if filial.pais_atuacao_id else "",
            "pais_atuacao_nome": filial.pais_atuacao.nome if filial.pais_atuacao_id else "",
        }
        for filial in get_filiais_escrita_queryset(usuario).order_by("nome")
    ]


def build_zona_campos_iniciais():
    return {
        "id": None,
        "filial_id": None,
        "codigo": "",
        "descricao": "",
        "prioridade": 0,
        "valor_cobranca_unitario_pedido": "0.00",
        "valor_pagamento_unitario_entrega": "0.00",
        "valor_pagamento_fixo_rota": "0.00",
        "valor_pagamento_unitario_entrega_pesado": "0.00",
        "valor_pagamento_fixo_rota_pesado": "0.00",
        "observacao": "",
        "ativa": True,
        "faixas": [],
        "excecoes": [],
    }


def serializar_faixas(zona):
    return [
        {
            "tipo_intervalo": faixa.tipo_intervalo,
            "codigo_postal_inicial": faixa.codigo_postal_inicial,
            "codigo_postal_final": faixa.codigo_postal_final,
            "ativa": faixa.ativa,
        }
        for faixa in zona.faixas_postais.order_by("tipo_intervalo", "codigo_postal_inicial")
    ]


def serializar_excecoes(zona):
    return [
        {
            "tipo_excecao": excecao.tipo_excecao,
            "codigo_postal": excecao.codigo_postal,
            "ativa": excecao.ativa,
            "observacao": excecao.observacao,
        }
        for excecao in zona.excecoes_postais.order_by("codigo_postal")
    ]


def serializar_form_zona(zona):
    return {
        "id": zona.id,
        "filial_id": zona.filial_id,
        "codigo": zona.codigo,
        "descricao": zona.descricao,
        "prioridade": zona.prioridade,
        "valor_cobranca_unitario_pedido": f"{zona.valor_cobranca_unitario_pedido:.2f}",
        "valor_pagamento_unitario_entrega": f"{zona.valor_pagamento_unitario_entrega:.2f}",
        "valor_pagamento_fixo_rota": f"{zona.valor_pagamento_fixo_rota:.2f}",
        "valor_pagamento_unitario_entrega_pesado": f"{zona.valor_pagamento_unitario_entrega_pesado:.2f}",
        "valor_pagamento_fixo_rota_pesado": f"{zona.valor_pagamento_fixo_rota_pesado:.2f}",
        "observacao": zona.observacao,
        "ativa": zona.ativa,
        "faixas": serializar_faixas(zona),
        "excecoes": serializar_excecoes(zona),
    }


def obter_filial_logistica(filial_id, usuario):
    try:
        filial_id = int(filial_id)
    except (TypeError, ValueError):
        return None

    return get_filiais_escrita_queryset(usuario).filter(id=filial_id).first()


def criar_faixa_instancia(zona, payload):
    if not isinstance(payload, dict):
        raise ValidationError("Faixa postal inválida.")

    faixa = ZonaEntregaFaixaPostal(
        zona_entrega=zona,
        tipo_intervalo=(payload.get("tipo_intervalo") or ZonaEntregaFaixaPostal.TIPO_CP7).strip().upper(),
        codigo_postal_inicial=payload.get("codigo_postal_inicial"),
        codigo_postal_final=payload.get("codigo_postal_final"),
        ativa=bool(payload.get("ativa", True)),
        cp4_inicial="0000",
        cp4_final="0000",
        cp7_inicial_num=0,
        cp7_final_num=0,
    )
    faixa.full_clean()
    return faixa


def criar_excecao_instancia(zona, payload):
    if not isinstance(payload, dict):
        raise ValidationError("Exceção postal inválida.")

    excecao = ZonaEntregaExcecaoPostal(
        zona_entrega=zona,
        codigo_postal=payload.get("codigo_postal"),
        tipo_excecao=(payload.get("tipo_excecao") or ZonaEntregaExcecaoPostal.TIPO_EXCLUIR).strip().upper(),
        ativa=bool(payload.get("ativa", True)),
        observacao=(payload.get("observacao") or "").strip(),
        cp4="0000",
        cp7_num=0,
    )
    excecao.full_clean()
    return excecao


@permission_required(PERMISSOES_ZONA_ENTREGA["acessar"], raise_exception=True)
def cadastro_zona_entrega_view(request):
    template = "zona_entrega_cadastro.html"
    nome_form = "cadZonaEntrega"
    nome_form_cons = "consZonaEntrega"
    usuario = getattr(request, "user", None)
    acoes_permitidas = obter_acoes_permitidas(usuario)

    schema = {
        nome_form: {
            "filial_id": {"type": "string", "required": True, "value": ""},
            "codigo": {"type": "string", "maxlength": 20, "minlength": 2, "required": True, "value": ""},
            "descricao": {"type": "string", "maxlength": 100, "minlength": 3, "required": True, "value": ""},
            "prioridade": {"type": "string", "required": False, "value": "0"},
            "valor_cobranca_unitario_pedido": {"type": "string", "required": False, "value": "0.00"},
            "valor_pagamento_unitario_entrega": {"type": "string", "required": False, "value": "0.00"},
            "valor_pagamento_fixo_rota": {"type": "string", "required": False, "value": "0.00"},
            "valor_pagamento_unitario_entrega_pesado": {"type": "string", "required": False, "value": "0.00"},
            "valor_pagamento_fixo_rota_pesado": {"type": "string", "required": False, "value": "0.00"},
            "observacao": {"type": "string", "maxlength": 500, "required": False, "value": ""},
            "ativa": {"type": "boolean", "required": False, "value": True},
        },
        nome_form_cons: {
            "filial_cons": {"type": "string", "required": False, "value": ""},
            "codigo_cons": {"type": "string", "maxlength": 20, "required": False, "value": ""},
            "descricao_cons": {"type": "string", "maxlength": 100, "required": False, "value": ""},
            "id_selecionado": {"type": "integer", "required": False, "value": None},
        },
    }

    if request.method == "GET":
        request.sisvar_extra = build_sisvar_payload(
            schema=schema,
            forms={
                nome_form: build_form_state(
                    estado="novo" if acoes_permitidas["incluir"] else "visualizar",
                    campos=build_zona_campos_iniciais(),
                ),
                nome_form_cons: build_form_state(
                    campos={
                        "filial_cons": "",
                        "codigo_cons": "",
                        "descricao_cons": "",
                        "id_selecionado": None,
                    },
                ),
            },
            permissions={"zona_entrega": acoes_permitidas},
            datasets={"filiais_atuacao": listar_filiais_logisticas(usuario)},
        )
        return render(request, template)

    data_front = request.sisvar_front
    form = data_front.get("form", {}).get(nome_form, {})
    campos = form.get("campos", {})
    estado = form.get("estado", "")

    if estado == "novo" and not acoes_permitidas["incluir"]:
        return resposta_sem_permissao("Você não possui permissão para incluir zona de entrega.")
    if estado == "editar" and not acoes_permitidas["editar"]:
        return resposta_sem_permissao("Você não possui permissão para editar zona de entrega.")

    validator = SchemaValidator(schema[nome_form])
    if not validator.validate(campos):
        erros = [f"{campo} - {', '.join(msgs)}" for campo, msgs in validator.get_errors().items()]
        return JsonResponse(build_error_payload(erros), status=400)

    faixas = campos.get("faixas", [])
    excecoes = campos.get("excecoes", [])
    if not isinstance(faixas, list):
        return JsonResponse(build_error_payload("Lista de faixas postais inválida."), status=400)
    if not isinstance(excecoes, list):
        return JsonResponse(build_error_payload("Lista de exceções postais inválida."), status=400)

    filial = obter_filial_logistica(campos.get("filial_id"), usuario)
    if not filial:
        return JsonResponse(build_error_payload("Matriz/filial inválida para a zona de entrega ou sem vínculo de escrita."), status=403)
    if not filial.pais_atuacao_id:
        return JsonResponse(build_error_payload("A matriz/filial selecionada não possui país de atuação cadastrado."), status=422)

    zona_id = campos.get("id")
    codigo = (campos.get("codigo") or "").strip().upper()
    descricao = (campos.get("descricao") or "").strip().upper()
    observacao = (campos.get("observacao") or "").strip()

    try:
        prioridade = int(campos.get("prioridade") or 0)
    except (TypeError, ValueError):
        return JsonResponse(build_error_payload("Prioridade inválida."), status=422)

    try:
        with transaction.atomic():
            if estado == "novo":
                zona = ZonaEntrega(
                    filial=filial,
                    codigo=codigo,
                    descricao=descricao,
                    prioridade=prioridade,
                    valor_cobranca_unitario_pedido=campos.get("valor_cobranca_unitario_pedido") or 0,
                    valor_pagamento_unitario_entrega=campos.get("valor_pagamento_unitario_entrega") or 0,
                    valor_pagamento_fixo_rota=campos.get("valor_pagamento_fixo_rota") or 0,
                    valor_pagamento_unitario_entrega_pesado=campos.get("valor_pagamento_unitario_entrega_pesado") or 0,
                    valor_pagamento_fixo_rota_pesado=campos.get("valor_pagamento_fixo_rota_pesado") or 0,
                    observacao=observacao,
                    ativa=bool(campos.get("ativa", True)),
                )
                before = {}
            elif estado == "editar":
                zona = ZonaEntrega.all_objects.filter(id=zona_id, is_deleted=False).first()
                if not zona:
                    return JsonResponse(build_error_payload("Registro não encontrado."), status=404)
                before = snapshot_instance(zona)
                zona.filial = filial
                zona.codigo = codigo
                zona.descricao = descricao
                zona.prioridade = prioridade
                zona.valor_cobranca_unitario_pedido = campos.get("valor_cobranca_unitario_pedido") or 0
                zona.valor_pagamento_unitario_entrega = campos.get("valor_pagamento_unitario_entrega") or 0
                zona.valor_pagamento_fixo_rota = campos.get("valor_pagamento_fixo_rota") or 0
                zona.valor_pagamento_unitario_entrega_pesado = campos.get("valor_pagamento_unitario_entrega_pesado") or 0
                zona.valor_pagamento_fixo_rota_pesado = campos.get("valor_pagamento_fixo_rota_pesado") or 0
                zona.observacao = observacao
                zona.ativa = bool(campos.get("ativa", True))
            else:
                return JsonResponse(build_error_payload(f"Estado inválido: '{estado}'"), status=400)

            zona.save()

            ZonaEntregaFaixaPostal.objects.filter(zona_entrega=zona).delete()
            ZonaEntregaExcecaoPostal.objects.filter(zona_entrega=zona).delete()

            faixas_instancias = [criar_faixa_instancia(zona, item) for item in faixas]
            excecoes_instancias = [criar_excecao_instancia(zona, item) for item in excecoes]

            ZonaEntregaFaixaPostal.objects.bulk_create(faixas_instancias)
            ZonaEntregaExcecaoPostal.objects.bulk_create(excecoes_instancias)

            after = snapshot_instance(zona)
            extra_data = {
                "faixas": serializar_faixas(zona),
                "excecoes": serializar_excecoes(zona),
            }
            registrar_auditoria(
                actor=request.user,
                action=AuditEvent.ACTION_CREATE if estado == "novo" else AuditEvent.ACTION_UPDATE,
                instance=zona,
                changed_fields=diff_snapshots(before, after),
                extra_data=extra_data,
            )
    except ValidationError as exc:
        return JsonResponse(build_error_payload(extrair_mensagens_validacao(exc)), status=422)

    zona.refresh_from_db()
    return JsonResponse(build_form_response(
        form_id=nome_form,
        estado="visualizar",
        update=None,
        campos=serializar_form_zona(zona),
        mensagem_sucesso="Zona de entrega salva com sucesso!",
    ))


@permission_required(PERMISSOES_ZONA_ENTREGA["consultar"], raise_exception=True)
def cadastro_zona_entrega_cons_view(request):
    nome_form = "cadZonaEntrega"
    nome_form_cons = "consZonaEntrega"

    if request.method != "POST":
        return JsonResponse(build_error_payload("Método não permitido."), status=405)

    data_front = request.sisvar_front
    form = data_front.get("form", {}).get(nome_form_cons, {})
    campos = form.get("campos", {})
    id_selecionado = campos.get("id_selecionado")
    usuario = getattr(request, "user", None)
    filiais_escrita_ids = list(get_filiais_escrita_queryset(usuario).values_list("id", flat=True))

    if id_selecionado:
        zona = ZonaEntrega.objects.filter(id=id_selecionado, is_deleted=False, filial_id__in=filiais_escrita_ids).first()
        if not zona:
            return JsonResponse(build_error_payload("Registro não encontrado."), status=404)

        return JsonResponse(build_form_response(
            form_id=nome_form,
            estado="visualizar",
            update=None,
            campos=serializar_form_zona(zona),
        ))

    filial_cons = campos.get("filial_cons")
    codigo_cons = (campos.get("codigo_cons") or "").strip().upper()
    descricao_cons = (campos.get("descricao_cons") or "").strip().upper()

    queryset = ZonaEntrega.objects.filter(is_deleted=False, filial_id__in=filiais_escrita_ids).select_related("filial__pais_atuacao").order_by("filial__nome", "descricao")
    if filial_cons:
        queryset = queryset.filter(filial_id=filial_cons)
    if codigo_cons:
        queryset = queryset.filter(codigo__icontains=codigo_cons)
    if descricao_cons:
        queryset = queryset.filter(descricao__icontains=descricao_cons)

    registros = [
        {
            "id": zona.id,
            "filial": f"{zona.filial.codigo} - {zona.filial.nome}",
            "pais_atuacao": zona.filial.pais_atuacao.sigla if zona.filial.pais_atuacao_id else "",
            "codigo": zona.codigo,
            "descricao": zona.descricao,
            "ativa": zona.ativa,
        }
        for zona in queryset
    ]

    return JsonResponse(build_records_response(registros))


@permission_required(PERMISSOES_ZONA_ENTREGA["acessar"], raise_exception=True)
def cadastro_zona_entrega_del_view(request):
    nome_form = "cadZonaEntrega"
    usuario = getattr(request, "user", None)

    if not usuario or not usuario.has_perm(PERMISSOES_ZONA_ENTREGA["excluir"]):
        return resposta_sem_permissao("Você não possui permissão para excluir zona de entrega.")

    if request.method != "POST":
        return JsonResponse(build_error_payload("Método não permitido."), status=405)

    zona_id = request.sisvar_front.get("form", {}).get(nome_form, {}).get("campos", {}).get("id")
    zona = ZonaEntrega.objects.filter(id=zona_id, is_deleted=False).first()
    if not zona:
        return JsonResponse(build_error_payload("Registro não encontrado."), status=404)

    if not usuario.is_superuser:
        possui_vinculo_escrita = UsuarioFilial.objects.filter(
            usuario=usuario,
            filial=zona.filial,
            ativo=True,
            pode_escrever=True,
        ).exists()
        if not possui_vinculo_escrita:
            return JsonResponse(build_error_payload("Você não possui vínculo de escrita para excluir rotas desta matriz/filial."), status=403)

    before = snapshot_instance(zona)
    zona.soft_delete(user=request.user, reason="Exclusão via cadastro de zona de entrega")
    zona.save()

    registrar_auditoria(
        actor=request.user,
        action=AuditEvent.ACTION_SOFT_DELETE,
        instance=zona,
        changed_fields=before,
    )

    return JsonResponse(build_success_payload("Zona de entrega excluída com sucesso!"))
