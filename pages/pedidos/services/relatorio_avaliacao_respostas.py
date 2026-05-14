"""Relatório de respostas à pesquisa de satisfação (logística): filtros por prev_entrega, motorista, agrupamento opcional."""

from __future__ import annotations

from datetime import date, datetime
from itertools import groupby

from django.db.models import CharField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from pages.motorista.models import Motorista
from pages.pedidos.models import AvaliacaoPedido, TentativaEntrega

# Cabeçalho curto (UI) e descrição completa (tooltip), alinhado a `avaliacao_publica.html`
PERGUNTAS_AVALIACAO_META = [
    {
        "campo": "p1",
        "sigla": "P1",
        "titulo_curto": "Prazo",
        "descricao": "A entrega foi feita no prazo combinado?",
    },
    {
        "campo": "p2",
        "sigla": "P2",
        "titulo_curto": "Aviso",
        "descricao": "Recebeu aviso antes da chegada da equipa?",
    },
    {
        "campo": "p3",
        "sigla": "P3",
        "titulo_curto": "Educação",
        "descricao": "Educação e simpatia da equipa (1–5).",
    },
    {
        "campo": "p4",
        "sigla": "P4",
        "titulo_curto": "Manuseio",
        "descricao": "Cuidado no manuseio da encomenda (1–5).",
    },
    {
        "campo": "p5",
        "sigla": "P5",
        "titulo_curto": "Identif.",
        "descricao": "A equipa estava identificada/uniformizada?",
    },
    {
        "campo": "p6",
        "sigla": "P6",
        "titulo_curto": "Facilidade",
        "descricao": "Quão fácil foi o processo de receber a encomenda? (1–5)",
    },
    {
        "campo": "p7",
        "sigla": "P7",
        "titulo_curto": "Veículo",
        "descricao": "O veículo parecia limpo e organizado?",
    },
    {
        "campo": "p8",
        "sigla": "P8",
        "titulo_curto": "Dúvidas",
        "descricao": "A equipa esclareceu as suas dúvidas no local?",
    },
    {
        "campo": "p9",
        "sigla": "P9",
        "titulo_curto": "Global",
        "descricao": "Avaliação geral da satisfação (1–5).",
    },
    {
        "campo": "p10",
        "sigla": "P10",
        "titulo_curto": "Recom.",
        "descricao": "Recomendaria o nosso serviço de transporte?",
    },
]

_CAMPO_MODELO_POR_CHAVE = {
    "p1": "p1_entrega_no_prazo",
    "p2": "p2_aviso_antes_chegada",
    "p3": "p3_educacao_simpatia",
    "p4": "p4_cuidado_encomenda",
    "p5": "p5_equipa_identificada",
    "p6": "p6_facilidade_processo",
    "p7": "p7_veiculo_limpo",
    "p8": "p8_esclareceu_duvidas",
    "p9": "p9_satisfacao_geral",
    "p10": "p10_recomendaria",
}


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


def _valor_p(av: AvaliacaoPedido, chave: str) -> str | int | None:
    nome_modelo = _CAMPO_MODELO_POR_CHAVE[chave]
    v = getattr(av, nome_modelo)
    if v is None:
        return ""
    return v


def _serializar_linha(av: AvaliacaoPedido) -> dict:
    ped = av.pedido
    comentario = (av.comentario or "").strip()
    mid = getattr(av, "t_motorista_id", None)
    mnome = getattr(av, "t_motorista_nome", None) or ""
    return {
        "avaliacao_id": av.id,
        "pedido": ped.pedido or str(ped.id_vonzu),
        "prev_entrega": ped.prev_entrega.isoformat() if ped.prev_entrega else "",
        "prev_entrega_fmt": _formatar_data_pt(ped.prev_entrega),
        "motorista_id": mid,
        "motorista": mnome,
        "respondido_em": av.respondido_em.isoformat() if av.respondido_em else "",
        "respondido_em_fmt": _formatar_dt_pt(av.respondido_em),
        "p1": _valor_p(av, "p1"),
        "p2": _valor_p(av, "p2"),
        "p3": _valor_p(av, "p3"),
        "p4": _valor_p(av, "p4"),
        "p5": _valor_p(av, "p5"),
        "p6": _valor_p(av, "p6"),
        "p7": _valor_p(av, "p7"),
        "p8": _valor_p(av, "p8"),
        "p9": _valor_p(av, "p9"),
        "p10": _valor_p(av, "p10"),
        "tem_comentario": bool(comentario),
        "comentario": comentario,
    }


