from datetime import date

from django.test import TestCase

from pages.agenda.constants import ModoEventoAgenda, TipoVinculoMaterializacao
from pages.agenda.models import AgendaManual, AgendaMaterializacao
from pages.agenda.services.coletar_flutuantes import coletar_eventos_flutuantes
from pages.filial.models import Filial


class DedupMaterializacaoTest(TestCase):
    def setUp(self):
        self.filial = Filial.objects.create(codigo="DAG", nome="Filial Dedup", ativa=True, is_matriz=True)
        self.agenda_mat = AgendaManual.objects.create(
            filial=self.filial,
            titulo="Pagar fornecedor",
            modo_evento=ModoEventoAgenda.MATERIALIZAVEL,
            tipo_materializacao="financeiro.registro_financeiro_manual",
            payload_template={},
            data_ancora=date(2026, 6, 15),
            recorrencia="nenhuma",
            intervalo=1,
            data_fim_serie=date(2026, 6, 15),
        )
        AgendaMaterializacao.objects.create(
            agenda_manual=self.agenda_mat,
            data_ocorrencia=date(2026, 6, 15),
            tipo_vinculo=TipoVinculoMaterializacao.MATERIALIZADO,
        )
        self.agenda_conf = AgendaManual.objects.create(
            filial=self.filial,
            titulo="Checklist",
            modo_evento=ModoEventoAgenda.AVISO_CONFIRMAVEL,
            data_ancora=date(2026, 6, 10),
            recorrencia="nenhuma",
            intervalo=1,
            data_fim_serie=date(2026, 6, 10),
        )
        AgendaMaterializacao.objects.create(
            agenda_manual=self.agenda_conf,
            data_ocorrencia=date(2026, 6, 10),
            tipo_vinculo=TipoVinculoMaterializacao.CONCLUIDO_CONFIRMADO,
        )

    def test_materializavel_suprime_flutuante_na_data(self):
        evs = coletar_eventos_flutuantes(
            filial_id=self.filial.id,
            data_inicio=date(2026, 6, 1),
            data_fim=date(2026, 6, 30),
            usuario=None,
            pode_confirmar=False,
            pode_materializar=True,
        )
        ids = [e["id"] for e in evs if e["agenda_manual_id"] == self.agenda_mat.id]
        self.assertEqual(ids, [])

    def test_confirmavel_mantem_flutuante_concluido(self):
        evs = coletar_eventos_flutuantes(
            filial_id=self.filial.id,
            data_inicio=date(2026, 6, 1),
            data_fim=date(2026, 6, 30),
            usuario=None,
            pode_confirmar=False,
            pode_materializar=False,
        )
        match = [e for e in evs if e["agenda_manual_id"] == self.agenda_conf.id]
        self.assertEqual(len(match), 1)
        self.assertEqual(match[0]["status"], "concluido")
