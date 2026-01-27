import json
from django.shortcuts import redirect
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import InvalidToken

ROTAS_PUBLICAS = [
    "/app/usuario/login/",
    "/app/usuario/logout/",
    "/static/",
]

class JWTAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.jwt_auth = JWTAuthentication()

    def __call__(self, request):
        # --- Captura da sisVar vinda do Front-End ---
        request.sisvar_front = {}

        if request.method == "POST" and request.content_type == "application/json":
            try:
                # O front-end envia apenas a variável sisVar 
                corpo_json = json.loads(request.body)
                # Alimenta o request para que o context_processor.py possa ler 
                request.sisvar_front = corpo_json if isinstance(corpo_json, dict) else {}
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        # --- Lógica de Autenticação ---
        path = request.path
        if any(path.startswith(r) for r in ROTAS_PUBLICAS):
            return self.get_response(request)

        token = request.COOKIES.get("access_token")
        refresh_token = request.COOKIES.get("refresh_token")

        try:
            # Tenta validar o access_token atual
            validated = self.jwt_auth.get_validated_token(token)
            request.user = self.jwt_auth.get_user(validated)
        except (InvalidToken, Exception):
            # Se o access_token falhou, tenta usar o refresh_token
            if refresh_token:
                try:
                    refresh = RefreshToken(refresh_token)
                    new_access_token = str(refresh.access_token)
                    
                    # Valida o novo token e anexa ao request
                    validated = self.jwt_auth.get_validated_token(new_access_token)
                    request.user = self.jwt_auth.get_user(validated)
                    
                    # Gera a resposta e renova o cookie do access_token
                    response = self.get_response(request)
                    response.set_cookie("access_token", new_access_token, httponly=True, samesite="Lax")
                    return response
                except Exception:
                    return redirect("/app/usuario/login/")
            else:
                return redirect("/app/usuario/login/")

        return self.get_response(request)