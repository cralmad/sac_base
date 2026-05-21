from __future__ import annotations

from django.core.exceptions import ValidationError

from pages.agenda.constants import CATEGORIAS_SEM_LANCAMENTO_VINCULADO, ModoEventoAgenda, RecorrenciaAgenda
from pages.agenda.registry_materializacao import obter_materialization_provider


def validar_regras_agenda_manual(
    *,
    categoria: str,
    modo_evento: str,
    tipo_materializacao: str | None,
    payload_template: dict,
    recorrencia: str,
    data_ancora,
    data_fim_serie,
    dia_semana: int | None,
    dia_mes_fixo: int | None,
    antecipar_fim_semana: bool,
) -> None:
    cat = (categoria or "").strip()
    if cat in CATEGORIAS_SEM_LANCAMENTO_VINCULADO and modo_evento == ModoEventoAgenda.MATERIALIZAVEL:
        raise ValidationError("Categoria lembrete não permite lançamento vinculado.")

    if modo_evento == ModoEventoAgenda.MATERIALIZAVEL:
        if not (tipo_materializacao or "").strip():
            raise ValidationError("Tipo de materialização é obrigatório para lançamento vinculado.")
        prov = obter_materialization_provider((tipo_materializacao or "").strip())
        if not prov:
            raise ValidationError("Tipo de materialização inválido.")
        cat_prov = getattr(prov, "categoria_agenda", None)
        if cat_prov and cat_prov != cat:
            raise ValidationError("Tipo de materialização incompatível com a categoria da regra.")
    else:
        if tipo_materializacao:
            raise ValidationError("Tipo de materialização só se aplica a lançamento vinculado.")
        if payload_template:
            raise ValidationError("Payload de materialização não se aplica a avisos simples ou confirmáveis.")

    if data_fim_serie is None:
        if recorrencia == RecorrenciaAgenda.NENHUMA:
            raise ValidationError("Recorrência 'nenhuma' exige data fim da série igual à data âncora.")
    else:
        if data_fim_serie < data_ancora:
            raise ValidationError("Data fim da série não pode ser anterior à data âncora.")

    if recorrencia == RecorrenciaAgenda.NENHUMA:
        if not data_fim_serie or data_fim_serie != data_ancora:
            raise ValidationError("Evento único exige data fim da série igual à data âncora.")
    elif data_fim_serie is None and recorrencia not in (
        RecorrenciaAgenda.DIARIA,
        RecorrenciaAgenda.SEMANAL,
        RecorrenciaAgenda.MENSAL,
        RecorrenciaAgenda.ANUAL,
    ):
        raise ValidationError("Recorrência inválida para série aberta.")

    if recorrencia == RecorrenciaAgenda.SEMANAL:
        if not dia_semana or dia_semana < 1 or dia_semana > 7:
            raise ValidationError("Selecione o dia da semana (1=segunda a 7=domingo).")
    elif recorrencia == RecorrenciaAgenda.MENSAL:
        if not dia_mes_fixo or dia_mes_fixo < 1 or dia_mes_fixo > 31:
            raise ValidationError("Informe o dia fixo do mês (1 a 31).")
    else:
        if dia_semana is not None:
            raise ValidationError("Dia da semana só se aplica a recorrência semanal.")
        if dia_mes_fixo is not None:
            raise ValidationError("Dia do mês só se aplica a recorrência mensal.")
        if antecipar_fim_semana:
            raise ValidationError("Antecipação de fim de semana só se aplica a recorrência mensal.")

    if modo_evento == ModoEventoAgenda.AVISO and recorrencia == RecorrenciaAgenda.NENHUMA:
        if not data_fim_serie or data_fim_serie != data_ancora:
            raise ValidationError("Aviso simples único exige data fim igual à data âncora.")
