import json
from django.http import JsonResponse
from django.contrib.auth import authenticate, get_user_model
from django.shortcuts import render, redirect
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

def login_view(request):
    schema = {
        'username': {'type': 'string', 'maxlength': 50, 'required': True},
        'password': {'type': 'password', 'required': True}
    }

    # ---------- GET ----------
    if request.method == "GET":
        return render(
            request,
            "login.html",
            {"sisVar": {"schema": schema, "usuario": {"autenticado":request.user.is_authenticated, "id":request.user.id}}}
        )

    # ---------- POST ----------
    try:
        payload = json.loads(request.body)
        form = payload["form"]["loginForm"]
        username = form.get("username")
        password = form.get("password")
    except (KeyError, json.JSONDecodeError):
        return JsonResponse(
            {"success": False, "error": "Payload inválido"},
            status=400
        )

    user = authenticate(username=username, password=password)
    if not user:
        return JsonResponse(
            {"success": False, "error": "Credenciais inválidas"},
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
        return render(request, "usuario.html",{"sisVar": {"usuario": {"autenticado":request.user.is_authenticated, "id":request.user.id, "nome":request.user.username, "permissoes":list(request.user.get_all_permissions())}}})

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
