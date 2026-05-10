from datetime import date
from decimal import Decimal

from django.test import TestCase

from pages.financeiro.models import PlanoContas, RegistroFinanceiro, RegistroFinanceiroTipo
from pages.financeiro.services.relatorio_registros import executar_relatorio_registros
from pages.filial.models import Filial


class RelatorioRegistrosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.filial = Filial.objects.filter(is_matriz=True).first() or Filial.objects.order_by("id").first()
        if not cls.filial:
            cls.filial = Filial.objects.create(
                codigo="RFREL",
                nome="FILIAL RELATORIO FIN",
                is_matriz=True,
            )
        cls.plano = PlanoContas.objects.get(codigo="1.1.1.1")

    def test_filial_invalida_retorna_erro(self):
        out = executar_relatorio_registros(
            filiais_escrita_ids=[self.filial.id],
            filtros={
                "filial_id": "999999",
                "data_emissao_ini": "2026-01-01",
                "data_emissao_fim": "2026-01-31",
            },
            agrupamento={},
            prefixo_app_manual="/app",
        )
        self.assertFalse(out["success"])

    def test_exclui_transferencia_e_agrupa(self):
        RegistroFinanceiro.objects.create(
            filial=self.filial,
            tipo=RegistroFinanceiroTipo.ENTRADA,
            valor=Decimal("10"),
            valor_fat=Decimal("0"),
            valor_rest=Decimal("10"),
            plano_contas=self.plano,
            data_emissao=date(2026, 1, 15),
            data_vencimento=date(2026, 1, 20),
        )
        RegistroFinanceiro.objects.create(
            filial=self.filial,
            tipo=RegistroFinanceiroTipo.TRANSFERENCIA,
            valor=Decimal("5"),
            valor_fat=Decimal("0"),
            valor_rest=Decimal("5"),
            plano_contas=self.plano,
            data_emissao=date(2026, 1, 15),
            data_vencimento=date(2026, 1, 20),
        )
        out = executar_relatorio_registros(
            filiais_escrita_ids=[self.filial.id],
            filtros={
                "filial_id": str(self.filial.id),
                "data_emissao_ini": "2026-01-01",
                "data_emissao_fim": "2026-01-31",
            },
            agrupamento={},
            prefixo_app_manual="/app",
        )
        self.assertTrue(out["success"])
        self.assertEqual(out["total"], 1)
        self.assertEqual(len(out["grupos"]), 1)
