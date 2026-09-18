"""Pesquisa na inbox Gmail global (IMAP) e devolve o primeiro anexo PDF/imagem.

Credenciais: `GMAIL_IMAP_USER` / `GMAIL_IMAP_PASSWORD`, com fallback para
`EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` (mesmo payload `EMAIL_AUTO`).
"""
from __future__ import annotations

import email
import imaplib
import logging
import re
from dataclasses import dataclass
from email.header import decode_header, make_header
from email.message import Message

from django.conf import settings

from pages.pedidos.models import Pedido

logger = logging.getLogger(__name__)

MAX_ANEXO_BYTES = 15 * 1024 * 1024
MIMES_PERMITIDOS = frozenset(
    {
        "application/pdf",
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/gif",
        "image/webp",
    }
)
MIME_GENERICO = frozenset({"application/octet-stream", "application/x-download"})
EXT_POR_MIME = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}
MIME_POR_EXT = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
CHARS_NOME_INVALIDOS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class ImapNaoConfigurado(Exception):
    """Utilizador/palavra-passe IMAP em falta."""


@dataclass(frozen=True)
class AnexoGmailResultado:
    ok: bool
    codigo: str
    mensagem: str
    http_status: int
    conteudo: bytes | None = None
    content_type: str = ""
    filename: str = ""


def _falha(codigo: str, mensagem: str, http_status: int) -> AnexoGmailResultado:
    return AnexoGmailResultado(
        ok=False, codigo=codigo, mensagem=mensagem, http_status=http_status
    )


def _pedido_da_filial_com_referencia(filial, referencia: str) -> Pedido | None:
    ref = (referencia or "").strip()
    if not ref:
        return None
    qs = Pedido.objects.filter(filial=filial)
    hit = qs.filter(pedido=ref).first()
    if hit:
        return hit
    if ref.isdigit():
        return qs.filter(id_vonzu=int(ref)).first()
    return None


def _escapar_query_gmail(referencia: str) -> str:
    return referencia.replace("\\", " ").replace('"', " ").strip()


def montar_query_assunto(referencia: str) -> str:
    termo = _escapar_query_gmail(referencia)
    if re.search(r"[\s(){}]", termo):
        return f'has:attachment subject:"{termo}"'
    return f"has:attachment subject:{termo}"


def _search_x_gm_raw(client, query: str):
    """X-GM-RAW via literal IMAP — evita aspas escapadas que o Gmail rejeita (BAD parse)."""
    client.literal = query.encode("utf-8")
    return client.search("UTF-8", "X-GM-RAW")


def _ids_pesquisa(client, referencia: str) -> list[bytes]:
    query = montar_query_assunto(referencia)
    termo = _escapar_query_gmail(referencia)
    data = None
    try:
        status, data = _search_x_gm_raw(client, query)
    except imaplib.IMAP4.error:
        status = "NO"
    if status != "OK" or not data or not data[0]:
        try:
            status, data = client.search(None, "SUBJECT", termo)
        except imaplib.IMAP4.error:
            return []
    if status != "OK" or not data or not data[0]:
        return []
    return data[0].split()


def _extensao_nome(nome: str) -> str:
    orig = (nome or "").strip()
    if "." not in orig:
        return ""
    ext = "." + orig.rsplit(".", 1)[-1].lower()
    if not re.fullmatch(r"\.[a-z0-9]{1,8}", ext):
        return ""
    return ext


def sanitizar_nome_ficheiro(referencia: str, mime: str, nome_original: str = "") -> str:
    base = CHARS_NOME_INVALIDOS.sub("_", (referencia or "").strip()) or "anexo"
    ext = _extensao_nome(nome_original)
    if not ext:
        ext = EXT_POR_MIME.get((mime or "").lower(), "")
    if not ext:
        ext = ".bin"
    return f"{base}{ext}"


def _mime_resposta(mime: str, nome_original: str) -> str:
    mime_l = (mime or "").lower()
    if mime_l == "image/jpg":
        return "image/jpeg"
    if mime_l in MIMES_PERMITIDOS:
        return mime_l
    return MIME_POR_EXT.get(_extensao_nome(nome_original), mime_l or "application/octet-stream")


def _nome_anexo(part: Message) -> str:
    raw = part.get_filename() or ""
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(raw)))
    except (LookupError, UnicodeError, ValueError):
        return raw


def _anexo_permitido(mime: str, nome: str) -> bool:
    mime_l = (mime or "").lower()
    if mime_l in MIMES_PERMITIDOS:
        return True
    if mime_l in MIME_GENERICO:
        return _extensao_nome(nome) in MIME_POR_EXT
    return False


