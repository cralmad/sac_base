import json
from django.http import JsonResponse
from django.contrib.auth import authenticate, get_user_model, update_session_auth_hash
from django.shortcuts import render, redirect
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.hashers import make_password
from pages.usuario.models import Usuarios
from sac_base.form_validador import SchemaValidator

User = get_user_model()

def login_view(request):
    
    request.sisvar_extra = {}

    schema = { "loginForm": {
        'username': {'type': 'string', 'maxlength': 50, 'required': True},
        'password': {'type': 'password', 'required': True}
        }
    }

    formulario = {"loginForm": {"estado": "novo", "update": None, "campos": {}}}
    
    # ---------- GET ----------
    if request.method == "GET":

        request.sisvar_extra |= {"schema": schema} | {"form": formulario}  
        return render(request, "login.html")

    # ---------- POST ----------
    try:
        payload = request.sisvar_front
        form = payload["form"]["loginForm"].get("campos")
        username = form.get("username")
        password = form.get("password")
    except (KeyError, json.JSONDecodeError):
        return JsonResponse(
            {"mensagens": {"erro": {"ignorar": False, "conteudo": ["Payload inválido"]}}},
            status=400
        )

    user = authenticate(username=username, password=password)
    if not user:
        return JsonResponse(
            {"mensagens": {"erro": {"ignorar": True, "conteudo": ["Credenciais inválidas"]}}},
            status=401
        )

    refresh = RefreshToken.for_user(user)

    response = JsonResponse({
        "success": True,
        "user": {
            "id": user.id,
            "username": user.username
        }
    })

    response.set_cookie(
        "access_token",
        str(refresh.access_token),
        httponly=True,
        samesite="Lax"
    )
    response.set_cookie(
        "refresh_token",
        str(refresh),
        httponly=True,
        samesite="Lax",
        max_age=60 * 60 * 24 * 7
    )

    return response

def logout_view(request):
    response = redirect("/login/")
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response

