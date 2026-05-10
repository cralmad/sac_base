"""Relatório de registros financeiros (entrada/saída), com filtros e agrupamento."""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable, Sequence
from datetime import date
from decimal import Decimal
from itertools import groupby
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.db.models import QuerySet

from pages.cad_cliente.models import Cliente
from pages.filial.models import Filial
from pages.financeiro.models import RegistroFinanceiro, RegistroFinanceiroTipo
from pages.financeiro.services.registro_manual import (
    listar_contrapartes,
    listar_filiais_escrita,
    registro_eh_lancamento_manual_sem_referencia,
)
from pages.motorista.models import Motorista
from sac_base.coercion import parse_date, parse_int
from sac_base.sisvar_builders import build_sisvar_payload

logger = logging.getLogger(__name__)

MAX_LINHAS_RELATORIO = 1000


def montar_sisvar_relatorio_registros_get(*, usuario, request, acoes_financeiro: dict) -> dict:
    """Payload inicial SisVar (GET) para o relatório de registros financeiros."""
    filiais_escrita = listar_filiais_escrita(usuario)
    filial_ativa = getattr(request, "filial_ativa", None)
    filial_ativa_id = str(filial_ativa.id) if filial_ativa else ""
    total_filiais_cadastradas = Filial.objects.filter(ativa=True).count()
    bloquear_filial_select = len(filiais_escrita) <= 1 or total_filiais_cadastradas <= 1
    contraparte = listar_contrapartes()
    return build_sisvar_payload(
        permissions={"financeiro": acoes_financeiro},
        datasets={
            "filiais_escrita": filiais_escrita,
            "filial_ativa_id": filial_ativa_id,
            "bloquear_filial_select": bloquear_filial_select,
            "tipos_registro_financeiro": [
                {"value": val, "label": label}
                for val, label in RegistroFinanceiroTipo.choices
                if val != RegistroFinanceiroTipo.TRANSFERENCIA
            ],
            "contraparte_tipos": contraparte["tipos"],
            "contrapartes_por_tipo": contraparte["por_tipo"],
            "url_relatorio_post": "/app/financeiro/relatorio/registros/",
        },
    )


_TIPO_LABEL = {
    RegistroFinanceiroTipo.ENTRADA: "Entrada",
    RegistroFinanceiroTipo.SAIDA: "Saída",
}


def _formatar_decimal_br(valor: Decimal) -> str:
    return f"{valor:.2f}".replace(".", ",")


def _rotulo_modelo_referencia(ct: ContentType | None) -> str:
    if not ct:
        return "Registro"
    model_cls = ct.model_class()
    if model_cls is not None:
        vn = getattr(model_cls._meta, "verbose_name", None)
        if vn:
            return str(vn).strip().capitalize()
    return (ct.model or "registro").replace("_", " ").strip().capitalize()


def montar_queryset_relatorio(
    *,
    filiais_escrita_ids: Sequence[int],
    filial_id: int | None,
    data_emissao_ini: date | None,
    data_emissao_fim: date | None,
    tipo: str | None,
    contraparte_tipo: str,
    contraparte_id: int | None,
    observacao_icontains: str,
) -> QuerySet[RegistroFinanceiro]:
    qs = (
        RegistroFinanceiro.objects.filter(
            filial_id__in=filiais_escrita_ids,
            tipo__in=[RegistroFinanceiroTipo.ENTRADA, RegistroFinanceiroTipo.SAIDA],
        )
        .select_related("filial", "plano_contas", "referencia_content_type", "contraparte_content_type")
        .order_by("filial_id", "tipo", "data_vencimento", "id")
    )
    if filial_id:
        qs = qs.filter(filial_id=filial_id)
    if data_emissao_ini:
        qs = qs.filter(data_emissao__gte=data_emissao_ini)
    if data_emissao_fim:
        qs = qs.filter(data_emissao__lte=data_emissao_fim)
    if tipo in (RegistroFinanceiroTipo.ENTRADA, RegistroFinanceiroTipo.SAIDA):
        qs = qs.filter(tipo=tipo)
    ct = None
    if contraparte_tipo == "cliente":
        ct = ContentType.objects.get_for_model(Cliente)
    elif contraparte_tipo == "motorista":
        ct = ContentType.objects.get_for_model(Motorista)
    elif contraparte_tipo:
        raise ValueError("Tipo de contraparte inválido.")
    if ct is not None:
        qs = qs.filter(contraparte_content_type_id=ct.id)
        if contraparte_id:
            qs = qs.filter(contraparte_object_id=contraparte_id)
    obs = (observacao_icontains or "").strip()
    if obs:
        qs = qs.filter(observacao__icontains=obs)
    return qs


