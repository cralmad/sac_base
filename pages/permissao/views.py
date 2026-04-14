from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import permission_required
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from pages.auditoria.models import AuditEvent
from pages.auditoria.utils import diff_snapshots, registrar_auditoria
from pages.filial.models import Filial, UsuarioFilial
from sac_base.permissions_utils import build_action_permissions, permission_denied_response
from sac_base.form_validador import SchemaValidator
from sac_base.sisvar_builders import build_error_payload, build_form_response, build_form_state, build_forms_response, build_records_response, build_sisvar_payload

User = get_user_model()


def snapshot_auth_group(grupo):
    return {
        "name": grupo.name,
        "permissions": sorted(
            f"{app_label}.{codename}"
            for app_label, codename in grupo.permissions.values_list(
                "content_type__app_label", "codename"
            )
        ),
    }


def snapshot_usuario_permissoes(usuario):
    return {
        "grupos": list(usuario.groups.order_by("name").values_list("id", flat=True)),
        "permissoes": sorted(serializar_permissoes_usuario(usuario)),
        "filiais": serializar_vinculos_filial_usuario(usuario),
    }


PERMISSOES_GRUPO = {
    "acessar": "auth.view_group",
    "consultar": "auth.view_group",
    "incluir": "auth.add_group",
    "editar": "auth.change_group",
    "excluir": "auth.delete_group",
}

PERMISSOES_PERMISSAO_USUARIO = {
    "acessar": "usuario.view_usuarios",
    "consultar": "usuario.view_usuarios",
    "editar": "usuario.change_usuarios",
}


def resolver_permissoes(codenames):
    perm_objects = []
    permissoes_invalidas = []

    for codename_full in codenames:
        try:
            app_label, codename = codename_full.split(".", 1)
            perm = Permission.objects.get(content_type__app_label=app_label, codename=codename)
            perm_objects.append(perm)
        except (ValueError, Permission.DoesNotExist, Permission.MultipleObjectsReturned):
            permissoes_invalidas.append(codename_full)

    return perm_objects, permissoes_invalidas


def get_queryset_usuarios_alvo(usuario_logado=None):
    usuarios = User.objects.filter(is_active=True, is_superuser=False)

    if usuario_logado and getattr(usuario_logado, "is_authenticated", False):
        usuarios = usuarios.exclude(id=usuario_logado.id)

    return usuarios.order_by("first_name", "username")


def listar_usuarios_ativos(usuario_logado=None):
    usuarios = get_queryset_usuarios_alvo(usuario_logado)
    return [
        {
            "id": usuario.id,
            "nome": usuario.first_name or usuario.username,
            "username": usuario.username,
        }
        for usuario in usuarios
    ]


def listar_grupos_cadastrados():
    grupos = Group.objects.order_by("name")
    return [{"id": grupo.id, "nome": grupo.name} for grupo in grupos]


def listar_filiais_cadastradas():
    filiais = Filial.objects.order_by("nome")
    return [
        {
            "id": filial.id,
            "codigo": filial.codigo,
            "nome": filial.nome,
            "is_matriz": filial.is_matriz,
            "ativa": filial.ativa,
        }
        for filial in filiais
    ]


def listar_todas_permissoes_disponiveis():
    return {
        f"{app_label}.{codename}"
        for app_label, codename in Permission.objects.values_list(
            "content_type__app_label", "codename"
        )
    }


def obter_permissoes_gerenciaveis(usuario):
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return set()

    if usuario.is_superuser:
        return listar_todas_permissoes_disponiveis()

    return set(usuario.get_all_permissions())


def grupo_para_codenames(grupo):
    return {
        f"{app_label}.{codename}"
        for app_label, codename in grupo.permissions.values_list(
            "content_type__app_label", "codename"
        )
    }


def listar_ids_grupos_gerenciaveis(usuario):
    permissoes_gerenciaveis = obter_permissoes_gerenciaveis(usuario)
    grupos = Group.objects.order_by("name").prefetch_related("permissions__content_type")

    return [
        grupo.id
        for grupo in grupos
        if grupo_para_codenames(grupo).issubset(permissoes_gerenciaveis)
    ]


def buscar_usuario_alvo(usuario_id, usuario_logado=None):
    usuario = User.objects.filter(id=usuario_id, is_active=True, is_superuser=False).first()

    if (
        usuario
        and usuario_logado
        and getattr(usuario_logado, "is_authenticated", False)
        and usuario.id == usuario_logado.id
    ):
        return None

    return usuario