def cadastro_view(request):
    template = "usuario.html"
    nomeForm = "cadUsuario"
    nomeFormCons = "consUsuario"

    schema = {
        nomeForm: {
            "username":    {'type': 'string',  'maxlength': 20, 'minlength': 3, 'required': True,  'value': ''},
            "first_name":  {'type': 'string',  'maxlength': 30, 'minlength': 3, 'required': True,  'value': ''},
            "email":       {'type': 'string',  'maxlength': 60, 'required': True,  'value': ''},
            "password":    {'type': 'password', 'required': True,  'value': ''},
            "confirmpass": {'type': 'password', 'required': True,  'value': ''},
            "ativo":       {'type': 'boolean', 'required': False, 'value': None}
        },
        nomeFormCons: {
            "username_cons": {'type': 'string', 'maxlength': 20},
            "first_name_cons":{'type': 'string', 'maxlength': 30},
            "email_cons": {'type': 'string', 'maxlength': 60},
            "ativo_cons": {'type': 'boolean'},
            "id_selecionado": {'type': 'integer'}
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
                        "id": None,
                        "username": "",
                        "first_name": "",
                        "email": "",
                        "password": "",
                        "confirmpass": "",
                        "ativo": None
                    }
                },
                nomeFormCons: {
                    "estado": "novo",
                    "campos": {
                        "username_cons": "",
                        "first_name_cons": "",
                        "email_cons": "",
                        "ativo_cons": None,
                        "id_selecionado": None
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

    # Validação de schema #####################################################
    validator = SchemaValidator(schema[nomeForm])
    if not validator.validate(campos):
        errosForm = [
            f"{campo} - {', '.join(erros)}"
            for campo, erros in validator.get_errors().items()
        ]
        return JsonResponse({
            "mensagens": {"erro": {"conteudo": errosForm, "ignorar": False}}
        }, status=400)
    ###########################################################################

    id_user     = campos.get("id")
    nome_user   = campos.get("username")
    nome        = campos.get("first_name")
    email       = campos.get("email")
    password    = campos.get("password")
    confirmpass = campos.get("confirmpass")
    ativo       = campos.get("ativo")
    usuario     = None

    # Carrega o registro existente quando há ID (editar) ######################
    if id_user:
        try:
            usuario = Usuarios.objects.get(id=id_user)
        except Usuarios.DoesNotExist:
            return JsonResponse({
                "mensagens": {"erro": {"conteudo": ["Registro não encontrado"], "ignorar": False}}
            }, status=404)
    ###########################################################################

    # Validações de negócio ###################################################

    # Username duplicado — exclui o próprio registro na edição
    qs_username = User.objects.filter(username=nome_user)
    if id_user:
        qs_username = qs_username.exclude(id=id_user)
    if qs_username.exists():
        return JsonResponse({
            "mensagens": {"erro": {"conteudo": ["Usuário já existe"], "ignorar": False}}
        }, status=422)

    # Senhas coincidem (obrigatório em 'novo'; opcional em 'editar' se informada)
    if estado == 'novo' or password:
        if password != confirmpass:
            return JsonResponse({
                "mensagens": {"erro": {"conteudo": ["Senha e confirmação de senha não coincidem"], "ignorar": False}}
            }, status=422)

    ###########################################################################

    match estado:

        case 'novo':
            usuario = Usuarios.objects.create(
                username=nome_user,
                first_name=nome,
                email=email,
                password=make_password(password),
                is_active=bool(ativo)
            )

        case 'editar':
            usuario.username   = nome_user
            usuario.first_name = nome
            usuario.email      = email
            usuario.is_active  = bool(ativo)

            # Senha só é alterada se o usuário informou um novo valor
            if password:
                usuario.password = make_password(password)

            usuario.save()

        case _:
            return JsonResponse({
                "mensagens": {"erro": {"conteudo": [f"Estado inválido: '{estado}'"], "ignorar": False}}
            }, status=400)

    # ===== RESPOSTA JSON =====
    return JsonResponse({
        "success": True,
        "form": {
            nomeForm: {
                "estado": "visualizar",
                "update": usuario.date_joined,
                "campos": {
                    "id":          usuario.id,
                    "username":    usuario.username,
                    "first_name":  usuario.first_name,
                    "email":       usuario.email,
                    "password":    "",
                    "confirmpass": "",
                    "ativo":       usuario.is_active
                }
            }
        },
        "mensagens": {
            "sucesso": {
                "ignorar": True,
                "conteudo": ["Operação realizada com sucesso!"]
            }
        }
    })

def alterar_senha_view(request):
    template = "alterarsenha.html"
    nomeForm = "alterarSenhaForm"

    schema = {
        nomeForm: {
            'senha_atual':     {'type': 'password', 'required': True},
            'nova_senha':      {'type': 'password', 'required': True},
            'confirmar_senha': {'type': 'password', 'required': True}
        }
    }

    # ---------- GET ----------
    if request.method == "GET":
        request.sisvar_extra = {
            "schema": schema,
            "form": {
                nomeForm: {
                    "estado": "editar",
                    "update": None,
                    "campos": {
                        "senha_atual": "",
                        "nova_senha": "",
                        "confirmar_senha": "",
                    }
                }
            }
        }
        return render(request, template)

    # ---------- POST ----------

    # Defesa em profundidade: o middleware já garante autenticação,
    # mas verificamos aqui como salvaguarda adicional.
    user = request.user
    if not user.is_authenticated:
        return JsonResponse(
            {"mensagens": {"erro": {"ignorar": False, "conteudo": ["Usuário não autenticado"]}}},
            status=401
        )

    try:
        payload       = request.sisvar_front
        form          = payload.get("form", {}).get(nomeForm, {})
        campos        = form.get("campos", {})
        senha_atual   = campos.get("senha_atual")
        nova_senha    = campos.get("nova_senha")
        confirmar     = campos.get("confirmar_senha")
    except (KeyError, json.JSONDecodeError, AttributeError):
        return JsonResponse(
            {"mensagens": {"erro": {"ignorar": False, "conteudo": ["Payload inválido"]}}},
            status=400
        )

    # Validação de schema #####################################################
    validator = SchemaValidator(schema[nomeForm])
    if not validator.validate(campos):
        errosForm = [
            f"{campo} - {', '.join(erros)}"
            for campo, erros in validator.get_errors().items()
        ]
        return JsonResponse({
            "mensagens": {"erro": {"conteudo": errosForm, "ignorar": False}}
        }, status=400)
    ###########################################################################

    mensagens_erro = []

    if not user.check_password(senha_atual):
        mensagens_erro.append("Senha atual inválida.")

    if nova_senha != confirmar:
        mensagens_erro.append("Nova senha e confirmação não coincidem.")

    if nova_senha:
        try:
            validate_password(nova_senha, user)
        except ValidationError as e:
            mensagens_erro.extend(e.messages)

    if mensagens_erro:
        return JsonResponse(
            {"mensagens": {"erro": {"ignorar": False, "conteudo": mensagens_erro}}},
            status=400
        )

    user.set_password(nova_senha)
    user.save()
    update_session_auth_hash(request, user)

    return JsonResponse({
        "success": True,
        "form": {
            nomeForm: {
                "estado": "editar",
                "update": None,
                "campos": {
                    "senha_atual": "",
                    "nova_senha": "",
                    "confirmar_senha": "",
                }
            }
        },
        "mensagens": {
            "sucesso": {
                "ignorar": False,
                "conteudo": ["Senha alterada com sucesso."]
            }
        }
    })

def cadastro_cons_view(request):
    nomeForm     = "cadUsuario"
    nomeFormCons = "consUsuario"

    if request.method == "POST":
        dataFront = request.sisvar_front
        form      = dataFront.get("form", {}).get(nomeFormCons, {})
        campos    = form.get("campos", {})

        id_selecionado = int(campos.get('id_selecionado') or 0)

        if id_selecionado:
            try:
                # is_superuser=False garante que superusuários nunca sejam retornados
                usuario = Usuarios.objects.get(id=id_selecionado, is_superuser=False)
                return JsonResponse({
                    "form": {
                        nomeForm: {
                            "estado": "visualizar",
                            "update": usuario.date_joined,
                            "campos": {
                                "id":          usuario.id,
                                "username":    usuario.username,
                                "first_name":  usuario.first_name,
                                "email":       usuario.email,
                                "password":    "",
                                "confirmpass": "",
                                "ativo":       usuario.is_active
                            }
                        }
                    }
                })
            except Usuarios.DoesNotExist:
                return JsonResponse({
                    "mensagens": {"erro": {"conteudo": ["Registro não encontrado"], "ignorar": False}}
                }, status=404)

        nome      = campos.get('first_name_cons', '').strip()
        username  = campos.get('username_cons', '').strip()
        userAtivo = campos.get('ativo_cons', False)
        email     = campos.get('email_cons', '').strip()

        filtros = {}
        if nome:     filtros['first_name__icontains'] = nome
        if username: filtros['username__icontains']   = username
        if email:    filtros['email']                 = email
        filtros['is_active']    = userAtivo
        filtros['is_superuser'] = False  # exclui superusuários de todos os resultados

        usuarios = Usuarios.objects.filter(**filtros).values(
            'id', 'first_name', 'username', 'email', 'is_active'
        )

        return JsonResponse({"registros": list(usuarios)})
