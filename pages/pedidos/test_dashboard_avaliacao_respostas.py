"""Dashboard de avaliações — funil e agregados."""

from datetime import date

from django.test import TestCase
from django.utils import timezone

from pages.core.models import Pais
from pages.filial.models import Filial
from pages.motorista.models import Motorista
from pages.pedidos.models import AvaliacaoPedido, Pedido, TentativaEntrega
from pages.pedidos.services.dashboard_avaliacao_respostas import (
    montar_dashboard_avaliacao_respostas,
    validar_e_montar_dashboard_avaliacao_respostas,
)


class DashboardAvaliacaoRespostasTests(TestCase):
    d0 = date(2026, 7, 1)
    d1 = date(2026, 7, 31)

    @classmethod
    def setUpTestData(cls):
        cls.pais = Pais.objects.create(nome="PT-DASH", sigla="PT", codigo_tel="+351")
        cls.filial = Filial.objects.create(
            codigo="DSH01",
            nome="FIL DASH",
            pais_atuacao=cls.pais,
            is_matriz=True,
        )
        cls.mot_a = Motorista.objects.create(
            filial=cls.filial,
            nome="MOT DASH A",
            telefone="910000001",
        )
        cls.mot_b = Motorista.objects.create(
            filial=cls.filial,
            nome="MOT DASH B",
            telefone="910000002",
        )

    def _pedido(self, id_vonzu: int, prev: date) -> Pedido:
        now = timezone.now()
        return Pedido.objects.create(
            filial=self.filial,
            id_vonzu=id_vonzu,
            pedido=f"D-{id_vonzu}",
            tipo="ENTREGA",
            criado=now,
            atualizacao=now,
            prev_entrega=prev,
        )

    def test_funil_taxa_resposta(self):
        p1 = self._pedido(501, self.d0)
        TentativaEntrega.objects.create(
            pedido=p1, data_tentativa=self.d0, estado="completed", motorista=self.mot_a
        )
        AvaliacaoPedido.objects.create(
            pedido=p1,
            email_enviado=True,
            respondido_em=timezone.now(),
            p3_educacao_simpatia=5,
        )
        p2 = self._pedido(502, self.d0)
        TentativaEntrega.objects.create(
            pedido=p2, data_tentativa=self.d0, estado="completed", motorista=self.mot_a
        )
        AvaliacaoPedido.objects.create(
            pedido=p2,
            email_enviado=True,
            respondido_em=None,
        )

        out = montar_dashboard_avaliacao_respostas(self.filial, self.d0, self.d1)
        self.assertEqual(out["funil"]["n_email_enviado"], 2)
        self.assertEqual(out["funil"]["n_respondido_e_enviado"], 1)
        self.assertEqual(out["funil"]["taxa_resposta_sobre_enviadas_pct"], 50.0)
        self.assertEqual(out["funil"]["pct_nao_respondeu_sobre_enviadas"], 50.0)

    def test_filtro_motorista(self):
        p1 = self._pedido(601, self.d0)
        TentativaEntrega.objects.create(
            pedido=p1, data_tentativa=self.d0, estado="completed", motorista=self.mot_a
        )
        AvaliacaoPedido.objects.create(
            pedido=p1,
            email_enviado=True,
            respondido_em=timezone.now(),
            p1_entrega_no_prazo="Sim",
        )
        p2 = self._pedido(602, self.d0)
        TentativaEntrega.objects.create(
            pedido=p2, data_tentativa=self.d0, estado="completed", motorista=self.mot_b
        )
        AvaliacaoPedido.objects.create(
            pedido=p2,
            email_enviado=True,
            respondido_em=timezone.now(),
            p1_entrega_no_prazo="Nao",
        )

        out_a = montar_dashboard_avaliacao_respostas(
            self.filial, self.d0, self.d1, motorista_id=self.mot_a.id
        )
        self.assertEqual(out_a["total_respondidas"], 1)
        out_b = montar_dashboard_avaliacao_respostas(
            self.filial, self.d0, self.d1, motorista_id=self.mot_b.id
        )
        self.assertEqual(out_b["total_respondidas"], 1)

    def test_validar_sem_filial(self):
        payload, err = validar_e_montar_dashboard_avaliacao_respostas(
            None, {"data_inicial": "2026-07-01", "data_final": "2026-07-01"}
        )
        self.assertIsNone(payload)
        self.assertIsNotNone(err)
