from django.urls import path

from .views import cadastro_zona_entrega_cons_view, cadastro_zona_entrega_del_view, cadastro_zona_entrega_view


urlpatterns = [
    path("logistica/zona-entrega/", cadastro_zona_entrega_view),
    path("logistica/zona-entrega/cons", cadastro_zona_entrega_cons_view),
    path("logistica/zona-entrega/del", cadastro_zona_entrega_del_view),
]
