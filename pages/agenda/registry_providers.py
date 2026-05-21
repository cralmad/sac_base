from __future__ import annotations

from pages.agenda.providers.base import PeriodAlertProvider

_PERIOD_ALERT_PROVIDERS: list[PeriodAlertProvider] = []
_KEYS: set[str] = set()


def registrar_period_alert_provider(provider: PeriodAlertProvider) -> None:
    key = provider.provider_key
    if key in _KEYS:
        return
    _KEYS.add(key)
    _PERIOD_ALERT_PROVIDERS.append(provider)


def listar_period_alert_providers() -> tuple[PeriodAlertProvider, ...]:
    return tuple(_PERIOD_ALERT_PROVIDERS)