def serializar_permissoes_usuario(usuario):
    permissoes = list(
        usuario.user_permissions.values_list(
            "content_type__app_label", "codename"
        )
    )
    return [f"{app_label}.{codename}" for app_label, codename in permissoes]


def serializar_vinculos_filial_usuario(usuario):
    vinculos = UsuarioFilial.objects.filter(usuario=usuario).select_related("filial").order_by("filial__nome")
    return [
        {
            "filial_id": vinculo.filial_id,
            "ativo": vinculo.ativo,
            "pode_consultar": bool(vinculo.pode_consultar or vinculo.pode_escrever),
            "pode_escrever": vinculo.pode_escrever,
        }
        for vinculo in vinculos
    ]


def serializar_form_permissao_usuario(usuario):
    return {
        "estado": "visualizar",
        "update": None,
        "campos": {
            "usuario_id": usuario.id,
            "grupos": list(usuario.groups.order_by("name").values_list("id", flat=True)),
            "permissoes": serializar_permissoes_usuario(usuario),
            "filiais": serializar_vinculos_filial_usuario(usuario),
        }
    }


def resolver_grupos(grupo_ids):
    ids_normalizados = []
    grupos_invalidos = []

    for grupo_id in grupo_ids:
        try:
            ids_normalizados.append(int(grupo_id))
        except (TypeError, ValueError):
            grupos_invalidos.append(str(grupo_id))

    ids_unicos = list(dict.fromkeys(ids_normalizados))
    grupos = list(Group.objects.filter(id__in=ids_unicos))
    grupos_por_id = {grupo.id: grupo for grupo in grupos}

    for grupo_id in ids_unicos:
        if grupo_id not in grupos_por_id:
            grupos_invalidos.append(str(grupo_id))

    grupos_ordenados = [grupos_por_id[grupo_id] for grupo_id in ids_unicos if grupo_id in grupos_por_id]
    return grupos_ordenados, grupos_invalidos


def resolver_vinculos_filial(vinculos_payload):
    if not isinstance(vinculos_payload, list):
        return None, ["Lista de matriz/filial inválida"]

    vinculos_normalizados = []
    filiais_invalidas = []
    ids_vistos = set()

    for item in vinculos_payload:
        if not isinstance(item, dict):
            filiais_invalidas.append("Formato inválido em matriz/filial")
            continue

        filial_id = item.get("filial_id")
        try:
            filial_id = int(filial_id)
        except (TypeError, ValueError):
            filiais_invalidas.append(f"Matriz/filial inválida: {filial_id}")
            continue

        if filial_id in ids_vistos:
            filiais_invalidas.append(f"Matriz/filial duplicada: {filial_id}")
            continue

        ids_vistos.add(filial_id)
        vinculos_normalizados.append({
            "filial_id": filial_id,
            "ativo": bool(item.get("ativo")),
            "pode_consultar": bool(item.get("pode_consultar")),
            "pode_escrever": bool(item.get("pode_escrever")),
        })

    filiais = Filial.objects.filter(id__in=ids_vistos)
    filiais_por_id = {filial.id: filial for filial in filiais}
    for filial_id in ids_vistos:
        if filial_id not in filiais_por_id:
            filiais_invalidas.append(f"Matriz/filial inválida: {filial_id}")

    return vinculos_normalizados, filiais_invalidas


