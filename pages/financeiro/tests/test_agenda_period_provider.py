from datetime import date
from decimal import Decimal

from django.test import TestCase

from pages.filial.models import Filial
from pages.financeiro.models import PlanoContas, RegistroFinanceiro, RegistroFinanceiroStatus, RegistroFinanceiroTipo
from pages.financeiro.providers.agenda_periodo import FinanceiroRegistroFinanceiroPeriodProvider


class FinanceiroAgendaPeriodProviderTest(TestCase):
    def setUp(self):
        self.filial = Filial.objects.create(codigo="TAF", nome="Filial Agenda Teste", ativa=True, is_matriz=True)
        plano = PlanoContas.objects.filter(nivel=4).first()
        if not plano:
            p1 = PlanoContas.objects.create(codigo="9.9.9.9", nome="Teste", nivel=4, tipo_classificacao="receita")
            plano = p1
        RegistroFinanceiro.objects.create(
            filial=self.filial,
            tipo=RegistroFinanceiroTipo.SAIDA,
            status=RegistroFinanceiroStatus.ABERTO,
            valor=Decimal("100.00"),
            valor_fat=Decimal("0"),
            valor_rest=Decimal("100.00"),
            data_emissao=date(2026, 6, 1),
            data_vencimento=date(2026, 6, 15),
            plano_contas=plano,
        )

    def test_filtra_por_filial_e_periodo(self):
        prov = FinanceiroRegistroFinanceiroPeriodProvider()
        eventos = prov.get_events_by_period(
            data_inicio=date(2026, 6, 1),
            data_fim=date(2026, 6, 30),
            filial_id=self.filial.id,
        )
        self.assertEqual(len(eventos), 1)
        self.assertEqual(eventos[0].origem_id, RegistroFinanceiro.objects.get().id)

        outros = prov.get_events_by_period(
            data_inicio=date(2026, 6, 1),
            data_fim=date(2026, 6, 30),
            filial_id=self.filial.id + 99999,
        )
        self.assertEqual(len(outros), 0)
