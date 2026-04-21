from django.urls import path
from .views_mapa import (
    mapa_conferencia_view,
    mapa_pontos_view,
    mapa_salvar_coord_view,
    mapa_rota_view,
    mapa_publico_gerar_link_view,
    mapa_publico_view,
    mapa_publico_pontos_view,
    mapa_publico_periodo_view,
)

urlpatterns = [
    path("mapa_conferencia/", mapa_conferencia_view, name="mapa_conferencia"),
    path("mapa_conferencia/pontos", mapa_pontos_view, name="mapa_conferencia_pontos"),
    path("mapa_conferencia/salvar_coord", mapa_salvar_coord_view, name="mapa_conferencia_salvar_coord"),
    path("mapa_conferencia/rota", mapa_rota_view, name="mapa_conferencia_rota"),

    # Mapa público (sem login) — link por carro com JWT válido até fim do dia
    path("mapa_conferencia/link", mapa_publico_gerar_link_view, name="mapa_publico_gerar_link"),
    path("mapa/<str:token>/", mapa_publico_view, name="mapa_publico"),
    path("mapa/<str:token>/pontos", mapa_publico_pontos_view, name="mapa_publico_pontos"),
    path("mapa/<str:token>/periodo", mapa_publico_periodo_view, name="mapa_publico_periodo"),
]
