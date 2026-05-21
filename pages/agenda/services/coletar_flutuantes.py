from __future__ import annotations

from datetime import date

from django.db.models import Q
from django.utils import timezone

from pages.agenda.constants import ModoEventoAgenda, TipoVinculoMaterializacao
from pages.agenda.models import AgendaManual, AgendaMaterializacao
from pages.agenda.services.recorrencia import projetar_datas_ocorrencia
from pages.agenda.services.status_ocorrencia import resolver_status_ocorrencia


def _mapa_materializacoes(
    agenda_ids: list[int],
    data_inicio: date,
    data_fim: date,
) -> dict[tuple[int, date], str]:
    rows = AgendaMaterializacao.objects.filter(
        agenda_manual_id__in=agenda_ids,
        data_ocorrencia__range=(data_inicio, data_fim),
    ).values_list("agenda_manual_id", "data_ocorrencia", "tipo_vinculo")
    return {(aid, d): tv for aid, d, tv in rows}


def coletar_eventos_flutuantes(
    *,
    filial_id: int,
    data_inicio: date,
    data_fim: date,
    usuario,
    pode_confirmar: bool,
    pode_materializar: bool,
) -> list[dict]:
    hoje = timezone.localdate()
    qs = AgendaManual.objects.filter(
        filial_id=filial_id,
        ativa=True,
        data_ancora__lte=data_fim,
    ).filter(Q(data_fim_serie__isnull=True) | Q(data_fim_serie__gte=data_inicio))

    manuais = list(qs)
    if not manuais:
        return []

    ids = [m.id for m in manuais]
    mat_map = _mapa_materializacoes(ids, data_inicio, data_fim)

    eventos: list[dict] = []
    for manual in manuais:
        datas = projetar_datas_ocorrencia(
            data_ancora=manual.data_ancora,
            recorrencia=manual.recorrencia,
            intervalo=manual.intervalo,
            data_inicio=data_inicio,
            data_fim=data_fim,
            data_fim_serie=manual.data_fim_serie,
            dia_semana=manual.dia_semana,
            dia_mes_fixo=manual.dia_mes_fixo,
            antecipar_fim_semana=manual.antecipar_fim_semana,
        )
        for d in datas:
            chave = (manual.id, d)
            tipo_vinc = mat_map.get(chave)
            if manual.modo_evento == ModoEventoAgenda.MATERIALIZAVEL:
                if tipo_vinc == TipoVinculoMaterializacao.MATERIALIZADO:
                    continue
            confirmado = tipo_vinc == TipoVinculoMaterializacao.CONCLUIDO_CONFIRMADO
            status = resolver_status_ocorrencia(
                modo_evento=manual.modo_evento,
                data_ocorrencia=d,
                confirmado=confirmado,
                hoje=hoje,
            )
            acoes = {
                "pode_confirmar": (
                    manual.modo_evento == ModoEventoAgenda.AVISO_CONFIRMAVEL
                    and status == "pendente"
                    and pode_confirmar
                ),
                "pode_materializar": (
                    manual.modo_evento == ModoEventoAgenda.MATERIALIZAVEL
                    and tipo_vinc != TipoVinculoMaterializacao.MATERIALIZADO
                    and pode_materializar
                ),
            }
            meta_flutuante: dict = {}
            if manual.categoria == "financeiro" and manual.payload_template:
                meta_flutuante["payload_template"] = manual.payload_template
                if isinstance(manual.payload_template, dict):
                    meta_flutuante["tipo"] = manual.payload_template.get("tipo")
            eventos.append(
                {
                    "id": f"flutuante:{manual.id}:{d.isoformat()}",
                    "tipo_dado": "flutuante",
                    "data": d.isoformat(),
                    "categoria": manual.categoria,
                    "provider_key": "agenda_manual",
                    "agenda_manual_id": manual.id,
                    "titulo": manual.titulo,
                    "subtitulo": (manual.descricao or "")[:120],
                    "valor": None,
                    "valor_decimal": None,
                    "observacao": (manual.descricao or "").strip(),
                    "status": status,
                    "url": None,
                    "acoes": acoes,
                    "modo_evento": manual.modo_evento,
                    "tipo_materializacao": manual.tipo_materializacao,
                    "meta": meta_flutuante,
                }
            )
    return eventos
