"""Envio de avaliação por canais (e-mail e/ou SMS) com link curto partilhado."""

from __future__ import annotations

from django.db.models import Q, QuerySet
from django.utils import timezone

from pages.filial.models import FilialConfig
from pages.pedidos.models import AvaliacaoPedido, ESTADOS_ENTREGA_EFETIVAMENTE_CONCLUIDA, Pedido
from pages.pedidos.services.avaliacao_link import garantir_token_para_envio, montar_link_publico
from pages.pedidos.services.sms_relatorio import ddi_padrao_operacao_filial
from sac_base.email_avaliacao_service import (
    enviar_email_avaliacao,
    montar_email_avaliacao,
    render_template_text,
)
from sac_base.sms_service import enviar_sms_bulkgate_resiliente, normalizar_numero

CANAL_EMAIL = "email"
CANAL_SMS = "sms"
CANAIS_VALIDOS = frozenset({CANAL_EMAIL, CANAL_SMS})

PERM_EMAIL = "pedidos.send_email_avaliacao"
PERM_SMS = "pedidos.send_sms_avaliacao"


def pedido_tem_email(pedido) -> bool:
    return bool((pedido.email_dest or "").strip())


def pedido_telefone_sms(pedido) -> str:
    return (pedido.fone_dest or "").strip() or (pedido.fone_dest2 or "").strip()


def pedido_tem_telefone(pedido) -> bool:
    return bool(pedido_telefone_sms(pedido))


def pedido_canais_disponiveis(pedido) -> list[str]:
    canais = []
    if pedido_tem_email(pedido):
        canais.append(CANAL_EMAIL)
    if pedido_tem_telefone(pedido):
        canais.append(CANAL_SMS)
    return canais


def q_pedido_com_contacto() -> Q:
    """Contacto com pelo menos um carácter não-branco (e-mail ou telefone)."""
    return Q(email_dest__regex=r"\S") | Q(fone_dest__regex=r"\S") | Q(fone_dest2__regex=r"\S")


def qs_pedidos_elegiveis_fila(filial, data_ref=None, ids=None) -> QuerySet[Pedido]:
    qs = Pedido.objects.filter(
        filial=filial,
        estado__in=ESTADOS_ENTREGA_EFETIVAMENTE_CONCLUIDA,
    ).filter(q_pedido_com_contacto())
    if data_ref:
        qs = qs.filter(prev_entrega=data_ref)
    if ids is not None:
        qs = qs.filter(id__in=ids)
    return qs


def canais_permitidos_user(user) -> list[str]:
    canais = []
    if user and user.has_perm(PERM_EMAIL):
        canais.append(CANAL_EMAIL)
    if user and user.has_perm(PERM_SMS):
        canais.append(CANAL_SMS)
    return canais


def filtrar_canais_pedidos(canais_pedidos: list[str], canais_user: list[str]) -> list[str]:
    permitidos = set(canais_user)
    out = []
    for c in canais_pedidos:
        if c not in CANAIS_VALIDOS:
            continue
        if c in permitidos and c not in out:
            out.append(c)
    return out


def montar_sms_avaliacao(*, pedido, filial, link_avaliacao: str, config=None) -> tuple[str | None, str | None]:
    """Retorna (mensagem, erro). erro preenchido se template inválido."""
    tpl = (getattr(config, "sms_padrao_avaliacao", "") or "").strip()
    if not tpl:
        return None, "Template SMS de avaliação não configurado na filial."
    if "{link_avaliacao}" not in tpl:
        return None, "Template SMS de avaliação deve conter {link_avaliacao}."
    contexto = {
        "nome": (pedido.nome_dest or "Cliente").strip(),
        "pedido": pedido.pedido or pedido.id_vonzu,
        "filial": getattr(filial, "nome", "SacBase"),
        "link_avaliacao": link_avaliacao,
    }
    return render_template_text(tpl, contexto), None


def enviar_email_pedido_avaliacao(
    *,
    avaliacao: AvaliacaoPedido,
    request=None,
    link: str | None = None,
    config=None,
) -> dict:
    """Envia e-mail. Se `link` for passado, não regenera token (orquestração multi-canal)."""
    pedido = avaliacao.pedido
    if not pedido_tem_email(pedido):
        return {"sucesso": False, "erro": "Pedido sem e-mail do destinatário."}
    if pedido.estado not in ESTADOS_ENTREGA_EFETIVAMENTE_CONCLUIDA:
        return {"sucesso": False, "erro": "Pedido ainda não está concluído para envio de pesquisa."}
    if not avaliacao.selecionado_para_envio:
        return {"sucesso": False, "erro": "Avaliação não está selecionada para envio."}

    if link is None:
        avaliacao = garantir_token_para_envio(avaliacao)
        link = montar_link_publico(request, avaliacao.token_publico)

    filial = pedido.filial
    cfg = config if config is not None else FilialConfig.objects.filter(filial=filial).first()
    assunto, corpo = montar_email_avaliacao(pedido=pedido, filial=filial, link_avaliacao=link, config=cfg)
    nome_remetente = (getattr(cfg, "email_nome_remetente", "") or "").strip() or None

    envio = enviar_email_avaliacao(
        destinatario=pedido.email_dest.strip(),
        assunto=assunto,
        corpo=corpo,
        nome_remetente=nome_remetente,
        link_avaliacao=link,
        nome_cliente=(pedido.nome_dest or "Cliente"),
        filial_nome=getattr(filial, "nome", "SacBase"),
    )

    avaliacao.email_tentativas += 1
    if envio.get("sucesso"):
        avaliacao.email_enviado = True
        avaliacao.email_enviado_em = timezone.now()
    avaliacao.save(update_fields=["email_tentativas", "email_enviado", "email_enviado_em", "updated_at"])
    return envio


