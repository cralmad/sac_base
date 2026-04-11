from django.urls import path

from .views import ativar_filial_view, selecionar_filial_view, sem_acesso_filial_view


urlpatterns = [
    path("usuario/filial/selecionar/", selecionar_filial_view),
    path("usuario/filial/ativar/", ativar_filial_view),
    path("usuario/filial/sem-acesso/", sem_acesso_filial_view),
]
