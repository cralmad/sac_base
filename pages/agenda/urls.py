from django.urls import path

from pages.agenda.views_agenda_manual import (
    agenda_manual_confirmar_view,
    agenda_manual_cons_view,
    agenda_manual_materializar_view,
    agenda_manual_schema_materializacao_view,
    agenda_manual_view,
)
from pages.agenda.views_relatorio import relatorio_previsibilidade_view

urlpatterns = [
    path("agenda/relatorio/previsibilidade/", relatorio_previsibilidade_view),
    path("agenda/manual/", agenda_manual_view),
    path("agenda/manual/cons", agenda_manual_cons_view),
    path("agenda/manual/confirmar-ocorrencia/", agenda_manual_confirmar_view),
    path("agenda/manual/materializar/", agenda_manual_materializar_view),
    path("agenda/manual/schema-materializacao/", agenda_manual_schema_materializacao_view),
]