def enviar_sms_pedido_avaliacao(
    *,
    avaliacao: AvaliacaoPedido,
    request=None,
    link: str | None = None,
    config=None,
) -> dict:
    pedido = avaliacao.pedido
    telefone = pedido_telefone_sms(pedido)
    if not telefone:
        return {"sucesso": False, "erro": "Pedido sem número de telefone."}
    if pedido.estado not in ESTADOS_ENTREGA_EFETIVAMENTE_CONCLUIDA:
        return {"sucesso": False, "erro": "Pedido ainda não está concluído para envio de pesquisa."}
    if not avaliacao.selecionado_para_envio:
        return {"sucesso": False, "erro": "Avaliação não está selecionada para envio."}

    if link is None:
        avaliacao = garantir_token_para_envio(avaliacao)
        link = montar_link_publico(request, avaliacao.token_publico)

    filial = pedido.filial
    cfg = config if config is not None else FilialConfig.objects.filter(filial=filial).first()
    mensagem, erro_tpl = montar_sms_avaliacao(pedido=pedido, filial=filial, link_avaliacao=link, config=cfg)
    if erro_tpl:
        return {"sucesso": False, "erro": erro_tpl}

    ddi = ddi_padrao_operacao_filial(filial)
    if not normalizar_numero(telefone, ddi):
        return {"sucesso": False, "erro": f"Número inválido: {telefone!r}"}

    envio = enviar_sms_bulkgate_resiliente(telefone, mensagem, ddi_padrao=ddi)

    avaliacao.sms_tentativas += 1
    update_fields = ["sms_tentativas", "updated_at"]
    if envio.get("sucesso"):
        avaliacao.sms_enviado = True
        avaliacao.sms_enviado_em = timezone.now()
        update_fields.extend(["sms_enviado", "sms_enviado_em"])
    avaliacao.save(update_fields=update_fields)
    return envio


def enviar_avaliacao_canais(*, avaliacao: AvaliacaoPedido, canais: list[str], request=None) -> dict:
    """
    Orquestra envio nos canais já filtrados pela view.
    Retorno: { status_linha, canais: [{canal, status, motivo?}], ... }
    """
    pedido = avaliacao.pedido
    referencia = pedido.pedido or str(getattr(pedido, "id_vonzu", pedido.pk))

    if avaliacao.respondido_em:
        return {
            "status_linha": "ignorado",
            "referencia": referencia,
            "canais": [],
            "motivo": "Avaliação já respondida.",
        }
    if not avaliacao.selecionado_para_envio:
        return {
            "status_linha": "ignorado",
            "referencia": referencia,
            "canais": [],
            "motivo": "Avaliação não está selecionada para envio.",
        }

    avaliacao = garantir_token_para_envio(avaliacao)
    link = montar_link_publico(request, avaliacao.token_publico)
    cfg = FilialConfig.objects.filter(filial=pedido.filial).first()

    detalhes_canais = []
    for canal in canais:
        if canal == CANAL_EMAIL:
            if not pedido_tem_email(pedido):
                detalhes_canais.append(
                    {"canal": CANAL_EMAIL, "status": "ignorado", "motivo": "Pedido sem e-mail."}
                )
                continue
            ret = enviar_email_pedido_avaliacao(
                avaliacao=avaliacao, request=request, link=link, config=cfg
            )
            if ret.get("sucesso"):
                detalhes_canais.append({"canal": CANAL_EMAIL, "status": "enviado"})
            else:
                detalhes_canais.append(
                    {
                        "canal": CANAL_EMAIL,
                        "status": "falha",
                        "motivo": ret.get("erro") or "Falha no envio de e-mail.",
                    }
                )
        elif canal == CANAL_SMS:
            if not pedido_tem_telefone(pedido):
                detalhes_canais.append(
                    {"canal": CANAL_SMS, "status": "ignorado", "motivo": "Pedido sem telefone."}
                )
                continue
            ret = enviar_sms_pedido_avaliacao(
                avaliacao=avaliacao, request=request, link=link, config=cfg
            )
            if ret.get("sucesso"):
                detalhes_canais.append({"canal": CANAL_SMS, "status": "enviado"})
            else:
                detalhes_canais.append(
                    {
                        "canal": CANAL_SMS,
                        "status": "falha",
                        "motivo": ret.get("erro") or "Falha no envio de SMS.",
                    }
                )

    tem_enviado = any(d["status"] == "enviado" for d in detalhes_canais)
    tem_falha = any(d["status"] == "falha" for d in detalhes_canais)
    if tem_enviado and not tem_falha:
        status_linha = "enviado"
    elif tem_falha and not tem_enviado:
        status_linha = "falha"
    elif tem_enviado and tem_falha:
        status_linha = "parcial"
    else:
        status_linha = "ignorado"

    return {
        "status_linha": status_linha,
        "referencia": referencia,
        "canais": detalhes_canais,
    }
