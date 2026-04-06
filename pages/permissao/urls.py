from django.urls import path
from .views import (
    cadastro_grupo_cons_view,
    cadastro_grupo_view,
    permissao_usuario_cons_view,
    permissao_usuario_view,
)

urlpatterns = [
    path("permissao/grupos/",      cadastro_grupo_view),
    path("permissao/grupos/cons",  cadastro_grupo_cons_view),
    path("permissao/usuario/",     permissao_usuario_view),
    path("permissao/usuario/cons", permissao_usuario_cons_view),
]