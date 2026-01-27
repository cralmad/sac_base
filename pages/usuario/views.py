import json
from django.http import JsonResponse
from django.contrib.auth import authenticate, get_user_model, update_session_auth_hash
from django.shortcuts import render, redirect
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password

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
    if request.method == "GET":

        usuario = {
            "autenticado": getattr(request.user, "is_authenticated", False),
            "id": getattr(request.user, "id", None),
            "nome": getattr(request.user, "username", None),
            "permissoes": list(getattr(request.user, "get_all_permissions", lambda: [])())
        }

        return render(
            request,
            "usuario.html",
            {"sisVar": {"usuario": usuario}}
        )

    username = request.POST.get("username")
    email = request.POST.get("email")
    password = request.POST.get("password")

    if User.objects.filter(username=username).exists():
        return render(request, "usuario.html", {"erro": "Usuário já existe"})

    User.objects.create_user(
        username=username,
        email=email,
        password=password
    )

    return redirect("/login/")

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