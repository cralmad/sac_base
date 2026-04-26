"""
Middleware para Content-Security-Policy (CSP).

Define os origins permitidos para scripts, estilos, imagens e conexões.
Adicionado para mitigar ataques XSS ao restringir de onde recursos podem ser carregados.

NOTA: 'unsafe-inline' é necessário enquanto o projeto usar scripts/estilos inline
      e o json_script tag do Django (que gera um <script type="application/json">).
      Para fortalecer ainda mais, considere usar nonces no futuro.
"""

_CSP = (
    "default-src 'self'; "
    # Scripts: próprio servidor + Bootstrap + Leaflet (CDNs aprovados)
    "script-src 'self' cdn.jsdelivr.net unpkg.com 'unsafe-inline'; "
    # Estilos: próprio servidor + Bootstrap + Leaflet + fontes inline do Leaflet
    "style-src 'self' cdn.jsdelivr.net unpkg.com 'unsafe-inline'; "
    # Imagens: próprio servidor, data URIs, tiles do mapa (CARTO), fotos do ImgBB, ícones Leaflet
    "img-src 'self' data: blob: *.cartocdn.com unpkg.com *.ibb.co i.ibb.co; "
    # Fontes: Bootstrap Icons via CDN
    "font-src 'self' cdn.jsdelivr.net unpkg.com; "
    # Conexões AJAX/fetch/WebSocket
    "connect-src 'self' "
    "https://cdn.jsdelivr.net "
    "https://unpkg.com "
    "https://nominatim.openstreetmap.org "
    "https://router.project-osrm.org "
    "https://api.imgbb.com "
    "https://portal.bulkgate.com "
    "wss: ws:; "
    # Web workers (usados internamente pelo Leaflet)
    "worker-src blob:; "
    # Proíbe framear a aplicação em iframes externos (redundante com X-Frame-Options)
    "frame-ancestors 'none'; "
    # Restringe o base URI para evitar base-tag hijacking
    "base-uri 'self';"
)


class CSPMiddleware:
    """Adiciona o cabeçalho Content-Security-Policy a todas as respostas HTML."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not response.has_header("Content-Security-Policy"):
            response["Content-Security-Policy"] = _CSP
        return response
