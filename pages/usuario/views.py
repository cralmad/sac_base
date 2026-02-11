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
        form = payload["form"]["loginForm"]["campos"]
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
            "username": {'type': 'string', 'maxlength': 20, 'minlength': 3, 'required': True},
            "first_name": {'type': 'string', 'maxlength': 30, 'minlength': 3, 'required': True},
            "email": {'type': 'string', 'maxlength': 60, 'required': True},
            "password": {'type': 'password', 'required': True},
            "confirmpass": {'type': 'password', 'required': True},
            "ativo": {'type': 'boolean', 'required': False}
        },
        nomeFormCons: {
            "username_cons": {'type': 'string', 'maxlength': 20},
            "first_name_cons": {'type': 'string', 'maxlength': 30},
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

    dataFront = request.sisvar_front
    form = dataFront.get("form", {}).get(nomeForm, {})
    campos = form.get("campos", {})
    estado = form.get("estado", "")

    # Validação dos campos do formulário ################################
    validator = SchemaValidator(schema[nomeForm])
    if not validator.validate(campos):
        errosList = validator.get_errors()
        errosForm = [
            f"{campo} - {', '.join(erros)}"
            for campo, erros in errosList.items()
        ]
        return JsonResponse({
            "mensagens": {"erro": {"conteudo": [errosForm], "ignorar": False}}
        }, status=400)
    #######################################################################

    id_user = campos.get("id", None)
    nome_user = campos.get("username")
    nome = campos.get("first_name")
    email = campos.get("email")
    password = campos.get("password")
    ativo = campos.get("ativo")
    confirmpass = campos.get("confirmpass")
    reg_user = None
    
    if id_user: reg_user = Usuarios.objects.get(id=id_user)

    # Validações do formulário  ###############################################
    if User.objects.filter(username=nome_user).exists():
        return JsonResponse({
            "mensagens": {
                "erro": {
                    "conteudo": ["Usuário já existe"],
                    "ignorar": False
                }
            }
        })
    if password != confirmpass:
        return JsonResponse({
            "mensagens": {
                "erro": {
                    "conteudo": ["Senha e confirmação de senha não coincidem"],
                    "ignorar": False
                }
            }
        })
    ############################################################################

    match estado:
        case 'novo':
            usuario = Usuarios.objects.create(
                username=nome_user,
                first_name=nome,
                email=email,
                password=make_password(password),
                is_active=(ativo == True)
            )
        
        case 'editar':
            reg_user.first_name = nome_user
            reg_user.email = email

            if campos.get("password"):
                reg_user.password = make_password(campos["password"])

            reg_user.save()

        case 'excluir':
            reg_user.is_active = False
            reg_user.save()

    # ===== RESPOSTA JSON (editar / visualizar / excluir) =====
    return JsonResponse({
        "form": {
            nomeForm: {
                "estado": "visualizar",
                "update": usuario.date_joined,
                "campos": {
                    "id": usuario.id,
                    "username": usuario.username,
                    "first_name": usuario.first_name,
                    "email": usuario.email,
                    "password": "",
                    "confirmpass": "",
                    "ativo": usuario.is_active
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
    
    # Esquema para validação no front-end (opcional, seguindo o padrão do login)
    schema = {
        "alterarSenhaForm": {
            'senha_atual': {'type': 'password', 'required': True},
            'nova_senha': {'type': 'password', 'required': True},
            'confirmar_senha': {'type': 'password', 'required': True}
        }
    }

    # ---------- GET ----------
    if request.method == "GET":
        request.sisvar_extra = {
            "schema": schema,
            "form": {
                "alterarSenhaForm": {
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
    try:
        payload = request.sisvar_front
        form = payload.get("form", {}).get("alterarSenhaForm", {}).get("campos", {})
        
        senha_atual = form.get("senha_atual")
        nova_senha = form.get("nova_senha")
        confirmar = form.get("confirmar_senha")
    except (KeyError, json.JSONDecodeError, AttributeError):
        return JsonResponse(
            {"mensagens": {"erro": {"ignorar": False, "conteudo": ["Payload inválido"]}}},
            status=400
        )

    mensagens_erro = []
    user = request.user

    # Validações de Negócio
    if not user.is_authenticated:
        return JsonResponse({"mensagens": {"erro": {"ignorar": False, "conteudo": ["Usuário não autenticado"]}}}, status=401)

    if not user.check_password(senha_atual):
        mensagens_erro.append("Senha atual inválida.")

    if nova_senha != confirmar:
        mensagens_erro.append("Nova senha e confirmação não coincidem.")

    try:
        validate_password(nova_senha, user)
    except ValidationError as e:
        mensagens_erro.extend(e.messages)

    # Retorno de Erros em formato JSON
    if mensagens_erro:
        return JsonResponse(
            {"mensagens": {"erro": {"ignorar": False, "conteudo": mensagens_erro}}},
            status=400
        )

    # Persistência
    user.set_password(nova_senha)
    user.save()
    update_session_auth_hash(request, user)

    # Retorno de Sucesso em formato JSON
    return JsonResponse({
        "success": True,
        "mensagens": {
            "sucesso": {
                "ignorar": False,
                "conteudo": ["Senha alterada com sucesso."]
            }
        }
    })

def cadastro_cons_view(request):
    nomeForm = "consUsuario"

    if request.method == "POST":
        dataFront = request.sisvar_front
        form = dataFront.get("form", {}).get(nomeForm, {})
        campos = form.get("campos", {})

        id_selecionado = campos.get('id_selecionado')

        if id_selecionado:
            try:
                user = Usuarios.objects.get(id=id_selecionado)
                return JsonResponse({
                    "form": {
                        nomeForm: {
                            "estado": "visualizar",
                            "update": user.date_joined,
                            "campos": {
                                "id": user.id,
                                "username": user.username,
                                "first_name": user.first_name,
                                "email": user.email,
                                "password": "",
                                "confirmpass": "",
                                "ativo": user.is_active
                            }
                        }
                    }
                })
            except Usuarios.DoesNotExist:
                return JsonResponse({"erro": "Registro não encontrado"}, status=404)

        nome = campos.get('first_name_cons', '').strip()
        username = campos.get('username_cons', '').strip()

        filtros = {}
        if nome: filtros['first_name__icontains'] = nome
        if username: filtros['username__icontains'] = username

        usuarios = Usuarios.objects.filter(**filtros).values('id', 'first_name', 'username')
        
        return JsonResponse({"registros": list(usuarios)})