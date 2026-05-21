import logging

from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import render

from pages.agenda.services.agenda_manual import (
    campos_iniciais_agenda,
    confirmar_ocorrencia,
    materializar_ocorrencia,
    salvar_agenda_manual,
    serializar_agenda_manual,
)
from pages.agenda.services.agenda_materializacao_orquestrador import (
    obter_schema_materializacao,
)
from pages.filial.services import get_filiais_escrita_queryset
from sac_base.coercion import parse_date, parse_int
from sac_base.http_json import json_method_not_allowed
from sac_base.permissions_utils import build_action_permissions, permission_denied_response
from sac_base.sisvar_builders import (
    build_error_payload,
    build_form_response,
    build_form_state,
    build_records_response,
    build_sisvar_payload,
    build_success_payload,
)

logger = logging.getLogger(__name__)

PERMISSOES_AGENDA_MANUAL = {
    "acessar": "agenda.view_agendamanual",
    "consultar": "agenda.view_agendamanual",
    "incluir": "agenda.add_agendamanual",
    "editar": "agenda.change_agendamanual",
    "excluir": "agenda.delete_agendamanual",
    "confirmar": "agenda.confirmar_ocorrencia_agendamanual",
    "materializar": "agenda.materializar_agendamanual",
}

PERMISSOES_RELATORIO = {
    "acessar": "agenda.view_relatorio_previsibilidade",
}
