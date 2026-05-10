"""Relatório logística: tentativas agrupadas por motorista e data; atalho financeiro mod_finan."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from itertools import groupby

from django.core.exceptions import ValidationError

from pages.financeiro.constants import PLANO_DIARIAS_MOTORISTAS
from pages.financeiro.models import PlanoContas, RegistroFinanceiroTipo
from pages.financeiro.services.registro_manual import salvar_registro_manual
from pages.motorista.models import Motorista
from pages.pedidos.models import TentativaEntrega, estado_label
from pages.pedidos.services.zona_entrega_pedido import (
    carregar_regras_zona_por_filial,
    resolver_zona_e_faixa_entrega,
)
from sac_base.sisvar_builders import build_sisvar_payload


def _peso_linha_para_texto(peso) -> str:
    if peso is None:
        return ""
    try:
        return str(int(peso))
    except (TypeError, ValueError):
        return str(peso)


def _somar_peso_grupo(lista_d: list) -> Decimal:
    total = Decimal("0")
    for mov in lista_d:
        p = mov.pedido
        if p.peso is not None:
            total += Decimal(str(p.peso))
    return total


def _somar_volume_grupo(lista_d: list) -> int:
    return sum(int(mov.pedido.volume or 0) for mov in lista_d)


def _peso_total_texto_observacao(total: Decimal) -> str:
    if total == 0:
        return "0"
    if total == total.to_integral_value():
        return str(int(total))
    texto = f"{total:.3f}".rstrip("0").rstrip(".")
    return texto.replace(".", ",")


def texto_observacao_padrao_mod_finan(
    zonas_distintas: list[str],
    total_registros: int,
    *,
    total_peso: Decimal,
    total_volume: int,
) -> str:
    zonas_txt = ", ".join(zonas_distintas) if zonas_distintas else "(sem zona)"
    peso_txt = _peso_total_texto_observacao(total_peso)
    return (
        f"Zonas: {zonas_txt} | Registros: {total_registros} | "
        f"Peso total: {peso_txt} | Vol. total: {total_volume}"
    )


def obter_plano_diarias_motoristas() -> PlanoContas | None:
    return (
        PlanoContas.objects.select_related("pai", "pai__pai", "pai__pai__pai")
        .filter(codigo=PLANO_DIARIAS_MOTORISTAS, nivel=4)
        .first()
    )


def hierarquia_plano_para_exibicao(plano_n4: PlanoContas) -> dict[str, str]:
    chain: list[PlanoContas] = []
    node: PlanoContas | None = plano_n4
    while node:
        chain.insert(0, node)
        node = node.pai
    por_nivel = {p.nivel: p for p in chain}
    n2 = por_nivel.get(2)
    n3 = por_nivel.get(3)
    n4 = por_nivel.get(4)
    return {
        "setor": n2.nome if n2 else "",
        "subsetor": n3.nome if n3 else "",
        "ativo": n4.nome if n4 else (plano_n4.nome or ""),
        "codigo_folha": plano_n4.codigo,
    }


def montar_sisvar_relatorio_logistica_motorista_get(
    *,
    request,
    acoes_relatorio: dict,
    acoes_mod_finan: dict,
) -> dict:
    """Payload inicial SisVar (GET) para o relatório logística × motorista × data."""
    filial_ativa = getattr(request, "filial_ativa", None)
    motoristas_choices = []
    if filial_ativa:
        motoristas_choices = [
            {"value": m.id, "label": m.nome}
            for m in Motorista.objects.filter(is_deleted=False, filial=filial_ativa).order_by("nome")
        ]
    plano = obter_plano_diarias_motoristas()
    plano_labels = hierarquia_plano_para_exibicao(plano) if plano else {}
    return build_sisvar_payload(
        permissions={
            "relatorio_motorista": acoes_relatorio,
            "mod_finan": acoes_mod_finan,
        },
        options={"motoristas": motoristas_choices},
        datasets={
            "plano_diarias_labels": plano_labels,
            "filial_nome": filial_ativa.nome if filial_ativa else "",
        },
    )


def montar_relatorio_logistica_motorista(
    *,
    filial_ativa,
    data_inicio: date,
    data_fim: date,
    motorista_ids: list[int] | None,
) -> dict:
    if data_fim < data_inicio:
        raise ValidationError("A data final deve ser maior ou igual à data inicial.")

    qs = (
        TentativaEntrega.objects.select_related("pedido", "motorista")
        .filter(
            pedido__filial_id=filial_ativa.pk,
            data_tentativa__gte=data_inicio,
            data_tentativa__lte=data_fim,
        )
    )
    ids_filtro = [i for i in (motorista_ids or []) if i]
    if ids_filtro:
        qs = qs.filter(motorista_id__in=ids_filtro)

    regras_zona = carregar_regras_zona_por_filial(filial_ativa)
    movs = list(qs)

    def sort_key(m):
        tem_m = m.motorista_id is not None
        nome = (m.motorista.nome if tem_m else "") or ""
        return (
            0 if tem_m else 1,
            nome.lower(),
            m.data_tentativa,
            m.pedido_id,
            m.id,
        )

    movs.sort(key=sort_key)

    def motorista_key(m):
        return m.motorista_id

    grupos_motorista = []
    for mid, iter_m in groupby(movs, key=motorista_key):
        lista_m = list(iter_m)
        dias_distintos = len({x.data_tentativa for x in lista_m})
        total_reg = len(lista_m)

        primeiro = lista_m[0]
        if mid is None:
            label = "Sem motorista"
            codigo = ""
            nome = ""
        else:
            mot = primeiro.motorista
            label = mot.nome if mot else ""
            codigo = (mot.codigo or "").strip() if mot else ""
            nome = mot.nome if mot else ""

        lista_m.sort(key=lambda x: (x.data_tentativa, x.pedido_id, x.id))
        grupos_data = []
        for dt_val, iter_d in groupby(lista_m, key=lambda x: x.data_tentativa):
            lista_d = list(iter_d)
            lista_d.sort(
                key=lambda m: (
                    m.carro is None,
                    m.carro if m.carro is not None else 0,
                    m.pedido_id,
                    m.id,
                )
            )
            zonas_set: set[str] = set()
            linhas = []
            for mov in lista_d:
                p = mov.pedido
                zona_desc, _faixa_desc = resolver_zona_e_faixa_entrega(p.codpost_dest, regras_zona)
                if zona_desc:
                    zonas_set.add(zona_desc)
                linhas.append({
                    "tentativa_id": mov.id,
                    "carro": int(mov.carro) if mov.carro is not None else None,
                    "pedido_ref": p.pedido or str(p.id_vonzu),
                    "id_vonzu": p.id_vonzu,
                    "estado": mov.estado or "",
                    "estado_label": estado_label(mov.estado),
                    "codpost_dest": p.codpost_dest or "",
                    "cidade_dest": p.cidade_dest or "",
                    "zona_entrega": zona_desc,
                    "peso": _peso_linha_para_texto(p.peso),
                    "volume": int(p.volume) if p.volume is not None else None,
                })
            zonas_ord = sorted(zonas_set)
            qtd = len(linhas)
            soma_peso = _somar_peso_grupo(lista_d)
            soma_vol = _somar_volume_grupo(lista_d)
            observacao_padrao = texto_observacao_padrao_mod_finan(
                zonas_ord,
                qtd,
                total_peso=soma_peso,
                total_volume=soma_vol,
            )
            grupos_data.append({
                "data_tentativa": dt_val.isoformat(),
                "data_fmt": dt_val.strftime("%d/%m/%Y"),
                "total_registros": qtd,
                "total_peso": _peso_total_texto_observacao(soma_peso),
                "total_volume": soma_vol,
                "zonas": [{"descricao": z} for z in zonas_ord],
                "zonas_texto": zonas_ord,
                "observacao_padrao": observacao_padrao,
                "linhas": linhas,
            })

        grupos_motorista.append({
            "motorista_id": mid,
            "motorista_codigo": codigo,
            "motorista_nome": nome,
            "motorista_label": label or "Sem motorista",
            "sem_motorista": mid is None,
            "total_dias_distintos": dias_distintos,
            "total_registros": total_reg,
            "datas": grupos_data,
        })

    plano = obter_plano_diarias_motoristas()
    plano_ctx = None
    if plano:
        plano_ctx = {"codigo": plano.codigo, **hierarquia_plano_para_exibicao(plano)}

    return {
        "motoristas": grupos_motorista,
        "plano_diarias_ctx": plano_ctx,
        "filial_nome": filial_ativa.nome,
        "filial_id": filial_ativa.pk,
    }


def montar_campos_registro_manual_mod_finan(
    *,
    filial_ativa,
    motorista_id: int,
    data_tentativa: date,
    valor: str,
    observacao: str,
) -> dict:
    plano = obter_plano_diarias_motoristas()
    if not plano:
        raise ValidationError("Plano de contas Diárias (motoristas) não encontrado.")

    mot = Motorista.objects.filter(
        id=motorista_id,
        is_deleted=False,
        ativa=True,
        filial_id=filial_ativa.pk,
    ).first()
    if not mot:
        raise ValidationError("Motorista inválido para a filial.")

    return {
        "id": None,
        "filial_id": str(filial_ativa.pk),
        "tipo": RegistroFinanceiroTipo.SAIDA,
        "contraparte_tipo": "motorista",
        "contraparte_id": str(motorista_id),
        "plano_n2_id": "",
        "plano_n3_id": "",
        "plano_n4_id": str(plano.id),
        "plano_contas_id": str(plano.id),
        "data_emissao": data_tentativa.isoformat(),
        "data_vencimento": data_tentativa.isoformat(),
        "valor": valor,
        "observacao": (observacao or "").strip(),
        "status": "aberto",
        "permite_editar": True,
        "permite_cancelar": True,
        "permite_excluir_permanente": False,
    }


def executar_salvar_mod_finan(*, usuario, filial_ativa, motorista_id: int, data_tentativa: date, valor: str, observacao: str, filiais_escrita_ids: list[int]):
    campos = montar_campos_registro_manual_mod_finan(
        filial_ativa=filial_ativa,
        motorista_id=motorista_id,
        data_tentativa=data_tentativa,
        valor=valor,
        observacao=observacao,
    )
    return salvar_registro_manual(
        usuario=usuario,
        campos=campos,
        estado="novo",
        filiais_escrita_ids=filiais_escrita_ids,
    )
