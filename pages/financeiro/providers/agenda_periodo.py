from __future__ import annotations

from decimal import Decimal

from pages.agenda.providers.base import AgendaEventoDTO
from pages.financeiro.models import (
    RegistroFinanceiro,
    RegistroFinanceiroStatus,
    RegistroFinanceiroTipo,
)

PROVIDER_KEY = "financeiro.registro_financeiro"

_TIPO_LABEL = {
    RegistroFinanceiroTipo.ENTRADA: "Entrada",
    RegistroFinanceiroTipo.SAIDA: "Saída",
}


class FinanceiroRegistroFinanceiroPeriodProvider:
    provider_key = PROVIDER_KEY

    def get_events_by_period(
        self,
        *,
        data_inicio,
        data_fim,
        filial_id: int,
    ) -> list[AgendaEventoDTO]:
        qs = (
            RegistroFinanceiro.objects.filter(
                filial_id=filial_id,
                data_vencimento__range=(data_inicio, data_fim),
                status__in=[RegistroFinanceiroStatus.ABERTO, RegistroFinanceiroStatus.PARCIAL],
                tipo__in=[RegistroFinanceiroTipo.ENTRADA, RegistroFinanceiroTipo.SAIDA],
            )
            .select_related("contraparte_content_type")
            .only(
                "id",
                "tipo",
                "valor",
                "data_vencimento",
                "status",
                "observacao",
                "contraparte_content_type_id",
                "contraparte_object_id",
            )
            .order_by("data_vencimento", "id")
        )
        eventos: list[AgendaEventoDTO] = []
        for rf in qs:
            tipo_lbl = _TIPO_LABEL.get(rf.tipo, rf.tipo)
            valor_txt = f"{rf.valor:.2f}".replace(".", ",") if rf.valor is not None else ""
            titulo = f"{tipo_lbl} — R$ {valor_txt}" if valor_txt else tipo_lbl
            eventos.append(
                AgendaEventoDTO(
                    provider_key=PROVIDER_KEY,
                    origem_id=rf.id,
                    data=rf.data_vencimento,
                    categoria="financeiro",
                    titulo=titulo,
                    subtitulo="",
                    valor=rf.valor,
                    status=rf.status,
                    url=f"/app/financeiro/registro/manual/?visualizar={rf.id}",
                    meta={"tipo": rf.tipo, "observacao": (rf.observacao or "").strip()},
                )
            )
        return eventos
