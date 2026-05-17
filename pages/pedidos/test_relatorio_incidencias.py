"""Relatório de incidências (data da incidência + origem + motorista + agrupamentos)."""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from pages.core.models import Pais
from pages.filial.models import Filial
from pages.motorista.models import Motorista
from pages.pedidos.models import Incidencia, Pedido
from pages.pedidos.services.relatorio_incidencias import (
    montar_relatorio_incidencias,
    validar_e_montar_relatorio_incidencias,
)


class RelatorioIncidenciasTests(TestCase):
    d0 = date(2026, 5, 1)
    d1 = date(2026, 5, 10)
    d2 = date(2026, 5, 3)

    @classmethod
    def setUpTestData(cls):
        cls.pais = Pais.objects.create(nome="PT-RI", sigla="PT", codigo_tel="+351")
        cls.filial = Filial.objects.create(
            codigo="RI01",
            nome="FIL RI",
            pais_atuacao=cls.pais,
            is_matriz=True,
        )
        cls.outra_filial = Filial.objects.create(
            codigo="RI02",
            nome="FIL OUTRA",
            pais_atuacao=cls.pais,
            is_matriz=False,
        )
        cls.mot_a = Motorista.objects.create(
            filial=cls.filial,
            nome="MOTOR A",
            telefone="910000001",
        )
        cls.mot_b = Motorista.objects.create(
            filial=cls.filial,
            nome="MOTOR B",
            telefone="910000002",
        )

    def _pedido(self, filial, id_vonzu: int) -> Pedido:
        now = timezone.now()
        return Pedido.objects.create(
            filial=filial,
            id_vonzu=id_vonzu,
            pedido=f"P-{id_vonzu}",
            tipo="ENTREGA",
            criado=now,
            atualizacao=now,
        )

    def test_filtro_periodo_tenant_e_ordem_data(self):
        p = self._pedido(self.filial, 201)
        p_out = self._pedido(self.outra_filial, 202)
        Incidencia.objects.create(
            pedido=p,
            data=self.d2,
            origem="Cliente",
            tipo="Outros",
        )
        Incidencia.objects.create(
            pedido=p,
            data=self.d0,
            origem="Cliente",
            tipo="Outros",
        )
        Incidencia.objects.create(
            pedido=p_out,
            data=self.d0,
            origem="Filial",
            tipo="Artigo Danificado",
            motorista=self.mot_a,
        )

        out = montar_relatorio_incidencias(self.filial, self.d0, self.d1)
        self.assertEqual(out["total"], 2)
        self.assertEqual(len(out["grupos_origem"]), 1)
        grupo = out["grupos_origem"][0]
        self.assertEqual(grupo["origem"], "Cliente")
        self.assertEqual(grupo["linhas"][0]["data"], "01/05/2026")
        self.assertEqual(grupo["linhas"][1]["data"], "03/05/2026")

    def test_valor_total_e_agrupamento_motorista(self):
        p = self._pedido(self.filial, 301)
        Incidencia.objects.create(
            pedido=p,
            data=self.d0,
            origem="Filial",
            tipo="Artigo Danificado",
            motorista=self.mot_a,
            valor=Decimal("12.50"),
        )
        Incidencia.objects.create(
            pedido=p,
            data=self.d0,
            origem="Filial",
            tipo="Artigo Extraviado",
            motorista=self.mot_b,
            valor=Decimal("7.50"),
        )
        Incidencia.objects.create(
            pedido=p,
            data=self.d0,
            origem="Cliente",
            tipo="Outros",
            valor=Decimal("5.00"),
        )

        out = montar_relatorio_incidencias(
            self.filial, self.d0, self.d1, agrupar_motorista=True
        )
        self.assertEqual(out["valor_total_fmt"], "25,00")
        self.assertEqual(len(out["grupos_origem"]), 2)

        grupo_filial = next(g for g in out["grupos_origem"] if g["origem"] == "Filial")
        self.assertEqual(grupo_filial["valor_total_fmt"], "20,00")
        self.assertEqual(len(grupo_filial["subgrupos"]), 2)

        grupo_cliente = next(g for g in out["grupos_origem"] if g["origem"] == "Cliente")
        self.assertEqual(grupo_cliente["valor_total_fmt"], "5,00")
        self.assertIn("subgrupos", grupo_cliente)

    def test_filtro_origem_e_motorista(self):
        p = self._pedido(self.filial, 401)
        Incidencia.objects.create(
            pedido=p,
            data=self.d0,
            origem="Filial",
            tipo="Artigo Danificado",
            motorista=self.mot_a,
            valor=Decimal("12.50"),
        )
        Incidencia.objects.create(
            pedido=p,
            data=self.d0,
            origem="Cliente",
            tipo="Outros",
        )

        out_filial = montar_relatorio_incidencias(
            self.filial, self.d0, self.d1, origem="Filial"
        )
        self.assertEqual(out_filial["total"], 1)
        self.assertEqual(out_filial["grupos_origem"][0]["linhas"][0]["motorista"], "MOTOR A")

        out_mot = montar_relatorio_incidencias(
            self.filial, self.d0, self.d1, motorista_id=self.mot_a.id
        )
        self.assertEqual(out_mot["total"], 1)

    def test_validar_http_payload(self):
        payload, err = validar_e_montar_relatorio_incidencias(
            self.filial,
            {"data_inicial": "2026-05-01", "data_final": "2026-05-10"},
        )
        self.assertIsNone(err)
        self.assertEqual(payload["total"], 0)
        self.assertEqual(payload["valor_total_fmt"], "0,00")

        _, err_inv = validar_e_montar_relatorio_incidencias(
            self.filial,
            {"data_inicial": "x", "data_final": "2026-05-10"},
        )
        self.assertIsNotNone(err_inv)