@permission_required(PERMISSOES_GRUPO["acessar"], raise_exception=True)
def cadastro_grupo_view(request):
    template    = "permissao.html"
    nomeForm    = "cadGrupo"
    nomeFormCons = "consGrupo"
    acoes_permitidas = build_action_permissions(getattr(request, "user", None), PERMISSOES_GRUPO)

    schema = {
        nomeForm: {
            "nome":  {'type': 'string', 'maxlength': 80, 'minlength': 3, 'required': True, 'value': ''},
        },
        nomeFormCons: {
            "nome_cons":        {'type': 'string', 'maxlength': 80},
            "id_selecionado":   {'type': 'integer'},
        }
    }

    # ---------- GET ----------
    if request.method == "GET":
        request.sisvar_extra = build_sisvar_payload(
            schema=schema,
            forms={
                nomeForm: build_form_state(
                    estado="novo" if acoes_permitidas["incluir"] else "visualizar",
                    campos={
                        "id": None,
                        "nome": "",
                        "permissoes": [],
                    },
                ),
                nomeFormCons: build_form_state(
                    campos={
                        "nome_cons": "",
                        "id_selecionado": None,
                    },
                ),
            },
            permissions={
                "permissao_grupo": acoes_permitidas,
            },
        )
        return render(request, template)

    # ---------- POST ----------
    dataFront = request.sisvar_front
    form      = dataFront.get("form", {}).get(nomeForm, {})
    campos    = form.get("campos", {})
    estado    = form.get("estado", "")

    if estado == 'novo' and not acoes_permitidas['incluir']:
        return permission_denied_response('Você não possui permissão para incluir grupos de permissão.')

    if estado == 'editar' and not acoes_permitidas['editar']:
        return permission_denied_response('Você não possui permissão para editar grupos de permissão.')

    if estado == 'excluir' and not acoes_permitidas['excluir']:
        return permission_denied_response('Você não possui permissão para excluir grupos de permissão.')

    # Validação de schema
    validator = SchemaValidator(schema[nomeForm])
    if not validator.validate(campos):
        erros = [
            f"{campo} - {', '.join(msgs)}"
            for campo, msgs in validator.get_errors().items()
        ]
        return JsonResponse(build_error_payload(erros), status=400)

    id_grupo    = campos.get("id")
    nome        = campos.get("nome", "").strip().upper()
    permissoes  = campos.get("permissoes", [])   # lista de codenames: ["app.acao_model", ...]
    grupo       = None

    if not isinstance(permissoes, list):
        return JsonResponse(build_error_payload("Lista de permissões inválida"), status=400)

    # Carrega registro existente no modo editar
    if id_grupo:
        try:
            grupo = Group.objects.get(id=id_grupo)
        except Group.DoesNotExist:
            return JsonResponse(build_error_payload("Registro não encontrado"), status=404)
        before = snapshot_auth_group(grupo)
    else:
        before = {}

    # Validação: nome duplicado
    qs_nome = Group.objects.filter(name=nome)
    if id_grupo:
        qs_nome = qs_nome.exclude(id=id_grupo)
    if qs_nome.exists():
        return JsonResponse(build_error_payload("Já existe um grupo com este nome"), status=422)

    perm_objects, permissoes_invalidas = resolver_permissoes(permissoes)
    if permissoes_invalidas:
        return JsonResponse(
            build_error_payload(f"Permissões inválidas: {', '.join(sorted(permissoes_invalidas))}"),
            status=422,
        )

    match estado:

        case 'novo':
            grupo = Group.objects.create(name=nome)

        case 'editar':
            grupo.name = nome
            grupo.save()

        case 'excluir':
            if not id_grupo:
                return JsonResponse(build_error_payload("ID não informado para exclusão"), status=400)
            registrar_auditoria(
                actor=request.user,
                action=AuditEvent.ACTION_DELETE,
                instance=grupo,
                changed_fields=before,
            )
            grupo.delete()
            return JsonResponse(build_form_response(
                form_id=nomeForm,
                estado="novo",
                update=None,
                campos={"id": None, "nome": "", "permissoes": []},
                mensagem_sucesso="Grupo excluído com sucesso!",
            ))

        case _:
            return JsonResponse(build_error_payload(f"Estado inválido: '{estado}'"), status=400)

    grupo.permissions.set(perm_objects)
    after = snapshot_auth_group(grupo)
    registrar_auditoria(
        actor=request.user,
        action=AuditEvent.ACTION_CREATE if estado == 'novo' else AuditEvent.ACTION_UPDATE,
        instance=grupo,
        changed_fields=diff_snapshots(before, after),
    )

    # Monta lista de codenames salvos para retorno ao front
    permissoes_salvas = list(
        grupo.permissions.values_list(
            'content_type__app_label', 'codename'
        )
    )
    permissoes_salvas_fmt = [f"{a}.{c}" for a, c in permissoes_salvas]

    return JsonResponse(build_form_response(
        form_id=nomeForm,
        estado="visualizar",
        update=None,
        campos={
            "id": grupo.id,
            "nome": grupo.name,
            "permissoes": permissoes_salvas_fmt,
        },
        mensagem_sucesso="Operação realizada com sucesso!",
    ))


@permission_required(PERMISSOES_GRUPO["consultar"], raise_exception=True)
def cadastro_grupo_cons_view(request):
    """
    Consulta/pesquisa de grupos. Padrão idêntico ao cadastro_cons_view de usuário.
    """
    nomeForm     = "cadGrupo"
    nomeFormCons = "consGrupo"

    if request.method != "POST":
        return JsonResponse(build_error_payload("Método não permitido."), status=405)

    dataFront = request.sisvar_front
    form = dataFront.get("form", {}).get(nomeFormCons, {})
    campos = form.get("campos", {})

    id_selecionado = int(campos.get("id_selecionado") or 0)

    if id_selecionado:
        try:
            grupo = Group.objects.get(id=id_selecionado)
            permissoes_fmt = [
                f"{a}.{c}"
                for a, c in grupo.permissions.values_list(
                    "content_type__app_label", "codename"
                )
            ]
            return JsonResponse(build_form_response(
                form_id=nomeForm,
                estado="visualizar",
                update=None,
                campos={
                    "id": grupo.id,
                    "nome": grupo.name,
                    "permissoes": permissoes_fmt,
                },
            ))
        except Group.DoesNotExist:
            return JsonResponse(build_error_payload("Registro não encontrado"), status=404)

    nome_filtro = campos.get("nome_cons", "").strip()
    filtros = {}
    if nome_filtro:
        filtros["name__icontains"] = nome_filtro

    grupos = Group.objects.filter(**filtros).values("id", "name")
    return JsonResponse(build_records_response(list(grupos)))


