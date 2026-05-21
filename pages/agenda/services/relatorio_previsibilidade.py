from __future__ import annotations

from datetime import date
from decimal import Decimal

from pages.agenda.constants import PERIODO_MAXIMO_AGENDA_DIAS
from pages.agenda.services.agenda_auto_provider import coletar_eventos_concretos
from pages.agenda.services.agrupamento_relatorio import montar_agrupamentos_relatorio
from pages.agenda.services.coletar_flutuantes import coletar_eventos_flutuantes
from pages.filial.models import Filial
from sac_base.coercion import parse_date
from sac_base.sisvar_builders import build_sisvar_payload


def validar_periodo_agenda(data_ini: date, data_fim: date) -> str | None:
    if data_ini > data_fim:
        return "A data inicial não pode ser maior que a data final."
    if (data_fim - data_ini).days > PERIODO_MAXIMO_AGENDA_DIAS:
        return f"O período máximo é de {PERIODO_MAXIMO_AGENDA_DIAS} dias."
    return None


def _formatar_valor_br(valor: Decimal | None) -> str | None:
    if valor is None:
        return None
    return f"{valor:.2f}".replace(".", ",")


def normalizar_evento_concreto(dto, *, prefixo_app: str) -> dict:
    url = dto.url
    if url and not url.startswith("/") and prefixo_app:
        url = f"{prefixo_app.rstrip('/')}/{url.lstrip('/')}"
    meta = dto.meta or {}
    return {
        "id": f"concreto:{dto.provider_key}:{dto.origem_id}",
        "tipo_dado": "concreto",
        "data": dto.data.isoformat(),
        "categoria": dto.categoria,
        "provider_key": dto.provider_key,
        "origem_id": dto.origem_id,
        "titulo": dto.titulo,
        "subtitulo": dto.subtitulo,
        "valor": _formatar_valor_br(dto.valor),
        "valor_decimal": str(dto.valor) if dto.valor is not None else None,
        "observacao": (meta.get("observacao") or "").strip(),
        "status": dto.status,
        "url": url,
        "acoes": {"pode_confirmar": False, "pode_materializar": False},
        "modo_evento": None,
        "tipo_materializacao": None,
        "meta": meta,
    }


def montar_sisvar_relatorio_previsibilidade_get(
    *,
    usuario,
    request,
    acoes_agenda: dict,
) -> dict:
    from pages.agenda.constants import CATEGORIA_CHOICES, DIAS_SEMANA_AGENDA
    from pages.agenda.services.agenda_materializacao_orquestrador import listar_tipos_materializacao

    filial_ativa = getattr(request, "filial_ativa", None)
    return build_sisvar_payload(
        permissions={"agenda": acoes_agenda},
        datasets={
            "url_relatorio_post": "/app/agenda/relatorio/previsibilidade/",
            "url_agenda_manual": "/app/agenda/manual/",
            "url_confirmar": "/app/agenda/manual/confirmar-ocorrencia/",
            "url_materializar": "/app/agenda/manual/materializar/",
            "url_schema_materializacao": "/app/agenda/manual/schema-materializacao/",
            "periodo_maximo_dias": PERIODO_MAXIMO_AGENDA_DIAS,
            "categorias_agenda": [{"value": v, "label": l} for v, l in CATEGORIA_CHOICES],
            "dias_semana_agenda": [{"value": v, "label": l} for v, l in DIAS_SEMANA_AGENDA],
            "tipos_materializacao": listar_tipos_materializacao(usuario),
            "filial_ativa_id": str(filial_ativa.id) if filial_ativa else "",
        },
    )


def validar_e_montar_relatorio(
    *,
    data_inicio: date,
    data_fim: date,
    filial_id: int,
    usuario,
    prefixo_app: str,
    pode_confirmar: bool,
    pode_materializar: bool,
) -> tuple[dict | None, str | None]:
    err = validar_periodo_agenda(data_inicio, data_fim)
    if err:
        return None, err

    filial = Filial.objects.filter(id=filial_id, ativa=True).only("id", "codigo", "nome").first()
    if not filial:
        return None, "Filial inválida."

    flutuantes = coletar_eventos_flutuantes(
        filial_id=filial_id,
        data_inicio=data_inicio,
        data_fim=data_fim,
        usuario=usuario,
        pode_confirmar=pode_confirmar,
        pode_materializar=pode_materializar,
    )
    concretos_dto = coletar_eventos_concretos(
        data_inicio=data_inicio,
        data_fim=data_fim,
        filial_id=filial_id,
        usuario=usuario,
    )
    concretos = [normalizar_evento_concreto(d, prefixo_app=prefixo_app) for d in concretos_dto]

    eventos = flutuantes + concretos
    agrupamentos = montar_agrupamentos_relatorio(eventos)

    por_tipo = {"flutuante": 0, "concreto": 0}
    por_status = {"concluido": 0, "pendente": 0}
    for ev in eventos:
        por_tipo[ev["tipo_dado"]] = por_tipo.get(ev["tipo_dado"], 0) + 1
        if ev["tipo_dado"] == "flutuante" and ev.get("status") in por_status:
            por_status[ev["status"]] += 1

    return {
        "success": True,
        "periodo": {
            "data_inicio": data_inicio.isoformat(),
            "data_fim": data_fim.isoformat(),
            "dias": (data_fim - data_inicio).days + 1,
        },
        "filial": {"id": filial.id, "codigo": filial.codigo, "nome": filial.nome},
        "eventos": eventos,
        "agrupamentos": agrupamentos,
        "resumo": {
            "total": len(eventos),
            "por_tipo_dado": por_tipo,
            "por_status_flutuante": por_status,
        },
        "truncado": False,
    }, None


def parse_filtros_relatorio(filtros: dict) -> tuple[date | None, date | None, str | None]:
    dt_ini = parse_date((filtros or {}).get("data_inicio"))
    dt_fim = parse_date((filtros or {}).get("data_fim"))
    if not dt_ini or not dt_fim:
        return None, None, "Informe data início e data fim."
    return dt_ini, dt_fim, None
