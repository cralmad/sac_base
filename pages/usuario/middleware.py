import json
from django.shortcuts import redirect
from rest_framework_simplejwt.authentication import JWTAuthentication
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

        # --- Lógica de Autenticação Original  ---
        path = request.path
        token = request.COOKIES.get("access_token")

        if token:
            try:
                validated = self.jwt_auth.get_validated_token(token)
                request.user = self.jwt_auth.get_user(validated)
                request.user_data = validated.payload
            except InvalidToken:
                pass

        if any(path.startswith(r) for r in ROTAS_PUBLICAS):
            return self.get_response(request)

        if not token:
            return redirect("/app/usuario/login/")

        try:
            validated = self.jwt_auth.get_validated_token(token)
            request.user = self.jwt_auth.get_user(validated)
            request.user_data = validated.payload
        except InvalidToken:
            return redirect("/app/usuario/login/")

        return self.get_response(request)