@permission_required(PERMISSOES_PERMISSAO_USUARIO["acessar"], raise_exception=True)
def permissao_usuario_view(request):
    template = "permissao_usuario.html"
    nomeForm = "cadPermissaoUsuario"
    nomeFormCons = "consPermissaoUsuario"
    acoes_permitidas = build_action_permissions(getattr(request, "user", None), PERMISSOES_PERMISSAO_USUARIO)

    schema = {
        nomeForm: {
            "usuario_id": {'type': 'integer', 'required': True, 'value': None},
        },
        nomeFormCons: {
            "first_name_cons": {'type': 'string', 'maxlength': 80, 'value': ''},
            "username_cons": {'type': 'string', 'maxlength': 80, 'value': ''},
            "id_selecionado": {'type': 'integer', 'value': None},
        }
    }

    if request.method == "GET":
        operador = getattr(request, "user", None)
        request.sisvar_extra = build_sisvar_payload(
            schema=schema,
            forms={
                nomeForm: build_form_state(
                    campos={
                        "usuario_id": None,
                        "grupos": [],
                        "permissoes": [],
                        "filiais": [],
                    },
                ),
                nomeFormCons: build_form_state(
                    campos={
                        "first_name_cons": "",
                        "username_cons": "",
                        "id_selecionado": None,
                    },
                ),
            },
            permissions={
                "permissao_usuario": acoes_permitidas,
            },
            datasets={
                "usuarios_ativos": listar_usuarios_ativos(operador),
                "grupos_cadastrados": listar_grupos_cadastrados(),
                "filiais_cadastradas": listar_filiais_cadastradas(),
                "grupos_gerenciaveis_ids": listar_ids_grupos_gerenciaveis(operador),
                "permissoes_gerenciaveis": sorted(obter_permissoes_gerenciaveis(operador)),
            },
        )
        return render(request, template)

    dataFront = request.sisvar_front
    form = dataFront.get("form", {}).get(nomeForm, {})
    campos = form.get("campos", {})
    estado = form.get("estado", "")

    if estado in {'novo', 'editar'} and not acoes_permitidas['editar']:
        return permission_denied_response('Você não possui permissão para alterar permissões de usuários.')

    validator = SchemaValidator(schema[nomeForm])
    if not validator.validate(campos):
        erros = [
            f"{campo} - {', '.join(msgs)}"
            for campo, msgs in validator.get_errors().items()
        ]
        return JsonResponse(build_error_payload(erros), status=400)

    try:
        usuario_id = int(campos.get("usuario_id"))
    except (TypeError, ValueError):
        return JsonResponse(build_error_payload("Usuário inválido"), status=400)

    grupos = campos.get("grupos", [])
    permissoes = campos.get("permissoes", [])
    filiais = campos.get("filiais", [])

    if not isinstance(grupos, list):
        return JsonResponse(build_error_payload("Lista de grupos inválida"), status=400)

    if not isinstance(permissoes, list):
        return JsonResponse(build_error_payload("Lista de permissões inválida"), status=400)

    if not isinstance(filiais, list):
        return JsonResponse(build_error_payload("Lista de matriz/filial inválida"), status=400)

    operador = getattr(request, "user", None)
    permissoes_gerenciaveis = obter_permissoes_gerenciaveis(operador)
    grupos_gerenciaveis_ids = set(listar_ids_grupos_gerenciaveis(operador))

    usuario = buscar_usuario_alvo(usuario_id, operador)
    if not usuario:
        return JsonResponse(build_error_payload("Usuário elegível não encontrado"), status=404)
    before = snapshot_usuario_permissoes(usuario)

    grupos_obj, grupos_invalidos = resolver_grupos(grupos)
    if grupos_invalidos:
        return JsonResponse(
            build_error_payload(f"Grupos inválidos: {', '.join(sorted(grupos_invalidos))}"),
            status=422,
        )

    permissoes_obj, permissoes_invalidas = resolver_permissoes(permissoes)
    if permissoes_invalidas:
        return JsonResponse(
            build_error_payload(f"Permissões inválidas: {', '.join(sorted(permissoes_invalidas))}"),
            status=422,
        )

    vinculos_filial, filiais_invalidas = resolver_vinculos_filial(filiais)
    if filiais_invalidas:
        return JsonResponse(
            build_error_payload([f"Matriz e Filiais - {mensagem}" for mensagem in filiais_invalidas]),
            status=422,
        )

    grupos_sem_alcada = sorted(
        str(grupo.id) for grupo in grupos_obj if grupo.id not in grupos_gerenciaveis_ids
    )
    if grupos_sem_alcada:
        return JsonResponse(
            build_error_payload(
                f"Você só pode atribuir grupos dentro do seu escopo: {', '.join(grupos_sem_alcada)}"
            ),
            status=403,
        )

    permissoes_sem_alcada = sorted(
        codename for codename in permissoes if codename not in permissoes_gerenciaveis
    )
    if permissoes_sem_alcada:
        return JsonResponse(
            build_error_payload(
                "Você só pode atribuir permissões que já possui: "
                f"{', '.join(permissoes_sem_alcada)}"
            ),
            status=403,
        )

    match estado:
        case 'novo' | 'editar':
            grupos_preservados = [
                grupo
                for grupo in usuario.groups.prefetch_related("permissions__content_type")
                if grupo.id not in grupos_gerenciaveis_ids
            ]
            permissoes_preservadas = [
                permissao
                for permissao in usuario.user_permissions.select_related("content_type")
                if f"{permissao.content_type.app_label}.{permissao.codename}" not in permissoes_gerenciaveis
            ]

            usuario.groups.set([*grupos_preservados, *grupos_obj])
            usuario.user_permissions.set([*permissoes_preservadas, *permissoes_obj])
            UsuarioFilial.objects.filter(usuario=usuario).delete()
            UsuarioFilial.objects.bulk_create([
                UsuarioFilial(
                    usuario=usuario,
                    filial_id=vinculo["filial_id"],
                    ativo=vinculo["ativo"],
                    pode_consultar=bool(vinculo["ativo"] and (vinculo["pode_consultar"] or vinculo["pode_escrever"])),
                    pode_escrever=bool(vinculo["ativo"] and vinculo["pode_escrever"]),
                )
                for vinculo in vinculos_filial
            ])
            after = snapshot_usuario_permissoes(usuario)
            registrar_auditoria(
                actor=request.user,
                action=AuditEvent.ACTION_PERMISSION_ASSIGN,
                instance=usuario,
                changed_fields=diff_snapshots(before, after),
            )
        case _:
            return JsonResponse(build_error_payload(f"Estado inválido: '{estado}'"), status=400)

    return JsonResponse(build_forms_response(
        forms={
            nomeForm: serializar_form_permissao_usuario(usuario),
        },
        mensagem_sucesso="Permissões do usuário atualizadas com sucesso!",
    ))