def credenciais_imap() -> tuple[str, str]:
    user = (
        getattr(settings, "GMAIL_IMAP_USER", "")
        or getattr(settings, "EMAIL_HOST_USER", "")
        or ""
    ).strip()
    password = (
        getattr(settings, "GMAIL_IMAP_PASSWORD", "")
        or getattr(settings, "EMAIL_HOST_PASSWORD", "")
        or ""
    ).strip()
    return user, password


def _conectar_imap():
    user, password = credenciais_imap()
    if not user or not password:
        raise ImapNaoConfigurado("IMAP Gmail não configurado.")
    host = getattr(settings, "GMAIL_IMAP_HOST", "imap.gmail.com")
    port = int(getattr(settings, "GMAIL_IMAP_PORT", 993))
    timeout = int(getattr(settings, "EMAIL_TIMEOUT", 20))
    client = imaplib.IMAP4_SSL(host, port, timeout=timeout)
    client.login(user, password)
    client.select("INBOX", readonly=True)
    return client


def _fechar_imap(client) -> None:
    if client is None:
        return
    try:
        client.close()
    except (imaplib.IMAP4.error, OSError):
        pass
    try:
        client.logout()
    except (imaplib.IMAP4.error, OSError):
        pass


def _bytes_rfc822(raw) -> bytes | None:
    if not raw:
        return None
    for item in raw:
        if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], (bytes, bytearray)):
            return bytes(item[1])
    return None


def _escolher_parte_anexo(msg: Message) -> Message | None:
    anexos: list[Message] = []
    com_nome: list[Message] = []
    for part in msg.walk():
        mime = (part.get_content_type() or "").lower()
        nome = _nome_anexo(part)
        if not _anexo_permitido(mime, nome):
            continue
        disp = (part.get_content_disposition() or "").lower()
        if disp == "attachment":
            anexos.append(part)
        elif nome:
            com_nome.append(part)
    if anexos:
        return anexos[0]
    if com_nome:
        return com_nome[0]
    return None


def _extrair_anexo(ref: str, parte: Message) -> AnexoGmailResultado | None:
    mime = (parte.get_content_type() or "application/octet-stream").lower()
    filename_orig = _nome_anexo(parte)
    conteudo = parte.get_payload(decode=True) or b""
    if not conteudo:
        return None
    if len(conteudo) > MAX_ANEXO_BYTES:
        return _falha(
            "anexo_grande",
            "O anexo excede o tamanho máximo permitido.",
            400,
        )
    content_type = _mime_resposta(mime, filename_orig)
    filename = sanitizar_nome_ficheiro(ref, content_type, filename_orig)
    return AnexoGmailResultado(
        ok=True,
        codigo="ok",
        mensagem="",
        http_status=200,
        conteudo=conteudo,
        content_type=content_type,
        filename=filename,
    )


def obter_anexo_gmail_gerencial(filial, referencia: str) -> AnexoGmailResultado:
    ref = (referencia or "").strip()
    if not ref:
        return _falha("referencia_invalida", "A referência é obrigatória.", 400)

    if _pedido_da_filial_com_referencia(filial, ref) is None:
        return _falha(
            "referencia_nao_encontrada",
            "Referência não encontrada nesta filial.",
            404,
        )

    client = None
    try:
        client = _conectar_imap()
        ids = _ids_pesquisa(client, ref)
        if not ids:
            return _falha(
                "sem_email",
                "Nenhum e-mail com anexo encontrado para esta referência no assunto.",
                404,
            )

        viu_mensagem = False
        for msg_id in reversed(ids):
            status, raw = client.fetch(msg_id, "(RFC822)")
            payload = _bytes_rfc822(raw) if status == "OK" else None
            if not payload:
                continue
            viu_mensagem = True
            msg = email.message_from_bytes(payload)
            parte = _escolher_parte_anexo(msg)
            if parte is None:
                continue
            extraido = _extrair_anexo(ref, parte)
            if extraido is None:
                continue
            return extraido

        if viu_mensagem:
            return _falha(
                "sem_anexo_permitido",
                "O e-mail encontrado não tem anexo PDF ou imagem.",
                404,
            )
        return _falha(
            "sem_email",
            "Nenhum e-mail com anexo encontrado para esta referência no assunto.",
            404,
        )
    except ImapNaoConfigurado:
        return _falha(
            "gmail_nao_configurado",
            "Inbox Gmail global não está configurada (utilizador e palavra-passe IMAP).",
            400,
        )
    except (imaplib.IMAP4.error, OSError, TimeoutError):
        logger.error("Falha IMAP ao obter anexo do relatório gerencial.", exc_info=True)
        return _falha(
            "erro_api",
            "Não foi possível consultar o Gmail. Tente novamente mais tarde.",
            502,
        )
    finally:
        _fechar_imap(client)
