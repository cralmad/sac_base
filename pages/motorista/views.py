from django.contrib.auth.decorators import permission_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render

from pages.auditoria.models import AuditEvent
from pages.auditoria.utils import diff_snapshots, registrar_auditoria, snapshot_instance
from pages.filial.models import Filial, UsuarioFilial
from sac_base.form_validador import SchemaValidator
from sac_base.sisvar_builders import build_error_payload, build_form_response, build_form_state, build_records_response, build_sisvar_payload, build_success_payload

from .models import Motorista


PERMISSOES_MOTORISTA = {
    "acessar": "motorista.view_motorista",
    "consultar": "motorista.view_motorista",
    "incluir": "motorista.add_motorista",
    "editar": "motorista.change_motorista",
    "excluir": "motorista.delete_motorista",
}


def obter_acoes_permitidas(usuario):
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return {acao: False for acao in PERMISSOES_MOTORISTA}

    return {
        acao: usuario.has_perm(codename)
        for acao, codename in PERMISSOES_MOTORISTA.items()
    }


def resposta_sem_permissao(mensagem, status=403):
    return JsonResponse(build_error_payload(mensagem), status=status)


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
        {
            "id": filial.id,
            "codigo": filial.codigo,
            "nome": filial.nome,
            "pais_atuacao_sigla": filial.pais_atuacao.sigla if filial.pais_atuacao_id else "",
            "pais_atuacao_nome": filial.pais_atuacao.nome if filial.pais_atuacao_id else "",
        }
        for filial in get_filiais_escrita_queryset(usuario).order_by("nome")
    ]


def build_campos_iniciais():
    return {
        "id": None,
        "filial_id": None,
        "codigo": "",
        "nome": "",
        "telefone": "",
        "ativa": True,
    }


def serializar_form_motorista(motorista):
    return {
        "id": motorista.id,
        "filial_id": motorista.filial_id,
        "codigo": motorista.codigo,
        "nome": motorista.nome,
        "telefone": motorista.telefone,
        "ativa": motorista.ativa,
    }


def obter_filial_escrita(filial_id, usuario):
    try:
        filial_id = int(filial_id)
    except (TypeError, ValueError):
        return None

    return get_filiais_escrita_queryset(usuario).filter(id=filial_id).first()


@permission_required(PERMISSOES_MOTORISTA["acessar"], raise_exception=True)
def cadastro_motorista_view(request):
    template = "motorista_cadastro.html"
    nome_form = "cadMotorista"
    nome_form_cons = "consMotorista"
    usuario = getattr(request, "user", None)
    acoes_permitidas = obter_acoes_permitidas(usuario)

    schema = {
        nome_form: {
            "filial_id": {"type": "string", "required": True, "value": ""},
            "codigo": {"type": "string", "maxlength": 20, "required": False, "value": ""},
            "nome": {"type": "string", "maxlength": 100, "minlength": 3, "required": True, "value": ""},
            "telefone": {"type": "string", "maxlength": 20, "minlength": 8, "required": True, "value": ""},
            "ativa": {"type": "boolean", "required": False, "value": True},
        },
        nome_form_cons: {
            "filial_cons": {"type": "string", "required": False, "value": ""},
            "codigo_cons": {"type": "string", "maxlength": 20, "required": False, "value": ""},
            "nome_cons": {"type": "string", "maxlength": 100, "required": False, "value": ""},
            "telefone_cons": {"type": "string", "maxlength": 20, "required": False, "value": ""},
            "id_selecionado": {"type": "integer", "required": False, "value": None},
        },
    }

    if request.method == "GET":
        request.sisvar_extra = build_sisvar_payload(
            schema=schema,
            forms={
                nome_form: build_form_state(
                    estado="novo" if acoes_permitidas["incluir"] else "visualizar",
                    campos=build_campos_iniciais(),
                ),
                nome_form_cons: build_form_state(
                    campos={
                        "filial_cons": "",
                        "codigo_cons": "",
                        "nome_cons": "",
                        "telefone_cons": "",
                        "id_selecionado": None,
                    },
                ),
            },
            permissions={"motorista": acoes_permitidas},
            datasets={"filiais_escrita": listar_filiais_escrita(usuario)},
        )
        return render(request, template)

    data_front = request.sisvar_front
    form = data_front.get("form", {}).get(nome_form, {})
    campos = form.get("campos", {})
    estado = form.get("estado", "")

    if estado == "novo" and not acoes_permitidas["incluir"]:
        return resposta_sem_permissao("Você não possui permissão para incluir motorista.")
    if estado == "editar" and not acoes_permitidas["editar"]:
        return resposta_sem_permissao("Você não possui permissão para editar motorista.")

    validator = SchemaValidator(schema[nome_form])
    if not validator.validate(campos):
        erros = [f"{campo} - {', '.join(msgs)}" for campo, msgs in validator.get_errors().items()]
        return JsonResponse(build_error_payload(erros), status=400)

    filial = obter_filial_escrita(campos.get("filial_id"), usuario)
    if not filial:
        return JsonResponse(build_error_payload("Matriz/filial inválida para o motorista ou sem vínculo de escrita."), status=403)

    motorista_id = campos.get("id")
    codigo = (campos.get("codigo") or "").strip().upper()
    nome = (campos.get("nome") or "").strip().upper()
    telefone = (campos.get("telefone") or "").strip()
    ativa = bool(campos.get("ativa", True))
    filiais_escrita_ids = list(get_filiais_escrita_queryset(usuario).values_list("id", flat=True))

    try:
        with transaction.atomic():
            if estado == "novo":
                motorista = Motorista(
                    filial=filial,
                    codigo=codigo,
                    nome=nome,
                    telefone=telefone,
                    ativa=ativa,
                )
                before = {}
            elif estado == "editar":
                motorista = Motorista.all_objects.filter(
                    id=motorista_id,
                    is_deleted=False,
                    filial_id__in=filiais_escrita_ids,
                ).first()
                if not motorista:
                    return JsonResponse(build_error_payload("Registro não encontrado."), status=404)

                before = snapshot_instance(motorista)
                motorista.filial = filial
                motorista.codigo = codigo
                motorista.nome = nome
                motorista.telefone = telefone
                motorista.ativa = ativa
            else:
                return JsonResponse(build_error_payload(f"Estado inválido: '{estado}'"), status=400)

            motorista.save()

            registrar_auditoria(
                actor=request.user,
                action=AuditEvent.ACTION_CREATE if estado == "novo" else AuditEvent.ACTION_UPDATE,
                instance=motorista,
                changed_fields=diff_snapshots(before, snapshot_instance(motorista)),
            )
    except Exception as exc:
        return JsonResponse(build_error_payload(str(exc)), status=422)

    return JsonResponse(build_form_response(
        form_id=nome_form,
        estado="visualizar",
        update=None,
        campos=serializar_form_motorista(motorista),
        mensagem_sucesso="Motorista salvo com sucesso!",
    ))


