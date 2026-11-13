from decimal import Decimal

from django.test import SimpleTestCase

from pages.pedidos.services.relatorio_gerencial import aplicar_filtro_peso


class _FakeQS:
    def __init__(self):
        self.filters = []

    def filter(self, *args, **kwargs):
        self.filters.append((args, kwargs))
        return self


class AplicarFiltroPesoTests(SimpleTestCase):
    def test_sem_operador_nao_altera(self):
        qs = _FakeQS()
        out, err = aplicar_filtro_peso(qs, "", "")
        self.assertIs(out, qs)
        self.assertIsNone(err)
        self.assertEqual(qs.filters, [])

    def test_sem_peso(self):
        qs = _FakeQS()
        out, err = aplicar_filtro_peso(qs, "null", "99")
        self.assertIsNone(err)
        self.assertEqual(out.filters, [((), {"peso__isnull": True})])

    def test_maior_que(self):
        qs = _FakeQS()
        out, err = aplicar_filtro_peso(qs, "gt", "10,5")
        self.assertIsNone(err)
        self.assertEqual(out.filters, [((), {"peso__gt": Decimal("10.5")})])

    def test_menor_que(self):
        qs = _FakeQS()
        out, err = aplicar_filtro_peso(qs, "lt", "3")
        self.assertIsNone(err)
        self.assertEqual(out.filters, [((), {"peso__lt": Decimal("3")})])

    def test_igual(self):
        qs = _FakeQS()
        out, err = aplicar_filtro_peso(qs, "eq", " 12 ")
        self.assertIsNone(err)
        self.assertEqual(out.filters, [((), {"peso": Decimal("12")})])

    def test_valor_obrigatorio(self):
        qs = _FakeQS()
        out, err = aplicar_filtro_peso(qs, "gt", "")
        self.assertIs(out, qs)
        self.assertEqual(err, "Informe um valor de peso válido para o filtro.")

    def test_operador_invalido(self):
        qs = _FakeQS()
        out, err = aplicar_filtro_peso(qs, "xyz", "1")
        self.assertIs(out, qs)
        self.assertEqual(err, "Operador de peso inválido.")
