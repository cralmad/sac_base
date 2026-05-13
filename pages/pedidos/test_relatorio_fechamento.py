"""Relatório de Fechamento — agregação, exceções e RF ENTRADA."""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from pages.core.models import Pais
from pages.filial.models import Filial
from pages.financeiro.models import PlanoContas, RegistroFinanceiro, RegistroFinanceiroTipo
from pages.logistica_config.models import ConfiguracaoLogistica, DataExcecaoConfigLogistica
from pages.pedidos.models import Pedido, TentativaEntrega
from pages.pedidos.services.relatorio_fechamento import (
    formatar_decimal_pt_br,
    montar_relatorio_fechamento,
    validar_periodo,
)


class RelatorioFechamentoServiceTests(TestCase):
    d0 = date(2026, 6, 10)
    d1 = date(2026, 6, 11)

    @classmethod
    def setUpTestData(cls):
        cls.pais = Pais.objects.create(nome="PT-RF", sigla="PT", codigo_tel="+351")
        cls.filial = Filial.objects.create(
            codigo="RFCL",
            nome="FIL RF FECH",
            pais_atuacao=cls.pais,
            is_matriz=True,
        )
        cls.plano = PlanoContas.objects.filter(codigo="1.1.1.1").first()
        if not cls.plano:
            raise RuntimeError("PlanoContas seed 1.1.1.1 necessário para testes.")

    def setUp(self):
        self.cfg = ConfiguracaoLogistica.objects.create(
            filial=self.filial,
            pedidos_pesado=2,
            pesado_reservado=3,
            valor_unitario_pesado=Decimal("10.00"),
            pedidos_ligeiro=5,
            ligeiro_reservado=1,
            valor_unitario_ligeiro=Decimal("4.00"),
            valor_excedente=Decimal("1.50"),
        )

    def _pedido(self, id_vonzu: int, expresso: bool = False) -> Pedido:
        now = timezone.now()
        return Pedido.objects.create(
            filial=self.filial,
            id_vonzu=id_vonzu,
            tipo="ENTREGA",
            criado=now,
            atualizacao=now,
            expresso=expresso,
        )

    def _tentativa(self, pedido: Pedido, dt: date) -> TentativaEntrega:
        return TentativaEntrega.objects.create(
            pedido=pedido,
            data_tentativa=dt,
            estado="created",
            periodo="MANHA",
        )

    def test_sem_config_retorna_erro(self):
        self.cfg.delete()
        payload, err = montar_relatorio_fechamento(self.filial, self.d0, self.d1)
        self.assertIsNone(payload)
        self.assertIsNotNone(err)
        self.assertIn("configuração de logística", err.lower())

    def test_validar_periodo_maximo(self):
        self.assertIsNotNone(validar_periodo(self.d1, self.d0))
        long_ini = date(2026, 1, 1)
        long_fim = date(2026, 5, 1)
        self.assertIsNotNone(validar_periodo(long_ini, long_fim))

    def test_formatar_decimal_milhares(self):
        self.assertEqual(formatar_decimal_pt_br(Decimal("11111.11")), "11.111,11")
        self.assertEqual(formatar_decimal_pt_br(Decimal("0")), "0,00")
        self.assertEqual(formatar_decimal_pt_br(Decimal("-5.5")), "-5,50")

    def test_agrega_distinct_e_ignora_expresso(self):
        p1 = self._pedido(50001, expresso=False)
        p2 = self._pedido(50002, expresso=False)
        self._pedido(50003, expresso=True)
        self._tentativa(p1, self.d0)
        self._tentativa(p2, self.d0)
        p_exp = Pedido.objects.get(id_vonzu=50003)
        self._tentativa(p_exp, self.d0)

        payload, err = montar_relatorio_fechamento(self.filial, self.d0, self.d0)
        self.assertIsNone(err)
        self.assertEqual(len(payload["linhas"]), 1)
        linha = payload["linhas"][0]
        self.assertEqual(linha["data"], "quarta-feira, 10/06/2026")
        self.assertEqual(linha["qtd_pedidos"], "2")
        self.assertEqual(linha["pedidos_excedentes"], "0")
        t = payload["totais"]
        self.assertEqual(t["qtd_pedidos"], "2")
        self.assertEqual(t["ligeiro_quantidade"], "1")
        self.assertEqual(t["ligeiro_valor"], "4,00")
        self.assertEqual(t["pesado_quantidade"], "3")
        self.assertEqual(t["pesado_valor"], "30,00")
        self.assertEqual(t["pedidos_reservados"], "11")
        self.assertEqual(t["pedidos_excedentes"], "0")
        self.assertEqual(t["pedidos_excedentes_valor"], "0,00")
        self.assertEqual(t["expresso_valor"], "0,00")
        self.assertEqual(payload["periodo_texto"], "10/06/2026 a 10/06/2026")
        self.assertEqual(payload["valor_total_consolidado"], "34,00")

    def test_excecao_substitui_reservados(self):
        DataExcecaoConfigLogistica.objects.create(
            configuracao=self.cfg,
            data=self.d0,
            pesado_reservado=9,
            ligeiro_reservado=7,
        )
        p = self._pedido(50010)
        self._tentativa(p, self.d0)

        payload, err = montar_relatorio_fechamento(self.filial, self.d0, self.d0)
        self.assertIsNone(err)
        linha = payload["linhas"][0]
        self.assertEqual(linha["ligeiro_quantidade"], "7")
        self.assertEqual(linha["pesado_quantidade"], "9")
        self.assertEqual(linha["ligeiro_valor"], "28,00")
        self.assertEqual(linha["pesado_valor"], "90,00")
        self.assertEqual(linha["pedidos_reservados"], "53")
        self.assertEqual(linha["pedidos_excedentes"], "0")
        t = payload["totais"]
        self.assertEqual(t["ligeiro_quantidade"], "7")
        self.assertEqual(t["pesado_quantidade"], "9")
        self.assertEqual(t["ligeiro_valor"], "28,00")
        self.assertEqual(t["pesado_valor"], "90,00")
        self.assertEqual(t["pedidos_reservados"], linha["pedidos_reservados"])
        self.assertEqual(t["pedidos_excedentes"], "0")
        self.assertEqual(t["pedidos_excedentes_valor"], "0,00")
        self.assertEqual(t["expresso_valor"], "0,00")
        self.assertEqual(payload["periodo_texto"], "10/06/2026 a 10/06/2026")
        self.assertEqual(payload["valor_total_consolidado"], "118,00")

    def test_expresso_rf_entrada_por_data(self):
        p = self._pedido(50020)
        self._tentativa(p, self.d0)
        RegistroFinanceiro.objects.create(
            filial=self.filial,
            tipo=RegistroFinanceiroTipo.ENTRADA,
            valor=Decimal("100.00"),
            valor_fat=Decimal("0"),
            valor_rest=Decimal("100.00"),
            data_emissao=self.d0,
            data_vencimento=self.d0,
            plano_contas=self.plano,
            observacao="Teste RF",
        )

        payload, err = montar_relatorio_fechamento(self.filial, self.d0, self.d0)
        self.assertIsNone(err)
        linha = payload["linhas"][0]
        self.assertEqual(len(linha["expresso"]), 1)
        self.assertEqual(linha["expresso"][0]["valor"], "100,00")
        self.assertEqual(linha["expresso"][0]["observacao"], "Teste RF")
        t = payload["totais"]
        self.assertEqual(t["expresso_valor"], "100,00")
        self.assertEqual(t["qtd_pedidos"], "1")
        self.assertEqual(t["ligeiro_valor"], "4,00")
        self.assertEqual(t["pesado_valor"], "30,00")
        self.assertEqual(t["pedidos_excedentes_valor"], "0,00")
        self.assertEqual(payload["periodo_texto"], "10/06/2026 a 10/06/2026")
        self.assertEqual(payload["valor_total_consolidado"], "134,00")

    def test_total_pedidos_excedentes_valor_multiplica_config(self):
        """Total excedente vezes ConfiguracaoLogistica.valor_excedente no rodape."""
        self.cfg.pedidos_ligeiro = 0
        self.cfg.pedidos_pesado = 0
        self.cfg.valor_excedente = Decimal("2.00")
        self.cfg.save()
        for i, vid in enumerate((61001, 61002, 61003), start=1):
            p = self._pedido(vid)
            self._tentativa(p, self.d0)
        payload, err = montar_relatorio_fechamento(self.filial, self.d0, self.d0)
        self.assertIsNone(err)
        t = payload["totais"]
        self.assertEqual(t["pedidos_excedentes"], "3")
        self.assertEqual(t["pedidos_excedentes_valor"], "6,00")
        self.assertEqual(payload["periodo_texto"], "10/06/2026 a 10/06/2026")
        self.assertEqual(payload["valor_total_consolidado"], "40,00")
