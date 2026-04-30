import logging
from datetime import datetime

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger(__name__)


ASSUNTO_PADRAO = "Como foi a sua entrega do pedido {pedido}?"
CORPO_PADRAO = (
    "Olá {nome},\n\n"
    "A sua opinião é importante para melhorarmos nosso serviço.\n"
    "Por favor, responda a pesquisa de satisfação do pedido {pedido}:\n"
    "{link_avaliacao}\n\n"
    "Obrigado,\n"
    "{filial}"
)


def render_template_text(template: str, contexto: dict) -> str:
    if not template:
        return ""
    try:
        return template.format(**contexto)
    except Exception:
        # Fallback seguro para não bloquear disparos por placeholders inválidos.
        return template


def montar_email_avaliacao(*, pedido, filial, link_avaliacao: str, config=None) -> tuple[str, str]:
    assunto_tpl = (getattr(config, "email_template_assunto", "") or "").strip() or ASSUNTO_PADRAO
    corpo_tpl = (getattr(config, "email_template_corpo", "") or "").strip() or CORPO_PADRAO
    contexto = {
        "nome": (pedido.nome_dest or "Cliente").strip(),
        "pedido": pedido.pedido or pedido.id_vonzu,
        "filial": getattr(filial, "nome", "SacBase"),
        "link_avaliacao": link_avaliacao,
        "data": datetime.now().strftime("%d/%m/%Y"),
    }
    assunto = render_template_text(assunto_tpl, contexto)
    corpo = render_template_text(corpo_tpl, contexto)
    return assunto, corpo


def enviar_email_avaliacao(*, destinatario: str, assunto: str, corpo: str, nome_remetente: str | None = None) -> dict:
    if not destinatario:
        return {"sucesso": False, "erro": "Destinatário vazio."}

    from_email = settings.DEFAULT_FROM_EMAIL
    if nome_remetente:
        from_email = f"{nome_remetente} <{settings.DEFAULT_FROM_EMAIL}>"

    try:
        msg = EmailMultiAlternatives(
            subject=f"{settings.EMAIL_SUBJECT_PREFIX}{assunto}",
            body=corpo,
            from_email=from_email,
            to=[destinatario],
        )
        msg.send(fail_silently=False)
        return {"sucesso": True}
    except Exception as exc:
        logger.exception("Falha ao enviar e-mail de avaliação para %s", destinatario)
        return {"sucesso": False, "erro": str(exc)}
