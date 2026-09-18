"""Testes do anexo Gmail no Relatório Gerencial (IMAP mockado)."""

from __future__ import annotations

import imaplib
from datetime import date
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.utils import timezone

from pages.core.models import Pais
from pages.filial.models import Filial, FilialConfig
from pages.pedidos.models import Pedido
from pages.pedidos.services.gmail_anexo_gerencial import (
    montar_query_assunto,
    obter_anexo_gmail_gerencial,
    sanitizar_nome_ficheiro,
)


def _msg_com_anexo(maintype: str, subtype: str, filename: str, payload: bytes) -> bytes:
    msg = EmailMessage()
    msg["Subject"] = "REF-OK"
    msg["From"] = "origem@example.com"
    msg.set_content("corpo")
    msg.add_attachment(payload, maintype=maintype, subtype=subtype, filename=filename)
    return msg.as_bytes()


def _imap_fake(ids: bytes, rfc822: bytes | None = None) -> MagicMock:
    client = MagicMock()
    client.search.return_value = ("OK", [ids])
    if rfc822 is not None:
        client.fetch.return_value = ("OK", [(b"1 (RFC822)", rfc822)])
    else:
        client.fetch.return_value = ("OK", [])
    return client


class GmailAnexoGerencialTests(TestCase):
    dt = date(2026, 5, 1)

    def setUp(self):
        self.pais = Pais.objects.create(nome="PT-GM", sigla="PT", codigo_tel="+351")
        self.filial = Filial.objects.create(
            codigo="GM1", nome="FIL GM 1", pais_atuacao=self.pais, is_matriz=True
        )
        FilialConfig.objects.create(filial=self.filial)
        self.filial_b = Filial.objects.create(
            codigo="GM2", nome="FIL GM 2", pais_atuacao=self.pais, is_matriz=False
        )
        FilialConfig.objects.create(filial=self.filial_b)

    def _pedido(self, id_vonzu: int, filial=None, pedido_ref: str | None = "REF-001") -> Pedido:
        filial = filial or self.filial
        now = timezone.now()
        return Pedido.objects.create(
            filial=filial,
            id_vonzu=id_vonzu,
            pedido=pedido_ref,
            tipo="ENTREGA",
            criado=now,
            atualizacao=now,
            prev_entrega=self.dt,
        )

    def test_montar_query_assunto(self):
        self.assertEqual(
            montar_query_assunto("REF-001"),
            "has:attachment subject:REF-001",
        )
        self.assertEqual(
            montar_query_assunto('ABC"123'),
            'has:attachment subject:"ABC 123"',
        )

    def test_sanitizar_nome_ficheiro(self):
        self.assertEqual(
            sanitizar_nome_ficheiro("REF/001", "application/pdf", "x.pdf"),
            "REF_001.pdf",
        )

    def test_referencia_vazia(self):
        r = obter_anexo_gmail_gerencial(self.filial, "  ")
        self.assertFalse(r.ok)
        self.assertEqual(r.codigo, "referencia_invalida")

    def test_referencia_outra_filial_nao_chama_imap(self):
        self._pedido(90001, filial=self.filial_b, pedido_ref="REF-B")
        with patch(
            "pages.pedidos.services.gmail_anexo_gerencial._conectar_imap"
        ) as conectar:
            r = obter_anexo_gmail_gerencial(self.filial, "REF-B")
        self.assertFalse(r.ok)
        self.assertEqual(r.codigo, "referencia_nao_encontrada")
        conectar.assert_not_called()

    @override_settings(GMAIL_IMAP_USER="", GMAIL_IMAP_PASSWORD="", EMAIL_HOST_USER="", EMAIL_HOST_PASSWORD="")
    def test_gmail_nao_configurado(self):
        self._pedido(90002, pedido_ref="REF-CFG")
        r = obter_anexo_gmail_gerencial(self.filial, "REF-CFG")
        self.assertFalse(r.ok)
        self.assertEqual(r.codigo, "gmail_nao_configurado")

    def test_sem_email(self):
        self._pedido(90003, pedido_ref="REF-MISS")
        client = _imap_fake(b"")
        with patch(
            "pages.pedidos.services.gmail_anexo_gerencial._conectar_imap",
            return_value=client,
        ):
            r = obter_anexo_gmail_gerencial(self.filial, "REF-MISS")
        self.assertEqual(r.codigo, "sem_email")
        self.assertEqual(r.http_status, 404)

    def test_sem_anexo_permitido(self):
        self._pedido(90004, pedido_ref="REF-ZIP")
        raw = _msg_com_anexo("application", "zip", "x.zip", b"PK\x03\x04")
        client = _imap_fake(b"1", raw)
        with patch(
            "pages.pedidos.services.gmail_anexo_gerencial._conectar_imap",
            return_value=client,
        ):
            r = obter_anexo_gmail_gerencial(self.filial, "REF-ZIP")
        self.assertEqual(r.codigo, "sem_anexo_permitido")

    def test_sucesso_pdf(self):
        self._pedido(90005, pedido_ref="REF-OK")
        pdf = b"%PDF-1.4 fake"
        raw = _msg_com_anexo("application", "pdf", "nota.pdf", pdf)
        client = _imap_fake(b"1 2", raw)
        with patch(
            "pages.pedidos.services.gmail_anexo_gerencial._conectar_imap",
            return_value=client,
        ):
            r = obter_anexo_gmail_gerencial(self.filial, "REF-OK")
        self.assertTrue(r.ok)
        self.assertEqual(r.conteudo, pdf)
        self.assertEqual(r.filename, "REF-OK.pdf")
        self.assertEqual(r.content_type, "application/pdf")
        client.fetch.assert_called_once()
        self.assertEqual(client.fetch.call_args[0][0], b"2")

    def test_ignora_zip_mais_recente_e_usa_pdf(self):
        self._pedido(90008, pedido_ref="REF-MIX")
        pdf = b"%PDF-1.4 ok"
        zip_raw = _msg_com_anexo("application", "zip", "x.zip", b"PK\x03\x04")
        pdf_raw = _msg_com_anexo("application", "pdf", "n.pdf", pdf)
        client = MagicMock()
        client.search.return_value = ("OK", [b"1 2"])
        client.fetch.side_effect = [
            ("OK", [(b"2 (RFC822)", zip_raw)]),
            ("OK", [(b"1 (RFC822)", pdf_raw)]),
        ]
        with patch(
            "pages.pedidos.services.gmail_anexo_gerencial._conectar_imap",
            return_value=client,
        ):
            r = obter_anexo_gmail_gerencial(self.filial, "REF-MIX")
        self.assertTrue(r.ok)
        self.assertEqual(r.conteudo, pdf)
        self.assertEqual(client.fetch.call_count, 2)

    def test_octet_stream_com_extensao_pdf(self):
        self._pedido(90009, pedido_ref="REF-OCT")
        pdf = b"%PDF-octet"
        raw = _msg_com_anexo("application", "octet-stream", "doc.pdf", pdf)
        client = _imap_fake(b"1", raw)
        with patch(
            "pages.pedidos.services.gmail_anexo_gerencial._conectar_imap",
            return_value=client,
        ):
            r = obter_anexo_gmail_gerencial(self.filial, "REF-OCT")
        self.assertTrue(r.ok)
        self.assertEqual(r.conteudo, pdf)
        self.assertEqual(r.content_type, "application/pdf")
        self.assertEqual(r.filename, "REF-OCT.pdf")

    def test_x_gm_raw_bad_cai_para_subject(self):
        self._pedido(90010, pedido_ref="REF-BAD")
        pdf = b"%PDF-fb"
        raw = _msg_com_anexo("application", "pdf", "n.pdf", pdf)
        client = MagicMock()
        client.search.side_effect = [
            imaplib.IMAP4.error("SEARCH command error: BAD"),
            ("OK", [b"1"]),
        ]
        client.fetch.return_value = ("OK", [(b"1 (RFC822)", raw)])
        with patch(
            "pages.pedidos.services.gmail_anexo_gerencial._conectar_imap",
            return_value=client,
        ):
            r = obter_anexo_gmail_gerencial(self.filial, "REF-BAD")
        self.assertTrue(r.ok)
        self.assertEqual(r.conteudo, pdf)
        self.assertEqual(client.search.call_count, 2)

    def test_fallback_id_vonzu_sem_campo_pedido(self):
        self._pedido(90006, pedido_ref=None)
        client = _imap_fake(b"")
        with patch(
            "pages.pedidos.services.gmail_anexo_gerencial._conectar_imap",
            return_value=client,
        ):
            r = obter_anexo_gmail_gerencial(self.filial, "90006")
        self.assertEqual(r.codigo, "sem_email")

    def test_erro_imap(self):
        self._pedido(90007, pedido_ref="REF-API")
        with patch(
            "pages.pedidos.services.gmail_anexo_gerencial._conectar_imap",
            side_effect=imaplib.IMAP4.error("auth"),
        ):
            r = obter_anexo_gmail_gerencial(self.filial, "REF-API")
        self.assertEqual(r.codigo, "erro_api")
        self.assertEqual(r.http_status, 502)