def _carregar_rotulos_contraparte(registros: list[RegistroFinanceiro]) -> dict[tuple[int, int], str]:
    por_ct: dict[int, list[int]] = defaultdict(list)
    for r in registros:
        if r.contraparte_content_type_id and r.contraparte_object_id:
            por_ct[r.contraparte_content_type_id].append(r.contraparte_object_id)
    out: dict[tuple[int, int], str] = {}
    for ct_id, ids in por_ct.items():
        uniq = list(set(ids))
        ct = ContentType.objects.get(id=ct_id)
        model_cls = ct.model_class()
        if model_cls is Cliente:
            for c in Cliente.objects.filter(id__in=uniq, is_deleted=False):
                out[(ct_id, c.id)] = f"{(c.codigo or '').strip()} - {c.nome}".strip(" -") or str(c.id)
        elif model_cls is Motorista:
            for m in Motorista.objects.filter(id__in=uniq, is_deleted=False):
                out[(ct_id, m.id)] = (m.nome or "").strip() or str(m.id)
        else:
            for pk in uniq:
                out[(ct_id, pk)] = f"#{pk}"
    return out


def _serializar_linha_relatorio(
    r: RegistroFinanceiro,
    contraparte_labels: dict[tuple[int, int], str],
    *,
    prefixo_app_manual: str,
) -> dict[str, Any]:
    filial_label = f"{r.filial.codigo} - {r.filial.nome}"
    ct_id = r.contraparte_content_type_id
    obj_id = r.contraparte_object_id
    if ct_id and obj_id:
        contraparte_label = contraparte_labels.get((ct_id, obj_id), f"#{obj_id}")
        contraparte_key = f"{ct_id}:{obj_id}"
    else:
        contraparte_label = "—"
        contraparte_key = "_sem_"

    if registro_eh_lancamento_manual_sem_referencia(r):
        origem_tipo = "manual"
        origem_texto = "MANUAL"
        base = (prefixo_app_manual or "/app").rstrip("/")
        url_visualizar = f"{base}/financeiro/registro/manual/?visualizar={r.id}"
    else:
        origem_tipo = "automatico"
        ref_ct = r.referencia_content_type
        ref_id = r.referencia_object_id
        rotulo = _rotulo_modelo_referencia(ref_ct)
        if ref_id:
            origem_texto = f"{rotulo} - {ref_id}"
        else:
            origem_texto = rotulo
        url_visualizar = None

    de = r.data_emissao
    dv = r.data_vencimento
    return {
        "id": r.id,
        "filial_id": r.filial_id,
        "filial_label": filial_label,
        "data_emissao_fmt": de.strftime("%d/%m/%Y") if de else "",
        "data_vencimento_iso": dv.isoformat() if dv else "",
        "data_vencimento_fmt": dv.strftime("%d/%m/%Y") if dv else "—",
        "tipo": r.tipo,
        "tipo_label": _TIPO_LABEL.get(r.tipo, r.tipo),
        "ativo_label": r.plano_contas.nome if r.plano_contas_id else "—",
        "plano_contas_id": r.plano_contas_id,
        "contraparte_label": contraparte_label,
        "contraparte_key": contraparte_key,
        "valor_fmt": _formatar_decimal_br(r.valor),
        "valor_numero": float(r.valor),
        "observacao": (r.observacao or "").strip(),
        "status": r.status,
        "origem_tipo": origem_tipo,
        "origem_texto": origem_texto,
        "url_visualizar_manual": url_visualizar,
    }


LevelSpec = tuple[str, Callable[[dict[str, Any]], tuple[str, str]]]


