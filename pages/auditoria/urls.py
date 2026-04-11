from django.urls import path

from .views import auditoria_cons_view, auditoria_view


urlpatterns = [
    path("auditoria/consulta/", auditoria_view),
    path("auditoria/consulta/cons", auditoria_cons_view),
]