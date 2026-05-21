from __future__ import annotations

import logging
from datetime import date

from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, transaction

from pages.agenda.constants import (
    CATEGORIA_CHOICES,
    MODO_EVENTO_CHOICES,
    RECORRENCIA_CHOICES,
    ModoEventoAgenda,
    TipoVinculoMaterializacao,
)
from pages.agenda.models import AgendaManual, AgendaMaterializacao
from pages.agenda.services.agenda_materializacao_orquestrador import (
    executar_materializacao,
    validar_payload_template,
)
from pages.agenda.services.validacao_agenda import validar_regras_agenda_manual
from pages.filial.services import get_filiais_escrita_queryset, obter_filial_escrita
from sac_base.coercion import parse_date, parse_int

logger = logging.getLogger(__name__)


_LABELS_CATEGORIA = dict(CATEGORIA_CHOICES)
_LABELS_MODO = dict(MODO_EVENTO_CHOICES)
_LABELS_RECORRENCIA = dict(RECORRENCIA_CHOICES)


def montar_linha_cons_agenda_manual(registro: AgendaManual) -> dict:
    return {
        "id": registro.id,
        "titulo": registro.titulo,
        "categoria": _LABELS_CATEGORIA.get(registro.categoria, registro.categoria),
        "modo_evento": _LABELS_MODO.get(registro.modo_evento, registro.modo_evento),
        "recorrencia": _LABELS_RECORRENCIA.get(registro.recorrencia, registro.recorrencia),
        "data_ancora": registro.data_ancora.isoformat() if registro.data_ancora else "",
        "ativa": "Sim" if registro.ativa else "Não",
    }


def serializar_agenda_manual(registro: AgendaManual) -> dict:
    return {
        "id": registro.id,
        "filial_id": str(registro.filial_id),
        "titulo": registro.titulo,
        "descricao": registro.descricao or "",
        "categoria": registro.categoria,
        "modo_evento": registro.modo_evento,
        "tipo_materializacao": registro.tipo_materializacao or "",
        "payload_template": registro.payload_template or {},
        "data_ancora": registro.data_ancora.isoformat() if registro.data_ancora else "",
        "recorrencia": registro.recorrencia,
        "intervalo": registro.intervalo,
        "dia_semana": registro.dia_semana,
        "dia_mes_fixo": registro.dia_mes_fixo,
        "antecipar_fim_semana": registro.antecipar_fim_semana,
        "data_fim_serie": registro.data_fim_serie.isoformat() if registro.data_fim_serie else "",
        "ativa": registro.ativa,
    }


def campos_iniciais_agenda(*, filial_id: str | None = None) -> dict:
    return {
        "id": None,
        "filial_id": filial_id or "",
        "titulo": "",
        "descricao": "",
        "categoria": "lembrete",
        "modo_evento": ModoEventoAgenda.AVISO,
        "tipo_materializacao": "",
        "payload_template": {},
        "data_ancora": date.today().isoformat(),
        "recorrencia": "mensal",
        "intervalo": 1,
        "dia_semana": None,
        "dia_mes_fixo": None,
        "antecipar_fim_semana": False,
        "data_fim_serie": "",
        "ativa": True,
    }


