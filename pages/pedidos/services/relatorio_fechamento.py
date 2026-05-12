"""Relatório de Fechamento: agrega tentativas por data, aplica config/exceções e RF ENTRADA."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db.models import Count

from pages.financeiro.models import RegistroFinanceiro, RegistroFinanceiroTipo
from pages.logistica_config.models import ConfiguracaoLogistica, DataExcecaoConfigLogistica
from pages.pedidos.models import TentativaEntrega

PERIODO_MAXIMO_DIAS = 90

_DIAS_SEMANA_PT = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)


def formatar_data_coluna_fechamento(d: date) -> str:
    """Ex.: terça-feira, 12/05/2026 (weekday alinhado a `date.weekday()`, segunda=0)."""
    return f"{_DIAS_SEMANA_PT[d.weekday()]}, {d.strftime('%d/%m/%Y')}"


def formatar_inteiro_pt_br(n: int) -> str:
    """Agrupa milhares com ponto (ex.: 11111 -> '11.111')."""
    neg = n < 0
    x = abs(int(n))
    s = str(x)
    partes = []
    while len(s) > 3:
        partes.append(s[-3:])
        s = s[:-3]
    partes.append(s)
    corpo = ".".join(reversed(partes))
    return ("-" if neg else "") + corpo


def formatar_decimal_pt_br(valor: Decimal, casas_decimais: int = 2) -> str:
    """Formato monetário pt-BR: milhar com ponto, decimais com vírgula (ex.: 11.111,11)."""
    q = valor.quantize(Decimal(10) ** -casas_decimais)
    neg = q < 0
    q = abs(q)
    texto = format(q, f".{casas_decimais}f")
    parte_int, parte_frac = texto.split(".")
    # parte_int sem sinal; evita duplo '-' em negativos
    ip_num = int(parte_int)
    ip_fmt = formatar_inteiro_pt_br(ip_num)
    return ("-" if neg else "") + ip_fmt + "," + parte_frac


def _item_expresso_linha_payload(item: dict) -> dict:
    """Monta o dict de exibição a partir do item em rf_por_data (só obs + valor formatado)."""
    raw_valor = item.get("valor", "0")
    return {
        "observacao": (item.get("observacao") or ""),
        "valor": formatar_decimal_pt_br(Decimal(str(raw_valor))),
    }


def validar_periodo(data_ini: date, data_fim: date) -> str | None:
    if data_ini > data_fim:
        return "A data inicial não pode ser maior que a data final."
    if (data_fim - data_ini).days > PERIODO_MAXIMO_DIAS:
        return f"O período máximo é de {PERIODO_MAXIMO_DIAS} dias."
    return None


def montar_relatorio_fechamento(filial, data_ini: date, data_fim: date) -> tuple[dict | None, str | None]:
    cfg = ConfiguracaoLogistica.objects.filter(filial=filial).first()
    if not cfg:
        return None, (
            "Não existe configuração de logística para a filial ativa. "
            "Cadastre-a em Logística > Cadastro > Configuração de Logística antes de emitir o relatório."
        )

    agg_rows = (
        TentativaEntrega.objects.filter(
            pedido__filial=filial,
            pedido__expresso=False,
            data_tentativa__range=(data_ini, data_fim),
        )
        .values("data_tentativa")
        .annotate(qtd_pedidos=Count("pedido_id", distinct=True))
        .order_by("data_tentativa")
    )

    exce_map = {
        e.data: e
        for e in DataExcecaoConfigLogistica.objects.filter(
            configuracao=cfg,
            data__range=(data_ini, data_fim),
        )
    }

    rf_por_data: dict[date, list[dict]] = defaultdict(list)
    for r in RegistroFinanceiro.objects.filter(
        filial=filial,
        tipo=RegistroFinanceiroTipo.ENTRADA,
        data_emissao__range=(data_ini, data_fim),
    ).values("id", "data_emissao", "observacao", "valor"):
        vd = r["valor"]
        if not isinstance(vd, Decimal):
            vd = Decimal(str(vd))
        rf_por_data[r["data_emissao"]].append(
            {
                "observacao": (r["observacao"] or ""),
                "valor": str(vd),
            }
        )

    v_unit_l = cfg.valor_unitario_ligeiro
    v_unit_p = cfg.valor_unitario_pesado

    tot_qtd = 0
    tot_l_q = 0
    tot_l_v = Decimal("0")
    tot_p_q = 0
    tot_p_v = Decimal("0")
    tot_res = 0
    tot_expresso_v = Decimal("0")
    tot_exc = 0

    linhas = []
    for row in agg_rows:
        d = row["data_tentativa"]
        qtd = row["qtd_pedidos"]
        ex = exce_map.get(d)
        qty_l = ex.ligeiro_reservado if ex else cfg.ligeiro_reservado
        qty_p = ex.pesado_reservado if ex else cfg.pesado_reservado

        valor_l = (Decimal(qty_l) * v_unit_l).quantize(Decimal("0.01"))
        valor_p = (Decimal(qty_p) * v_unit_p).quantize(Decimal("0.01"))

        ped_reservados = int(cfg.pedidos_ligeiro) * int(qty_l) + int(cfg.pedidos_pesado) * int(qty_p)
        ped_excedentes = max(0, int(qtd) - ped_reservados)

        expresso_raw = rf_por_data.get(d, [])
        for ex_item in expresso_raw:
            tot_expresso_v += Decimal(str(ex_item.get("valor", "0")))

        tot_qtd += int(qtd)
        tot_l_q += int(qty_l)
        tot_l_v += valor_l
        tot_p_q += int(qty_p)
        tot_p_v += valor_p
        tot_res += ped_reservados
        tot_exc += ped_excedentes

        expresso_fmt = [_item_expresso_linha_payload(x) for x in expresso_raw]

        linhas.append(
            {
                "data": formatar_data_coluna_fechamento(d),
                "qtd_pedidos": formatar_inteiro_pt_br(int(qtd)),
                "ligeiro_quantidade": formatar_inteiro_pt_br(int(qty_l)),
                "ligeiro_valor": formatar_decimal_pt_br(valor_l),
                "pesado_quantidade": formatar_inteiro_pt_br(int(qty_p)),
                "pesado_valor": formatar_decimal_pt_br(valor_p),
                "pedidos_reservados": formatar_inteiro_pt_br(ped_reservados),
                "pedidos_excedentes": formatar_inteiro_pt_br(ped_excedentes),
                "expresso": expresso_fmt,
            }
        )

    tot_exc_valor = (Decimal(tot_exc) * cfg.valor_excedente).quantize(Decimal("0.01"))

    totais = {
        "qtd_pedidos": formatar_inteiro_pt_br(tot_qtd),
        "ligeiro_quantidade": formatar_inteiro_pt_br(tot_l_q),
        "ligeiro_valor": formatar_decimal_pt_br(tot_l_v),
        "pesado_quantidade": formatar_inteiro_pt_br(tot_p_q),
        "pesado_valor": formatar_decimal_pt_br(tot_p_v),
        "pedidos_reservados": formatar_inteiro_pt_br(tot_res),
        "pedidos_excedentes": formatar_inteiro_pt_br(tot_exc),
        "pedidos_excedentes_valor": formatar_decimal_pt_br(tot_exc_valor),
        "expresso_valor": formatar_decimal_pt_br(tot_expresso_v),
    }

    return {"linhas": linhas, "totais": totais, "periodo_maximo_dias": PERIODO_MAXIMO_DIAS}, None
