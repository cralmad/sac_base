import logging
from datetime import datetime

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger(__name__)


ASSUNTO_PADRAO = "Como foi a sua entrega do pedido {pedido}?"
CORPO_PADRAO = (
    "Esperamos que esteja bem.\n"
    "Gostaríamos de solicitar a vossa colaboração no preenchimento do formulário abaixo, "
    "relativo à avaliação do serviço de transporte referente ao pedido {pedido}.\n"
    "Reforçamos o pedido para que, ao realizar a avaliação, considere exclusivamente os serviços "
    "prestados pela nossa equipe de transporte (como pontualidade, postura do motorista e manuseio da carga), "
    "distinguindo-os de outras etapas do processo logístico.\n"
    "A sua opinião é fundamental para mantermos o padrão de qualidade no atendimento aos nossos parceiros.\n"
    "Agradecemos antecipadamente pela sua colaboração."
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


def _sanitize_corpo_for_html(corpo: str, link_avaliacao: str | None) -> str:
    linhas = [ln.strip() for ln in (corpo or "").splitlines()]
    limpas = []
    saudacao_removida = False
    for ln in linhas:
        if not ln:
            limpas.append("")
            continue
        if link_avaliacao and ln == link_avaliacao:
            # O link será apresentado no botão e no fallback do rodapé.
            continue
        if not saudacao_removida and ln.lower().startswith("olá"):
            # Evita duplicar saudação quando o template já começa com "Olá ...".
            saudacao_removida = True
            continue
        limpas.append(ln)
    return "\n".join(limpas).strip()


def _build_email_html(*, nome_cliente: str, filial_nome: str, corpo: str, link_avaliacao: str | None) -> str:
    corpo_limpo = _sanitize_corpo_for_html(corpo, link_avaliacao)
    corpo_html = (corpo_limpo or "").replace("\n", "<br>")
    cta = ""
    if link_avaliacao:
        cta = (
            f'<p style="margin:20px 0;">'
            f'<a href="{link_avaliacao}" '
            f'style="display:inline-block;background:#198754;color:#ffffff;text-decoration:none;'
            f'padding:12px 18px;border-radius:8px;font-weight:600;">Responder avaliação</a></p>'
        )
    return (
        "<!doctype html><html><body style='margin:0;padding:0;background:#f5f7fb;'>"
        "<div style='max-width:640px;margin:24px auto;background:#ffffff;border:1px solid #e9ecef;border-radius:10px;'>"
        "<div style='padding:18px 22px;border-bottom:1px solid #e9ecef;'>"
        f"<h2 style='margin:0;font-size:20px;color:#1f2937;'>Pesquisa de Satisfação</h2>"
        "</div>"
        "<div style='padding:22px;'>"
        f"<p style='margin:0 0 12px;color:#374151;'>Olá <strong>{nome_cliente}</strong>,</p>"
        f"<p style='margin:0 0 12px;color:#374151;'>{corpo_html}</p>"
        f"{cta}"
        "<p style='margin:16px 0 0;color:#6b7280;font-size:13px;'>"
        "Se o botão não funcionar, copie e cole o link no navegador:</p>"
        f"<p style='margin:6px 0 0;word-break:break-all;color:#2563eb;font-size:13px;'>{link_avaliacao or ''}</p>"
        f"<p style='margin:18px 0 0;color:#374151;'>Obrigado,<br><strong>{filial_nome}</strong></p>"
        "</div></div></body></html>"
    )


def enviar_email_avaliacao(
    *,
    destinatario: str,
    assunto: str,
    corpo: str,
    nome_remetente: str | None = None,
    link_avaliacao: str | None = None,
    nome_cliente: str = "Cliente",
    filial_nome: str = "SacBase",
) -> dict:
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
        html = _build_email_html(
            nome_cliente=nome_cliente,
            filial_nome=filial_nome,
            corpo=corpo,
            link_avaliacao=link_avaliacao,
        )
        msg.attach_alternative(html, "text/html")
        msg.send(fail_silently=False)
        return {"sucesso": True}
    except Exception as exc:
        logger.exception("Falha ao enviar e-mail de avaliação para %s", destinatario)
        return {"sucesso": False, "erro": str(exc)}
