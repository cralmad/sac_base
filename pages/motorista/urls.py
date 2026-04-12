from django.urls import path

from .views import cadastro_motorista_cons_view, cadastro_motorista_del_view, cadastro_motorista_view


urlpatterns = [
    path("logistica/motorista/", cadastro_motorista_view),
    path("logistica/motorista/cons", cadastro_motorista_cons_view),
    path("logistica/motorista/del", cadastro_motorista_del_view),
]
