from datetime import date

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from pages.logistica_config.services.config_logistica import _normalizar_payload_excecoes_periodo
from pages.logistica_config.models import (
    DataExcecaoConfigLogistica,
    PeriodoExcecaoConfigLogistica,
    ConfiguracaoLogistica,
)
from pages.logistica_config.services.excecoes_resolucao import (
    periodos_sobrepostos,
    resolver_reservados_para_data,
)


class PeriodosExcecaoValidacaoTests(SimpleTestCase):
    def test_periodos_nao_sobrepostos(self):
        periodos = [
            {"data_inicio": date(2026, 1, 1), "data_fim": date(2026, 1, 31)},
            {"data_inicio": date(2026, 2, 1), "data_fim": date(2026, 2, 28)},
        ]
        self.assertFalse(periodos_sobrepostos(periodos))

    def test_periodos_sobrepostos_parcialmente(self):
        periodos = [
            {"data_inicio": date(2026, 1, 1), "data_fim": date(2026, 1, 31)},
            {"data_inicio": date(2026, 1, 15), "data_fim": date(2026, 2, 15)},
        ]
        self.assertTrue(periodos_sobrepostos(periodos))

    def test_normalizar_rejeita_sobreposicao(self):
        raw = [
            {
                "data_inicio": "2026-01-01",
                "data_fim": "2026-01-31",
                "pesado_reservado": "1",
                "ligeiro_reservado": "2",
            },
            {
                "data_inicio": "2026-01-15",
                "data_fim": "2026-02-15",
                "pesado_reservado": "3",
                "ligeiro_reservado": "4",
            },
        ]
        with self.assertRaisesMessage(
            ValidationError,
            "Existem períodos de exceção com datas sobrepostas.",
        ):
            _normalizar_payload_excecoes_periodo(raw)

    def test_normalizar_aceita_periodo_valido(self):
        raw = [
            {
                "data_inicio": "2026-01-01",
                "data_fim": "2026-01-31",
                "pesado_reservado": "5",
                "ligeiro_reservado": "6",
            },
        ]
        resultado = _normalizar_payload_excecoes_periodo(raw)
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["pesado_reservado"], 5)
        self.assertEqual(resultado[0]["ligeiro_reservado"], 6)


class ExcecoesResolucaoTests(SimpleTestCase):
    def test_resolver_prioridade_data_individual(self):
        cfg = ConfiguracaoLogistica(ligeiro_reservado=1, pesado_reservado=2)
        dt = date(2026, 1, 15)
        ex_ind = {
            dt: DataExcecaoConfigLogistica(
                data=dt, ligeiro_reservado=7, pesado_reservado=9,
            ),
        }
        periodos = [
            PeriodoExcecaoConfigLogistica(
                data_inicio=date(2026, 1, 1),
                data_fim=date(2026, 1, 31),
                ligeiro_reservado=3,
                pesado_reservado=4,
            ),
        ]
        self.assertEqual(resolver_reservados_para_data(dt, cfg, ex_ind, periodos), (7, 9))

    def test_resolver_periodo_quando_sem_data_individual(self):
        cfg = ConfiguracaoLogistica(ligeiro_reservado=1, pesado_reservado=2)
        dt = date(2026, 1, 20)
        periodos = [
            PeriodoExcecaoConfigLogistica(
                data_inicio=date(2026, 1, 1),
                data_fim=date(2026, 1, 31),
                ligeiro_reservado=5,
                pesado_reservado=6,
            ),
        ]
        self.assertEqual(resolver_reservados_para_data(dt, cfg, {}, periodos), (5, 6))

    def test_resolver_padrao_quando_sem_excecao(self):
        cfg = ConfiguracaoLogistica(ligeiro_reservado=1, pesado_reservado=2)
        self.assertEqual(
            resolver_reservados_para_data(date(2026, 2, 1), cfg, {}, []),
            (1, 2),
        )
