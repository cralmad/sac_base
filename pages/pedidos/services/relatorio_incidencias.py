"""Relatório de incidências (logística): filtros por data, origem e motorista; agrupamento por origem."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from itertools import groupby

from django.utils import timezone

from pages.motorista.models import Motorista
from pages.pedidos.models import INCIDENCIA_ORIG_CHOICE, Incidencia
from pages.pedidos.services.relatorio_fechamento import formatar_decimal_pt_br, validar_periodo

_ORDEM_ORIGEM = [v for v, _ in INCIDENCIA_ORIG_CHOICE]


def _formatar_data_pt(d: date | None) -> str:
    if not d:
        return ""
    return d.strftime("%d/%m/%Y")


def _formatar_dt_pt(dt: datetime | None) -> str:
    if not dt:
        return ""
    if timezone.is_aware(dt):
        dt = timezone.localtime(dt)
    return dt.strftime("%d/%m/%Y %H:%M")


def _valor_decimal(inc: Incidencia) -> Decimal:
    if inc.valor is None:
        return Decimal("0")
    return Decimal(str(inc.valor))


def _formatar_soma_valores(soma: Decimal) -> str:
    return formatar_decimal_pt_br(soma)


def _serializar_linha(inc: Incidencia) -> dict:
    ped = inc.pedido
    fotos_publicas = [
        {"id": f["id"], "url": f["url"], "thumb_url": f.get("thumb_url", f["url"])}
        for f in (inc.fotos or [])
    ]
    valor_dec = _valor_decimal(inc)
    valor_fmt = formatar_decimal_pt_br(valor_dec) if inc.valor is not None else ""
    return {
        "id": inc.id,
        "pedido_id": ped.id,
        "pedido": ped.pedido or str(ped.id_vonzu),
        "data": _formatar_data_pt(inc.data),
        "data_ordem": inc.data.isoformat() if inc.data else "",
        "origem": inc.origem or "",
        "tipo": inc.tipo or "",
        "artigo": inc.artigo or "",
        "valor": str(inc.valor) if inc.valor is not None else "",
        "valor_fmt": valor_fmt,
        "valor_num": str(valor_dec),
        "motorista_id": inc.motorista_id,
        "motorista": inc.motorista.nome if inc.motorista_id else "",
        "obs": inc.obs or "",
        "created_at_fmt": _formatar_dt_pt(inc.created_at),
        "fotos": fotos_publicas,
        "fotos_count": len(fotos_publicas),
    }


def _somar_valores_linhas(linhas: list[dict]) -> Decimal:
    return sum((Decimal(linha["valor_num"]) for linha in linhas), Decimal("0"))


def _montar_subgrupos_motorista(linhas: list[dict]) -> list[dict]:
    def sort_key(item: dict):
        nome = (item.get("motorista") or "").strip() or "(sem motorista)"
        mid = item.get("motorista_id")
        return (nome.lower(), mid or 0)

    linhas_ordenadas = sorted(linhas, key=sort_key)
    subgrupos = []
    for nome_key, grupo_iter in groupby(
        linhas_ordenadas,
        key=lambda x: (x.get("motorista") or "").strip() or "(sem motorista)",
    ):
        grupo_list = list(grupo_iter)
        soma = _somar_valores_linhas(grupo_list)
        subgrupos.append(
            {
                "motorista_id": grupo_list[0].get("motorista_id"),
                "motorista_nome": nome_key,
                "total": len(grupo_list),
                "valor_total_fmt": _formatar_soma_valores(soma),
                "linhas": grupo_list,
            }
        )
    return subgrupos


def _montar_grupos_origem(linhas: list[dict], *, agrupar_motorista: bool) -> list[dict]:
    por_origem: dict[str, list[dict]] = {o: [] for o in _ORDEM_ORIGEM}
    for linha in linhas:
        origem = linha.get("origem") or ""
        if origem not in por_origem:
            por_origem[origem] = []
        por_origem[origem].append(linha)

    grupos = []
    chaves = _ORDEM_ORIGEM + [k for k in por_origem if k not in _ORDEM_ORIGEM]
    for origem in chaves:
        lista = por_origem.get(origem) or []
        if not lista:
            continue
        soma = _somar_valores_linhas(lista)
        bloco: dict = {
            "origem": origem,
            "total": len(lista),
            "valor_total_fmt": _formatar_soma_valores(soma),
            "agrupar_motorista": agrupar_motorista,
        }
        if agrupar_motorista:
            bloco["subgrupos"] = _montar_subgrupos_motorista(lista)
        else:
            bloco["linhas"] = lista
        grupos.append(bloco)
    return grupos


def montar_relatorio_incidencias(
    filial_ativa,
    data_ini: date,
    data_fim: date,
    *,
    origem: str | None = None,
    motorista_id: int | None = None,
    agrupar_motorista: bool = False,
) -> dict:
    qs = (
        Incidencia.objects.filter(
            pedido__filial=filial_ativa,
            data__range=(data_ini, data_fim),
        )
        .select_related("pedido", "motorista")
        .order_by("data", "pedido__pedido", "id")
    )
    if origem:
        qs = qs.filter(origem=origem)
    if motorista_id is not None:
        qs = qs.filter(motorista_id=motorista_id)

    linhas = [_serializar_linha(inc) for inc in qs]
    soma_geral = _somar_valores_linhas(linhas)
    periodo_texto = f"{_formatar_data_pt(data_ini)} a {_formatar_data_pt(data_fim)}"
    if data_ini == data_fim:
        periodo_texto = _formatar_data_pt(data_ini)

    return {
        "periodo_texto": periodo_texto,
        "total": len(linhas),
        "valor_total_fmt": _formatar_soma_valores(soma_geral),
        "agrupar_motorista": agrupar_motorista,
        "grupos_origem": _montar_grupos_origem(linhas, agrupar_motorista=agrupar_motorista),
    }


def validar_e_montar_relatorio_incidencias(filial_ativa, filtros: dict) -> tuple[dict | None, str | None]:
    from sac_base.coercion import parse_date, parse_int

    if not filial_ativa:
        return None, "Filial ativa não encontrada na sessão."

    data_inicial = (filtros.get("data_inicial") or "").strip()
    data_final = (filtros.get("data_final") or "").strip()
    if not data_inicial:
        return None, "A data inicial é obrigatória."
    if not data_final:
        return None, "A data final é obrigatória."

    dt_ini = parse_date(data_inicial)
    dt_fim = parse_date(data_final)
    if not dt_ini or not dt_fim:
        return None, "Data inválida."

    err_periodo = validar_periodo(dt_ini, dt_fim)
    if err_periodo:
        return None, err_periodo

    origem = (filtros.get("origem") or "").strip()
    origens_validas = {v for v, _ in INCIDENCIA_ORIG_CHOICE}
    if origem and origem not in origens_validas:
        return None, "Origem inválida."

    raw_mot = filtros.get("motorista_id")
    motorista_id = parse_int(raw_mot, context="form") if raw_mot not in (None, "") else None
    if motorista_id is not None:
        existe = Motorista.objects.filter(
            id=motorista_id,
            filial=filial_ativa,
            is_deleted=False,
        ).exists()
        if not existe:
            return None, "Motorista inválido para a filial ativa."

    agr = filtros.get("agrupar_motorista")
    agrupar_motorista = agr in (True, "true", "True", "1", 1)

    payload = montar_relatorio_incidencias(
        filial_ativa,
        dt_ini,
        dt_fim,
        origem=origem or None,
        motorista_id=motorista_id,
        agrupar_motorista=agrupar_motorista,
    )
    return payload, None


def montar_sisvar_relatorio_incidencias_get(*, request, acoes: dict) -> dict:
    from sac_base.sisvar_builders import build_sisvar_payload

    filial_ativa = getattr(request, "filial_ativa", None)
    motoristas_choices = []
    if filial_ativa:
        motoristas_choices = [
            {"value": m.id, "label": m.nome}
            for m in Motorista.objects.filter(is_deleted=False, filial=filial_ativa).order_by("nome")
        ]
    origens_choices = [{"value": "", "label": "Todas"}] + [
        {"value": v, "label": l} for v, l in INCIDENCIA_ORIG_CHOICE
    ]
    return build_sisvar_payload(
        permissions={"relatorio_incidencias": acoes},
        options={
            "motoristas": motoristas_choices,
            "origens": origens_choices,
        },
        datasets={"filial_nome": filial_ativa.nome if filial_ativa else ""},
    )