@permission_required(PERMISSOES_PERMISSAO_USUARIO["consultar"], raise_exception=True)
def permissao_usuario_cons_view(request):
    nomeForm = "cadPermissaoUsuario"
    nomeFormCons = "consPermissaoUsuario"

    if request.method != "POST":
        return JsonResponse(build_error_payload("Método não permitido"), status=405)

    dataFront = request.sisvar_front
    form = dataFront.get("form", {}).get(nomeFormCons, {})
    campos = form.get("campos", {})
    operador = getattr(request, "user", None)

    id_selecionado = int(campos.get("id_selecionado") or 0)

    if id_selecionado:
        usuario = buscar_usuario_alvo(id_selecionado, operador)
        if not usuario:
            return JsonResponse(build_error_payload("Usuário elegível não encontrado"), status=404)

        return JsonResponse(build_forms_response(
            forms={
                nomeForm: serializar_form_permissao_usuario(usuario),
            },
        ))

    nome_filtro = campos.get("first_name_cons", "").strip()
    username_filtro = campos.get("username_cons", "").strip()

    usuarios = get_queryset_usuarios_alvo(operador)
    if nome_filtro:
        usuarios = usuarios.filter(first_name__icontains=nome_filtro)
    if username_filtro:
        usuarios = usuarios.filter(username__icontains=username_filtro)

    registros = [
        {
            "id": usuario.id,
            "first_name": usuario.first_name,
            "username": usuario.username,
        }
        for usuario in usuarios
    ]

    return JsonResponse(build_records_response(registros))