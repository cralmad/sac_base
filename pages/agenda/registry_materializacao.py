from __future__ import annotations

from pages.agenda.providers.base import AgendaMaterializationProvider

_MATERIALIZATION_PROVIDERS: dict[str, AgendaMaterializationProvider] = {}


def registrar_materialization_provider(provider: AgendaMaterializationProvider) -> None:
    key = provider.materialization_key
    if key in _MATERIALIZATION_PROVIDERS:
        return
    _MATERIALIZATION_PROVIDERS[key] = provider


def obter_materialization_provider(key: str) -> AgendaMaterializationProvider | None:
    return _MATERIALIZATION_PROVIDERS.get(key)


def listar_materialization_providers() -> tuple[AgendaMaterializationProvider, ...]:
    return tuple(_MATERIALIZATION_PROVIDERS.values())
