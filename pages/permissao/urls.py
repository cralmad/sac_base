from django.urls import path
from .views import cadastro_grupo_view, cadastro_grupo_cons_view

urlpatterns = [
    path("permissao/grupos/",      cadastro_grupo_view),
    path("permissao/grupos/cons",  cadastro_grupo_cons_view),
]