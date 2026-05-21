from datetime import date

from django.test import SimpleTestCase

from pages.agenda.services.recorrencia import (
    ajustar_data_nominal_mensal,
    projetar_datas_ocorrencia,
)


class RecorrenciaProjetarTest(SimpleTestCase):
    def test_mensal_doze_meses_serie_aberta(self):
        datas = projetar_datas_ocorrencia(
            data_ancora=date(2026, 1, 15),
            recorrencia="mensal",
            intervalo=1,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 12, 31),
            data_fim_serie=None,
            dia_semana=None,
            dia_mes_fixo=15,
        )
        self.assertEqual(len(datas), 12)
        self.assertEqual(datas[0], date(2026, 1, 15))

    def test_antecipacao_domingo_para_sexta(self):
        # 2026-06-17 é quarta; usar um mês onde 17 cai domingo: 2027-01-17 é domingo
        nominal = date(2027, 1, 17)
        self.assertEqual(nominal.weekday() + 1, 7)
        ajustada = ajustar_data_nominal_mensal(nominal, antecipar_fim_semana=True)
        self.assertEqual(ajustada, date(2027, 1, 15))
        self.assertEqual(ajustada.weekday() + 1, 5)

    def test_semanal_dia_semana(self):
        datas = projetar_datas_ocorrencia(
            data_ancora=date(2026, 1, 5),
            recorrencia="semanal",
            intervalo=1,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 1, 31),
            data_fim_serie=None,
            dia_semana=3,
            dia_mes_fixo=None,
        )
        for d in datas:
            self.assertEqual(d.weekday() + 1, 3)

    def test_nenhuma_evento_unico(self):
        datas = projetar_datas_ocorrencia(
            data_ancora=date(2026, 5, 10),
            recorrencia="nenhuma",
            intervalo=1,
            data_inicio=date(2026, 5, 1),
            data_fim=date(2026, 5, 31),
            data_fim_serie=date(2026, 5, 10),
            dia_semana=None,
            dia_mes_fixo=None,
        )
        self.assertEqual(datas, [date(2026, 5, 10)])
