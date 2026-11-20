"""Tokens opacos e URL curta /a/<token>/ da avaliação pública."""

import json
from datetime import date

from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from io import StringIO

from pages.core.models import Pais
from pages.filial.models import Filial
from pages.pedidos.models import AvaliacaoPedido, Pedido
from pages.pedidos.services.avaliacao_link import (
    TOKEN_MAX_LEN_CURTO,
    gerar_token_opaco,
    garantir_token_para_envio,
    montar_link_publico,
    resolver_avaliacao_por_token,
    token_precisa_upgrade,
)


JWT_FAKE = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJhdmFsaWFjYW9faWQiOjEsImV4cCI6OTk5OTk5OTk5OX0."
    "dGVzdGUtc2lnbmF0dXJlLXNlbS12YWxvci1yZWFs"
)


class AvaliacaoLinkServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pais = Pais.objects.create(nome="PT-AVL", sigla="PT", codigo_tel="+351")
        cls.filial = Filial.objects.create(
            codigo="AVL01",
            nome="FIL AVL",
            pais_atuacao=cls.pais,
            is_matriz=True,
        )

    def _pedido(self, id_vonzu: int) -> Pedido:
        now = timezone.now()
        return Pedido.objects.create(
            filial=self.filial,
            id_vonzu=id_vonzu,
            pedido=f"P-{id_vonzu}",
            tipo="ENTREGA",
            criado=now,
            atualizacao=now,
            prev_entrega=date(2026, 6, 10),
            estado="completed",
        )

    def test_gerar_token_opaco_curto_e_unico_heuristica(self):
        t1 = gerar_token_opaco()
        t2 = gerar_token_opaco()
        self.assertLessEqual(len(t1), TOKEN_MAX_LEN_CURTO)
        self.assertNotEqual(t1, t2)
        self.assertFalse(token_precisa_upgrade(t1))
        self.assertTrue(token_precisa_upgrade(None))
        self.assertTrue(token_precisa_upgrade(""))
        self.assertTrue(token_precisa_upgrade(JWT_FAKE))

    def test_resolver_por_token(self):
        pedido = self._pedido(501)
        av = AvaliacaoPedido.objects.create(pedido=pedido, token_publico="abcTOKEN12xy")
        found = resolver_avaliacao_por_token("abcTOKEN12xy")
        self.assertEqual(found.id, av.id)

    @override_settings(
        PUBLIC_BASE_URL="https://app.exemplo.pt",
        APP_BASE_URL="https://app.exemplo.pt",
    )
    def test_upgrade_jwt_e_montar_link_curto(self):
        pedido = self._pedido(502)
        av = AvaliacaoPedido.objects.create(pedido=pedido, token_publico=JWT_FAKE)
        jwt_antigo = av.token_publico

        av = garantir_token_para_envio(av)
        self.assertNotEqual(av.token_publico, jwt_antigo)
        self.assertFalse(token_precisa_upgrade(av.token_publico))
        self.assertLessEqual(len(av.token_publico), TOKEN_MAX_LEN_CURTO)

        link = montar_link_publico(None, av.token_publico)
        self.assertIn("/a/", link)
        self.assertTrue(link.startswith("https://app.exemplo.pt/a/"))
        self.assertLessEqual(len(av.token_publico), TOKEN_MAX_LEN_CURTO)

        with self.assertRaises(AvaliacaoPedido.DoesNotExist):
            resolver_avaliacao_por_token(jwt_antigo)

    def test_compat_jwt_na_rota_longa_sem_upgrade(self):
        pedido = self._pedido(503)
        AvaliacaoPedido.objects.create(
            pedido=pedido,
            token_publico=JWT_FAKE,
            link_ativo=True,
        )
        client = Client()
        resp = client.get(f"/app/logistica/avaliacao/{JWT_FAKE}/")
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "invalido")

    def test_get_rota_curta_e_token_invalido(self):
        pedido = self._pedido(504)
        av = AvaliacaoPedido.objects.create(pedido=pedido, token_publico="shortTok12ab")
        client = Client()
        ok = client.get(f"/a/{av.token_publico}/")
        self.assertEqual(ok.status_code, 200)

        bad = client.get("/a/naoexiste999/")
        self.assertEqual(bad.status_code, 200)
        self.assertContains(bad, "Link inválido")

    def test_post_enviar_rota_curta(self):
        pedido = self._pedido(505)
        av = AvaliacaoPedido.objects.create(pedido=pedido, token_publico="postTok12xyz")
        client = Client()
        payload = {
            "p1": "Sim",
            "p2": "Sim",
            "p3": 5,
            "p4": 4,
            "p5": "Sim",
            "p6": 3,
            "p7": "Sim",
            "p8": "Sim",
            "p9": 5,
            "p10": "Sim",
        }
        resp = client.post(
            f"/a/{av.token_publico}/enviar",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body.get("success"))
        av.refresh_from_db()
        self.assertFalse(av.link_ativo)
        self.assertIsNotNone(av.respondido_em)

    def test_comando_default_nao_toca_email_enviado(self):
        p1 = self._pedido(601)
        p2 = self._pedido(602)
        nao_enviado = AvaliacaoPedido.objects.create(
            pedido=p1, token_publico=JWT_FAKE, email_enviado=False, link_ativo=True
        )
        enviado = AvaliacaoPedido.objects.create(
            pedido=p2,
            token_publico=JWT_FAKE + "x",
            email_enviado=True,
            link_ativo=True,
        )
        out = StringIO()
        call_command("regenerar_tokens_avaliacao_curtos", stdout=out)
        nao_enviado.refresh_from_db()
        enviado.refresh_from_db()
        self.assertFalse(token_precisa_upgrade(nao_enviado.token_publico))
        self.assertTrue(token_precisa_upgrade(enviado.token_publico))

    def test_comando_force_invalida_jwt_enviado(self):
        pedido = self._pedido(603)
        av = AvaliacaoPedido.objects.create(
            pedido=pedido,
            token_publico=JWT_FAKE,
            email_enviado=True,
            link_ativo=True,
        )
        antigo = av.token_publico
        call_command("regenerar_tokens_avaliacao_curtos", force=True)
        av.refresh_from_db()
        self.assertNotEqual(av.token_publico, antigo)
        self.assertFalse(token_precisa_upgrade(av.token_publico))
        with self.assertRaises(AvaliacaoPedido.DoesNotExist):
            resolver_avaliacao_por_token(antigo)
