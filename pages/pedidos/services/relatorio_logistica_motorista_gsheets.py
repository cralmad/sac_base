"""Envio do relatório logística motorista para Google Sheets (planilha FilialConfig _2)."""

from __future__ import annotations

from datetime import date

from django.core.exceptions import ValidationError

from pages.filial.models import FilialConfig
from pages.pedidos.models import TentativaEntrega, estado_label
from sac_base.gsheets_service import append_logistica_motorista_rows

MSG_GSHEETS_NAO_CONFIGURADO = (
    "Google Sheets (outra tabela) não configurado para esta filial. "
    "Acesse Cadastro → Filial → aba Configurações → Google Sheets — Outra tabela."
)
MSG_PLANILHA_NAO_NATIVA = (
    "O ficheiro indicado não é uma planilha nativa do Google Sheets. "
    "Crie uma nova planilha em sheets.google.com (não faça upload de um ficheiro Excel) "
    "e use o ID dessa nova planilha nas configurações da filial."
)
MSG_NENHUMA_ELEGIVEL = (
    "Nenhuma tentativa elegível para envio "
    "(Concluído, interno ou sem registros no período)."
)


def _ler_config_gsheets_2(filial_ativa) -> tuple[str, str]:
    try:
        cfg = filial_ativa.config
        spreadsheet_id = (cfg.gsheets_spreadsheet_id_2 or "").strip()
        sheet_name = (cfg.gsheets_sheet_name_2 or "").strip()
    except FilialConfig.DoesNotExist:
        spreadsheet_id = ""
        sheet_name = ""
    return spreadsheet_id, sheet_name


def _qs_tentativas_periodo_gsheets(
    filial_ativa,
    data_inicio: date,
    data_fim: date,
    motorista_ids: list[int] | None,
):
    if data_fim < data_inicio:
        raise ValidationError("A data final deve ser maior ou igual à data inicial.")

    qs = TentativaEntrega.objects.select_related("pedido").filter(
        pedido__filial_id=filial_ativa.pk,
        data_tentativa__gte=data_inicio,
        data_tentativa__lte=data_fim,
    )
    ids_filtro = [i for i in (motorista_ids or []) if i]
    if ids_filtro:
        qs = qs.filter(motorista_id__in=ids_filtro)
    return qs.order_by("data_tentativa", "pedido_id", "id")


def serializar_tentativa_ignorada_gsheets(mov: TentativaEntrega) -> dict:
    p = mov.pedido
    return {
        "tentativa_id": mov.id,
        "referencia": p.pedido or str(p.id_vonzu),
        "data_tentativa": mov.data_tentativa.strftime("%d/%m/%Y") if mov.data_tentativa else "",
        "estado": mov.estado or "",
        "estado_label": estado_label(mov.estado),
        "motivo": "interno",
    }


def listar_tentativas_para_gsheets(
    filial_ativa,
    data_inicio: date,
    data_fim: date,
    motorista_ids: list[int] | None,
) -> list[TentativaEntrega]:
    return list(
        _qs_tentativas_periodo_gsheets(filial_ativa, data_inicio, data_fim, motorista_ids)
        .exclude(estado="completed")
        .filter(interno=False)
    )


def listar_tentativas_ignoradas_interno(
    filial_ativa,
    data_inicio: date,
    data_fim: date,
    motorista_ids: list[int] | None,
) -> list[TentativaEntrega]:
    return list(
        _qs_tentativas_periodo_gsheets(filial_ativa, data_inicio, data_fim, motorista_ids)
        .filter(interno=True)
    )


def _coluna_estado_e_obs(estado: str | None, obs: str | None) -> str:
    partes = []
    lbl = estado_label(estado)
    if lbl:
        partes.append(lbl)
    obs_txt = (obs or "").strip()
    if obs_txt:
        partes.append(obs_txt)
    return " | ".join(partes)


def montar_rows_gsheets_logistica_motorista(tentativas: list[TentativaEntrega]) -> list[list]:
    rows = []
    for mov in tentativas:
        p = mov.pedido
        data_fmt = mov.data_tentativa.strftime("%d/%m/%Y") if mov.data_tentativa else ""
        ref = p.pedido or str(p.id_vonzu)
        rows.append([
            data_fmt,
            ref,
            "Outro",
            "",
            _coluna_estado_e_obs(mov.estado, p.obs),
        ])
    return rows


def executar_envio_gsheets_logistica_motorista(
    filial_ativa,
    *,
    data_inicio: date,
    data_fim: date,
    motorista_ids: list[int] | None,
) -> dict:
    spreadsheet_id, sheet_name = _ler_config_gsheets_2(filial_ativa)
    if not spreadsheet_id or not sheet_name:
        raise ValidationError(MSG_GSHEETS_NAO_CONFIGURADO)

    ignoradas_qs = listar_tentativas_ignoradas_interno(
        filial_ativa,
        data_inicio,
        data_fim,
        motorista_ids,
    )
    ignorados = [serializar_tentativa_ignorada_gsheets(t) for t in ignoradas_qs]

    tentativas = listar_tentativas_para_gsheets(
        filial_ativa,
        data_inicio,
        data_fim,
        motorista_ids,
    )
    if not tentativas:
        raise ValidationError(MSG_NENHUMA_ELEGIVEL)

    rows = montar_rows_gsheets_logistica_motorista(tentativas)
    try:
        append_logistica_motorista_rows(spreadsheet_id, sheet_name, rows)
    except Exception as exc:
        msg = str(exc)
        if "not supported for this document" in msg:
            raise ValidationError(MSG_PLANILHA_NAO_NATIVA) from exc
        raise

    tentativa_ids = [t.id for t in tentativas]
    n = len(tentativa_ids)
    n_ign = len(ignorados)
    mensagem = f"{n} tentativa(s) enviada(s) ao Google Sheets com sucesso."
    if n_ign:
        mensagem += f" {n_ign} ignorada(s) (interno)."
    return {
        "enviados": n,
        "tentativa_ids": tentativa_ids,
        "ignorados": ignorados,
        "ignorados_total": n_ign,
        "mensagem": mensagem,
    }
