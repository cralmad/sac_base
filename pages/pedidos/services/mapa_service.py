import logging
import time
import unicodedata

import requests as http_requests
from django.db import transaction

from pages.pedidos.models import TentativaEntrega, estado_segue_para_entrega

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_HEADERS = {"User-Agent": "sac-base-mapa/1.0"}
MAX_GEOCODE_POR_REQUISICAO = 12
MAX_GEOCODE_SEGUNDOS = 20

CORES_CARRO = [
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
    "#42d4f4", "#f032e6", "#bfef45", "#fabed4", "#469990",
    "#dcbeff", "#9A6324", "#fffac8", "#800000", "#aaffc3",
    "#808000", "#ffd8b1", "#000075", "#a9a9a9", "#ffffff",
]

_GEOCODING_TIPOS_MUITO_IMPRECISOS = frozenset({
    "postcode", "city", "town", "village", "county",
    "municipality", "state", "country", "region",
})
_GEOCODING_CLASSES_IMPRECISAS = frozenset({"highway", "place"})
_GEOCODING_CLASSES_MUITO_IMPRECISAS = frozenset({"landuse", "boundary", "natural"})
_PALAVRAS_GENERICAS_END = frozenset({
    "rua", "avenida", "av", "travessa", "largo", "praca", "praceta",
    "alameda", "beco", "calcada", "estrada", "est", "lugar", "quinta",
    "lote", "bloco", "andar", "esq", "dto", "dir", "apartamento", "apt",
    "edificio", "edif", "portugal", "loja", "zona", "urbanizacao", "urb",
    "bairro", "s/n", "sem", "numero", "casa", "fracao", "fraccao",
})


def cor_carro(carro):
    if carro is None:
        return "#6c757d"
    try:
        idx = (int(carro) - 1) % len(CORES_CARRO)
        return CORES_CARRO[idx]
    except (ValueError, TypeError):
        return "#6c757d"


def _normalizar_texto(texto):
    nfkd = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _palavras_significativas(texto):
    partes = _normalizar_texto(texto).split()
    return {p for p in partes if len(p) >= 4 and not p.isdigit() and p not in _PALAVRAS_GENERICAS_END}


def determinar_precisao(resultado, codpost_original, cidade_original=None, endereco_original=None):
    tipo = resultado.get("type", "")
    classe = resultado.get("class", "")
    address = resultado.get("address", {})
    display_name_norm = _normalizar_texto(resultado.get("display_name") or "")

    cp_ref = "".join(c for c in (codpost_original or "") if c.isdigit())[:4]
    cp_geo = "".join(c for c in (address.get("postcode") or "") if c.isdigit())[:4]

    road_geo = address.get("road") or address.get("pedestrian") or address.get("path") or ""
    palavras_geo = _palavras_significativas(road_geo)
    palavras_ref = _palavras_significativas(endereco_original or "")
    rua_sem_match = bool(palavras_ref and palavras_geo and not palavras_ref & palavras_geo)

    cidade_ref = _normalizar_texto(cidade_original or "").strip()
    cidade_geo = _normalizar_texto(
        address.get("city") or address.get("town") or address.get("village") or address.get("municipality") or ""
    ).strip()
    cidade_no_display = bool(cidade_ref and cidade_ref in display_name_norm)
    cidade_diverge = bool(
        cidade_ref and not cidade_no_display and cidade_geo and cidade_ref not in cidade_geo and cidade_geo not in cidade_ref
    )

    if cp_geo:
        if cp_ref == cp_geo:
            if tipo in _GEOCODING_TIPOS_MUITO_IMPRECISOS:
                return "impreciso" if palavras_ref else "ok"
            if palavras_ref and not palavras_geo:
                return "impreciso"
            if rua_sem_match:
                return "impreciso"
            return "ok"

        cp_diverge = cp_ref != cp_geo if cp_ref else False
        cp_muito_diverge = cp_diverge and bool(cp_ref) and cp_ref[0] != cp_geo[0]
        if cp_muito_diverge or (cp_diverge and cidade_diverge):
            return "muito_impreciso"
        if cp_diverge or cidade_diverge:
            return "impreciso"
        if classe in _GEOCODING_CLASSES_IMPRECISAS:
            return "impreciso"
        return "ok"

    if tipo in _GEOCODING_TIPOS_MUITO_IMPRECISOS or classe == "boundary":
        return "muito_impreciso"
    if classe in _GEOCODING_CLASSES_MUITO_IMPRECISAS:
        return "muito_impreciso"
    if palavras_ref and not palavras_geo:
        return "impreciso"
    if rua_sem_match:
        return "impreciso"
    if cidade_diverge:
        return "impreciso"
    if classe in _GEOCODING_CLASSES_IMPRECISAS:
        return "impreciso"
    return "ok"


def _score_precisao(precisao):
    if precisao == "ok":
        return 3
    if precisao == "impreciso":
        return 2
    return 1


def _selecionar_melhor_resultado(resultados, codpost, cidade, endereco):
    melhor = None
    melhor_score = -1
    for item in resultados:
        precisao = determinar_precisao(item, codpost, cidade, endereco)
        score = _score_precisao(precisao)
        if score > melhor_score:
            melhor = (item, precisao)
            melhor_score = score
        if score == 3:
            break
    return melhor


