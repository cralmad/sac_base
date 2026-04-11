import json
import logging
from django.shortcuts import redirect
from django.http import JsonResponse
from django.middleware.csrf import get_token
from pages.filial.services import ACTIVE_FILIAL_COOKIE, FILIAL_ACTIVATE_PATH, FILIAL_NO_ACCESS_PATH, FILIAL_SELECT_PATH, listar_filiais_permitidas, obter_filial_unica_se_existir, obter_nivel_acesso, validar_filial_ativa
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

logger = logging.getLogger(__name__)

ROTAS_PUBLICAS = [
    "/app/usuario/login/",
    "/app/usuario/logout/",
    "/static/",
]

ROTAS_AUTENTICADAS_SEM_FILIAL = [
    FILIAL_SELECT_PATH,
    FILIAL_ACTIVATE_PATH,
    FILIAL_NO_ACCESS_PATH,
]

# Headers que indicam que é uma requisição API
API_HEADERS = ["application/json", "application/api+json"]


class JWTAuthMiddleware:
    """
    Middleware de autenticação JWT que:
    - Gerencia tokens de acesso e refresh
    - Injeta CSRF token automaticamente em respostas JSON (sucesso e erro)
    - Captura dados do front-end em requisições JSON
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.jwt_auth = JWTAuthentication()

    def __call__(self, request):
        # --- Captura da sisVar vinda do Front-End ---
        request.sisvar_front = self._extract_json_body(request)
        request.filiais_permitidas = []
        request.filial_ativa = None
        request.filial_access = {"consultar": False, "escrever": False}
        request._new_access_token = None

        # --- Lógica de Autenticação ---
        path = request.path
        is_public_route = any(path.startswith(r) for r in ROTAS_PUBLICAS)

        if is_public_route:
            # Mesmo em rotas públicas, tenta popular request.user com o token
            # existente (sem bloquear), para que a view possa verificar
            # request.user.is_authenticated e agir conforme necessário.
            self._try_authenticate_silent(request)
            response = self.get_response(request)
            return self._finalize_response(request, response)

        # Autentica o usuário (bloqueia se não autenticado)
        auth_response = self._authenticate_user(request)
        if auth_response:
            return auth_response

        self._resolve_filial_context(request)

        if not self._is_authenticated_route_without_filial_allowed(path):
            branch_response = self._ensure_filial_context(request)
            if branch_response:
                return branch_response

        # Resposta padrão para usuários autenticados
        response = self.get_response(request)
        return self._finalize_response(request, response)

    def _try_authenticate_silent(self, request):
        """
        Tenta autenticar silenciosamente nas rotas públicas.
        Não bloqueia nem redireciona em caso de falha — apenas popula
        request.user se o token for válido.
        """
        token = request.COOKIES.get("access_token")
        refresh_token_str = request.COOKIES.get("refresh_token")

        if token:
            try:
                validated = self.jwt_auth.get_validated_token(token)
                request.user = self.jwt_auth.get_user(validated)
                return
            except (InvalidToken, TokenError):
                pass
            except Exception as e:
                logger.error(f"Erro ao autenticar silenciosamente (access): {e}")

        if refresh_token_str:
            try:
                refresh = RefreshToken(refresh_token_str)
                new_access = str(refresh.access_token)
                validated = self.jwt_auth.get_validated_token(new_access)
                request.user = self.jwt_auth.get_user(validated)
                request._new_access_token = new_access
            except (InvalidToken, TokenError):
                pass
            except Exception as e:
                logger.error(f"Erro ao autenticar silenciosamente (refresh): {e}")

    def _extract_json_body(self, request):
        """Extrai dados JSON do corpo da requisição com segurança."""
        if request.method != "POST" or request.content_type != "application/json":
            return {}

        try:
            corpo_json = json.loads(request.body)
            return corpo_json if isinstance(corpo_json, dict) else {}
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning(f"Erro ao decodificar JSON: {e}")
            return {}
        except Exception as e:
            logger.error(f"Erro inesperado ao extrair JSON: {e}")
            return {}

    def _authenticate_user(self, request):
        """
        Autentica o usuário usando JWT.
        Retorna uma resposta de erro se a autenticação falhar.
        """
        token = request.COOKIES.get("access_token")
        refresh_token = request.COOKIES.get("refresh_token")

        # Tenta usar o access_token
        if token:
            try:
                validated = self.jwt_auth.get_validated_token(token)
                request.user = self.jwt_auth.get_user(validated)
                return None  # Autenticação bem-sucedida
            except (InvalidToken, TokenError) as e:
                logger.debug(f"Access token inválido: {e}")
            except Exception as e:
                logger.error(f"Erro ao validar access token: {e}")

        # Tenta fazer refresh com o refresh_token
        if refresh_token:
            return self._handle_refresh_token(request, refresh_token)

        # Nenhum token disponível
        return self._unauthorized_response(request)

    def _handle_refresh_token(self, request, refresh_token_str):
        """
        Processa o refresh token para obter um novo access token.
        """
        try:
            refresh = RefreshToken(refresh_token_str)
            new_access_token = str(refresh.access_token)

            # Valida o novo token
            validated = self.jwt_auth.get_validated_token(new_access_token)
            request.user = self.jwt_auth.get_user(validated)
            request._new_access_token = new_access_token
            return None

        except TokenError as e:
            logger.warning(f"Erro ao processar refresh token: {e}")
            return self._unauthorized_response(request)
        except Exception as e:
            logger.error(f"Erro inesperado no refresh token: {e}")
            return self._unauthorized_response(request)

    def _unauthorized_response(self, request):
        """
        Retorna resposta de não autorizado.
        Detecta se é uma requisição API ou HTML.
        """
        is_api_request = self._is_api_request(request)

        if is_api_request:
            return JsonResponse(
                {
                    "error": "unauthorized",
                    "message": "Autenticação necessária",
                    "csrfToken": get_token(request)
                },
                status=401
            )
        else:
            return redirect("/app/usuario/login/")

    def _inject_csrf_token(self, request, response):
        """
        Injeta o CSRF token em todas as respostas JSON (sucesso e erro).
        """
        if not isinstance(response, JsonResponse):
            return response

        try:
            # Decodifica o JSON atual da resposta
            response_data = json.loads(response.content.decode('utf-8'))
            
            # Só injeta se for um dicionário
            if isinstance(response_data, dict):
                response_data['csrfToken'] = get_token(request)
                
                # Re-codifica com ensure_ascii=False para suportar caracteres especiais
                response.content = json.dumps(response_data, ensure_ascii=False).encode('utf-8')
        
        except json.JSONDecodeError as e:
            logger.warning(f"Resposta JSON inválida: {e}")
        except UnicodeDecodeError as e:
            logger.warning(f"Erro ao decodificar resposta: {e}")
        except Exception as e:
            logger.error(f"Erro inesperado ao injetar CSRF token: {e}")
        
        return response

    def _finalize_response(self, request, response):
        response = self._inject_csrf_token(request, response)

        if getattr(request, "_new_access_token", None):
            response.set_cookie(
                "access_token",
                request._new_access_token,
                httponly=True,
                samesite="Lax",
                secure=True,
                max_age=15 * 60
            )

        return response

    def _resolve_filial_context(self, request):
        filiais = listar_filiais_permitidas(getattr(request, "user", None))
        request.filiais_permitidas = filiais

        filial_cookie = request.COOKIES.get(ACTIVE_FILIAL_COOKIE)
        filial_ativa = validar_filial_ativa(getattr(request, "user", None), filial_cookie)

        request.filial_ativa = filial_ativa
        request.filial_access = obter_nivel_acesso(getattr(request, "user", None), filial_ativa)

    def _ensure_filial_context(self, request):
        filiais = getattr(request, "filiais_permitidas", [])
        filial_ativa = getattr(request, "filial_ativa", None)

        if filial_ativa is not None:
            return None

        if not filiais:
            response = redirect(FILIAL_NO_ACCESS_PATH)
            response.delete_cookie(ACTIVE_FILIAL_COOKIE)
            return self._finalize_response(request, response)

        filial_unica = obter_filial_unica_se_existir(request.user)
        if filial_unica is not None:
            response = redirect(request.get_full_path())
            response.set_cookie(ACTIVE_FILIAL_COOKIE, str(filial_unica.id), httponly=True, samesite="Lax")
            return self._finalize_response(request, response)

        response = redirect(FILIAL_SELECT_PATH)
        response.delete_cookie(ACTIVE_FILIAL_COOKIE)
        return self._finalize_response(request, response)

    def _is_authenticated_route_without_filial_allowed(self, path):
        return any(path.startswith(route) for route in ROTAS_AUTENTICADAS_SEM_FILIAL)

    def _is_api_request(self, request):
        """
        Detecta se é uma requisição API pelo Content-Type.
        """
        content_type = request.content_type or ""
        return any(api_type in content_type for api_type in API_HEADERS)