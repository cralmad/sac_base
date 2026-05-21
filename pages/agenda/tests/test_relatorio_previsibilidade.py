from datetime import date

from django.test import SimpleTestCase

from pages.agenda.services.relatorio_previsibilidade import validar_periodo_agenda


class ValidarPeriodoAgendaTest(SimpleTestCase):
    def test_rejeita_mais_de_366_dias(self):
        err = validar_periodo_agenda(date(2026, 1, 1), date(2027, 1, 3))
        self.assertIsNotNone(err)

    def test_aceita_366_dias(self):
        err = validar_periodo_agenda(date(2026, 1, 1), date(2026, 12, 31))
        self.assertIsNone(err)
