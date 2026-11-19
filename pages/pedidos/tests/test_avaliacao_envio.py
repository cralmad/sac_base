"""Fila e envio multi-canal de avaliação (e-mail / SMS)."""

import json
import uuid
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from pages.core.models import Pais
from pages.filial.models import Filial, FilialConfig
from pages.pedidos.models import AvaliacaoPedido, Pedido
from pages.pedidos.services.avaliacao_envio import (
    canais_permitidos_user,
    enviar_avaliacao_canais,
    filtrar_canais_pedidos,
    montar_sms_avaliacao,
    qs_pedidos_elegiveis_fila,
)
from pages.pedidos.views_avaliacao import (
    relatorio_avaliacao_enviar_lote_view,
    relatorio_avaliacao_enviar_view,
)


User = get_user_model()


class AvaliacaoEnvioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pais = Pais.objects.create(nome="PT-AVE", sigla="PT", codigo_tel="+351")
        cls.filial = Filial.objects.create(
            codigo="AVE01",
            nome="FIL AVE",
            pais_atuacao=cls.pais,
            is_matriz=True,
        )
        FilialConfig.objects.create(
            filial=cls.filial,
            sms_padrao_avaliacao="Ola {nome}, avalie {pedido}: {link_avaliacao}",
        )

    def _pedido(self, id_vonzu: int, **kwargs) -> Pedido:
        now = timezone.now()
        defaults = dict(
            filial=self.filial,
            id_vonzu=id_vonzu,
            pedido=f"P-{id_vonzu}",
            tipo="ENTREGA",
            criado=now,
            atualizacao=now,
            prev_entrega=date(2026, 6, 10),
            estado="completed",
            nome_dest="Cliente Teste",
        )
        defaults.update(kwargs)
        return Pedido.objects.create(**defaults)

    def _user_com_perms(self, *codenames):
        user = User.objects.create_user(
            username=f"u_{'_'.join(codenames)}_{uuid.uuid4().hex[:8]}",
            password="x",
        )
        for code in codenames:
            perm = Permission.objects.get(codename=code)
            user.user_permissions.add(perm)
        return user

    def test_fila_inclui_so_telefone_exclui_sem_contacto(self):
        so_tel = self._pedido(701, fone_dest="912345678", email_dest="")
        so_email = self._pedido(702, email_dest="a@b.com", fone_dest="")
        sem = self._pedido(703, email_dest="", fone_dest="", fone_dest2="")
        so_espacos = self._pedido(704, email_dest="   ", fone_dest="  ", fone_dest2="")
        qs = qs_pedidos_elegiveis_fila(self.filial, data_ref=date(2026, 6, 10))
        ids = set(qs.values_list("id", flat=True))
        self.assertIn(so_tel.id, ids)
        self.assertIn(so_email.id, ids)
        self.assertNotIn(sem.id, ids)
        self.assertNotIn(so_espacos.id, ids)

    def test_montar_sms_exige_link_placeholder(self):
        pedido = self._pedido(710, fone_dest="912345678")
        cfg = self.filial.config
        cfg.sms_padrao_avaliacao = "Sem link"
        cfg.save()
        msg, err = montar_sms_avaliacao(
            pedido=pedido, filial=self.filial, link_avaliacao="https://x/a/abc/", config=cfg
        )
        self.assertIsNone(msg)
        self.assertIn("link_avaliacao", err or "")

        cfg.sms_padrao_avaliacao = ""
        cfg.save()
        msg2, err2 = montar_sms_avaliacao(
            pedido=pedido, filial=self.filial, link_avaliacao="https://x/a/abc/", config=cfg
        )
        self.assertIsNone(msg2)
        self.assertIn("não configurado", err2 or "")

    @override_settings(APP_BASE_URL="https://app.exemplo.pt")
    @patch("pages.pedidos.services.avaliacao_envio.enviar_sms_bulkgate_resiliente")
    def test_envio_sms_marca_flag_e_usa_link_curto(self, mock_sms):
        mock_sms.return_value = {"sucesso": True, "sms_id": "1"}
        pedido = self._pedido(720, fone_dest="912345678", email_dest="")
        av = AvaliacaoPedido.objects.create(pedido=pedido, selecionado_para_envio=True)
        out = enviar_avaliacao_canais(avaliacao=av, canais=["sms"], request=None)
        self.assertEqual(out["status_linha"], "enviado")
        av.refresh_from_db()
        self.assertTrue(av.sms_enviado)
        self.assertTrue(av.token_publico)
        args, _kwargs = mock_sms.call_args
        mensagem = args[1]
        self.assertIn("/a/", mensagem)
        self.assertIn(av.token_publico, mensagem)

    @override_settings(APP_BASE_URL="https://app.exemplo.pt")
    @patch("pages.pedidos.services.avaliacao_envio.enviar_email_avaliacao")
    @patch("pages.pedidos.services.avaliacao_envio.enviar_sms_bulkgate_resiliente")
    def test_lote_ambos_sms_ignorado_sem_telefone(self, mock_sms, mock_email):
        mock_email.return_value = {"sucesso": True}
        pedido = self._pedido(730, email_dest="a@b.com", fone_dest="", fone_dest2="")
        av = AvaliacaoPedido.objects.create(pedido=pedido, selecionado_para_envio=True)
        out = enviar_avaliacao_canais(avaliacao=av, canais=["email", "sms"], request=None)
        self.assertEqual(out["status_linha"], "enviado")
        canais = {d["canal"]: d["status"] for d in out["canais"]}
        self.assertEqual(canais["email"], "enviado")
        self.assertEqual(canais["sms"], "ignorado")
        mock_sms.assert_not_called()

    @override_settings(APP_BASE_URL="https://app.exemplo.pt")
    @patch("pages.pedidos.services.avaliacao_envio.enviar_email_avaliacao")
    def test_template_sms_vazio_falha_email_ok(self, mock_email):
        mock_email.return_value = {"sucesso": True}
        self.filial.config.sms_padrao_avaliacao = ""
        self.filial.config.save()
        pedido = self._pedido(740, email_dest="a@b.com", fone_dest="912345678")
        av = AvaliacaoPedido.objects.create(pedido=pedido, selecionado_para_envio=True)
        out = enviar_avaliacao_canais(avaliacao=av, canais=["email", "sms"], request=None)
        self.assertEqual(out["status_linha"], "parcial")
        by_canal = {d["canal"]: d for d in out["canais"]}
        self.assertEqual(by_canal["email"]["status"], "enviado")
        self.assertEqual(by_canal["sms"]["status"], "falha")

    def test_views_auth_uniao_permissoes(self):
        pedido = self._pedido(750, fone_dest="912345678", email_dest="a@b.com")
        av = AvaliacaoPedido.objects.create(pedido=pedido, selecionado_para_envio=True)
        factory = RequestFactory()

        user0 = self._user_com_perms("view_relatorio_avaliacao")
        self.assertEqual(canais_permitidos_user(user0), [])
        self.assertEqual(filtrar_canais_pedidos(["sms"], canais_permitidos_user(user0)), [])

        req0 = factory.post(
            f"/app/logistica/relatorio_avaliacao/{av.id}/enviar",
            data='{"canal":"sms"}',
            content_type="application/json",
        )
        req0.user = user0
        req0.filial_ativa = self.filial
        resp0 = relatorio_avaliacao_enviar_view(req0, av.id)
        self.assertEqual(resp0.status_code, 403)

        user_sms = self._user_com_perms("view_relatorio_avaliacao", "send_sms_avaliacao")
        self.assertEqual(canais_permitidos_user(user_sms), ["sms"])
        user_email = self._user_com_perms("view_relatorio_avaliacao", "send_email_avaliacao")
        self.assertEqual(
            filtrar_canais_pedidos(["email", "sms"], canais_permitidos_user(user_email)),
            ["email"],
        )

        req_sms = factory.post(
            f"/app/logistica/relatorio_avaliacao/{av.id}/enviar",
            data='{"canal":"sms"}',
            content_type="application/json",
        )
        req_sms.user = user_sms
        req_sms.filial_ativa = self.filial
        with patch("pages.pedidos.services.avaliacao_envio.enviar_sms_bulkgate_resiliente") as mock_sms:
            mock_sms.return_value = {"sucesso": True, "sms_id": "x"}
            resp_sms = relatorio_avaliacao_enviar_view(req_sms, av.id)
        self.assertEqual(resp_sms.status_code, 200)
        body = json.loads(resp_sms.content.decode())
        self.assertTrue(body.get("success"))

        req_sem_filial = factory.post(
            f"/app/logistica/relatorio_avaliacao/{av.id}/enviar",
            data='{"canal":"sms"}',
            content_type="application/json",
        )
        req_sem_filial.user = user_sms
        req_sem_filial.filial_ativa = None
        resp_sem_filial = relatorio_avaliacao_enviar_view(req_sem_filial, av.id)
        self.assertEqual(resp_sem_filial.status_code, 403)

        user_email_only = self._user_com_perms("view_relatorio_avaliacao", "send_email_avaliacao")
        req_lote = factory.post(
            "/app/logistica/relatorio_avaliacao/enviar-lote",
            data=json.dumps({"ids": [av.id], "canais": ["sms"]}),
            content_type="application/json",
        )
        req_lote.user = user_email_only
        req_lote.filial_ativa = self.filial
        resp_lote = relatorio_avaliacao_enviar_lote_view(req_lote)
        self.assertEqual(resp_lote.status_code, 403)

        req_lote_bad = factory.post(
            "/app/logistica/relatorio_avaliacao/enviar-lote",
            data=json.dumps({"ids": [av.id], "canais": []}),
            content_type="application/json",
        )
        req_lote_bad.user = user_sms
        req_lote_bad.filial_ativa = self.filial
        resp_bad = relatorio_avaliacao_enviar_lote_view(req_lote_bad)
        self.assertEqual(resp_bad.status_code, 400)

    @override_settings(APP_BASE_URL="https://app.exemplo.pt")
    @patch("pages.pedidos.services.avaliacao_envio.enviar_sms_bulkgate_resiliente")
    def test_sem_contacto_sms_ignorado(self, mock_sms):
        pedido = self._pedido(760, email_dest="a@b.com", fone_dest="", fone_dest2="")
        av = AvaliacaoPedido.objects.create(pedido=pedido, selecionado_para_envio=True)
        out = enviar_avaliacao_canais(avaliacao=av, canais=["sms"], request=None)
        self.assertEqual(out["status_linha"], "ignorado")
        self.assertEqual(out["canais"][0]["status"], "ignorado")
        mock_sms.assert_not_called()