def qs_avaliacoes_periodo_anotada_motorista(
    filial_ativa,
    data_ini: date,
    data_fim: date,
    *,
    motorista_id: int | None = None,
):
    """Queryset de `AvaliacaoPedido` no período (`prev_entrega`) com motorista da tentativa alinhada; **sem** filtrar `respondido_em`."""
    tent_sub = (
        TentativaEntrega.objects.filter(
            pedido_id=OuterRef("pedido_id"),
            data_tentativa=OuterRef("pedido__prev_entrega"),
        )
        .order_by("id")
        .values("motorista_id")[:1]
    )
    mot_nome_sub = Motorista.objects.filter(
        pk=OuterRef("t_motorista_id"),
        filial_id=filial_ativa.pk,
        is_deleted=False,
    ).values("nome")[:1]

    qs = (
        AvaliacaoPedido.objects.filter(
            pedido__filial=filial_ativa,
            pedido__prev_entrega__range=(data_ini, data_fim),
        )
        .select_related("pedido")
        .annotate(
            t_motorista_id=Subquery(tent_sub),
            t_motorista_nome=Coalesce(
                Subquery(mot_nome_sub),
                Value("", output_field=CharField()),
            ),
        )
        .order_by("pedido__prev_entrega", "respondido_em", "id")
    )
    if motorista_id is not None:
        qs = qs.filter(t_motorista_id=motorista_id)
    return qs


def montar_relatorio_avaliacao_respostas(
    filial_ativa,
    data_ini: date,
    data_fim: date,
    *,
    motorista_id: int | None = None,
    agrupar_motorista: bool = False,
) -> dict:
    qs = qs_avaliacoes_periodo_anotada_motorista(
        filial_ativa, data_ini, data_fim, motorista_id=motorista_id
    ).filter(respondido_em__isnull=False)

    linhas_objs = list(qs)
    linhas = [_serializar_linha(av) for av in linhas_objs]

    periodo_texto = f"{_formatar_data_pt(data_ini)} a {_formatar_data_pt(data_fim)}"
    out: dict = {
        "periodo_texto": periodo_texto,
        "perguntas_meta": PERGUNTAS_AVALIACAO_META,
        "total_linhas": len(linhas),
        "agrupar_motorista": agrupar_motorista,
    }

    if not agrupar_motorista:
        out["linhas"] = linhas
        return out

    def sort_key(item):
        nome = (item.get("motorista") or "").strip() or "(sem motorista)"
        mid = item.get("motorista_id")
        return (nome.lower(), mid or 0)

    linhas_ordenadas = sorted(linhas, key=sort_key)
    grupos = []
    for nome_key, grupo_iter in groupby(linhas_ordenadas, key=lambda x: (x.get("motorista") or "").strip() or "(sem motorista)"):
        grupo_list = list(grupo_iter)
        mid0 = grupo_list[0].get("motorista_id")
        grupos.append(
            {
                "motorista_id": mid0,
                "motorista_nome": nome_key,
                "linhas": grupo_list,
            }
        )
    out["grupos"] = grupos
    return out


def validar_e_montar_relatorio_avaliacao_respostas(filial_ativa, filtros: dict) -> tuple[dict | None, str | None]:
    """Valida filtros HTTP e devolve o payload do relatório ou mensagem de erro."""
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

    agr = filtros.get("agrupar_motorista")
    agrupar_motorista = agr in (True, "true", "True", "1", 1)

    payload = montar_relatorio_avaliacao_respostas(
        filial_ativa,
        dt_ini,
        dt_fim,
        motorista_id=motorista_id,
        agrupar_motorista=agrupar_motorista,
    )
    return payload, None


def montar_sisvar_relatorio_avaliacao_respostas_get(*, request, acoes: dict) -> dict:
    from sac_base.sisvar_builders import build_sisvar_payload

    filial_ativa = getattr(request, "filial_ativa", None)
    motoristas_choices = []
    if filial_ativa:
        motoristas_choices = [
            {"value": m.id, "label": m.nome}
            for m in Motorista.objects.filter(is_deleted=False, filial=filial_ativa).order_by("nome")
        ]
    return build_sisvar_payload(
        permissions={"relatorio_avaliacao_respostas": acoes},
        options={"motoristas": motoristas_choices},
        datasets={
            "filial_nome": filial_ativa.nome if filial_ativa else "",
            "perguntas_meta": PERGUNTAS_AVALIACAO_META,
        },
    )
