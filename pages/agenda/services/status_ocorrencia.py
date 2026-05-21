from __future__ import annotations

from datetime import date

from django.utils import timezone

from pages.agenda.constants import ModoEventoAgenda


def derivar_status_aviso(data_ocorrencia: date, *, hoje: date | None = None) -> str:
    ref = hoje or timezone.localdate()
    return "concluido" if data_ocorrencia < ref else "pendente"


def resolver_status_ocorrencia(
    *,
    modo_evento: str,
    data_ocorrencia: date,
    confirmado: bool,
    hoje: date | None = None,
) -> str:
    if modo_evento == ModoEventoAgenda.AVISO:
        return derivar_status_aviso(data_ocorrencia, hoje=hoje)
    if modo_evento == ModoEventoAgenda.AVISO_CONFIRMAVEL:
        return "concluido" if confirmado else "pendente"
    return "pendente"
