from datetime import date

from django.test import SimpleTestCase

from pages.agenda.constants import ModoEventoAgenda
from pages.agenda.services.status_ocorrencia import resolver_status_ocorrencia


class StatusOcorrenciaTest(SimpleTestCase):
    def test_aviso_passado_concluido(self):
        st = resolver_status_ocorrencia(
            modo_evento=ModoEventoAgenda.AVISO,
            data_ocorrencia=date(2020, 1, 1),
            confirmado=False,
            hoje=date(2026, 1, 1),
        )
        self.assertEqual(st, "concluido")

    def test_aviso_confirmavel_pendente_sem_confirmacao(self):
        st = resolver_status_ocorrencia(
            modo_evento=ModoEventoAgenda.AVISO_CONFIRMAVEL,
            data_ocorrencia=date(2020, 1, 1),
            confirmado=False,
            hoje=date(2026, 1, 1),
        )
        self.assertEqual(st, "pendente")

    def test_aviso_confirmavel_concluido_apos_confirmar(self):
        st = resolver_status_ocorrencia(
            modo_evento=ModoEventoAgenda.AVISO_CONFIRMAVEL,
            data_ocorrencia=date(2020, 1, 1),
            confirmado=True,
            hoje=date(2026, 1, 1),
        )
        self.assertEqual(st, "concluido")
