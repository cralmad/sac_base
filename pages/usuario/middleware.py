import json
from django.shortcuts import redirect
from django.http import JsonResponse
from django.middleware.csrf import get_token
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
                corpo_json = json.loads(request.body)
                request.sisvar_front = corpo_json if isinstance(corpo_json, dict) else {}
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        # --- Lógica de Autenticação ---
        path = request.path
        if any(path.startswith(r) for r in ROTAS_PUBLICAS):
            return self.process_response(request, self.get_response(request))

        token = request.COOKIES.get("access_token")
        refresh_token = request.COOKIES.get("refresh_token")

        try:
            validated = self.jwt_auth.get_validated_token(token)
            request.user = self.jwt_auth.get_user(validated)
        except (InvalidToken, Exception):
            if refresh_token:
                try:
                    refresh = RefreshToken(refresh_token)
                    new_access_token = str(refresh.access_token)
                    
                    validated = self.jwt_auth.get_validated_token(new_access_token)
                    request.user = self.jwt_auth.get_user(validated)
                    
                    response = self.get_response(request)
                    response = self.process_response(request, response) # Injeta CSRF
                    response.set_cookie("access_token", new_access_token, httponly=True, samesite="Lax")
                    return response
                except Exception:
                    return redirect("/app/usuario/login/")
            else:
                return redirect("/app/usuario/login/")

        # Resposta padrão para usuários autenticados
        response = self.get_response(request)
        return self.process_response(request, response)

    def process_response(self, request, response):
        """
        Método auxiliar para injetar o csrfToken em qualquer JsonResponse 
        sem repetir código nos pontos de retorno do middleware.
        """
        if isinstance(response, JsonResponse) and response.status_code == 200:
            try:
                # Decodifica o JSON atual da resposta
                data = json.loads(response.content.decode('utf-8'))
                if isinstance(data, dict):
                    # Injeta o token atualizado para o front-end
                    data['csrfToken'] = get_token(request)
                    response.content = json.dumps(data)
            except Exception:
                pass
        return response