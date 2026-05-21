from __future__ import annotations

import calendar
from datetime import date, timedelta

from pages.agenda.constants import MAX_OCORRENCIAS_POR_REGRA, RecorrenciaAgenda


def _add_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _dia_valido_no_mes(ano: int, mes: int, dia: int) -> int:
    ultimo = calendar.monthrange(ano, mes)[1]
    return min(dia, ultimo)


def ajustar_data_nominal_mensal(d_nominal: date, *, antecipar_fim_semana: bool) -> date:
    if not antecipar_fim_semana:
        return d_nominal
    wd = d_nominal.weekday() + 1
    if wd == 6:
        return d_nominal - timedelta(days=1)
    if wd == 7:
        return d_nominal - timedelta(days=2)
    return d_nominal


def _primeira_data_semanal(data_ancora: date, dia_semana: int) -> date:
    """Primeira data >= ancora com dia_semana (1=seg .. 7=dom)."""
    atual_wd = data_ancora.weekday() + 1
    delta = (dia_semana - atual_wd) % 7
    return data_ancora + timedelta(days=delta)


def projetar_datas_ocorrencia(
    *,
    data_ancora: date,
    recorrencia: str,
    intervalo: int,
    data_inicio: date,
    data_fim: date,
    data_fim_serie: date | None,
    dia_semana: int | None,
    dia_mes_fixo: int | None,
    antecipar_fim_semana: bool = False,
) -> list[date]:
    intervalo = max(1, int(intervalo or 1))
    ini_eff = max(data_inicio, data_ancora)
    fim_eff = min(data_fim, data_fim_serie) if data_fim_serie else data_fim
    if ini_eff > fim_eff:
        return []

    out: list[date] = []

    if recorrencia == RecorrenciaAgenda.NENHUMA:
        if data_ancora >= ini_eff and data_ancora <= fim_eff:
            out.append(data_ancora)
        return out

    if recorrencia == RecorrenciaAgenda.DIARIA:
        cur = data_ancora
        while cur < ini_eff:
            cur += timedelta(days=intervalo)
        while cur <= fim_eff and len(out) < MAX_OCORRENCIAS_POR_REGRA:
            if cur >= ini_eff:
                out.append(cur)
            cur += timedelta(days=intervalo)
        return out

    if recorrencia == RecorrenciaAgenda.SEMANAL:
        if not dia_semana or dia_semana < 1 or dia_semana > 7:
            return []
        cur = _primeira_data_semanal(data_ancora, dia_semana)
        step = timedelta(days=7 * intervalo)
        while cur < ini_eff:
            cur += step
        while cur <= fim_eff and len(out) < MAX_OCORRENCIAS_POR_REGRA:
            if cur >= ini_eff:
                out.append(cur)
            cur += step
        return out

    if recorrencia == RecorrenciaAgenda.MENSAL:
        if not dia_mes_fixo or dia_mes_fixo < 1 or dia_mes_fixo > 31:
            return []
        cur = date(data_ancora.year, data_ancora.month, 1)
        while cur <= fim_eff and len(out) < MAX_OCORRENCIAS_POR_REGRA:
            dia = _dia_valido_no_mes(cur.year, cur.month, dia_mes_fixo)
            nominal = date(cur.year, cur.month, dia)
            exib = ajustar_data_nominal_mensal(nominal, antecipar_fim_semana=antecipar_fim_semana)
            if exib >= ini_eff and exib <= fim_eff and exib >= data_ancora:
                out.append(exib)
            cur = _add_months(cur, intervalo)
        return sorted(set(out))

    if recorrencia == RecorrenciaAgenda.ANUAL:
        cur = data_ancora
        while cur < ini_eff:
            try:
                cur = date(cur.year + intervalo, cur.month, cur.day)
            except ValueError:
                cur = date(cur.year + intervalo, cur.month, 28)
        while cur <= fim_eff and len(out) < MAX_OCORRENCIAS_POR_REGRA:
            if cur >= ini_eff:
                out.append(cur)
            try:
                cur = date(cur.year + intervalo, cur.month, cur.day)
            except ValueError:
                cur = date(cur.year + intervalo, cur.month, 28)
        return out

    return out
