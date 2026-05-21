from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Protocol

from django.db import models


@dataclass(frozen=True)
class AgendaEventoDTO:
    provider_key: str
    origem_id: int
    data: date
    categoria: str
    titulo: str
    subtitulo: str
    valor: Decimal | None
    status: str | None
    url: str | None
    meta: dict[str, Any] = field(default_factory=dict)


class PeriodAlertProvider(Protocol):
    provider_key: str

    def get_events_by_period(
        self,
        *,
        data_inicio: date,
        data_fim: date,
        filial_id: int,
    ) -> list[AgendaEventoDTO]: ...


@dataclass(frozen=True)
class MaterializacaoFormSchema:
    schema: dict[str, dict]
    datasets_keys: tuple[str, ...]
    form_id: str


class AgendaMaterializationProvider(Protocol):
    materialization_key: str
    label: str
    permission_codename: str
    categoria_agenda: str

    def get_form_schema(self, *, filial_id: int, usuario) -> MaterializacaoFormSchema: ...

    def validate_payload(
        self,
        payload: dict,
        *,
        filial_id: int,
        usuario,
    ) -> tuple[dict | None, list[str]]: ...

    def materialize(
        self,
        *,
        payload: dict,
        filial_id: int,
        data_ocorrencia: date,
        agenda_manual_id: int,
        usuario,
    ) -> models.Model: ...
