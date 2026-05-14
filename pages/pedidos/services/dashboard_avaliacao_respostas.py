"""Dashboard de avaliações: funil e-mail × resposta e agregados por pergunta."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db.models import Avg, Count, Q

from pages.pedidos.services.relatorio_avaliacao_respostas import (
    PERGUNTAS_AVALIACAO_META,
    _CAMPO_MODELO_POR_CHAVE,
    _formatar_data_pt,
    qs_avaliacoes_periodo_anotada_motorista,
)

_SIM_NAO = {"p1", "p2", "p5", "p7", "p10"}
_SIM_NAO_NA = {"p8"}
_LIKERT = {"p3", "p4", "p6", "p9"}


def _pct(part: int, total: int) -> float | None:
    if total <= 0:
        return None
    return round(100.0 * float(part) / float(total), 1)


def _agregar_categorica(qs, campo_modelo: str) -> tuple[dict[str, int], int]:
    rows = (
        qs.exclude(**{f"{campo_modelo}__isnull": True})
        .exclude(**{campo_modelo: ""})
        .values(campo_modelo)
        .annotate(c=Count("id"))
    )
    dist: dict[str, int] = {}
    n = 0
    for row in rows:
        k = (row[campo_modelo] or "").strip() or "Outro"
        c = row["c"]
        dist[k] = dist.get(k, 0) + c
        n += c
    return dist, n


def _dist_pct(dist: dict[str, int], n: int) -> dict[str, float]:
    if n <= 0:
        return {}
    return {k: round(100.0 * float(v) / float(n), 1) for k, v in sorted(dist.items(), key=lambda x: (-x[1], x[0]))}


def _agregar_likert(qs, campo_modelo: str) -> dict:
    agg = qs.aggregate(
        avg=Avg(campo_modelo),
        n=Count("id", filter=Q(**{f"{campo_modelo}__isnull": False})),
        n1=Count("id", filter=Q(**{campo_modelo: 1})),
        n2=Count("id", filter=Q(**{campo_modelo: 2})),
        n3=Count("id", filter=Q(**{campo_modelo: 3})),
        n4=Count("id", filter=Q(**{campo_modelo: 4})),
        n5=Count("id", filter=Q(**{campo_modelo: 5})),
    )
    n = int(agg["n"] or 0)
    abs_d = {1: int(agg["n1"] or 0), 2: int(agg["n2"] or 0), 3: int(agg["n3"] or 0), 4: int(agg["n4"] or 0), 5: int(agg["n5"] or 0)}
    pct_d = {str(k): (_pct(abs_d[k], n) or 0.0) for k in range(1, 6)}
    media = agg["avg"]
    media_f = None
    if media is not None:
        media_f = float(Decimal(str(media)).quantize(Decimal("0.01")))
    return {
        "n": n,
        "media": media_f,
        "distribuicao_abs": abs_d,
        "distribuicao_pct": pct_d,
    }


def montar_dashboard_avaliacao_respostas(
    filial_ativa,
    data_ini: date,
    data_fim: date,
    *,
    motorista_id: int | None = None,
) -> dict:
    qs_base = qs_avaliacoes_periodo_anotada_motorista(
        filial_ativa, data_ini, data_fim, motorista_id=motorista_id
    )

    funil_agg = qs_base.aggregate(
        n_email_enviado=Count("id", filter=Q(email_enviado=True)),
        n_respondido=Count("id", filter=Q(respondido_em__isnull=False)),
        n_respondido_e_enviado=Count(
            "id",
            filter=Q(email_enviado=True, respondido_em__isnull=False),
        ),
    )
    n_email = int(funil_agg["n_email_enviado"] or 0)
    n_resp_env = int(funil_agg["n_respondido_e_enviado"] or 0)
    taxa = _pct(n_resp_env, n_email)
    pct_nao = round(100.0 - taxa, 1) if taxa is not None else None

    qs_resp = qs_base.filter(respondido_em__isnull=False)
    n_total_resp = qs_resp.count()
    n_comentario = qs_resp.exclude(comentario__isnull=True).exclude(comentario="").count()
    n_sem_motorista = qs_resp.filter(t_motorista_id__isnull=True).count()

    perguntas_resumo = []
    likert_medias = []
    likert_ns = []

    for meta in PERGUNTAS_AVALIACAO_META:
        chave = meta["campo"]
        campo_m = _CAMPO_MODELO_POR_CHAVE[chave]
        if chave in _SIM_NAO:
            dist, n = _agregar_categorica(qs_resp, campo_m)
            perguntas_resumo.append(
                {
                    "campo": chave,
                    "tipo": "sim_nao",
                    "n": n,
                    "distribuicao_abs": dist,
                    "distribuicao_pct": _dist_pct(dist, n),
                }
            )
        elif chave in _SIM_NAO_NA:
            dist, n = _agregar_categorica(qs_resp, campo_m)
            perguntas_resumo.append(
                {
                    "campo": chave,
                    "tipo": "sim_nao_na",
                    "n": n,
                    "distribuicao_abs": dist,
                    "distribuicao_pct": _dist_pct(dist, n),
                }
            )
        elif chave in _LIKERT:
            block = _agregar_likert(qs_resp, campo_m)
            perguntas_resumo.append(
                {
                    "campo": chave,
                    "tipo": "likert_1_5",
                    **block,
                }
            )
            if block.get("media") is not None and block["n"] > 0:
                likert_medias.append(float(block["media"]) * block["n"])
                likert_ns.append(block["n"])

    media_global_likert = None
    sum_n = sum(likert_ns)
    if sum_n > 0 and likert_medias:
        s = sum(likert_medias)
        media_global_likert = float(Decimal(str(s / sum_n)).quantize(Decimal("0.01")))

    likert_comparativo = []
    for item in perguntas_resumo:
        if item["tipo"] == "likert_1_5":
            likert_comparativo.append(
                {
                    "campo": item["campo"],
                    "label": item["campo"].upper(),
                    "media": item.get("media"),
                    "n": item.get("n", 0),
                }
            )

    periodo_texto = f"{_formatar_data_pt(data_ini)} a {_formatar_data_pt(data_fim)}"
    return {
        "periodo_texto": periodo_texto,
        "perguntas_meta": PERGUNTAS_AVALIACAO_META,
        "funil": {
            "n_email_enviado": n_email,
            "n_respondido": int(funil_agg["n_respondido"] or 0),
            "n_respondido_e_enviado": n_resp_env,
            "taxa_resposta_sobre_enviadas_pct": taxa,
            "pct_nao_respondeu_sobre_enviadas": pct_nao,
        },
        "total_respondidas": n_total_resp,
        "com_comentario": n_comentario,
        "pct_comentario": _pct(n_comentario, n_total_resp) if n_total_resp else None,
        "n_sem_motorista": n_sem_motorista,
        "media_global_likert": media_global_likert,
        "likert_comparativo": likert_comparativo,
        "perguntas_resumo": perguntas_resumo,
    }


def validar_e_montar_dashboard_avaliacao_respostas(filial_ativa, filtros: dict) -> tuple[dict | None, str | None]:
    from pages.pedidos.services.relatorio_fechamento import validar_periodo
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

    raw_mot = filtros.get("motorista_id")
    motorista_id = parse_int(raw_mot, context="form") if raw_mot not in (None, "") else None

    payload = montar_dashboard_avaliacao_respostas(
        filial_ativa,
        dt_ini,
        dt_fim,
        motorista_id=motorista_id,
    )
    return payload, None


def montar_sisvar_relatorio_avaliacao_dashboard_get(*, request, acoes: dict) -> dict:
    from pages.motorista.models import Motorista
    from sac_base.sisvar_builders import build_sisvar_payload

    filial_ativa = getattr(request, "filial_ativa", None)
    motoristas_choices = []
    if filial_ativa:
        motoristas_choices = [
            {"value": m.id, "label": m.nome}
            for m in Motorista.objects.filter(is_deleted=False, filial=filial_ativa).order_by("nome")
        ]
    return build_sisvar_payload(
        permissions={"relatorio_avaliacao_dashboard": acoes},
        options={"motoristas": motoristas_choices},
        datasets={
            "filial_nome": filial_ativa.nome if filial_ativa else "",
            "perguntas_meta": PERGUNTAS_AVALIACAO_META,
        },
    )
