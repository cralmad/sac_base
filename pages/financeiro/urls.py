from django.urls import path

from pages.financeiro.views import (
    registro_manual_cancelar_view,
    registro_manual_cons_view,
    registro_manual_view,
)

urlpatterns = [
    path("financeiro/registro/manual/", registro_manual_view),
    path("financeiro/registro/manual/cons", registro_manual_cons_view),
    path("financeiro/registro/manual/cancelar", registro_manual_cancelar_view),
]
