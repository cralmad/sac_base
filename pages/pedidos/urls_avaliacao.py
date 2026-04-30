from django.urls import path

from .views_avaliacao import (
    avaliacao_publica_view,
    avaliacao_publica_enviar_view,
    relatorio_avaliacao_geracao_view,
    relatorio_avaliacao_view,
    relatorio_avaliacao_enviar_view,
    relatorio_avaliacao_enviar_lote_view,
)

urlpatterns = [
    path("avaliacao/<str:token>/", avaliacao_publica_view, name="avaliacao_publica"),
    path("avaliacao/<str:token>/enviar", avaliacao_publica_enviar_view, name="avaliacao_publica_enviar"),
    path("relatorio_avaliacao/geracao", relatorio_avaliacao_geracao_view, name="relatorio_avaliacao_geracao"),
    path("relatorio_avaliacao/", relatorio_avaliacao_view, name="relatorio_avaliacao"),
    path("relatorio_avaliacao/<int:avaliacao_id>/enviar", relatorio_avaliacao_enviar_view, name="relatorio_avaliacao_enviar"),
    path("relatorio_avaliacao/enviar-lote", relatorio_avaliacao_enviar_lote_view, name="relatorio_avaliacao_enviar_lote"),
]
