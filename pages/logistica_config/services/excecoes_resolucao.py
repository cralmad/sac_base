"""Resolução de vagas reservadas com prioridade: data individual > período > padrão."""

from __future__ import annotations

from datetime import date

from pages.logistica_config.models import (
    ConfiguracaoLogistica,
    DataExcecaoConfigLogistica,
    PeriodoExcecaoConfigLogistica,
)


def periodos_sobrepostos(periodos: list[dict]) -> bool:
    """True se algum par de intervalos [data_inicio, data_fim] compartilha ao menos um dia."""
    n = len(periodos)
    for i in range(n):
        a_ini = periodos[i]["data_inicio"]
        a_fim = periodos[i]["data_fim"]
        for j in range(i + 1, n):
            b_ini = periodos[j]["data_inicio"]
            b_fim = periodos[j]["data_fim"]
            if a_ini <= b_fim and b_ini <= a_fim:
                return True
    return False


def carregar_excecoes_individuais_no_intervalo(
    configuracao: ConfiguracaoLogistica,
    data_ini: date,
    data_fim: date,
) -> dict[date, DataExcecaoConfigLogistica]:
    return {
        e.data: e
        for e in DataExcecaoConfigLogistica.objects.filter(
            configuracao=configuracao,
            data__range=(data_ini, data_fim),
        ).only("data", "ligeiro_reservado", "pesado_reservado")
    }


def carregar_periodos_excecao_sobrepostos_intervalo(
    configuracao: ConfiguracaoLogistica,
    data_ini: date,
    data_fim: date,
) -> list[PeriodoExcecaoConfigLogistica]:
    return list(
        PeriodoExcecaoConfigLogistica.objects.filter(
            configuracao=configuracao,
            data_inicio__lte=data_fim,
            data_fim__gte=data_ini,
        ).order_by("data_inicio", "id")
        .only("data_inicio", "data_fim", "ligeiro_reservado", "pesado_reservado")
    )


def carregar_contexto_excecoes_intervalo(
    configuracao: ConfiguracaoLogistica,
    data_ini: date,
    data_fim: date,
) -> tuple[dict[date, DataExcecaoConfigLogistica], list[PeriodoExcecaoConfigLogistica]]:
    """Carrega exceções individuais e períodos relevantes para um intervalo de relatório."""
    return (
        carregar_excecoes_individuais_no_intervalo(configuracao, data_ini, data_fim),
        carregar_periodos_excecao_sobrepostos_intervalo(configuracao, data_ini, data_fim),
    )


def resolver_reservados_para_data(
    data: date,
    cfg: ConfiguracaoLogistica,
    exce_individual: dict[date, DataExcecaoConfigLogistica],
    periodos: list[PeriodoExcecaoConfigLogistica],
) -> tuple[int, int]:
    """Retorna (ligeiro_reservado, pesado_reservado) para a data."""
    ex = exce_individual.get(data)
    if ex:
        return ex.ligeiro_reservado, ex.pesado_reservado
    for periodo in periodos:
        if periodo.data_inicio <= data <= periodo.data_fim:
            return periodo.ligeiro_reservado, periodo.pesado_reservado
    return cfg.ligeiro_reservado, cfg.pesado_reservado
