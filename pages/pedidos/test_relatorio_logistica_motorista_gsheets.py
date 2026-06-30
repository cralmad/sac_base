"""Testes do envio Google Sheets — relatório logística motorista."""

from datetime import date
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from pages.core.models import Pais
from pages.filial.models import Filial, FilialConfig
from pages.pedidos.models import Pedido, TentativaEntrega
from pages.pedidos.services.relatorio_logistica_motorista_gsheets import (
    executar_envio_gsheets_logistica_motorista,
    listar_tentativas_ignoradas_interno,
    listar_tentativas_para_gsheets,
    montar_rows_gsheets_logistica_motorista,
)


class RelatorioLogisticaMotoristaGSheetsTests(TestCase):
    dt = date(2026, 5, 10)
    dt_out = date(2026, 5, 11)

    def setUp(self):
        self.pais = Pais.objects.create(nome="PT-GS", sigla="PT", codigo_tel="+351")
        self.filial = Filial.objects.create(
            codigo="GS1", nome="FIL GS 1", pais_atuacao=self.pais, is_matriz=True
        )
        FilialConfig.objects.create(
            filial=self.filial,
            gsheets_spreadsheet_id_2="sheet-id-2",
            gsheets_sheet_name_2="Logistica",
        )
        self.filial_b = Filial.objects.create(
            codigo="GS2", nome="FIL GS 2", pais_atuacao=self.pais, is_matriz=False
        )
        FilialConfig.objects.create(filial=self.filial_b)

    def _pedido(self, id_vonzu: int, filial=None, pedido_ref: str = "", obs: str = "") -> Pedido:
        filial = filial or self.filial
        now = timezone.now()
        return Pedido.objects.create(
            filial=filial,
            id_vonzu=id_vonzu,
            pedido=pedido_ref or None,
            tipo="ENTREGA",
            criado=now,
            atualizacao=now,
            prev_entrega=self.dt,
            obs=obs or None,
        )

    def _tentativa(self, pedido: Pedido, **kwargs) -> TentativaEntrega:
        defaults = {
            "data_tentativa": self.dt,
            "estado": "CA",
        }
        defaults.update(kwargs)
        return TentativaEntrega.objects.create(pedido=pedido, **defaults)

    def test_montar_rows_colunas_a_e(self):
        p = self._pedido(20001, pedido_ref="PED-001", obs="Obs teste")
        t = self._tentativa(p, estado="CA")
        rows = montar_rows_gsheets_logistica_motorista([t])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "10/05/2026")
        self.assertEqual(rows[0][1], "PED-001")
        self.assertEqual(rows[0][2], "Outro")
        self.assertEqual(rows[0][3], "")
        self.assertIn("Cliente ausente", rows[0][4])
        self.assertIn("Obs teste", rows[0][4])

    def test_montar_rows_referencia_id_vonzu_sem_pedido(self):
        p = self._pedido(20002, pedido_ref="")
        t = self._tentativa(p)
        rows = montar_rows_gsheets_logistica_motorista([t])
        self.assertEqual(rows[0][1], "20002")

    def test_listar_exclui_completed(self):
        p1 = self._pedido(20003)
        t_ok = self._tentativa(p1, estado="CA")
        p2 = self._pedido(20004)
        self._tentativa(p2, estado="completed")
        ids = [x.id for x in listar_tentativas_para_gsheets(self.filial, self.dt, self.dt, None)]
        self.assertIn(t_ok.id, ids)
        self.assertEqual(len(ids), 1)

    def test_listar_exclui_estados_danos_recusa(self):
        p_ok = self._pedido(20011)
        t_ok = self._tentativa(p_ok, estado="CA")
        excluidos = ("DVP", "CI", "PNR", "RCD", "recusa_parcial")
        for idx, estado in enumerate(excluidos):
            p = self._pedido(20012 + idx)
            self._tentativa(p, estado=estado)
        ids = [x.id for x in listar_tentativas_para_gsheets(self.filial, self.dt, self.dt, None)]
        self.assertEqual(ids, [t_ok.id])

    def test_listar_exclui_interno(self):
        p1 = self._pedido(20007)
        t_ok = self._tentativa(p1, interno=False)
        p2 = self._pedido(20008)
        t_int = self._tentativa(p2, interno=True)
        elegiveis = listar_tentativas_para_gsheets(self.filial, self.dt, self.dt, None)
        ignorados = listar_tentativas_ignoradas_interno(self.filial, self.dt, self.dt, None)
        self.assertEqual([x.id for x in elegiveis], [t_ok.id])
        self.assertEqual([x.id for x in ignorados], [t_int.id])

    def test_listar_respeita_filial(self):
        p = self._pedido(20005, filial=self.filial_b)
        t = self._tentativa(p)
        ids = list(
            listar_tentativas_para_gsheets(self.filial, self.dt, self.dt, None)
        )
        self.assertEqual(len(ids), 0)
        self.assertNotIn(t.id, [x.id for x in ids])

    @patch("pages.pedidos.services.relatorio_logistica_motorista_gsheets.append_logistica_motorista_rows")
    def test_executar_envio_chama_append(self, mock_append):
        mock_append.return_value = 1
        p = self._pedido(20006, pedido_ref="X1")
        self._tentativa(p)
        out = executar_envio_gsheets_logistica_motorista(
            self.filial,
            data_inicio=self.dt,
            data_fim=self.dt,
            motorista_ids=None,
        )
        self.assertEqual(out["enviados"], 1)
        self.assertEqual(out["ignorados_total"], 0)
        self.assertEqual(out["ignorados"], [])
        mock_append.assert_called_once()
        args = mock_append.call_args[0]
        self.assertEqual(args[0], "sheet-id-2")
        self.assertEqual(args[1], "Logistica")
        self.assertEqual(len(args[2]), 1)

    @patch("pages.pedidos.services.relatorio_logistica_motorista_gsheets.append_logistica_motorista_rows")
    def test_executar_retorna_ignorados_interno(self, mock_append):
        mock_append.return_value = 1
        p1 = self._pedido(20009, pedido_ref="ENV")
        self._tentativa(p1, interno=False)
        p2 = self._pedido(20010, pedido_ref="INT")
        self._tentativa(p2, interno=True)
        out = executar_envio_gsheets_logistica_motorista(
            self.filial,
            data_inicio=self.dt,
            data_fim=self.dt,
            motorista_ids=None,
        )
        self.assertEqual(out["enviados"], 1)
        self.assertEqual(out["ignorados_total"], 1)
        self.assertEqual(len(out["ignorados"]), 1)
        self.assertEqual(out["ignorados"][0]["referencia"], "INT")
        self.assertEqual(out["ignorados"][0]["motivo"], "interno")
