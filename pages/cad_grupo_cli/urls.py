from django.urls import path
from . import views

urlpatterns = [
    path('',     views.cad_grupo_cli_view,      name='cadgrupocli'),
    path('cons', views.cad_grupo_cli_cons_view, name='cadgrupocli_cons'),
    path('del',  views.cad_grupo_cli_del_view,  name='cadgrupocli_del'),
]