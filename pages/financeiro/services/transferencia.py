"""Transferências internas: RF tipo TRANSFERENCIA + plano neutro."""

from decimal import Decimal

from django.db import transaction

from pages.financeiro.models import (
    PlanoContas,
    RegistroFinanceiro,
    RegistroFinanceiroTipo,
    TipoClassificacaoPlano,
)


@transaction.atomic
def registrar_transferencia_interna(
    *,
    filial_id: int,
    valor: Decimal,
    conta_origem_id: int,
    conta_destino_id: int,
    plano_codigo: str,
    observacao: str = "",
    usuario=None,
) -> RegistroFinanceiro:
    plano = PlanoContas.objects.get(codigo=plano_codigo)
    if plano.tipo_classificacao != TipoClassificacaoPlano.NEUTRO:
        raise ValueError("Transferência interna exige PlanoContas com tipo_classificacao=neutro.")
    rf = RegistroFinanceiro(
        filial_id=filial_id,
        tipo=RegistroFinanceiroTipo.TRANSFERENCIA,
        valor=valor,
        valor_fat=Decimal("0"),
        valor_rest=valor,
        plano_contas=plano,
        observacao=observacao or "",
    )
    if usuario and getattr(usuario, "is_authenticated", False):
        rf.created_by = usuario
        rf.updated_by = usuario
    rf.save()
    # Movimento entre contas (custódia) pode ser modelo futuro; MVP só persiste o título documental.
    _ = (conta_origem_id, conta_destino_id)
    return rf