def geocodificar(endereco, codpost, cidade):
    consultas = []
    if endereco and cidade:
        consultas.append(f"{endereco}, {cidade}, Portugal")
    if codpost and cidade:
        consultas.append(f"{codpost} {cidade} Portugal")
    if codpost:
        consultas.append(f"{codpost} Portugal")

    for q in consultas:
        time.sleep(1.1)
        try:
            resp = http_requests.get(
                NOMINATIM_URL,
                params={"q": q, "format": "json", "limit": 3, "countrycodes": "pt", "addressdetails": 1},
                headers=NOMINATIM_HEADERS,
                timeout=10,
            )
            resp.raise_for_status()
            resultados = resp.json()
        except http_requests.RequestException as exc:
            logger.warning("Geocoding falhou para '%s': %s", q, exc)
            continue
        except ValueError:
            logger.warning("Geocoding retornou JSON inválido para '%s'", q)
            continue

        if not resultados:
            continue
        melhor = _selecionar_melhor_resultado(resultados, codpost, cidade, endereco)
        if not melhor:
            continue
        r, precision = melhor
        return float(r["lat"]), float(r["lon"]), (r.get("display_name", "") or ""), precision

    return None, None, None, None


def buscar_local_para_pedido(pedido, query):
    try:
        resp = http_requests.get(
            NOMINATIM_URL,
            params={"q": query, "format": "json", "limit": 3, "countrycodes": "pt", "addressdetails": 1},
            headers=NOMINATIM_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        resultados = resp.json()
    except http_requests.RequestException as exc:
        logger.warning("Busca manual Nominatim falhou: %s", exc)
        return None
    except ValueError:
        return None

    if not resultados:
        return None
    melhor = _selecionar_melhor_resultado(resultados, pedido.codpost_dest, pedido.cidade_dest, pedido.endereco_dest)
    if not melhor:
        return None
    r, precision = melhor
    return {
        "lat": float(r["lat"]),
        "lng": float(r["lon"]),
        "geocoding_display": r.get("display_name", "") or "",
        "geocoding_precision": precision,
    }


def montar_payload_mapa(filial, data_tentativa):
    movs = list(
        TentativaEntrega.objects
        .filter(data_tentativa=data_tentativa, pedido__filial=filial)
        .select_related("pedido")
        .order_by("carro", "pedido__codpost_dest")
    )

    pedidos_sem_coord = []
    for mov in movs:
        pedido = mov.pedido
        if pedido is None:
            continue
        if pedido.lat is None or pedido.lng is None:
            pedidos_sem_coord.append(pedido)

    geocoding_falhou = 0
    atualizar = []
    ja_processados = set()
    geocoding_processados = 0
    limite_atingido = False
    geocode_t0 = time.monotonic()
    for pedido in pedidos_sem_coord:
        if geocoding_processados >= MAX_GEOCODE_POR_REQUISICAO:
            limite_atingido = True
            break
        if (time.monotonic() - geocode_t0) >= MAX_GEOCODE_SEGUNDOS:
            limite_atingido = True
            break
        if pedido.id in ja_processados:
            continue
        ja_processados.add(pedido.id)
        geocoding_processados += 1
        lat, lng, display_name, precision = geocodificar(pedido.endereco_dest, pedido.codpost_dest, pedido.cidade_dest)
        if lat is None:
            geocoding_falhou += 1
            continue
        pedido.lat = lat
        pedido.lng = lng
        pedido.geocoding_display = display_name
        pedido.geocoding_precision = precision or ""
        atualizar.append(pedido)

    pendentes_sem_coord = max(0, len(pedidos_sem_coord) - geocoding_processados)
    if atualizar:
        with transaction.atomic():
            type(atualizar[0]).objects.bulk_update(
                atualizar,
                ["lat", "lng", "geocoding_display", "geocoding_precision"],
                batch_size=200,
            )

    movs = list(
        TentativaEntrega.objects
        .filter(data_tentativa=data_tentativa, pedido__filial=filial)
        .select_related("pedido")
        .order_by("carro", "pedido__codpost_dest")
    )
    pedido_ids = {m.pedido_id for m in movs}
    pedidos_com_tentativa_posterior = set()
    if pedido_ids:
        pedidos_com_tentativa_posterior = set(
            TentativaEntrega.objects
            .filter(pedido_id__in=pedido_ids, data_tentativa__gt=data_tentativa, pedido__filial=filial)
            .values_list("pedido_id", flat=True)
            .distinct()
        )

    features = []
    for mov in movs:
        pedido = mov.pedido
        if pedido is None or pedido.lat is None or pedido.lng is None:
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [float(pedido.lng), float(pedido.lat)]},
            "properties": {
                "mov_id": mov.id,
                "pedido_id": pedido.id,
                "referencia": str(pedido.pedido or pedido.id_vonzu),
                "tipo": pedido.tipo or "",
                "endereco": pedido.endereco_dest or "",
                "codpost": pedido.codpost_dest or "",
                "cidade": pedido.cidade_dest or "",
                "volume": pedido.volume,
                "volume_conf": pedido.volume_conf,
                "peso": str(pedido.peso) if pedido.peso is not None else "",
                "obs": pedido.obs or "",
                "obs_rota": pedido.obs_rota or "",
                "carro": mov.carro,
                "periodo": mov.periodo or "",
                "cor": cor_carro(mov.carro),
                "geocoding_display": pedido.geocoding_display or "",
                "geocoding_precision": pedido.geocoding_precision or "",
                "segue_para_entrega": (
                    estado_segue_para_entrega(mov.estado)
                    and (pedido.id not in pedidos_com_tentativa_posterior)
                ),
                "updated_at": mov.updated_at.isoformat(),
            },
        })

    return {
        "geojson": {"type": "FeatureCollection", "features": features},
        "total": len(features),
        "sem_coord": geocoding_falhou + pendentes_sem_coord,
        "pendentes_sem_coord": pendentes_sem_coord,
        "limite_atingido": limite_atingido,
    }
