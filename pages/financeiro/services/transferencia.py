"""Transferências internas: RF tipo TRANSFERENCIA + plano neutro."""

from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from pages.financeiro.models import (
    ContaFinanceira,
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
    if not ContaFinanceira.objects.filter(id=conta_origem_id, filial_id=filial_id).exists():
        raise ValueError("Conta de origem inválida ou fora da filial.")
    ct_conta = ContentType.objects.get_for_model(ContaFinanceira)
    rf = RegistroFinanceiro(
        filial_id=filial_id,
        tipo=RegistroFinanceiroTipo.TRANSFERENCIA,
        valor=valor,
        valor_fat=Decimal("0"),
        valor_rest=valor,
        plano_contas=plano,
        observacao=observacao or "",
        referencia_content_type=ct_conta,
        referencia_object_id=conta_origem_id,
    )
    if usuario and getattr(usuario, "is_authenticated", False):
        rf.created_by = usuario
        rf.updated_by = usuario
    rf.save()
    # Movimento entre contas (custódia) pode ser modelo futuro; MVP só persiste o título documental.
    _ = conta_destino_id
    return rf
