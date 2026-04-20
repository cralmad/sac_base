from django.urls import path
from .views_relatorio import relatorio_conferencia_view, relatorio_conferencia_imprimir_view, relatorio_rotas_view
from .views_relatorio_api import relatorio_conferencia_salvar_view

urlpatterns = [
    path('relatorio_conferencia/', relatorio_conferencia_view, name='relatorio_conferencia'),
    path('relatorio_conferencia/salvar', relatorio_conferencia_salvar_view, name='relatorio_conferencia_salvar'),
    path('relatorio_conferencia/imprimir', relatorio_conferencia_imprimir_view, name='relatorio_conferencia_imprimir'),
    path('relatorio_rotas/', relatorio_rotas_view, name='relatorio_rotas'),
]
