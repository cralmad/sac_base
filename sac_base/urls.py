from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('app/painel_adm/', admin.site.urls),
    path('app/cad/cliente/', include('pages.cad_cliente.urls')),
    path('app/cad/grupo/', include('pages.cad_grupo_cli.urls')),
    path('app/', include('pages.usuario.urls')),
    path('', include('pages.home.urls')),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
