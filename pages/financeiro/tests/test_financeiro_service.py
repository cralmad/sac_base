from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase

from pages.financeiro.models import (
    ContaFinanceira,
    Faturamento,
    FaturamentoFormaPagamento,
    FaturamentoRegistroFinanceiro,
    FormaPagamento,
    ParcelaFaturamento,
    ParcelaFaturamentoStatus,
    PlanoContas,
    RegistroFinanceiro,
    RegistroFinanceiroTipo,
)
from pages.financeiro.services.financeiro_service import FinanceiroService
from pages.filial.models import Filial


class WaterfallTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.filial = Filial.objects.filter(is_matriz=True).first() or Filial.objects.order_by("id").first()
        if not cls.filial:
            cls.filial = Filial.objects.create(
                codigo="TST",
                nome="FILIAL TESTE FIN",
                is_matriz=True,
            )
        cls.plano = PlanoContas.objects.get(codigo="1.1.1.1")
        conta, _ = ContaFinanceira.objects.get_or_create(
            filial=cls.filial,
            nome="Caixa teste financeiro",
            defaults={"codigo": "CXT", "ativo": True},
        )
        FormaPagamento.objects.get_or_create(
            codigo="DINHEIRO",
            defaults={
                "nome": "Dinheiro",
                "aceita_parcelamento": False,
                "conta_custodia_padrao": conta,
                "ordem": 1,
                "ativo": True,
            },
        )

    def _rf(self, valor: Decimal, valor_rest: Decimal | None = None):
        return RegistroFinanceiro.objects.create(
            filial=self.filial,
            tipo=RegistroFinanceiroTipo.ENTRADA,
            valor=valor,
            valor_fat=Decimal("0"),
            valor_rest=valor_rest if valor_rest is not None else valor,
            plano_contas=self.plano,
        )

    def test_waterfall_respeita_ordem_e_pool(self):
        r1 = self._rf(Decimal("100"))
        r2 = self._rf(Decimal("50"))
        Faturamento.objects.create(filial=self.filial)
        seq = [(r1.id, 1), (r2.id, 2)]
        with transaction.atomic():
            linhas = FinanceiroService.calcular_waterfall_abatimentos(
                Decimal("120"), seq, self.filial.id
            )
        self.assertEqual(len(linhas), 2)
        self.assertEqual(linhas[0]["valor_abatido"], Decimal("100"))
        self.assertEqual(linhas[1]["valor_abatido"], Decimal("20"))

    def test_recalc_agregados(self):
        r = self._rf(Decimal("200"))
        fat = Faturamento.objects.create(filial=self.filial)
        FaturamentoRegistroFinanceiro.objects.create(
            faturamento=fat,
            registro_financeiro=r,
            filial=self.filial,
            ordem=1,
            valor_abatido=Decimal("80"),
        )
        FinanceiroService.recalcular_agregados_registro(r.id)
        r.refresh_from_db()
        self.assertEqual(r.valor_fat, Decimal("80"))
        self.assertEqual(r.valor_rest, Decimal("120"))

    def test_parcelas_nao_excedem_formas(self):
        fat = Faturamento.objects.create(filial=self.filial)
        forma = FormaPagamento.objects.get(codigo="DINHEIRO")
        ffp = FaturamentoFormaPagamento.objects.create(
            faturamento=fat,
            forma_pagamento=forma,
            valor=Decimal("100"),
        )
        ParcelaFaturamento.objects.create(
            faturamento=fat,
            faturamento_forma_pagamento=ffp,
            forma_pagamento=forma,
            valor=Decimal("50"),
            status=ParcelaFaturamentoStatus.ABERTO,
        )
        FinanceiroService.validar_soma_parcelas_vs_formas(fat.id)
        ParcelaFaturamento.objects.create(
            faturamento=fat,
            faturamento_forma_pagamento=ffp,
            forma_pagamento=forma,
            valor=Decimal("60"),
            status=ParcelaFaturamentoStatus.ABERTO,
        )
        with self.assertRaises(ValidationError):
            FinanceiroService.validar_soma_parcelas_vs_formas(fat.id)