def _aplicar_campos(registro: AgendaManual, campos: dict, filial_id: int, usuario) -> None:
    registro.filial_id = filial_id
    registro.titulo = (campos.get("titulo") or "").strip()[:200]
    if not registro.titulo:
        raise ValidationError("Informe o título.")
    registro.descricao = (campos.get("descricao") or "").strip()
    registro.categoria = (campos.get("categoria") or "lembrete").strip()
    registro.modo_evento = (campos.get("modo_evento") or ModoEventoAgenda.AVISO).strip()
    registro.tipo_materializacao = (campos.get("tipo_materializacao") or "").strip() or None
    registro.data_ancora = parse_date(campos.get("data_ancora"))
    if not registro.data_ancora:
        raise ValidationError("Informe a data âncora.")
    registro.recorrencia = (campos.get("recorrencia") or "mensal").strip()
    registro.intervalo = parse_int(campos.get("intervalo"), context="form") or 1
    ds = campos.get("dia_semana")
    registro.dia_semana = parse_int(ds, context="form") if ds not in (None, "") else None
    dmf = campos.get("dia_mes_fixo")
    registro.dia_mes_fixo = parse_int(dmf, context="form") if dmf not in (None, "") else None
    registro.antecipar_fim_semana = bool(campos.get("antecipar_fim_semana"))
    dfs = parse_date(campos.get("data_fim_serie")) if campos.get("data_fim_serie") else None
    registro.data_fim_serie = dfs
    registro.ativa = campos.get("ativa") is not False and campos.get("ativa") != "false"

    payload = campos.get("payload_template")
    if isinstance(payload, dict):
        registro.payload_template = payload
    elif registro.modo_evento != ModoEventoAgenda.MATERIALIZAVEL:
        registro.payload_template = {}

    validar_regras_agenda_manual(
        categoria=registro.categoria,
        modo_evento=registro.modo_evento,
        tipo_materializacao=registro.tipo_materializacao,
        payload_template=registro.payload_template or {},
        recorrencia=registro.recorrencia,
        data_ancora=registro.data_ancora,
        data_fim_serie=registro.data_fim_serie,
        dia_semana=registro.dia_semana,
        dia_mes_fixo=registro.dia_mes_fixo,
        antecipar_fim_semana=registro.antecipar_fim_semana,
    )

    if registro.modo_evento == ModoEventoAgenda.MATERIALIZAVEL:
        registro.payload_template = validar_payload_template(
            tipo_materializacao=registro.tipo_materializacao or "",
            payload=registro.payload_template or {},
            filial_id=filial_id,
            usuario=usuario,
        )


@transaction.atomic
def salvar_agenda_manual(*, usuario, campos: dict, estado: str) -> AgendaManual:
    filial = obter_filial_escrita(campos.get("filial_id"), usuario)
    if not filial:
        raise ValidationError("Filial inválida ou sem permissão de escrita.")

    registro_id = parse_int(campos.get("id"), context="form")
    if estado == "novo":
        registro = AgendaManual(created_by=usuario if usuario.is_authenticated else None)
    elif estado == "editar":
        registro = AgendaManual.objects.filter(id=registro_id, filial_id=filial.id).first()
        if not registro:
            raise ValidationError("Registro de agenda não encontrado.")
        registro.updated_by = usuario if usuario.is_authenticated else None
    else:
        raise ValidationError("Estado do formulário inválido.")

    _aplicar_campos(registro, campos, filial.id, usuario)
    try:
        registro.save()
    except (IntegrityError, DatabaseError) as exc:
        logger.error(exc, exc_info=True)
        raise ValidationError("Não foi possível salvar o registro de agenda.") from exc
    return registro


@transaction.atomic
def confirmar_ocorrencia(
    *,
    agenda_manual_id: int,
    data_ocorrencia: date,
    filial_id: int,
    usuario,
) -> AgendaMaterializacao:
    agenda = AgendaManual.objects.filter(id=agenda_manual_id, filial_id=filial_id).first()
    if not agenda:
        raise ValidationError("Agenda não encontrada para a filial.")
    if agenda.modo_evento != ModoEventoAgenda.AVISO_CONFIRMAVEL:
        raise ValidationError("Somente avisos com confirmação podem ser confirmados desta forma.")

    if AgendaMaterializacao.objects.filter(
        agenda_manual_id=agenda.id,
        data_ocorrencia=data_ocorrencia,
    ).exists():
        raise ValidationError("Esta ocorrência já foi registrada.")

    try:
        return AgendaMaterializacao.objects.create(
            agenda_manual=agenda,
            data_ocorrencia=data_ocorrencia,
            tipo_vinculo=TipoVinculoMaterializacao.CONCLUIDO_CONFIRMADO,
            created_by=usuario if usuario.is_authenticated else None,
        )
    except (IntegrityError, DatabaseError) as exc:
        logger.error(exc, exc_info=True)
        raise ValidationError("Não foi possível confirmar a ocorrência.") from exc


def materializar_ocorrencia(
    *,
    agenda_manual_id: int,
    data_ocorrencia: date,
    filial_id: int,
    usuario,
    payload_override: dict | None = None,
) -> AgendaMaterializacao:
    agenda = AgendaManual.objects.filter(id=agenda_manual_id, filial_id=filial_id).first()
    if not agenda:
        raise ValidationError("Agenda não encontrada para a filial.")
    return executar_materializacao(
        agenda=agenda,
        data_ocorrencia=data_ocorrencia,
        usuario=usuario,
        payload_override=payload_override,
    )
