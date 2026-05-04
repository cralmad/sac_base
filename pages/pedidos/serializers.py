"""Serialização de pedidos e agregados para respostas JSON SisVar."""

from django.utils import timezone


def _dt_to_local_input(dt):
    if not dt:
        return ""
    local = timezone.localtime(dt)
    return local.strftime("%Y-%m-%dT%H:%M")


def serialize_pedido_form(pedido):
    return {
        "id": pedido.id,
        "filial_id": pedido.filial_id,
        "origem": pedido.origem,
        "id_vonzu": pedido.id_vonzu,
        "pedido": pedido.pedido or "",
        "tipo": pedido.tipo,
        "criado": _dt_to_local_input(pedido.criado),
        "atualizacao": _dt_to_local_input(pedido.atualizacao),
        "prev_entrega": pedido.prev_entrega.isoformat() if pedido.prev_entrega else "",
        "dt_entrega": pedido.dt_entrega.isoformat() if pedido.dt_entrega else "",
        "estado": pedido.estado or "",
        "volume": pedido.volume,
        "volume_conf": pedido.volume_conf,
        "nome_dest": pedido.nome_dest or "",
        "email_dest": pedido.email_dest or "",
        "fone_dest": pedido.fone_dest or "",
        "fone_dest2": pedido.fone_dest2 or "",
        "endereco_dest": pedido.endereco_dest or "",
        "codpost_dest": pedido.codpost_dest or "",
        "cidade_dest": pedido.cidade_dest or "",
        "obs": pedido.obs or "",
        "obs_rota": pedido.obs_rota or "",
        "cliente_id": pedido.cliente_id,
        "motorista_id": pedido.motorista_id,
        "peso": str(pedido.peso) if pedido.peso is not None else "",
        "expresso": pedido.expresso,
    }


def serialize_tentativa(reg):
    return {
        "id": reg.id,
        "pedido_id": reg.pedido_id,
        "data_tentativa": reg.data_tentativa.isoformat() if reg.data_tentativa else "",
        "estado": reg.estado or "",
        "carro": reg.carro,
        "motorista_id": reg.motorista_id,
        "motorista_nome": reg.motorista.nome if reg.motorista_id else "",
        "periodo": reg.periodo or "",
        "faturado": reg.faturado,
        "interno": reg.interno,
        "dt_entrega": reg.dt_entrega.isoformat() if reg.dt_entrega else "",
    }


def serialize_devolucao(reg):
    fotos_publicas = [
        {"id": f["id"], "url": f["url"], "thumb_url": f.get("thumb_url", f["url"])}
        for f in (reg.fotos or [])
    ]
    return {
        "id": reg.id,
        "pedido_id": reg.pedido_id,
        "data": reg.data.isoformat() if reg.data else "",
        "palete": reg.palete,
        "volume": reg.volume,
        "motivo": reg.motivo or "",
        "obs": reg.obs or "",
        "fotos": fotos_publicas,
        "fotos_count": len(fotos_publicas),
    }


def serialize_incidencia(reg):
    fotos_publicas = [
        {"id": f["id"], "url": f["url"], "thumb_url": f.get("thumb_url", f["url"])}
        for f in (reg.fotos or [])
    ]
    return {
        "id": reg.id,
        "pedido_id": reg.pedido_id,
        "data": reg.data.isoformat() if reg.data else "",
        "origem": reg.origem or "",
        "tipo": reg.tipo or "",
        "artigo": reg.artigo or "",
        "valor": str(reg.valor) if reg.valor is not None else "",
        "motorista_id": reg.motorista_id,
        "motorista_nome": reg.motorista.nome if reg.motorista_id else "",
        "obs": reg.obs or "",
        "fotos": fotos_publicas,
        "fotos_count": len(fotos_publicas),
    }


def serialize_avaliacao(pedido):
    avaliacao = getattr(pedido, "avaliacao", None)
    if not avaliacao:
        return None
    return {
        "id": avaliacao.id,
        "link_ativo": avaliacao.link_ativo,
        "email_enviado": avaliacao.email_enviado,
        "email_enviado_em": avaliacao.email_enviado_em.isoformat() if avaliacao.email_enviado_em else "",
        "email_tentativas": avaliacao.email_tentativas,
        "respondido_em": avaliacao.respondido_em.isoformat() if avaliacao.respondido_em else "",
        "p1_entrega_no_prazo": avaliacao.p1_entrega_no_prazo or "",
        "p2_aviso_antes_chegada": avaliacao.p2_aviso_antes_chegada or "",
        "p3_educacao_simpatia": avaliacao.p3_educacao_simpatia,
        "p4_cuidado_encomenda": avaliacao.p4_cuidado_encomenda,
        "p5_equipa_identificada": avaliacao.p5_equipa_identificada or "",
        "p6_facilidade_processo": avaliacao.p6_facilidade_processo,
        "p7_veiculo_limpo": avaliacao.p7_veiculo_limpo or "",
        "p8_esclareceu_duvidas": avaliacao.p8_esclareceu_duvidas or "",
        "p9_satisfacao_geral": avaliacao.p9_satisfacao_geral,
        "p10_recomendaria": avaliacao.p10_recomendaria or "",
        "comentario": avaliacao.comentario or "",
    }


def build_pedido_extra_payload(pedido):
    return {
        "registros_mov": [
            serialize_tentativa(t)
            for t in pedido.tentativas.select_related("motorista").order_by("-data_tentativa", "-id")
        ],
        "registros_dev": [
            serialize_devolucao(d) for d in pedido.devolucoes.order_by("-data", "-id")
        ],
        "registros_inc": [
            serialize_incidencia(i)
            for i in pedido.incidencias.select_related("motorista").order_by("-data", "-id")
        ],
        "avaliacao": serialize_avaliacao(pedido),
    }
