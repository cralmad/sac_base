from django.urls import path

from .views import ativar_filial_view, cadastro_filial_cons_view, cadastro_filial_del_view, cadastro_filial_view, selecionar_filial_view, sem_acesso_filial_view


urlpatterns = [
    path("filial/cadastro/", cadastro_filial_view),
    path("filial/cadastro/cons", cadastro_filial_cons_view),
    path("filial/cadastro/del", cadastro_filial_del_view),
    path("usuario/filial/selecionar/", selecionar_filial_view),
    path("usuario/filial/ativar/", ativar_filial_view),
    path("usuario/filial/sem-acesso/", sem_acesso_filial_view),
]
