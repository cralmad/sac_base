from __future__ import annotations

from datetime import date

from pages.agenda.constants import PERIOD_PROVIDER_PERMISSIONS
from pages.agenda.registry_providers import listar_period_alert_providers


def _usuario_pode_provider(usuario, provider_key: str) -> bool:
    if not usuario or not usuario.is_authenticated:
        return False
    if usuario.is_superuser:
        return True
    perm = PERIOD_PROVIDER_PERMISSIONS.get(provider_key)
    if not perm:
        return False
    return usuario.has_perm(perm)


def coletar_eventos_concretos(
    *,
    data_inicio: date,
    data_fim: date,
    filial_id: int,
    usuario,
) -> list:
    from pages.agenda.providers.base import AgendaEventoDTO

    eventos: list[AgendaEventoDTO] = []
    for provider in listar_period_alert_providers():
        if not _usuario_pode_provider(usuario, provider.provider_key):
            continue
        eventos.extend(
            provider.get_events_by_period(
                data_inicio=data_inicio,
                data_fim=data_fim,
                filial_id=filial_id,
            )
        )
    return eventos
