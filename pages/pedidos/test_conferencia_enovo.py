from datetime import date
import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.utils import timezone

from pages.core.models import Pais
from pages.filial.models import Filial, UsuarioFilial

from .models import Pedido, TentativaEntrega
from .services.conferencia_enovo import (
    aplicar_leituras_lote,
    preview_leitura_etiqueta,
    resolver_carro,
)
from .views_conferencia_enovo import (
    conferencia_enovo_preview_view,
    conferencia_enovo_view,
)

User = get_user_model()

QR_VOL1 = "008007108629003001"
QR_VOL2 = "008007108629003002"
TRK = 8007108629


class ConferenciaEnovoServiceTests(TestCase):
    def setUp(self):
        self.pais = Pais.objects.create(nome="PORTUGAL", sigla="PRT", codigo_tel="+351")
        self.filial = Filial.objects.create(
            codigo="MAT", nome="MATRIZ", pais_atuacao=self.pais, is_matriz=True
        )
        self.outra = Filial.objects.create(
            codigo="FIL", nome="OUTRA", pais_atuacao=self.pais, is_matriz=False
        )
        agora = timezone.now()
        self.pedido = Pedido.objects.create(
            filial=self.filial,
            origem="IMPORTADO",
            id_vonzu=TRK,
            pedido="REF-QR",
            tipo="ENTREGA",
            criado=agora,
            atualizacao=agora,
            prev_entrega=date(2026, 9, 18),
            volume=3,
        )

    def test_preview_qr_invalido(self):
        dados, erro = preview_leitura_etiqueta(self.filial, "123")
        self.assertIsNone(dados)
        self.assertIn("inválido", erro)

    def test_preview_ok_sem_carro(self):
        dados, erro = preview_leitura_etiqueta(self.filial, QR_VOL1)
        self.assertIsNone(erro)
        self.assertEqual(dados["trk"], TRK)
        self.assertEqual(dados["volume"], 1)
        self.assertTrue(dados["sem_carro"])
        self.assertIsNone(dados["carro"])

    def test_carro_mais_recente_com_carro_preenchido(self):
        TentativaEntrega.objects.create(
            pedido=self.pedido,
            data_tentativa=date(2026, 9, 10),
            carro=5,
            periodo="TARDE",
        )
        TentativaEntrega.objects.create(
            pedido=self.pedido,
            data_tentativa=date(2026, 9, 18),
            carro=None,
            periodo="TARDE",
        )
        TentativaEntrega.objects.create(
            pedido=self.pedido,
            data_tentativa=date(2026, 9, 17),
            carro=12,
            periodo="MANHA",
        )
        self.assertEqual(resolver_carro(self.pedido), 12)
        dados, erro = preview_leitura_etiqueta(self.filial, QR_VOL1)
        self.assertIsNone(erro)
        self.assertEqual(dados["carro"], 12)
        self.assertFalse(dados["sem_carro"])

    def test_idor_outra_filial(self):
        dados, erro = preview_leitura_etiqueta(self.outra, QR_VOL1)
        self.assertIsNone(dados)
        self.assertIn("não encontrado", erro)

    def test_duplicado_ja_conferido(self):
        aplicar_leituras_lote(self.filial, [{"codigo": QR_VOL1}])
        dados, erro = preview_leitura_etiqueta(self.filial, QR_VOL1)
        self.assertIsNone(dados)
        self.assertIn("já foi conferido", erro)

    def test_lote_grava_json_e_volume_conf(self):
        resultado = aplicar_leituras_lote(
            self.filial,
            [{"codigo": QR_VOL1}, {"codigo": QR_VOL2}],
        )
        self.assertTrue(resultado["todos_ok"])
        self.assertEqual(len(resultado["gravados"]), 2)
        self.pedido.refresh_from_db()
        conf = self.pedido.conferencia_volumes
        self.assertEqual(conf["TRK"], TRK)
        self.assertEqual(conf["total_volume"], 3)
        self.assertEqual(conf["total_vol_conferido"], 2)
        self.assertEqual(self.pedido.volume_conf, 2)
        vols = {item[1] for item in conf["conferido"].values()}
        self.assertEqual(vols, {1, 2})

    def test_lote_parcial_duplicado_no_lote(self):
        resultado = aplicar_leituras_lote(
            self.filial,
            [{"codigo": QR_VOL1}, {"codigo": QR_VOL1}],
        )
        self.assertFalse(resultado["todos_ok"])
        self.assertEqual(len(resultado["gravados"]), 1)
        self.assertEqual(len(resultado["erros"]), 1)
        self.assertIn("duplicado", resultado["erros"][0]["mensagem"].lower())

    def test_lote_misto_ok_e_trk_inexistente(self):
        resultado = aplicar_leituras_lote(
            self.filial,
            [{"codigo": QR_VOL1}, {"codigo": "009999999999003001"}],
        )
        self.assertFalse(resultado["todos_ok"])
        self.assertEqual(len(resultado["gravados"]), 1)
        self.assertEqual(len(resultado["erros"]), 1)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.volume_conf, 1)


class ConferenciaEnovoViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.pais = Pais.objects.create(nome="PORTUGAL", sigla="PRT", codigo_tel="+351")
        self.filial = Filial.objects.create(
            codigo="MAT", nome="MATRIZ", pais_atuacao=self.pais, is_matriz=True
        )
        self.usuario = User.objects.create_user(username="op_qr", password="x")
        UsuarioFilial.objects.create(
            usuario=self.usuario,
            filial=self.filial,
            ativo=True,
            pode_consultar=True,
            pode_escrever=True,
        )
        self.perm = Permission.objects.get(
            content_type__app_label="pedidos",
            codename="conferir_etiqueta_enovo",
        )
        agora = timezone.now()
        Pedido.objects.create(
            filial=self.filial,
            origem="IMPORTADO",
            id_vonzu=TRK,
            tipo="ENTREGA",
            criado=agora,
            atualizacao=agora,
            volume=3,
        )

    def test_get_sem_permissao(self):
        req = self.factory.get("/app/logistica/conferencia-enovo/")
        req.user = self.usuario
        with self.assertRaises(PermissionDenied):
            conferencia_enovo_view(req)

    def test_preview_com_permissao(self):
        self.usuario.user_permissions.add(self.perm)
        req = self.factory.post("/app/logistica/conferencia-enovo/preview")
        req.user = self.usuario
        req.filial_ativa = self.filial
        req.sisvar_front = {"codigo": QR_VOL1}
        resp = conferencia_enovo_preview_view(req)
        self.assertEqual(resp.status_code, 200)
        payload = json.loads(resp.content)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["leitura"]["trk"], TRK)
