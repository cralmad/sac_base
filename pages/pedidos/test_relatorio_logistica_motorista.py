"""Testes do relatório logística motorista × data e texto mod_finan."""

from decimal import Decimal

from django.test import SimpleTestCase

from pages.pedidos.services.relatorio_logistica_motorista import texto_observacao_padrao_mod_finan
from pages.pedidos.services.zona_entrega_pedido import normalizar_cp7_num, resolver_zona_e_faixa_entrega


class TextoObservacaoModFinanTests(SimpleTestCase):
    def test_formato_com_zonas(self):
        t = texto_observacao_padrao_mod_finan(
            ["NORTE", "SUL"], 5, total_peso=Decimal("10.5"), total_volume=3
        )
        self.assertIn("NORTE", t)
        self.assertIn("SUL", t)
        self.assertIn("5", t)
        self.assertIn("Peso total", t)
        self.assertIn("Vol. total", t)
        self.assertIn("3", t)

    def test_sem_zona(self):
        t = texto_observacao_padrao_mod_finan(
            [], 2, total_peso=Decimal("0"), total_volume=0
        )
        self.assertIn("(sem zona)", t)
        self.assertIn("2", t)


class ZonaEntregaPedidoTests(SimpleTestCase):
    def test_cp_invalido_retorna_vazio(self):
        desc, faixa = resolver_zona_e_faixa_entrega("", [])
        self.assertEqual(desc, "")
        self.assertEqual(faixa, "")

    def test_normalizar_cp_curto(self):
        self.assertEqual(normalizar_cp7_num("12"), (None, None))
