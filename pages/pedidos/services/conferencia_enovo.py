"""Conferência de etiquetas QR ENOVO (filial activa)."""

from __future__ import annotations

import logging
from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo

from django.db import DatabaseError, IntegrityError, transaction

from pages.pedidos.models import (
    Pedido,
    TentativaEntrega,
    conferencia_volumes_padrao,
    parse_qr_etiqueta_enovo,
)

LISBON_TZ = ZoneInfo("Europe/Lisbon")
logger = logging.getLogger(__name__)


def _hoje_lisboa_ddmmaaaa() -> str:
    return datetime.now(LISBON_TZ).date().strftime("%d/%m/%Y")


def _volumes_em_conferido(conferido) -> set[int]:
    vols = set()
    if not isinstance(conferido, dict):
        return vols
    for item in conferido.values():
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        try:
            vols.add(int(item[1]))
        except (TypeError, ValueError):
            continue
    return vols


def _proxima_chave_conf(conferido: dict) -> str:
    numeros = []
    for chave in conferido:
        if not str(chave).startswith("conf_"):
            continue
        sufixo = str(chave).split("_", 1)[-1]
        try:
            numeros.append(int(sufixo))
        except (TypeError, ValueError):
            continue
    return f"conf_{max(numeros, default=0) + 1}"


def _normalizar_json(pedido: Pedido) -> dict:
    dados = pedido.conferencia_volumes
    if not isinstance(dados, dict):
        dados = conferencia_volumes_padrao()
    else:
        dados = deepcopy(dados)
        for chave, valor in conferencia_volumes_padrao().items():
            dados.setdefault(chave, valor)
        if not isinstance(dados.get("conferido"), dict):
            dados["conferido"] = {}
    return dados


def resolver_carro(pedido: Pedido):
    """Tentativa mais recente com carro preenchido; None se não houver."""
    mov = (
        TentativaEntrega.objects.filter(pedido_id=pedido.pk)
        .filter(carro__isnull=False)
        .exclude(carro=0)
        .order_by("-data_tentativa", "-id")
        .only("carro")
        .first()
    )
    if mov is None:
        return None
    return int(mov.carro)


def _qs_pedido_filial(filial, id_vonzu: int):
    return Pedido.objects.filter(filial_id=filial.pk, id_vonzu=id_vonzu)


def preview_leitura_etiqueta(filial, codigo) -> tuple[dict | None, str | None]:
    parsed = parse_qr_etiqueta_enovo(codigo)
    if not parsed:
        return None, "Código da etiqueta inválido. Espere 18 dígitos (TRK + total + volume)."

    pedido = _qs_pedido_filial(filial, parsed["TRK"]).first()
    if not pedido:
        return None, (
            f"Pedido TRK {parsed['TRK']} não encontrado nesta filial."
        )

    dados = _normalizar_json(pedido)
    if parsed["volume"] in _volumes_em_conferido(dados.get("conferido")):
        return None, (
            f"Volume {parsed['volume']} do TRK {parsed['TRK']} já foi conferido."
        )

    carro = resolver_carro(pedido)
    prev = pedido.prev_entrega.isoformat() if pedido.prev_entrega else ""
    return {
        "codigo": "".join(str(codigo or "").split()),
        "pedido_id": pedido.id,
        "trk": parsed["TRK"],
        "referencia": pedido.pedido or "",
        "volume": parsed["volume"],
        "total_volume": parsed["total_volume"],
        "prev_entrega": prev,
        "carro": carro,
        "sem_carro": carro is None,
    }, None


def _aplicar_volume_no_pedido(pedido: Pedido, parsed: dict, data_str: str) -> None:
    dados = _normalizar_json(pedido)
    conferido = dados["conferido"]
    if parsed["volume"] in _volumes_em_conferido(conferido):
        raise ValueError(
            f"Volume {parsed['volume']} do TRK {parsed['TRK']} já foi conferido."
        )
    if dados.get("TRK") is None:
        dados["TRK"] = parsed["TRK"]
    if not dados.get("total_volume"):
        dados["total_volume"] = parsed["total_volume"]
    conferido[_proxima_chave_conf(conferido)] = [data_str, parsed["volume"]]
    dados["total_vol_conferido"] = len(_volumes_em_conferido(conferido))
    pedido.conferencia_volumes = dados
    pedido.volume_conf = dados["total_vol_conferido"]


def aplicar_leituras_lote(filial, leituras) -> dict:
    """Aplica cada código; transacção por linha. Retorna gravados e erros."""
    if not isinstance(leituras, list) or not leituras:
        return {
            "gravados": [],
            "erros": [{"codigo": "", "mensagem": "Nenhuma leitura para gravar."}],
            "todos_ok": False,
        }

    data_str = _hoje_lisboa_ddmmaaaa()
    gravados = []
    erros = []
    vistos_lote = set()

    for item in leituras:
        codigo = item.get("codigo") if isinstance(item, dict) else None
        parsed = parse_qr_etiqueta_enovo(codigo)
        if not parsed:
            erros.append({
                "codigo": str(codigo or ""),
                "trk": None,
                "volume": None,
                "mensagem": "Código da etiqueta inválido.",
            })
            continue

        chave = (parsed["TRK"], parsed["volume"])
        if chave in vistos_lote:
            erros.append({
                "codigo": "".join(str(codigo or "").split()),
                "trk": parsed["TRK"],
                "volume": parsed["volume"],
                "mensagem": "Volume duplicado neste lote.",
            })
            continue
        vistos_lote.add(chave)

        try:
            with transaction.atomic():
                pedido = (
                    _qs_pedido_filial(filial, parsed["TRK"])
                    .select_for_update()
                    .first()
                )
                if not pedido:
                    raise ValueError(
                        f"Pedido TRK {parsed['TRK']} não encontrado nesta filial."
                    )
                _aplicar_volume_no_pedido(pedido, parsed, data_str)
                pedido.save(update_fields=["conferencia_volumes", "volume_conf"])
        except ValueError as exc:
            erros.append({
                "codigo": "".join(str(codigo or "").split()),
                "trk": parsed["TRK"],
                "volume": parsed["volume"],
                "mensagem": str(exc),
            })
        except (IntegrityError, DatabaseError) as exc:
            logger.error(exc, exc_info=True)
            erros.append({
                "codigo": "".join(str(codigo or "").split()),
                "trk": parsed["TRK"],
                "volume": parsed["volume"],
                "mensagem": "Não foi possível gravar esta leitura. Tente novamente.",
            })
        else:
            gravados.append({
                "codigo": "".join(str(codigo or "").split()),
                "trk": parsed["TRK"],
                "volume": parsed["volume"],
            })

    return {
        "gravados": gravados,
        "erros": erros,
        "todos_ok": bool(gravados) and not erros,
    }
