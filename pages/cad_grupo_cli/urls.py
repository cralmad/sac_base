from django.urls import path
from . import views

urlpatterns = [
    path('grupocli/',      views.cad_grupo_cli_view, name='cadgrupocli'),
    path('grupocli/cons',  views.cad_grupo_cli_cons_view, name='cadgrupocli_cons'),
]