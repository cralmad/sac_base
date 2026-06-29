"""Testes de geocodificação via codigo-postal.pt."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from pages.core.models import Pais
from pages.filial.models import Filial
from pages.pedidos.models import Pedido
from pages.pedidos.services.codigo_postal_pt import (
    GEOCODE_LOTE_PEDIDOS,
    GEOCODE_SYNC_MAX_PEDIDOS,
    _parse_candidatos_html,
    atribuir_coordenadas_pedidos,
    consultar_codigo_postal_pt,
    executar_geocodificacao_diaria,
    geocodificar_filial_manual,
    resolver_coordenadas,
    verificar_estrutura_codigo_postal_pt,
)

HTML_UM_CANDIDATO = """
<a class='search-title'>Estrada Nacional 253</a></div>
<span class='pull-right gps'><b>GPS:</b> 38.322772 , -8.772580</span>
"""

HTML_DOIS_GPS_IGUAIS = """
<a class='search-title'>Rua A</a></div>
<span class='pull-right gps'><b>GPS:</b> 38.322772 , -8.772580</span>
<a class='search-title'>Rua B</a></div>
<span class='pull-right gps'><b>GPS:</b> 38.322772 , -8.772580</span>
"""

HTML_DOIS_GPS_DISTINTOS = """
<a class='search-title'>Estrada Nacional 253</a></div>
<span class='pull-right gps'><b>GPS:</b> 38.322772 , -8.772580</span>
<a class='search-title'>Rua Sem Match</a></div>
<span class='pull-right gps'><b>GPS:</b> 38.500000 , -8.900000</span>
"""

HTML_SEM_MARCADOR_GPS = "<html><body><h1>Alterado</h1></body></html>"


class ParseCandidatosHtmlTests(TestCase):
    def test_um_candidato_aspas_simples(self):
        candidatos = _parse_candidatos_html(HTML_UM_CANDIDATO)
        self.assertEqual(len(candidatos), 1)
        self.assertEqual(candidatos[0]["rua"], "Estrada Nacional 253")
        self.assertAlmostEqual(candidatos[0]["gps_lat"], 38.322772)
        self.assertAlmostEqual(candidatos[0]["gps_lng"], -8.772580)

    def test_multiplos_mesmo_gps(self):
        candidatos = _parse_candidatos_html(HTML_DOIS_GPS_IGUAIS)
        self.assertEqual(len(candidatos), 2)

    def test_multiplos_gps_distintos(self):
        candidatos = _parse_candidatos_html(HTML_DOIS_GPS_DISTINTOS)
        self.assertEqual(len(candidatos), 2)
        self.assertNotEqual(candidatos[0]["gps_lat"], candidatos[1]["gps_lat"])


class ResolverCoordenadasTests(TestCase):
    def test_um_candidato_cp_pt(self):
        candidatos = _parse_candidatos_html(HTML_UM_CANDIDATO)
        res = resolver_coordenadas("Estrada Nacional 253", "7580-610", "COMPORTA", candidatos)
        self.assertEqual(res["precision"], "cp_pt")
        self.assertAlmostEqual(res["lat"], 38.322772)

    def test_mesmo_gps_cp_pt(self):
        candidatos = _parse_candidatos_html(HTML_DOIS_GPS_IGUAIS)
        res = resolver_coordenadas("Qualquer morada", "7580-610", "", candidatos)
        self.assertEqual(res["precision"], "cp_pt")

    def test_match_unico_rua_cp_pt_rua(self):
        candidatos = _parse_candidatos_html(HTML_DOIS_GPS_DISTINTOS)
        res = resolver_coordenadas(
            "Estrada Nacional 253 Comporta",
            "7580-610",
            "COMPORTA",
            candidatos,
        )
        self.assertEqual(res["precision"], "cp_pt_rua")
        self.assertAlmostEqual(res["lat"], 38.322772)

    def test_fallback_zero_matches(self):
        candidatos = _parse_candidatos_html(HTML_DOIS_GPS_DISTINTOS)
        res = resolver_coordenadas("Morada totalmente diferente", "7580-610", "", candidatos)
        self.assertEqual(res["precision"], "cp_pt_fallback")
        self.assertIsNotNone(res["aviso"])

    def test_fallback_dois_matches(self):
        candidatos = [
            {"rua": "Estrada Nacional 253", "gps_lat": 38.1, "gps_lng": -8.1, "localidade": ""},
            {"rua": "Estrada Nacional 253 Sul", "gps_lat": 38.2, "gps_lng": -8.2, "localidade": ""},
        ]
        res = resolver_coordenadas(
            "Estrada Nacional 253 Comporta",
            "7580-610",
            "",
            candidatos,
        )
        self.assertEqual(res["precision"], "cp_pt_fallback")
        self.assertAlmostEqual(res["lat"], 38.1)

    def test_sem_candidatos_retorna_none(self):
        self.assertIsNone(resolver_coordenadas("Rua X", "1000-001", "Lisboa", []))


class VerificarEstruturaTests(TestCase):
    def setUp(self):
        import pages.pedidos.services.codigo_postal_pt as mod

        mod._SITE_CHECK_CACHE["expira_em"] = 0.0
        mod._SITE_CHECK_CACHE["resultado"] = None

    @patch("pages.pedidos.services.codigo_postal_pt._http_get")
    def test_site_alterado_sem_marcador(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = HTML_SEM_MARCADOR_GPS
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        resultado = verificar_estrutura_codigo_postal_pt(forcar=True)
        self.assertFalse(resultado["ok"])
        self.assertEqual(resultado["codigo"], "site_alterado")

    @patch("pages.pedidos.services.codigo_postal_pt._http_get")
    def test_site_ok_com_marcadores(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = HTML_UM_CANDIDATO
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        resultado = verificar_estrutura_codigo_postal_pt(forcar=True)
        self.assertTrue(resultado["ok"])


class GeocodificacaoLoteTests(TestCase):
    def setUp(self):
        cache.clear()
        self.pais = Pais.objects.create(nome="PT-GEO", sigla="PT", codigo_tel="+351")
        self.filial = Filial.objects.create(
            codigo="GEO1", nome="FIL GEO", pais_atuacao=self.pais, is_matriz=True
        )
        now = timezone.now()
        self.pedido = Pedido.objects.create(
            filial=self.filial,
            id_vonzu=9001,
            tipo="ENTREGA",
            criado=now,
            atualizacao=now,
            prev_entrega=now.date(),
            endereco_dest="Estrada Nacional 253",
            codpost_dest="7580-610",
            cidade_dest="COMPORTA",
        )

    def tearDown(self):
        cache.clear()

    @patch("pages.pedidos.services.codigo_postal_pt.consultar_codigo_postal_pt")
    @patch("pages.pedidos.services.codigo_postal_pt.verificar_estrutura_codigo_postal_pt")
    def test_atribuir_coordenadas_bulk_update(self, mock_check, mock_consulta):
        mock_check.return_value = {"ok": True, "codigo": "ok", "mensagem": ""}
        mock_consulta.return_value = {
            "ok": True,
            "candidatos": _parse_candidatos_html(HTML_UM_CANDIDATO),
            "codigo_erro": None,
        }

        stats = atribuir_coordenadas_pedidos(
            self.filial,
            [self.pedido.id],
            origem="importacao",
        )
        self.assertEqual(stats["coords_atribuidas"], 1)
        self.assertEqual(stats["coords_cp_pt"], 1)

        self.pedido.refresh_from_db()
        self.assertIsNotNone(self.pedido.lat)
        self.assertIsNotNone(self.pedido.lng)
        self.assertEqual(self.pedido.geocoding_precision, "cp_pt")

    @patch("pages.pedidos.services.codigo_postal_pt.verificar_estrutura_codigo_postal_pt")
    def test_aborta_lote_site_alterado(self, mock_check):
        mock_check.return_value = {
            "ok": False,
            "codigo": "site_alterado",
            "mensagem": "Estrutura alterada.",
        }

        stats = atribuir_coordenadas_pedidos(
            self.filial,
            [self.pedido.id],
            origem="importacao",
        )
        self.assertFalse(stats["site_ok"])
        self.pedido.refresh_from_db()
        self.assertIsNone(self.pedido.lat)

    def test_ignora_pedido_ja_com_coordenadas(self):
        self.pedido.lat = Decimal("38.0")
        self.pedido.lng = Decimal("-9.0")
        self.pedido.save(update_fields=["lat", "lng"])

        with patch(
            "pages.pedidos.services.codigo_postal_pt.verificar_estrutura_codigo_postal_pt",
            return_value={"ok": True, "codigo": "ok", "mensagem": ""},
        ), patch("pages.pedidos.services.codigo_postal_pt.consultar_codigo_postal_pt") as mock_consulta:
            stats = atribuir_coordenadas_pedidos(
                self.filial,
                [self.pedido.id],
                origem="importacao",
            )
            mock_consulta.assert_not_called()
            self.assertEqual(stats["coords_ignoradas_ja_possuiam"], 1)


class GeocodificarFilialManualTests(TestCase):
    def setUp(self):
        self.pais = Pais.objects.create(nome="PT-MAN", sigla="PT", codigo_tel="+351")
        self.filial = Filial.objects.create(
            codigo="MAN1", nome="FIL MAN", pais_atuacao=self.pais, is_matriz=True
        )

    def test_sem_pendentes_retorna_vazio(self):
        stats = geocodificar_filial_manual(self.filial)
        self.assertEqual(stats["coords_atribuidas"], 0)
        self.assertEqual(stats["coords_restantes_filial"], 0)

    @patch("pages.pedidos.services.codigo_postal_pt.atribuir_coordenadas_pedidos")
    def test_acima_limite_processa_lote_por_clique(self, mock_atribuir):
        mock_atribuir.return_value = {
            "coords_atribuidas": GEOCODE_SYNC_MAX_PEDIDOS,
            "coords_cp_pt": GEOCODE_SYNC_MAX_PEDIDOS,
            "coords_cp_pt_rua": 0,
            "coords_cp_pt_fallback": 0,
            "coords_sem_cp": 0,
            "coords_ignoradas_ja_possuiam": 0,
            "coords_cp_nao_encontrado": 0,
            "coords_falha_site": 0,
            "coords_enfileiradas": 0,
            "coords_restantes_filial": 121,
            "modo": "sync",
            "site_ok": True,
            "avisos": [],
        }
        now = timezone.now()
        for i in range(GEOCODE_SYNC_MAX_PEDIDOS + 5):
            Pedido.objects.create(
                filial=self.filial,
                id_vonzu=30000 + i,
                tipo="ENTREGA",
                criado=now,
                atualizacao=now,
                prev_entrega=now.date(),
                endereco_dest=f"Rua {i}",
                codpost_dest="7580-610",
                cidade_dest="COMPORTA",
            )

        stats = geocodificar_filial_manual(self.filial)
        mock_atribuir.assert_called_once()
        self.assertEqual(mock_atribuir.call_args.kwargs["max_processar"], GEOCODE_SYNC_MAX_PEDIDOS)
        self.assertEqual(stats["coords_atribuidas"], GEOCODE_SYNC_MAX_PEDIDOS)
        self.assertEqual(stats["coords_enfileiradas"], 121)
        self.assertEqual(stats["modo"], "noturno")


class ExecutarGeocodificacaoDiariaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.pais = Pais.objects.create(nome="PT-CMD", sigla="PT", codigo_tel="+351")
        self.filial = Filial.objects.create(
            codigo="CMD1", nome="FIL CMD", pais_atuacao=self.pais, is_matriz=True
        )
        now = timezone.now()
        for i in range(GEOCODE_LOTE_PEDIDOS + 3):
            Pedido.objects.create(
                filial=self.filial,
                id_vonzu=20000 + i,
                tipo="ENTREGA",
                criado=now,
                atualizacao=now,
                prev_entrega=now.date(),
                endereco_dest=f"Rua {i}",
                codpost_dest="7580-610",
                cidade_dest="COMPORTA",
            )

    def tearDown(self):
        cache.clear()

    def test_dry_run_conta_pendentes(self):
        resumo = executar_geocodificacao_diaria(dry_run=True)
        self.assertEqual(resumo["pendentes"], GEOCODE_LOTE_PEDIDOS + 3)

    @patch("pages.pedidos.services.codigo_postal_pt.time.sleep")
    @patch("pages.pedidos.services.codigo_postal_pt.existe_pendente_global")
    @patch("pages.pedidos.services.codigo_postal_pt.listar_ids_pedidos_sem_coord")
    @patch("pages.pedidos.services.codigo_postal_pt.atribuir_coordenadas_pedidos")
    def test_loop_multi_lote(self, mock_atribuir, mock_listar, mock_pendente, mock_sleep):
        lote1 = list(range(1, GEOCODE_LOTE_PEDIDOS + 1))
        lote2 = list(range(GEOCODE_LOTE_PEDIDOS + 1, GEOCODE_LOTE_PEDIDOS + 4))
        mock_listar.side_effect = [lote1, lote2, []]
        mock_pendente.side_effect = [True, False]
        mock_atribuir.side_effect = [
            {
                "coords_atribuidas": GEOCODE_LOTE_PEDIDOS,
                "site_ok": True,
                "coords_cp_pt": GEOCODE_LOTE_PEDIDOS,
                "coords_cp_pt_rua": 0,
                "coords_cp_pt_fallback": 0,
                "coords_sem_cp": 0,
                "coords_ignoradas_ja_possuiam": 0,
                "coords_cp_nao_encontrado": 0,
                "coords_falha_site": 0,
                "coords_enfileiradas": 0,
                "coords_restantes_filial": 3,
                "modo": "noturno",
                "avisos": [],
            },
            {
                "coords_atribuidas": 3,
                "site_ok": True,
                "coords_cp_pt": 3,
                "coords_cp_pt_rua": 0,
                "coords_cp_pt_fallback": 0,
                "coords_sem_cp": 0,
                "coords_ignoradas_ja_possuiam": 0,
                "coords_cp_nao_encontrado": 0,
                "coords_falha_site": 0,
                "coords_enfileiradas": 0,
                "coords_restantes_filial": 0,
                "modo": "noturno",
                "avisos": [],
            },
        ]

        resumo = executar_geocodificacao_diaria()
        self.assertEqual(resumo["lotes"], 2)
        self.assertEqual(resumo["coords_atribuidas_total"], GEOCODE_LOTE_PEDIDOS + 3)
        mock_sleep.assert_called_once()

    @patch("pages.pedidos.services.codigo_postal_pt.atribuir_coordenadas_pedidos")
    def test_aborta_site_alterado(self, mock_atribuir):
        mock_atribuir.return_value = {
            "coords_atribuidas": 0,
            "site_ok": False,
            "coords_cp_pt": 0,
            "coords_cp_pt_rua": 0,
            "coords_cp_pt_fallback": 0,
            "coords_sem_cp": 0,
            "coords_ignoradas_ja_possuiam": 0,
            "coords_cp_nao_encontrado": 0,
            "coords_falha_site": 1,
            "coords_enfileiradas": 0,
            "coords_restantes_filial": GEOCODE_LOTE_PEDIDOS + 3,
            "modo": "noturno",
            "avisos": ["Estrutura alterada."],
        }

        resumo = executar_geocodificacao_diaria()
        self.assertTrue(resumo["abortado_site"])


class ConsultarCodigoPostalPtTests(TestCase):
    @patch("pages.pedidos.services.codigo_postal_pt._http_get")
    def test_consulta_parseia_candidatos(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = HTML_UM_CANDIDATO
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        resultado = consultar_codigo_postal_pt("7580-610", aplicar_sleep=False)
        self.assertTrue(resultado["ok"])
        self.assertEqual(len(resultado["candidatos"]), 1)
