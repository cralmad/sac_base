"""Persistência e serialização da Configuração de Logística e datas de exceção."""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from pages.filial.services import get_filiais_escrita_queryset
from pages.logistica_config.models import ConfiguracaoLogistica, DataExcecaoConfigLogistica
from sac_base.coercion import parse_date, parse_decimal, parse_int


def build_campos_iniciais():
    return {
        "id": None,
        "filial_id": None,
        "pedidos_pesado": "0",
        "pesado_reservado": "0",
        "valor_unitario_pesado": "0.00",
        "pedidos_ligeiro": "0",
        "ligeiro_reservado": "0",
        "valor_unitario_ligeiro": "0.00",
        "valor_excedente": "0.00",
        "excecoes": [],
    }


def _decimal_br(val, default="0") -> Decimal:
    if val is None or val == "":
        val = default
    d = parse_decimal(val, context="form")
    if d is None:
        raise ValidationError("Valor decimal inválido.")
    return d


def _small_int(val, label: str) -> int:
    n = parse_int(val, context="form")
    if n is None or n < 0:
        raise ValidationError(f"{label} inválido.")
    if n > 32767:
        raise ValidationError(f"{label} excede o limite permitido.")
    return n


def serializar_excecoes(config: ConfiguracaoLogistica):
    return [
        {
            "id": ex.id,
            "data": ex.data.isoformat() if ex.data else "",
            "pesado_reservado": str(ex.pesado_reservado),
            "ligeiro_reservado": str(ex.ligeiro_reservado),
        }
        for ex in config.datas_excecao.order_by("data")
    ]


def serializar_config(config: ConfiguracaoLogistica):
    return {
        "id": config.id,
        "filial_id": str(config.filial_id),
        "pedidos_pesado": str(config.pedidos_pesado),
        "pesado_reservado": str(config.pesado_reservado),
        "valor_unitario_pesado": f"{config.valor_unitario_pesado:.2f}",
        "pedidos_ligeiro": str(config.pedidos_ligeiro),
        "ligeiro_reservado": str(config.ligeiro_reservado),
        "valor_unitario_ligeiro": f"{config.valor_unitario_ligeiro:.2f}",
        "valor_excedente": f"{config.valor_excedente:.2f}",
        "excecoes": serializar_excecoes(config),
    }


def _normalizar_payload_excecoes(raw) -> list[dict]:
    if not isinstance(raw, list):
        raise ValidationError("Lista de datas de exceção inválida.")
    vistos = set()
    resultado = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValidationError("Item de exceção inválido.")
        dt = parse_date(item.get("data"))
        if not dt:
            raise ValidationError("Cada exceção deve ter uma data válida.")
        if dt in vistos:
            raise ValidationError("Existem datas duplicadas nas exceções.")
        vistos.add(dt)
        resultado.append(
            {
                "data": dt,
                "pesado_reservado": _small_int(item.get("pesado_reservado"), "Pesado reservado (exceção)"),
                "ligeiro_reservado": _small_int(item.get("ligeiro_reservado"), "Ligeiro reservado (exceção)"),
            }
        )
    resultado.sort(key=lambda x: x["data"])
    return resultado


def persistir_configuracao(usuario, estado: str, campos: dict) -> ConfiguracaoLogistica:
    filial_id = campos.get("filial_id")
    try:
        fid = int(filial_id)
    except (TypeError, ValueError):
        raise ValidationError("Matriz/filial inválida.")

    filial = get_filiais_escrita_queryset(usuario).filter(id=fid).first()
    if not filial:
        raise ValidationError("Matriz/filial inválida ou sem vínculo de escrita.")

    excecoes_norm = _normalizar_payload_excecoes(campos.get("excecoes") or [])

    pedidos_pesado = _small_int(campos.get("pedidos_pesado"), "Pedidos pesado")
    pesado_reservado = _small_int(campos.get("pesado_reservado"), "Pesado reservado")
    pedidos_ligeiro = _small_int(campos.get("pedidos_ligeiro"), "Pedidos ligeiro")
    ligeiro_reservado = _small_int(campos.get("ligeiro_reservado"), "Ligeiro reservado")

    v_pesado = _decimal_br(campos.get("valor_unitario_pesado"))
    v_ligeiro = _decimal_br(campos.get("valor_unitario_ligeiro"))
    v_exc = _decimal_br(campos.get("valor_excedente"))

    with transaction.atomic():
        if estado == "novo":
            if ConfiguracaoLogistica.objects.filter(filial_id=fid).exists():
                raise ValidationError(
                    "Já existe configuração de logística para esta filial. Utilize Pesquisar para editar."
                )
            config = ConfiguracaoLogistica(
                filial=filial,
                pedidos_pesado=pedidos_pesado,
                pesado_reservado=pesado_reservado,
                valor_unitario_pesado=v_pesado,
                pedidos_ligeiro=pedidos_ligeiro,
                ligeiro_reservado=ligeiro_reservado,
                valor_unitario_ligeiro=v_ligeiro,
                valor_excedente=v_exc,
            )
            config.save()
        elif estado == "editar":
            cfg_id = parse_int(campos.get("id"))
            if not cfg_id:
                raise ValidationError("Identificador da configuração inválido.")
            config = (
                ConfiguracaoLogistica.objects.select_for_update()
                .filter(id=cfg_id, filial_id__in=get_filiais_escrita_queryset(usuario).values("id"))
                .first()
            )
            if not config:
                raise ValidationError("Registro não encontrado.")
            if config.filial_id != fid:
                raise ValidationError("Não é permitido alterar a filial da configuração.")
            config.pedidos_pesado = pedidos_pesado
            config.pesado_reservado = pesado_reservado
            config.valor_unitario_pesado = v_pesado
            config.pedidos_ligeiro = pedidos_ligeiro
            config.ligeiro_reservado = ligeiro_reservado
            config.valor_unitario_ligeiro = v_ligeiro
            config.valor_excedente = v_exc
            config.save()
        else:
            raise ValidationError(f"Estado inválido: '{estado}'.")

        DataExcecaoConfigLogistica.objects.filter(configuracao=config).delete()
        DataExcecaoConfigLogistica.objects.bulk_create(
            [
                DataExcecaoConfigLogistica(
                    configuracao=config,
                    data=row["data"],
                    pesado_reservado=row["pesado_reservado"],
                    ligeiro_reservado=row["ligeiro_reservado"],
                )
                for row in excecoes_norm
            ]
        )

    config.refresh_from_db()
    return config


def obter_config_por_id(usuario, config_id: int) -> ConfiguracaoLogistica | None:
    return (
        ConfiguracaoLogistica.objects.filter(
            id=config_id,
            filial_id__in=get_filiais_escrita_queryset(usuario).values("id"),
        )
        .prefetch_related("datas_excecao")
        .first()
    )


def listar_registros_consulta(usuario, filial_cons) -> list[dict]:
    ids = list(get_filiais_escrita_queryset(usuario).values_list("id", flat=True))
    qs = (
        ConfiguracaoLogistica.objects.filter(filial_id__in=ids)
        .select_related("filial")
        .order_by("filial__nome")
    )
    if filial_cons:
        try:
            fc = int(filial_cons)
        except (TypeError, ValueError):
            fc = None
        if fc:
            qs = qs.filter(filial_id=fc)
    return [
        {
            "id": c.id,
            "filial": f"{c.filial.codigo} - {c.filial.nome}",
            "pedidos_pesado": c.pedidos_pesado,
            "pedidos_ligeiro": c.pedidos_ligeiro,
        }
        for c in qs
    ]
