from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect, render

from pages.auditoria.models import AuditEvent
from pages.auditoria.utils import diff_snapshots, registrar_auditoria, snapshot_instance
from pages.core.models import Pais
from sac_base.form_validador import SchemaValidator
from sac_base.sisvar_builders import build_error_payload, build_form_response, build_form_state, build_records_response, build_sisvar_payload, build_success_payload

from .services import (
    ACTIVE_FILIAL_COOKIE,
    FILIAL_NO_ACCESS_PATH,
    listar_filiais_permitidas,
    obter_filial_unica_se_existir,
    serializar_filial,
    validar_filial_ativa,
)
from .models import Filial


PERMISSOES_FILIAL = {
    "acessar": "filial.view_filial",
    "consultar": "filial.view_filial",
    "incluir": "filial.add_filial",
    "editar": "filial.change_filial",
    "excluir": "filial.delete_filial",
}


def obter_acoes_permitidas_filial(usuario):
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return {acao: False for acao in PERMISSOES_FILIAL}

    return {
        acao: usuario.has_perm(codename)
        for acao, codename in PERMISSOES_FILIAL.items()
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

    return list(getattr(exc, "messages", [])) or [str(exc)]


def build_filial_campos_iniciais():
    primeira_unidade = not Filial.objects.exists()
    return {
        "id": None,
        "codigo": "",
        "nome": "",
        "pais_endereco_id": None,
        "pais_atuacao_id": None,
        "is_matriz": primeira_unidade,
        "ativa": True,
    }


def listar_paises_cadastrados():
    return [
        {
            "id": pais.id,
            "nome": pais.nome,
            "sigla": pais.sigla,
        }
        for pais in Pais.objects.order_by("nome")
    ]


def serializar_form_filial(filial):
    return {
        "id": filial.id,
        "codigo": filial.codigo,
        "nome": filial.nome,
        "pais_endereco_id": filial.pais_endereco_id,
        "pais_atuacao_id": filial.pais_atuacao_id,
        "is_matriz": filial.is_matriz,
        "ativa": filial.ativa,
    }


@permission_required(PERMISSOES_FILIAL["acessar"], raise_exception=True)
def cadastro_filial_view(request):
    template = "filial_cadastro.html"
    nome_form = "cadFilial"
    nome_form_cons = "consFilial"
    acoes_permitidas = obter_acoes_permitidas_filial(getattr(request, "user", None))
    primeira_unidade = not Filial.objects.exists()

    schema = {
        nome_form: {
            "codigo": {"type": "string", "maxlength": 20, "minlength": 2, "required": True, "value": ""},
            "nome": {"type": "string", "maxlength": 100, "minlength": 3, "required": True, "value": ""},
            "pais_endereco_id": {"type": "string", "required": True, "value": ""},
            "pais_atuacao_id": {"type": "string", "required": True, "value": ""},
            "is_matriz": {"type": "boolean", "required": False, "value": primeira_unidade},
            "ativa": {"type": "boolean", "required": False, "value": True},
        },
        nome_form_cons: {
            "codigo_cons": {"type": "string", "maxlength": 20, "required": False, "value": ""},
            "nome_cons": {"type": "string", "maxlength": 100, "required": False, "value": ""},
            "id_selecionado": {"type": "integer", "required": False, "value": None},
        },
    }

    if request.method == "GET":
        request.sisvar_extra = build_sisvar_payload(
            schema=schema,
            forms={
                nome_form: build_form_state(
                    estado="novo" if acoes_permitidas["incluir"] else "visualizar",
                    campos=build_filial_campos_iniciais(),
                ),
                nome_form_cons: build_form_state(
                    campos={
                        "codigo_cons": "",
                        "nome_cons": "",
                        "id_selecionado": None,
                    },
                ),
            },
            permissions={
                "filial": acoes_permitidas,
            },
            datasets={
                "paises_cadastrados": listar_paises_cadastrados(),
                "filialDefaults": {
                    "is_matriz": primeira_unidade,
                    "ativa": True,
                },
            },
        )
        return render(request, template)

    data_front = request.sisvar_front
    form = data_front.get("form", {}).get(nome_form, {})
    campos = form.get("campos", {})
    estado = form.get("estado", "")

    if estado == "novo" and not acoes_permitidas["incluir"]:
        return resposta_sem_permissao("Você não possui permissão para incluir matriz/filial.")

    if estado == "editar" and not acoes_permitidas["editar"]:
        return resposta_sem_permissao("Você não possui permissão para editar matriz/filial.")

    validator = SchemaValidator(schema[nome_form])
    if not validator.validate(campos):
        erros = [
            f"{campo} - {', '.join(msgs)}"
            for campo, msgs in validator.get_errors().items()
        ]
        return JsonResponse(build_error_payload(erros), status=400)

    filial_id = campos.get("id")
    codigo = (campos.get("codigo") or "").strip().upper()
    nome = (campos.get("nome") or "").strip().upper()
    pais_endereco_id = campos.get("pais_endereco_id")
    pais_atuacao_id = campos.get("pais_atuacao_id")
    is_matriz = bool(campos.get("is_matriz"))
    ativa = bool(campos.get("ativa"))

    try:
        pais_endereco = Pais.objects.get(id=int(pais_endereco_id))
    except (TypeError, ValueError, Pais.DoesNotExist):
        return JsonResponse(build_error_payload("País do endereço inválido."), status=422)

    try:
        pais_atuacao = Pais.objects.get(id=int(pais_atuacao_id))
    except (TypeError, ValueError, Pais.DoesNotExist):
        return JsonResponse(build_error_payload("País de atuação inválido."), status=422)

    match estado:
        case "novo":
            if Filial.objects.filter(codigo=codigo).exists():
                return JsonResponse(build_error_payload("Código já cadastrado."), status=422)
            if Filial.objects.filter(nome=nome).exists():
                return JsonResponse(build_error_payload("Nome já cadastrado."), status=422)

            try:
                filial = Filial.objects.create(
                    codigo=codigo,
                    nome=nome,
                    pais_endereco=pais_endereco,
                    pais_atuacao=pais_atuacao,
                    is_matriz=is_matriz,
                    ativa=ativa,
                )
            except ValidationError as exc:
                return JsonResponse(build_error_payload(extrair_mensagens_validacao(exc)), status=422)
            registrar_auditoria(
                actor=request.user,
                action=AuditEvent.ACTION_CREATE,
                instance=filial,
                changed_fields=diff_snapshots({}, snapshot_instance(filial)),
            )

        case "editar":
            try:
                filial = Filial.objects.get(id=filial_id)
            except Filial.DoesNotExist:
                return JsonResponse(build_error_payload("Registro não encontrado."), status=404)

            before = snapshot_instance(filial)
            if Filial.objects.filter(codigo=codigo).exclude(id=filial_id).exists():
                return JsonResponse(build_error_payload("Código já cadastrado."), status=422)
            if Filial.objects.filter(nome=nome).exclude(id=filial_id).exists():
                return JsonResponse(build_error_payload("Nome já cadastrado."), status=422)

            filial.codigo = codigo
            filial.nome = nome
            filial.pais_endereco = pais_endereco
            filial.pais_atuacao = pais_atuacao
            filial.is_matriz = is_matriz
            filial.ativa = ativa

            try:
                filial.save()
            except ValidationError as exc:
                return JsonResponse(build_error_payload(extrair_mensagens_validacao(exc)), status=422)

            changed_fields = diff_snapshots(before, snapshot_instance(filial))
            if changed_fields:
                registrar_auditoria(
                    actor=request.user,
                    action=AuditEvent.ACTION_UPDATE,
                    instance=filial,
                    changed_fields=changed_fields,
                )

        case _:
            return JsonResponse(build_error_payload(f"Estado inválido: '{estado}'"), status=400)

    return JsonResponse(build_form_response(
        form_id=nome_form,
        estado="visualizar",
        update=None,
        campos=serializar_form_filial(filial),
        mensagem_sucesso="Matriz/filial salva com sucesso!",
        extra_payload={
            "meta": {
                "datasets": {
                    "filialDefaults": {
                        "is_matriz": False,
                        "ativa": True,
                    }
                }
            }
        },
    ))


@permission_required(PERMISSOES_FILIAL["consultar"], raise_exception=True)
def cadastro_filial_cons_view(request):
    nome_form = "cadFilial"
    nome_form_cons = "consFilial"

    if request.method != "POST":
        return JsonResponse(build_error_payload("Método não permitido."), status=405)

    data_front = request.sisvar_front
    form = data_front.get("form", {}).get(nome_form_cons, {})
    campos = form.get("campos", {})

    id_selecionado = campos.get("id_selecionado")

    if id_selecionado:
        try:
            filial = Filial.objects.get(id=id_selecionado)
        except Filial.DoesNotExist:
            return JsonResponse(build_error_payload("Registro não encontrado."), status=404)

        return JsonResponse(build_form_response(
            form_id=nome_form,
            estado="visualizar",
            update=None,
            campos=serializar_form_filial(filial),
        ))

    codigo_cons = (campos.get("codigo_cons") or "").strip().upper()
    nome_cons = (campos.get("nome_cons") or "").strip().upper()

    queryset = Filial.objects.all().order_by("nome")
    if codigo_cons:
        queryset = queryset.filter(codigo__icontains=codigo_cons)
    if nome_cons:
        queryset = queryset.filter(nome__icontains=nome_cons)

    registros = [
        {
            "id": filial.id,
            "codigo": filial.codigo,
            "nome": filial.nome,
            "pais_atuacao": filial.pais_atuacao.sigla if filial.pais_atuacao_id else "",
            "tipo": "Matriz" if filial.is_matriz else "Filial",
            "ativa": filial.ativa,
        }
        for filial in queryset
    ]

    return JsonResponse(build_records_response(registros))


@permission_required(PERMISSOES_FILIAL["acessar"], raise_exception=True)
def cadastro_filial_del_view(request):
    nome_form = "cadFilial"
    usuario = getattr(request, "user", None)

    if not usuario or not usuario.has_perm(PERMISSOES_FILIAL["excluir"]):
        return resposta_sem_permissao("Você não possui permissão para excluir matriz/filial.")

    data_front = request.sisvar_front
    campos = data_front.get("form", {}).get(nome_form, {}).get("campos", {})
    filial_id = campos.get("id")

    if not filial_id:
        return JsonResponse(build_error_payload("ID não informado."), status=400)

    try:
        filial = Filial.objects.get(id=filial_id)
    except Filial.DoesNotExist:
        return JsonResponse(build_error_payload("Registro não encontrado."), status=404)

    if Filial.objects.count() == 1:
        return JsonResponse(build_error_payload("Não é permitido excluir a única matriz/filial cadastrada."), status=409)

    if filial.is_matriz and Filial.objects.exclude(id=filial.id).exists():
        return JsonResponse(build_error_payload("Não é permitido excluir a matriz enquanto existirem filiais cadastradas."), status=409)

    if filial.usuarios_vinculados.exists():
        return JsonResponse(build_error_payload("Esta matriz/filial não pode ser excluída pois possui usuários vinculados."), status=409)

    before = snapshot_instance(filial)
    registrar_auditoria(
        actor=request.user,
        action=AuditEvent.ACTION_DELETE,
        instance=filial,
        changed_fields=before,
    )
    filial.delete()

    return JsonResponse(build_success_payload(
        "Matriz/filial excluída com sucesso!",
        extra_payload={
            "meta": {
                "datasets": {
                    "filialDefaults": {
                        "is_matriz": False,
                        "ativa": True,
                    }
                }
            }
        },
    ))


@login_required
def selecionar_filial_view(request):
    if getattr(request, "filial_ativa", None) is not None:
        return redirect("/app/home/")

    filiais = listar_filiais_permitidas(request.user)

    if not filiais:
        return redirect(FILIAL_NO_ACCESS_PATH)

    filial_unica = obter_filial_unica_se_existir(request.user)
    if filial_unica:
        response = redirect("/app/home/")
        response.set_cookie(
            ACTIVE_FILIAL_COOKIE,
            str(filial_unica.id),
            httponly=settings.ACTIVE_FILIAL_COOKIE_HTTPONLY,
            samesite=settings.ACTIVE_FILIAL_COOKIE_SAMESITE,
            secure=settings.ACTIVE_FILIAL_COOKIE_SECURE,
        )
        return response

    if request.method == "GET":
        request.sisvar_extra = build_sisvar_payload(
            forms={
                "selecionarFilialForm": build_form_state(
                    estado="novo",
                    campos={"filial_id": None},
                )
            },
            datasets={
                "availableFiliais": [serializar_filial(filial) for filial in filiais],
            },
        )
        return render(request, "filial_selecionar.html")

    return JsonResponse(build_error_payload("Método não permitido."), status=405)


@login_required
def ativar_filial_view(request):
    if getattr(request, "filial_ativa", None) is not None:
        return JsonResponse(build_error_payload("Já existe uma matriz/filial ativa para a sessão atual."), status=409)

    if request.method != "POST":
        return JsonResponse(build_error_payload("Método não permitido."), status=405)

    filial_id = request.sisvar_front.get("form", {}).get("selecionarFilialForm", {}).get("campos", {}).get("filial_id")
    filial = validar_filial_ativa(request.user, filial_id)

    if not filial:
        return JsonResponse(build_error_payload("Matriz/filial inválida para o usuário autenticado."), status=403)

    response = JsonResponse(build_success_payload(extra_payload={"redirect": "/app/home/"}))
    response.set_cookie(
        ACTIVE_FILIAL_COOKIE,
        str(filial.id),
        httponly=settings.ACTIVE_FILIAL_COOKIE_HTTPONLY,
        samesite=settings.ACTIVE_FILIAL_COOKIE_SAMESITE,
        secure=settings.ACTIVE_FILIAL_COOKIE_SECURE,
    )
    return response


@login_required
def sem_acesso_filial_view(request):
    if getattr(request, "filial_ativa", None) is not None:
        return redirect("/app/home/")

    filiais = listar_filiais_permitidas(request.user)
    if filiais:
        filial_unica = obter_filial_unica_se_existir(request.user)
        if filial_unica:
            response = redirect("/app/home/")
            response.set_cookie(
                ACTIVE_FILIAL_COOKIE,
                str(filial_unica.id),
                httponly=settings.ACTIVE_FILIAL_COOKIE_HTTPONLY,
                samesite=settings.ACTIVE_FILIAL_COOKIE_SAMESITE,
                secure=settings.ACTIVE_FILIAL_COOKIE_SECURE,
            )
            return response

        return redirect("/app/usuario/filial/selecionar/")

    return render(request, "filial_sem_acesso.html")
