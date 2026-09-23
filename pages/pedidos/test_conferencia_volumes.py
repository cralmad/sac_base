from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from pages.core.models import Pais
from pages.filial.models import Filial, UsuarioFilial

from .models import Pedido, parse_qr_etiqueta_enovo
from .serializers import serialize_pedido_form
from .services.pedido_form import persistir_pedido_cadastro

User = get_user_model()


class ParseQrEtiquetaEnovoTests(TestCase):
    def test_parseia_trk_volume_e_total_sem_zeros_a_esquerda(self):
        self.assertEqual(
            parse_qr_etiqueta_enovo("008007108629003001"),
            {"TRK": 8007108629, "total_volume": 3, "volume": 1},
        )

    def test_rejeita_tamanho_ou_nao_numerico(self):
        self.assertIsNone(parse_qr_etiqueta_enovo(""))
        self.assertIsNone(parse_qr_etiqueta_enovo("8007108629003001"))
        self.assertIsNone(parse_qr_etiqueta_enovo("00800710862900300A"))

    def test_rejeita_volume_maior_que_total(self):
        self.assertIsNone(parse_qr_etiqueta_enovo("008007108629001003"))


class ConferenciaVolumesCadastroTests(TestCase):
    def setUp(self):
        self.pais = Pais.objects.create(nome="PORTUGAL", sigla="PRT", codigo_tel="+351")
        self.filial = Filial.objects.create(
            codigo="MAT", nome="MATRIZ", pais_atuacao=self.pais, is_matriz=True
        )
        self.usuario = User.objects.create_user(username="op_conf", password="x")
        UsuarioFilial.objects.create(
            usuario=self.usuario,
            filial=self.filial,
            ativo=True,
            pode_consultar=True,
            pode_escrever=True,
        )

    def test_novo_pedido_inicializa_json_com_trk_e_total_volume(self):
        agora = timezone.now().strftime("%Y-%m-%dT%H:%M")
        pedido, err = persistir_pedido_cadastro(
            self.usuario,
            "novo",
            {
                "id_vonzu": "8007108629",
                "tipo": "ENTREGA",
                "criado": agora,
                "atualizacao": agora,
                "volume": "3",
            },
            self.filial,
        )
        self.assertIsNone(err)
        self.assertEqual(
            pedido.conferencia_volumes,
            {
                "TRK": 8007108629,
                "total_volume": 3,
                "total_vol_conferido": 0,
                "conferido": {},
            },
        )

    def test_editar_preserva_conferido_e_ignora_payload_do_form(self):
        agora = timezone.now()
        pedido = Pedido.objects.create(
            filial=self.filial,
            origem="MANUAL",
            id_vonzu=8007108629,
            tipo="ENTREGA",
            criado=agora,
            atualizacao=agora,
            volume=3,
            conferencia_volumes={
                "TRK": 8007108629,
                "total_volume": 3,
                "total_vol_conferido": 2,
                "conferido": {
                    "conf_1": ["25/08/2026", 1],
                    "conf_2": ["25/08/2026", 3],
                },
            },
        )
        pedido_salvo, err = persistir_pedido_cadastro(
            self.usuario,
            "editar",
            {
                "id": pedido.id,
                "id_vonzu": "8007108629",
                "tipo": "ENTREGA",
                "volume": "3",
                "conferencia_volumes": {"TRK": 1, "conferido": {}},
            },
            self.filial,
        )
        self.assertIsNone(err)
        pedido_salvo.refresh_from_db()
        self.assertEqual(pedido_salvo.conferencia_volumes["total_vol_conferido"], 2)
        self.assertEqual(
            pedido_salvo.conferencia_volumes["conferido"]["conf_2"],
            ["25/08/2026", 3],
        )

    def test_editar_preserva_motivo_incidencia_mesmo_com_payload(self):
        agora = timezone.now()
        pedido = Pedido.objects.create(
            filial=self.filial,
            origem="IMPORTADO",
            id_vonzu=8007108630,
            tipo="ENTREGA",
            criado=agora,
            atualizacao=agora,
            estado="Incidência",
            motivo_incidencia="Fora da zona",
        )
        pedido_salvo, err = persistir_pedido_cadastro(
            self.usuario,
            "editar",
            {
                "id": pedido.id,
                "id_vonzu": "8007108630",
                "tipo": "ENTREGA",
                "estado": "Incidência",
                "motivo_incidencia": "tentativa de alteração",
            },
            self.filial,
        )
        self.assertIsNone(err)
        pedido_salvo.refresh_from_db()
        self.assertEqual(pedido_salvo.motivo_incidencia, "Fora da zona")

    def test_serialize_inclui_json(self):
        agora = timezone.now()
        pedido = Pedido.objects.create(
            filial=self.filial,
            origem="MANUAL",
            id_vonzu=8007108629,
            tipo="ENTREGA",
            criado=agora,
            atualizacao=agora,
        )
        dados = serialize_pedido_form(pedido)
        self.assertIn("conferencia_volumes", dados)
        self.assertEqual(dados["conferencia_volumes"]["TRK"], 8007108629)
        self.assertEqual(dados["motivo_incidencia"], "")
