from django.urls import path
from .views_mapa import (
    mapa_conferencia_view,
    mapa_pontos_view,
    mapa_salvar_coord_view,
    mapa_rota_view,
)

urlpatterns = [
    path("mapa_conferencia/", mapa_conferencia_view, name="mapa_conferencia"),
    path("mapa_conferencia/pontos", mapa_pontos_view, name="mapa_conferencia_pontos"),
    path("mapa_conferencia/salvar_coord", mapa_salvar_coord_view, name="mapa_conferencia_salvar_coord"),
    path("mapa_conferencia/rota", mapa_rota_view, name="mapa_conferencia_rota"),
]
