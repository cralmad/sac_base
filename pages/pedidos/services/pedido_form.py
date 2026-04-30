"""Persistência do cadastro de pedido (formulário SisVar)."""

import logging

from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone

from pages.filial.services import get_filiais_escrita_queryset
from pages.pedidos.models import Pedido
from sac_base.coercion import parse_date, parse_datetime, parse_decimal, parse_int
from sac_base.sisvar_builders import build_error_payload

logger = logging.getLogger(__name__)

TRAVAS_IMPORTADOS = {
    "filial_id",
    "origem",
    "id_vonzu",
    "pedido",
    "tipo",
    "criado",
    "cliente_id",
}


def persistir_pedido_cadastro(usuario, estado_form, campos, filial):
    """
    Retorna (pedido, None) em sucesso ou (None, (payload, status_code))
    para uso em JsonResponse(*args).
    """
    def fail(msg, status=400):
        return None, (build_error_payload(msg), status)

    try:
        with transaction.atomic():
            if estado_form == "novo":
                pedido = Pedido(filial=filial)
                origem = "MANUAL"
            elif estado_form == "editar":
                pedido = Pedido.objects.filter(
                    id=campos.get("id"),
                    filial_id__in=list(
                        get_filiais_escrita_queryset(usuario).values_list("id", flat=True)
                    ),
                ).first()
                if not pedido:
                    return fail("Pedido não encontrado.", 404)
                origem = pedido.origem
            else:
                return fail("Estado inválido.", 400)

            parsed = {
                "filial_id": filial.id,
                "origem": "MANUAL" if estado_form == "novo" else origem,
                "id_vonzu": parse_int(campos.get("id_vonzu")),
                "pedido": (campos.get("pedido") or "").strip() or None,
                "tipo": (campos.get("tipo") or "ENTREGA").strip(),
                "criado": parse_datetime(campos.get("criado")) or timezone.now(),
                "atualizacao": parse_datetime(campos.get("atualizacao")) or timezone.now(),
                "prev_entrega": parse_date(campos.get("prev_entrega")),
                "dt_entrega": parse_date(campos.get("dt_entrega")),
                "estado": (campos.get("estado") or "").strip() or None,
                "volume": parse_int(campos.get("volume")),
                "volume_conf": parse_int(campos.get("volume_conf")) or 0,
                "nome_dest": (campos.get("nome_dest") or "").strip() or None,
                "email_dest": (campos.get("email_dest") or "").strip() or None,
                "fone_dest": (campos.get("fone_dest") or "").strip() or None,
                "fone_dest2": (campos.get("fone_dest2") or "").strip() or None,
                "endereco_dest": (campos.get("endereco_dest") or "").strip() or None,
                "codpost_dest": (campos.get("codpost_dest") or "").strip() or None,
                "cidade_dest": (campos.get("cidade_dest") or "").strip() or None,
                "obs": (campos.get("obs") or "").strip() or None,
                "obs_rota": (campos.get("obs_rota") or "").strip() or None,
                "cliente_id": parse_int(campos.get("cliente_id")),
                "motorista_id": parse_int(campos.get("motorista_id")),
                "peso": parse_decimal(campos.get("peso")),
                "expresso": bool(campos.get("expresso", False)),
            }

            if estado_form == "editar" and pedido.origem == "IMPORTADO":
                for chave in TRAVAS_IMPORTADOS:
                    parsed[chave] = getattr(pedido, chave)

            if parsed["id_vonzu"] is None:
                return fail("ID Vonzu é obrigatório e numérico.", 400)

            for campo, valor in parsed.items():
                setattr(pedido, campo, valor)

            pedido.save()
    except (ValidationError, IntegrityError, DatabaseError):
        logger.exception("persistir_pedido_cadastro")
        return fail(
            "Não foi possível salvar o pedido. Verifique os dados.",
            422,
        )

    return pedido, None


def apply_prev_entrega_range_filters(qs, campos):
    """
    Aplica filtros prev_entrega_ini / prev_entrega_fim quando informados.
    Retorna (qs_atualizado, lista_de_erros). Erros não vazia: entrada inválida.
    """
    erros = []
    if campos.get("prev_entrega_ini"):
        d_ini = parse_date(campos["prev_entrega_ini"])
        if d_ini is None:
            erros.append("Data inicial de pré-entrega inválida (use AAAA-MM-DD).")
        else:
            qs = qs.filter(prev_entrega__gte=d_ini)
    if campos.get("prev_entrega_fim"):
        d_fim = parse_date(campos["prev_entrega_fim"])
        if d_fim is None:
            erros.append("Data final de pré-entrega inválida (use AAAA-MM-DD).")
        else:
            qs = qs.filter(prev_entrega__lte=d_fim)
    return qs, erros
