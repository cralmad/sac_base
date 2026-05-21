"""Agrupamento obrigatório do relatório de previsibilidade: data → categoria → subgrupo de origem."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from pages.agenda.constants import CATEGORIA_CHOICES, CategoriaAgenda
from pages.financeiro.models import RegistroFinanceiroTipo

_LABELS_CATEGORIA = dict(CATEGORIA_CHOICES)

_ORDEM_CATEGORIA = {
    CategoriaAgenda.FINANCEIRO: 0,
    CategoriaAgenda.OPERACIONAL: 1,
    CategoriaAgenda.LEMBRETE: 2,
}

_ORDEM_SUBGRUPO_FINANCEIRO = {
    RegistroFinanceiroTipo.ENTRADA: 0,
    RegistroFinanceiroTipo.SAIDA: 1,
    "_previsao": 2,
    "_geral": 3,
}

_CHAVES_VALOR_OPOSTO_FINANCEIRO = frozenset({
    RegistroFinanceiroTipo.ENTRADA,
    RegistroFinanceiroTipo.SAIDA,
})


def _formatar_valor_br(valor: Decimal | None) -> str | None:
    if valor is None:
        return None
    return f"{valor:.2f}".replace(".", ",")


def resolver_subagrupamento(ev: dict) -> tuple[str, str]:
    """Subagrupamento herdado do model de origem (ex.: ENTRADA/SAÍDA no financeiro)."""
    categoria = (ev.get("categoria") or "").strip()
    meta = ev.get("meta") or {}
    provider_key = (ev.get("provider_key") or "").strip()

    if categoria == CategoriaAgenda.FINANCEIRO or provider_key == "financeiro.registro_financeiro":
        tipo = (meta.get("tipo") or "").strip()
        if tipo == RegistroFinanceiroTipo.ENTRADA:
            return RegistroFinanceiroTipo.ENTRADA, "Entrada"
        if tipo == RegistroFinanceiroTipo.SAIDA:
            return RegistroFinanceiroTipo.SAIDA, "Saída"
        payload = meta.get("payload_template") if isinstance(meta.get("payload_template"), dict) else {}
        tipo_payload = (payload.get("tipo") or "").strip()
        if tipo_payload == RegistroFinanceiroTipo.ENTRADA:
            return RegistroFinanceiroTipo.ENTRADA, "Entrada (previsão)"
        if tipo_payload == RegistroFinanceiroTipo.SAIDA:
            return RegistroFinanceiroTipo.SAIDA, "Saída (previsão)"
        return "_previsao", "Previsão financeira"

    return "_geral", "Geral"


def enriquecer_evento_relatorio(ev: dict) -> dict:
    """Campos derivados para exibição e totais."""
    out = dict(ev)
    cat = (ev.get("categoria") or "").strip()
    out["categoria_label"] = _LABELS_CATEGORIA.get(cat, cat or "—")
    chave, rotulo = resolver_subagrupamento(ev)
    out["subagrupamento_chave"] = chave
    out["subagrupamento_label"] = rotulo

    valor_dec = ev.get("valor_decimal")
    if valor_dec is None and ev.get("valor") is not None:
        from sac_base.coercion import parse_decimal

        valor_dec = parse_decimal(ev.get("valor"), context="form")
    if valor_dec is not None:
        if not isinstance(valor_dec, Decimal):
            valor_dec = Decimal(str(valor_dec))
        out["valor_decimal"] = str(valor_dec)
        out["valor"] = out.get("valor") or _formatar_valor_br(valor_dec)

    obs = (ev.get("observacao") or "").strip()
    if not obs:
        meta = ev.get("meta") or {}
        obs = (meta.get("observacao") or "").strip()
    if not obs and ev.get("tipo_dado") == "flutuante":
        obs = (ev.get("subtitulo") or "").strip()
    out["observacao"] = obs
    return out


def _somar_valores(eventos: list[dict]) -> Decimal | None:
    total = Decimal("0")
    tem_valor = False
    for ev in eventos:
        raw = ev.get("valor_decimal")
        if raw in (None, ""):
            continue
        total += Decimal(str(raw))
        tem_valor = True
    return total if tem_valor else None


def _tem_entrada_e_saida_financeiro(eventos: list[dict]) -> bool:
    """True se o conjunto mistura ENTRADA e SAÍDA (valores opostos — não somar)."""
    chaves: set[str] = set()
    for ev in eventos:
        if (ev.get("categoria") or "").strip() != CategoriaAgenda.FINANCEIRO:
            continue
        ch = ev.get("subagrupamento_chave")
        if ch in _CHAVES_VALOR_OPOSTO_FINANCEIRO:
            chaves.add(ch)
    return (
        RegistroFinanceiroTipo.ENTRADA in chaves
        and RegistroFinanceiroTipo.SAIDA in chaves
    )


def _pode_somar_valor_agregado(eventos: list[dict], *, categoria: str | None = None) -> bool:
    if categoria == CategoriaAgenda.FINANCEIRO:
        return False
    return not _tem_entrada_e_saida_financeiro(eventos)


def _totais_grupo(
    eventos: list[dict],
    *,
    categoria: str | None = None,
    somar_valor: bool | None = None,
) -> dict:
    if somar_valor is None:
        somar_valor = _pode_somar_valor_agregado(eventos, categoria=categoria)
    out: dict = {
        "total_registros": len(eventos),
        "total_valor": None,
    }
    if somar_valor:
        out["total_valor"] = _formatar_valor_br(_somar_valores(eventos))
    return out


def _totais_valor_por_subgrupo(subgrupos: list[dict]) -> list[dict]:
    """Totais de valor por subgrupo (ex.: Entrada e Saída separados no financeiro)."""
    itens = []
    for sg in subgrupos:
        if sg.get("total_valor"):
            itens.append(
                {
                    "label": sg.get("label") or sg.get("chave") or "",
                    "total_registros": sg.get("total_registros", 0),
                    "total_valor": sg["total_valor"],
                }
            )
    return itens


def montar_agrupamentos_relatorio(eventos: list[dict]) -> list[dict]:
    """
    Hierarquia: data → categoria → subagrupamento → eventos (uma linha cada no front).
    """
    enriquecidos = [enriquecer_evento_relatorio(e) for e in eventos]

    por_data: dict[str, list[dict]] = defaultdict(list)
    for ev in enriquecidos:
        por_data[ev["data"]].append(ev)

    agrupamentos: list[dict] = []
    for data_iso in sorted(por_data.keys()):
        evs_dia = por_data[data_iso]
        por_cat: dict[str, list[dict]] = defaultdict(list)
        for ev in evs_dia:
            por_cat[ev.get("categoria") or ""].append(ev)

        categorias_out = []
        for cat in sorted(por_cat.keys(), key=lambda c: (_ORDEM_CATEGORIA.get(c, 99), c)):
            evs_cat = por_cat[cat]
            por_sub: dict[str, list[dict]] = defaultdict(list)
            labels_sub: dict[str, str] = {}
            for ev in evs_cat:
                ch = ev["subagrupamento_chave"]
                por_sub[ch].append(ev)
                labels_sub[ch] = ev["subagrupamento_label"]

            subgrupos_out = []
            for ch in sorted(
                por_sub.keys(),
                key=lambda k: (_ORDEM_SUBGRUPO_FINANCEIRO.get(k, 99), labels_sub.get(k, k)),
            ):
                evs_sub = sorted(
                    por_sub[ch],
                    key=lambda e: (e.get("tipo_dado", ""), e.get("titulo", ""), e.get("id", "")),
                )
                subgrupos_out.append(
                    {
                        "chave": ch,
                        "label": labels_sub.get(ch, ch),
                        **_totais_grupo(evs_sub),
                        "eventos": evs_sub,
                    }
                )

            todos_cat = [ev for sg in subgrupos_out for ev in sg["eventos"]]
            cat_totais = _totais_grupo(todos_cat, categoria=cat)
            if cat == CategoriaAgenda.FINANCEIRO:
                cat_totais["totais_valor_subgrupos"] = _totais_valor_por_subgrupo(subgrupos_out)
            categorias_out.append(
                {
                    "categoria": cat,
                    "categoria_label": _LABELS_CATEGORIA.get(cat, cat or "—"),
                    **cat_totais,
                    "subgrupos": subgrupos_out,
                }
            )

        dia_totais = _totais_grupo(evs_dia)
        if _tem_entrada_e_saida_financeiro(evs_dia):
            dia_totais["totais_valor_subgrupos"] = _totais_valor_por_subgrupo(
                [sg for cat in categorias_out for sg in cat.get("subgrupos", [])]
            )
        agrupamentos.append(
            {
                "data": data_iso,
                **dia_totais,
                "categorias": categorias_out,
            }
        )

    return agrupamentos
