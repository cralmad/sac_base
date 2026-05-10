from django.urls import path
from .views_relatorio import (
    relatorio_conferencia_view,
    relatorio_conferencia_imprimir_view,
    relatorio_rotas_view,
    relatorio_rotas_importar_artigos_view,
    relatorio_sms_view,
    relatorio_sms_enviar_view,
    relatorio_sms_preview_view,
    relatorio_gerencial_view,
    relatorio_devolucao_view,
    relatorio_devolucao_gsheets_view,
)
from .views_relatorio_motorista import (
    relatorio_logistica_motorista_mod_finan_view,
    relatorio_logistica_motorista_view,
)
from .views_relatorio_api import relatorio_conferencia_salvar_view

urlpatterns = [
    path('relatorio_conferencia/', relatorio_conferencia_view, name='relatorio_conferencia'),
    path('relatorio_conferencia/salvar', relatorio_conferencia_salvar_view, name='relatorio_conferencia_salvar'),
    path('relatorio_conferencia/imprimir', relatorio_conferencia_imprimir_view, name='relatorio_conferencia_imprimir'),
    path('relatorio_logistica_motorista/', relatorio_logistica_motorista_view, name='relatorio_logistica_motorista'),
    path(
        'relatorio_logistica_motorista/mod-finan/salvar',
        relatorio_logistica_motorista_mod_finan_view,
        name='relatorio_logistica_motorista_mod_finan',
    ),
    path('relatorio_rotas/', relatorio_rotas_view, name='relatorio_rotas'),
    path('relatorio_rotas/importar-artigos/', relatorio_rotas_importar_artigos_view, name='relatorio_rotas_importar_artigos'),
    path('relatorio_sms/', relatorio_sms_view, name='relatorio_sms'),
    path('relatorio_sms/enviar', relatorio_sms_enviar_view, name='relatorio_sms_enviar'),
    path('relatorio_sms/preview', relatorio_sms_preview_view, name='relatorio_sms_preview'),
    path('relatorio_gerencial/', relatorio_gerencial_view, name='relatorio_gerencial'),
    path('relatorio_devolucao/', relatorio_devolucao_view, name='relatorio_devolucao'),
    path('relatorio_devolucao/gsheets', relatorio_devolucao_gsheets_view, name='relatorio_devolucao_gsheets'),
]
