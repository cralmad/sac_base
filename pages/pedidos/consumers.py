import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

GRUPO_RELATORIO = "relatorio_conferencia"


def _extrair_cookie(scope, nome):
    """
    Extrai o valor de um cookie a partir dos headers brutos do scope ASGI.
    O scope de WebSocket não tem chave 'cookies'; os cookies chegam no header
    b'cookie' como bytes dentro de scope['headers'].
    """
    headers = dict(scope.get("headers", []))
    cookie_header = headers.get(b"cookie", b"").decode("latin-1")
    for part in cookie_header.split(";"):
        chave, sep, valor = part.strip().partition("=")
        if sep and chave.strip() == nome:
            return valor
    return None


class RelatorioConferenciaConsumer(AsyncWebsocketConsumer):
    """
    Consumer WebSocket para a tela de Conferência de Volumes.
    Autentica via JWT cookie (access_token) e verifica permissão de leitura.
    Ao conectar, entra no grupo `relatorio_conferencia`.
    A API de salvar faz broadcast para o grupo; o consumer repassa ao cliente.
    """

    async def connect(self):
        # Aceita ANTES de verificar permissão para poder enviar
        # o close code 4001 via frame WebSocket (exige handshake completo).
        await self.accept()
        if not await self._has_access():
            await self.close(code=4001)
            return
        await self.channel_layer.group_add(GRUPO_RELATORIO, self.channel_name)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(GRUPO_RELATORIO, self.channel_name)

    async def receive(self, text_data):
        # Consumer apenas receptor; broadcasts partem da API REST
        pass

    async def relatorio_update(self, event):
        """Recebe evento do grupo e repassa ao cliente conectado."""
        await self.send(text_data=json.dumps(event["payload"]))

    @database_sync_to_async
    def _has_access(self):
        """Valida JWT a partir do cookie e verifica permissão de leitura."""
        from rest_framework_simplejwt.authentication import JWTAuthentication
        from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

        try:
            raw_token = _extrair_cookie(self.scope, "access_token")
            if not raw_token:
                return False
            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(raw_token)
            user = jwt_auth.get_user(validated_token)
            return bool(
                user
                and user.is_authenticated
                and user.has_perm("pedidos.view_tentativaentrega")
            )
        except (InvalidToken, TokenError, Exception):
            return False