@permission_required(PERMISSOES_MOTORISTA["consultar"], raise_exception=True)
def cadastro_motorista_cons_view(request):
    nome_form = "cadMotorista"
    nome_form_cons = "consMotorista"
    usuario = getattr(request, "user", None)
    filiais_escrita_ids = list(get_filiais_escrita_queryset(usuario).values_list("id", flat=True))

    if request.method != "POST":
        return JsonResponse(build_error_payload("Método não permitido."), status=405)

    data_front = request.sisvar_front
    form = data_front.get("form", {}).get(nome_form_cons, {})
    campos = form.get("campos", {})
    id_selecionado = campos.get("id_selecionado")

    if id_selecionado:
        motorista = Motorista.objects.filter(
            id=id_selecionado,
            is_deleted=False,
            filial_id__in=filiais_escrita_ids,
        ).first()
        if not motorista:
            return JsonResponse(build_error_payload("Registro não encontrado."), status=404)

        return JsonResponse(build_form_response(
            form_id=nome_form,
            estado="visualizar",
            update=None,
            campos=serializar_form_motorista(motorista),
        ))

    filial_cons = campos.get("filial_cons")
    codigo_cons = (campos.get("codigo_cons") or "").strip().upper()
    nome_cons = (campos.get("nome_cons") or "").strip().upper()
    telefone_cons = (campos.get("telefone_cons") or "").strip()

    queryset = Motorista.objects.filter(
        is_deleted=False,
        filial_id__in=filiais_escrita_ids,
    ).select_related("filial").order_by("nome")
    if filial_cons:
        queryset = queryset.filter(filial_id=filial_cons)
    if codigo_cons:
        queryset = queryset.filter(codigo__icontains=codigo_cons)
    if nome_cons:
        queryset = queryset.filter(nome__icontains=nome_cons)
    if telefone_cons:
        queryset = queryset.filter(telefone__icontains=telefone_cons)

    registros = [
        {
            "id": motorista.id,
            "filial": f"{motorista.filial.codigo} - {motorista.filial.nome}",
            "codigo": motorista.codigo,
            "nome": motorista.nome,
            "telefone": motorista.telefone,
            "ativa": motorista.ativa,
        }
        for motorista in queryset
    ]

    return JsonResponse(build_records_response(registros))


@permission_required(PERMISSOES_MOTORISTA["acessar"], raise_exception=True)
def cadastro_motorista_del_view(request):
    nome_form = "cadMotorista"
    usuario = getattr(request, "user", None)

    if not usuario or not usuario.has_perm(PERMISSOES_MOTORISTA["excluir"]):
        return resposta_sem_permissao("Você não possui permissão para excluir motorista.")

    if request.method != "POST":
        return JsonResponse(build_error_payload("Método não permitido."), status=405)

    motorista_id = request.sisvar_front.get("form", {}).get(nome_form, {}).get("campos", {}).get("id")
    filiais_escrita_ids = list(get_filiais_escrita_queryset(usuario).values_list("id", flat=True))
    motorista = Motorista.objects.filter(
        id=motorista_id,
        is_deleted=False,
        filial_id__in=filiais_escrita_ids,
    ).first()

    if not motorista:
        return JsonResponse(build_error_payload("Registro não encontrado."), status=404)

    before = snapshot_instance(motorista)
    motorista.soft_delete(user=request.user, reason="Exclusão via cadastro de motorista")
    motorista.save()

    registrar_auditoria(
        actor=request.user,
        action=AuditEvent.ACTION_SOFT_DELETE,
        instance=motorista,
        changed_fields=before,
    )

    return JsonResponse(build_success_payload("Motorista excluído com sucesso!"))
