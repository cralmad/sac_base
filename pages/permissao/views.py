from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from sac_base.form_validador import SchemaValidator

User = get_user_model()


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


def serializar_form_permissao_usuario(usuario):
    return {
        "estado": "visualizar",
        "update": None,
        "campos": {
            "usuario_id": usuario.id,
            "grupos": list(usuario.groups.order_by("name").values_list("id", flat=True)),
            "permissoes": serializar_permissoes_usuario(usuario),
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


def cadastro_grupo_view(request):
    template    = "permissao.html"
    nomeForm    = "cadGrupo"
    nomeFormCons = "consGrupo"

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
        request.sisvar_extra = {
            "schema": schema,
            "form": {
                nomeForm: {
                    "estado": "novo",
                    "update": None,
                    "campos": {
                        "id":         None,
                        "nome":       "",
                        "permissoes": [],
                    }
                },
                nomeFormCons: {
                    "estado": "novo",
                    "campos": {
                        "nome_cons":      "",
                        "id_selecionado": None,
                    }
                }
            }
        }
        return render(request, template)

    # ---------- POST ----------
    dataFront = request.sisvar_front
    form      = dataFront.get("form", {}).get(nomeForm, {})
    campos    = form.get("campos", {})
    estado    = form.get("estado", "")

    # Validação de schema
    validator = SchemaValidator(schema[nomeForm])
    if not validator.validate(campos):
        erros = [
            f"{campo} - {', '.join(msgs)}"
            for campo, msgs in validator.get_errors().items()
        ]
        return JsonResponse({
            "mensagens": {"erro": {"conteudo": erros, "ignorar": False}}
        }, status=400)

    id_grupo    = campos.get("id")
    nome        = campos.get("nome", "").strip().upper()
    permissoes  = campos.get("permissoes", [])   # lista de codenames: ["app.acao_model", ...]
    grupo       = None

    if not isinstance(permissoes, list):
        return JsonResponse({
            "mensagens": {"erro": {"conteudo": ["Lista de permissões inválida"], "ignorar": False}}
        }, status=400)

    # Carrega registro existente no modo editar
    if id_grupo:
        try:
            grupo = Group.objects.get(id=id_grupo)
        except Group.DoesNotExist:
            return JsonResponse({
                "mensagens": {"erro": {"conteudo": ["Registro não encontrado"], "ignorar": False}}
            }, status=404)

    # Validação: nome duplicado
    qs_nome = Group.objects.filter(name=nome)
    if id_grupo:
        qs_nome = qs_nome.exclude(id=id_grupo)
    if qs_nome.exists():
        return JsonResponse({
            "mensagens": {"erro": {"conteudo": ["Já existe um grupo com este nome"], "ignorar": False}}
        }, status=422)

    perm_objects, permissoes_invalidas = resolver_permissoes(permissoes)
    if permissoes_invalidas:
        return JsonResponse({
            "mensagens": {
                "erro": {
                    "conteudo": [f"Permissões inválidas: {', '.join(sorted(permissoes_invalidas))}"],
                    "ignorar": False
                }
            }
        }, status=422)

    match estado:

        case 'novo':
            grupo = Group.objects.create(name=nome)

        case 'editar':
            grupo.name = nome
            grupo.save()

        case 'excluir':
            if not id_grupo:
                return JsonResponse({
                    "mensagens": {"erro": {"conteudo": ["ID não informado para exclusão"], "ignorar": False}}
                }, status=400)
            grupo.delete()
            return JsonResponse({
                "success": True,
                "form": {
                    nomeForm: {
                        "estado": "novo",
                        "update": None,
                        "campos": {"id": None, "nome": "", "permissoes": []}
                    }
                },
                "mensagens": {"sucesso": {"ignorar": True, "conteudo": ["Grupo excluído com sucesso!"]}}
            })

        case _:
            return JsonResponse({
                "mensagens": {"erro": {"conteudo": [f"Estado inválido: '{estado}'"], "ignorar": False}}
            }, status=400)

    grupo.permissions.set(perm_objects)

    # Monta lista de codenames salvos para retorno ao front
    permissoes_salvas = list(
        grupo.permissions.values_list(
            'content_type__app_label', 'codename'
        )
    )
    permissoes_salvas_fmt = [f"{a}.{c}" for a, c in permissoes_salvas]

    return JsonResponse({
        "success": True,
        "form": {
            nomeForm: {
                "estado": "visualizar",
                "update": None,
                "campos": {
                    "id":         grupo.id,
                    "nome":       grupo.name,
                    "permissoes": permissoes_salvas_fmt,
                }
            }
        },
        "mensagens": {"sucesso": {"ignorar": True, "conteudo": ["Operação realizada com sucesso!"]}}
    })


def cadastro_grupo_cons_view(request):
    """
    Consulta/pesquisa de grupos. Padrão idêntico ao cadastro_cons_view de usuário.
    """
    nomeForm     = "cadGrupo"
    nomeFormCons = "consGrupo"

    if request.method == "POST":
        dataFront = request.sisvar_front
        form      = dataFront.get("form", {}).get(nomeFormCons, {})
        campos    = form.get("campos", {})

        id_selecionado = int(campos.get("id_selecionado") or 0)

        if id_selecionado:
            try:
                grupo = Group.objects.get(id=id_selecionado)
                permissoes_fmt = [
                    f"{a}.{c}"
                    for a, c in grupo.permissions.values_list(
                        'content_type__app_label', 'codename'
                    )
                ]
                return JsonResponse({
                    "form": {
                        nomeForm: {
                            "estado": "visualizar",
                            "update": None,
                            "campos": {
                                "id":         grupo.id,
                                "nome":       grupo.name,
                                "permissoes": permissoes_fmt,
                            }
                        }
                    }
                })
            except Group.DoesNotExist:
                return JsonResponse({
                    "mensagens": {"erro": {"conteudo": ["Registro não encontrado"], "ignorar": False}}
                }, status=404)

        nome_filtro = campos.get("nome_cons", "").strip()
        filtros = {}
        if nome_filtro:
            filtros["name__icontains"] = nome_filtro

        grupos = Group.objects.filter(**filtros).values("id", "name")
        return JsonResponse({"registros": list(grupos)})


def permissao_usuario_view(request):
    template = "permissao_usuario.html"
    nomeForm = "cadPermissaoUsuario"
    nomeFormCons = "consPermissaoUsuario"

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
        request.sisvar_extra = {
            "schema": schema,
            "form": {
                nomeForm: {
                    "estado": "novo",
                    "update": None,
                    "campos": {
                        "usuario_id": None,
                        "grupos": [],
                        "permissoes": [],
                    }
                },
                nomeFormCons: {
                    "estado": "novo",
                    "campos": {
                        "first_name_cons": "",
                        "username_cons": "",
                        "id_selecionado": None,
                    }
                }
            },
            "others": {
                "usuarios_ativos": listar_usuarios_ativos(operador),
                "grupos_cadastrados": listar_grupos_cadastrados(),
                "grupos_gerenciaveis_ids": listar_ids_grupos_gerenciaveis(operador),
                "permissoes_gerenciaveis": sorted(obter_permissoes_gerenciaveis(operador)),
            }
        }
        return render(request, template)

    dataFront = request.sisvar_front
    form = dataFront.get("form", {}).get(nomeForm, {})
    campos = form.get("campos", {})
    estado = form.get("estado", "")

    validator = SchemaValidator(schema[nomeForm])
    if not validator.validate(campos):
        erros = [
            f"{campo} - {', '.join(msgs)}"
            for campo, msgs in validator.get_errors().items()
        ]
        return JsonResponse({
            "mensagens": {"erro": {"conteudo": erros, "ignorar": False}}
        }, status=400)

    try:
        usuario_id = int(campos.get("usuario_id"))
    except (TypeError, ValueError):
        return JsonResponse({
            "mensagens": {"erro": {"conteudo": ["Usuário inválido"], "ignorar": False}}
        }, status=400)

    grupos = campos.get("grupos", [])
    permissoes = campos.get("permissoes", [])

    if not isinstance(grupos, list):
        return JsonResponse({
            "mensagens": {"erro": {"conteudo": ["Lista de grupos inválida"], "ignorar": False}}
        }, status=400)

    if not isinstance(permissoes, list):
        return JsonResponse({
            "mensagens": {"erro": {"conteudo": ["Lista de permissões inválida"], "ignorar": False}}
        }, status=400)

    operador = getattr(request, "user", None)
    permissoes_gerenciaveis = obter_permissoes_gerenciaveis(operador)
    grupos_gerenciaveis_ids = set(listar_ids_grupos_gerenciaveis(operador))

    usuario = buscar_usuario_alvo(usuario_id, operador)
    if not usuario:
        return JsonResponse({
            "mensagens": {"erro": {"conteudo": ["Usuário elegível não encontrado"], "ignorar": False}}
        }, status=404)

    grupos_obj, grupos_invalidos = resolver_grupos(grupos)
    if grupos_invalidos:
        return JsonResponse({
            "mensagens": {
                "erro": {
                    "conteudo": [f"Grupos inválidos: {', '.join(sorted(grupos_invalidos))}"],
                    "ignorar": False
                }
            }
        }, status=422)

    permissoes_obj, permissoes_invalidas = resolver_permissoes(permissoes)
    if permissoes_invalidas:
        return JsonResponse({
            "mensagens": {
                "erro": {
                    "conteudo": [f"Permissões inválidas: {', '.join(sorted(permissoes_invalidas))}"],
                    "ignorar": False
                }
            }
        }, status=422)

    grupos_sem_alcada = sorted(
        str(grupo.id) for grupo in grupos_obj if grupo.id not in grupos_gerenciaveis_ids
    )
    if grupos_sem_alcada:
        return JsonResponse({
            "mensagens": {
                "erro": {
                    "conteudo": [
                        f"Você só pode atribuir grupos dentro do seu escopo: {', '.join(grupos_sem_alcada)}"
                    ],
                    "ignorar": False
                }
            }
        }, status=403)

    permissoes_sem_alcada = sorted(
        codename for codename in permissoes if codename not in permissoes_gerenciaveis
    )
    if permissoes_sem_alcada:
        return JsonResponse({
            "mensagens": {
                "erro": {
                    "conteudo": [
                        "Você só pode atribuir permissões que já possui: "
                        f"{', '.join(permissoes_sem_alcada)}"
                    ],
                    "ignorar": False
                }
            }
        }, status=403)

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
        case _:
            return JsonResponse({
                "mensagens": {"erro": {"conteudo": [f"Estado inválido: '{estado}'"], "ignorar": False}}
            }, status=400)

    return JsonResponse({
        "success": True,
        "form": {
            nomeForm: serializar_form_permissao_usuario(usuario)
        },
        "mensagens": {
            "sucesso": {
                "ignorar": True,
                "conteudo": ["Permissões do usuário atualizadas com sucesso!"]
            }
        }
    })


def permissao_usuario_cons_view(request):
    nomeForm = "cadPermissaoUsuario"
    nomeFormCons = "consPermissaoUsuario"

    if request.method != "POST":
        return JsonResponse({
            "mensagens": {"erro": {"conteudo": ["Método não permitido"], "ignorar": False}}
        }, status=405)

    dataFront = request.sisvar_front
    form = dataFront.get("form", {}).get(nomeFormCons, {})
    campos = form.get("campos", {})
    operador = getattr(request, "user", None)

    id_selecionado = int(campos.get("id_selecionado") or 0)

    if id_selecionado:
        usuario = buscar_usuario_alvo(id_selecionado, operador)
        if not usuario:
            return JsonResponse({
                "mensagens": {"erro": {"conteudo": ["Usuário elegível não encontrado"], "ignorar": False}}
            }, status=404)

        return JsonResponse({
            "success": True,
            "form": {
                nomeForm: serializar_form_permissao_usuario(usuario)
            }
        })

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

    return JsonResponse({"success": True, "registros": registros})