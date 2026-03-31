from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from sac_base.form_validador import SchemaValidator


def cadastro_grupo_view(request):
    template    = "permissao.html"
    nomeForm    = "cadGrupo"
    nomeFormCons = "consGrupo"

    schema = {
        nomeForm: {
            "nome":  {'type': 'string', 'maxlength': 80, 'minlength': 3, 'required': True, 'value': ''},
            "ativo": {'type': 'boolean', 'required': False, 'value': None},
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
                        "ativo":      None,
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
    ativo       = campos.get("ativo", False)
    permissoes  = campos.get("permissoes", [])   # lista de codenames: ["app.acao_model", ...]
    grupo       = None

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
                        "campos": {"id": None, "nome": "", "ativo": None, "permissoes": []}
                    }
                },
                "mensagens": {"sucesso": {"ignorar": True, "conteudo": ["Grupo excluído com sucesso!"]}}
            })

        case _:
            return JsonResponse({
                "mensagens": {"erro": {"conteudo": [f"Estado inválido: '{estado}'"], "ignorar": False}}
            }, status=400)

    # Atualiza permissões do grupo
    # permissoes recebidas: ["cad_cliente.add_cliente", "auth.view_group", ...]
    perm_objects = []
    for codename_full in permissoes:
        try:
            app_label, codename = codename_full.split(".", 1)
            ct = ContentType.objects.get(app_label=app_label)
            perm = Permission.objects.get(content_type=ct, codename=codename)
            perm_objects.append(perm)
        except (ValueError, ContentType.DoesNotExist, Permission.DoesNotExist):
            pass  # permissão inválida ou não encontrada: ignora silenciosamente

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
                    "ativo":      True,
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
                                "ativo":      True,
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