def _montar_niveis_agrupamento(agrupamento: dict[str, Any]) -> list[LevelSpec]:
    niveis: list[LevelSpec] = [
        ("filial", lambda r: (str(r["filial_id"]), r["filial_label"])),
        ("tipo", lambda r: (r["tipo"], r["tipo_label"])),
    ]
    if agrupamento.get("data_vencimento"):
        niveis.append(
            ("vencimento", lambda r: (r["data_vencimento_iso"] or "", r["data_vencimento_fmt"])),
        )
    if agrupamento.get("contraparte"):
        niveis.append(
            ("contraparte", lambda r: (r["contraparte_key"], r["contraparte_label"])),
        )
    if agrupamento.get("ativo"):
        niveis.append(
            ("ativo", lambda r: (str(r["plano_contas_id"] or ""), r["ativo_label"])),
        )
    return niveis


def _construir_arvore_grupos(linhas: list[dict[str, Any]], niveis: list[LevelSpec], level_idx: int) -> dict[str, Any]:
    if level_idx >= len(niveis):
        return {"linhas": linhas}
    nome_nivel, key_fn = niveis[level_idx]
    linhas_ordenadas = sorted(linhas, key=lambda r: (key_fn(r)[0], r["id"]))
    filhos: list[dict[str, Any]] = []
    for _key_val, grupo in groupby(linhas_ordenadas, key=lambda r: key_fn(r)[0]):
        grupo_lista = list(grupo)
        _, titulo = key_fn(grupo_lista[0])
        sub = _construir_arvore_grupos(grupo_lista, niveis, level_idx + 1)
        filhos.append({"nivel": nome_nivel, "titulo": titulo, **sub})
    return {"filhos": filhos}


def executar_relatorio_registros(
    *,
    filiais_escrita_ids: list[int],
    filtros: dict[str, Any],
    agrupamento: dict[str, Any],
    prefixo_app_manual: str,
) -> dict[str, Any]:
    filial_id = parse_int(filtros.get("filial_id"), context="form")
    if not filial_id or filial_id not in filiais_escrita_ids:
        return {"success": False, "mensagem": "Selecione uma matriz/filial válida."}
    data_ini = parse_date(filtros.get("data_emissao_ini"))
    data_fim = parse_date(filtros.get("data_emissao_fim"))
    if not data_ini or not data_fim:
        return {"success": False, "mensagem": "Informe o período de emissão (início e fim)."}
    if data_ini > data_fim:
        return {"success": False, "mensagem": "A data inicial não pode ser maior que a data final."}
    if (data_fim - data_ini).days > 366:
        return {"success": False, "mensagem": "O período máximo é de 366 dias."}

    tipo_f = (filtros.get("tipo") or "").strip().upper()
    tipo = tipo_f if tipo_f in (RegistroFinanceiroTipo.ENTRADA, RegistroFinanceiroTipo.SAIDA) else None
    contraparte_tipo = (filtros.get("contraparte_tipo") or "").strip().lower()
    contraparte_id = parse_int(filtros.get("contraparte_id"), context="form")
    observacao = (filtros.get("observacao") or "").strip()

    try:
        qs = montar_queryset_relatorio(
            filiais_escrita_ids=filiais_escrita_ids,
            filial_id=filial_id,
            data_emissao_ini=data_ini,
            data_emissao_fim=data_fim,
            tipo=tipo,
            contraparte_tipo=contraparte_tipo,
            contraparte_id=contraparte_id,
            observacao_icontains=observacao,
        )
    except ValueError as exc:
        return {"success": False, "mensagem": str(exc)}

    total = qs.count()
    truncado = total > MAX_LINHAS_RELATORIO
    if truncado:
        logger.info("Relatório financeiro truncado em %s linhas (total %s).", MAX_LINHAS_RELATORIO, total)
    registros = list(qs[:MAX_LINHAS_RELATORIO])
    labels_ct = _carregar_rotulos_contraparte(registros)
    linhas = [_serializar_linha_relatorio(r, labels_ct, prefixo_app_manual=prefixo_app_manual) for r in registros]

    agrup = {
        "data_vencimento": bool(agrupamento.get("data_vencimento")),
        "contraparte": bool(agrupamento.get("contraparte")),
        "ativo": bool(agrupamento.get("ativo")),
    }
    niveis = _montar_niveis_agrupamento(agrup)
    arvore = _construir_arvore_grupos(linhas, niveis, 0).get("filhos", [])

    return {
        "success": True,
        "grupos": arvore,
        "total": total,
        "exibidos": len(linhas),
        "truncado": truncado,
    }
