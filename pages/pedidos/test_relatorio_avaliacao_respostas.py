"""Relatório de respostas à pesquisa de satisfação (prev_entrega + motorista)."""

from datetime import date

from django.test import TestCase
from django.utils import timezone

from pages.core.models import Pais
from pages.filial.models import Filial
from pages.motorista.models import Motorista
from pages.pedidos.models import AvaliacaoPedido, Pedido, TentativaEntrega
from pages.pedidos.services.relatorio_avaliacao_respostas import (
    montar_relatorio_avaliacao_respostas,
    validar_e_montar_relatorio_avaliacao_respostas,
)


class RelatorioAvaliacaoRespostasTests(TestCase):
    d0 = date(2026, 6, 10)
    d1 = date(2026, 6, 12)

    @classmethod
    def setUpTestData(cls):
        cls.pais = Pais.objects.create(nome="PT-RAR", sigla="PT", codigo_tel="+351")
        cls.filial = Filial.objects.create(
            codigo="RAR01",
            nome="FIL RAR",
            pais_atuacao=cls.pais,
            is_matriz=True,
        )
        cls.mot_a = Motorista.objects.create(
            filial=cls.filial,
            nome="MOTOR A",
            telefone="900000001",
        )
        cls.mot_b = Motorista.objects.create(
            filial=cls.filial,
            nome="MOTOR B",
            telefone="900000002",
        )

    def _pedido(self, id_vonzu: int, prev_entrega: date) -> Pedido:
        now = timezone.now()
        return Pedido.objects.create(
            filial=self.filial,
            id_vonzu=id_vonzu,
            pedido=f"P-{id_vonzu}",
            tipo="ENTREGA",
            criado=now,
            atualizacao=now,
            prev_entrega=prev_entrega,
        )

    def test_periodo_prev_entrega_e_respondido_em(self):
        p = self._pedido(101, self.d0)
        TentativaEntrega.objects.create(
            pedido=p,
            data_tentativa=self.d0,
            estado="completed",
            motorista=self.mot_a,
        )
        AvaliacaoPedido.objects.create(
            pedido=p,
            respondido_em=timezone.now(),
            p1_entrega_no_prazo="Sim",
        )

        out = montar_relatorio_avaliacao_respostas(self.filial, self.d0, self.d1)
        self.assertEqual(out["total_linhas"], 1)
        self.assertEqual(out["linhas"][0]["motorista"], "MOTOR A")

        out_fora = montar_relatorio_avaliacao_respostas(self.filial, date(2026, 7, 1), date(2026, 7, 2))
        self.assertEqual(out_fora["total_linhas"], 0)

    def test_sem_respondido_exclui(self):
        p = self._pedido(102, self.d0)
        TentativaEntrega.objects.create(
            pedido=p,
            data_tentativa=self.d0,
            estado="completed",
            motorista=self.mot_a,
        )
        AvaliacaoPedido.objects.create(pedido=p, respondido_em=None)
        out = montar_relatorio_avaliacao_respostas(self.filial, self.d0, self.d1)
        self.assertEqual(out["total_linhas"], 0)

    def test_filtro_motorista(self):
        p = self._pedido(103, self.d0)
        TentativaEntrega.objects.create(
            pedido=p,
            data_tentativa=self.d0,
            estado="completed",
            motorista=self.mot_b,
        )
        AvaliacaoPedido.objects.create(pedido=p, respondido_em=timezone.now())

        out_all = montar_relatorio_avaliacao_respostas(self.filial, self.d0, self.d1)
        self.assertEqual(out_all["total_linhas"], 1)

        out_a = montar_relatorio_avaliacao_respostas(
            self.filial, self.d0, self.d1, motorista_id=self.mot_a.id
        )
        self.assertEqual(out_a["total_linhas"], 0)

        out_b = montar_relatorio_avaliacao_respostas(
            self.filial, self.d0, self.d1, motorista_id=self.mot_b.id
        )
        self.assertEqual(out_b["total_linhas"], 1)

    def test_agrupar_motorista(self):
        p1 = self._pedido(201, self.d0)
        TentativaEntrega.objects.create(
            pedido=p1, data_tentativa=self.d0, estado="completed", motorista=self.mot_a
        )
        AvaliacaoPedido.objects.create(pedido=p1, respondido_em=timezone.now())
        p2 = self._pedido(202, self.d0)
        TentativaEntrega.objects.create(
            pedido=p2, data_tentativa=self.d0, estado="completed", motorista=self.mot_a
        )
        AvaliacaoPedido.objects.create(pedido=p2, respondido_em=timezone.now())

        out = montar_relatorio_avaliacao_respostas(
            self.filial, self.d0, self.d1, agrupar_motorista=True
        )
        self.assertTrue(out["agrupar_motorista"])
        self.assertIn("grupos", out)
        self.assertEqual(len(out["grupos"]), 1)
        self.assertEqual(out["grupos"][0]["total"], 2)
        self.assertEqual(len(out["grupos"][0]["linhas"]), 2)

    def test_validar_sem_filial(self):
        payload, err = validar_e_montar_relatorio_avaliacao_respostas(
            None, {"data_inicial": "2026-06-10", "data_final": "2026-06-10"}
        )
        self.assertIsNone(payload)
        self.assertIsNotNone(err)
