import logging
import math
import time
import unicodedata

import requests as http_requests
from django.db import transaction

from pages.pedidos.models import Devolucao, TentativaEntrega, estado_segue_para_entrega

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_HEADERS = {"User-Agent": "sac-base-mapa/1.0"}
OSRM_ROUTE_URL = "https://router.project-osrm.org/route/v1/driving"
NOMINATIM_MIN_INTERVAL_SECONDS = 1.1
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


def _cp_quatro_digitos(codpost):
    return "".join(c for c in (codpost or "") if c.isdigit())[:4]


_MAX_AREA_CP_MEMO = 128
_AREA_CP_MEMO = {}
_ULTIMA_CHAMADA_NOMINATIM_MONO = 0.0


def _throttle_nominatim():
    """Limita taxa de requests ao Nominatim sem impor sleep fixo desnecessário."""
    global _ULTIMA_CHAMADA_NOMINATIM_MONO
    agora = time.monotonic()
    delta = agora - _ULTIMA_CHAMADA_NOMINATIM_MONO
    if _ULTIMA_CHAMADA_NOMINATIM_MONO > 0 and delta < NOMINATIM_MIN_INTERVAL_SECONDS:
        time.sleep(NOMINATIM_MIN_INTERVAL_SECONDS - delta)
    _ULTIMA_CHAMADA_NOMINATIM_MONO = time.monotonic()


def _buscar_area_referencia_codigo_postal(codpost_limpo):
    """Área administrativa oficial do CP em PT (sem cidade), via Nominatim estruturado."""
    cp = (codpost_limpo or "").strip()
    if len(_cp_quatro_digitos(cp)) < 4:
        return None
    try:
        resp = http_requests.get(
            NOMINATIM_URL,
            params={
                "postalcode": cp,
                "countrycodes": "pt",
                "format": "json",
                "limit": 1,
                "addressdetails": 1,
            },
            headers=NOMINATIM_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        js = resp.json()
    except (http_requests.RequestException, ValueError):
        return None
    if not js:
        return None
    addr = js[0].get("address") or {}
    if not addr:
        return None
    return {
        "county": (addr.get("county") or "").strip(),
        "town": (addr.get("town") or addr.get("village") or "").strip(),
        "iso3166_2": (addr.get("ISO3166-2-lvl6") or "").strip().upper(),
    }


def _obter_area_referencia_cp(codpost_limpo):
    cp = (codpost_limpo or "").strip()
    if len(_cp_quatro_digitos(cp)) < 4:
        return None
    if cp in _AREA_CP_MEMO:
        return _AREA_CP_MEMO[cp]
    _throttle_nominatim()
    area = _buscar_area_referencia_codigo_postal(cp)
    if len(_AREA_CP_MEMO) >= _MAX_AREA_CP_MEMO:
        _AREA_CP_MEMO.clear()
    _AREA_CP_MEMO[cp] = area
    return area


def _resultado_incoerente_area_do_cp(resultado, area_ref):
    """
    True se distrito/concelho (ISO3166-2 ou county) do resultado Nominatim
    difere da área onde o código postal está oficialmente localizado.
    Cobre casos em que o hit não traz postcode em address mas o ponto está noutro distrito.
    """
    if not area_ref or not any(area_ref.values()):
        return False
    addr = resultado.get("address") or {}
    ref_iso = (area_ref.get("iso3166_2") or "").strip().upper()
    res_iso = (addr.get("ISO3166-2-lvl6") or "").strip().upper()
    if ref_iso and res_iso and ref_iso != res_iso:
        return True
    ref_co = _normalizar_texto(area_ref.get("county") or "")
    res_co = _normalizar_texto(addr.get("county") or "")
    if ref_co and res_co and ref_co != res_co:
        return True
    return False


def _ajustar_precisao_coerencia_area_cp(precisao, resultado, area_ref):
    if not area_ref or precisao == "muito_impreciso":
        return precisao
    if _resultado_incoerente_area_do_cp(resultado, area_ref):
        return "muito_impreciso"
    return precisao


def _rescue_deve_ignorar_candidato(resultado, precision, codpost_limpo, area_ref):
    """No resgate, não fixar ponto claramente incoerente com o CP ou com a área do CP."""
    if precision != "muito_impreciso":
        return False
    if _resultado_cp_diverge_referencia(resultado, codpost_limpo):
        return True
    if area_ref and _resultado_incoerente_area_do_cp(resultado, area_ref):
        return True
    return False


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


def determinar_precisao(
    resultado,
    codpost_original,
    cidade_original=None,
    endereco_original=None,
    *,
    modo_rescue=False,
):
    tipo = resultado.get("type", "")
    classe = resultado.get("class", "")
    address = resultado.get("address", {})
    display_name_norm = _normalizar_texto(resultado.get("display_name") or "")

    cp_ref = "".join(c for c in (codpost_original or "") if c.isdigit())[:4]
    cp_geo = "".join(c for c in (address.get("postcode") or "") if c.isdigit())[:4]
    cp_prefix_ref = cp_ref[:2] if len(cp_ref) >= 2 else ""
    cp_prefix_geo = cp_geo[:2] if len(cp_geo) >= 2 else ""

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
        # Regra dura inicial: divergência nos 2 primeiros dígitos do CP
        # indica região distinta e deve sempre ser muito impreciso.
        if cp_prefix_ref and cp_prefix_geo and cp_prefix_ref != cp_prefix_geo:
            return "muito_impreciso"
        if cp_ref == cp_geo:
            if tipo in _GEOCODING_TIPOS_MUITO_IMPRECISOS:
                return "impreciso" if palavras_ref else "ok"
            if palavras_ref and not palavras_geo:
                return "impreciso"
            if rua_sem_match:
                return "impreciso"
            return "ok"

        cp_diverge = cp_ref != cp_geo if cp_ref else False
        cp_muito_diverge = cp_diverge and bool(cp_prefix_ref) and bool(cp_prefix_geo) and cp_prefix_ref != cp_prefix_geo
        if cp_muito_diverge or (cp_diverge and cidade_diverge):
            return "muito_impreciso"
        if cp_diverge or cidade_diverge:
            return "impreciso"
        if classe in _GEOCODING_CLASSES_IMPRECISAS:
            return "impreciso"
        return "ok"

    if modo_rescue:
        if classe == "boundary" and tipo == "administrative" and cidade_ref:
            if cidade_no_display or (cidade_geo and (cidade_ref in cidade_geo or cidade_geo in cidade_ref)):
                return "impreciso"

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


def _selecionar_melhor_resultado(resultados, codpost, cidade, endereco, *, modo_rescue=False, area_ref=None):
    melhor = None
    melhor_score = -1
    for item in resultados:
        precisao = determinar_precisao(item, codpost, cidade, endereco, modo_rescue=modo_rescue)
        precisao = _ajustar_precisao_coerencia_area_cp(precisao, item, area_ref)
        score = _score_precisao(precisao)
        if score > melhor_score:
            melhor = (item, precisao)
            melhor_score = score
        if score == 3:
            break
    return melhor


def _resultado_cp_diverge_referencia(resultado, codpost_original):
    """True se há CP na resposta OSM e os 4 dígitos diferem do pedido — sítio errado."""
    cp_ref = _cp_quatro_digitos(codpost_original)
    if len(cp_ref) < 4:
        return False
    addr = resultado.get("address") or {}
    cp_geo = _cp_quatro_digitos(addr.get("postcode") or "")
    return bool(cp_geo) and cp_geo != cp_ref


def _geocodificar_rescue_apos_muito_impreciso(endereco, codpost_limpo, cidade_limpa, area_ref=None):
    """
    Estratégia de correção só quando o caminho legado devolveu muito_impreciso:
    pesquisa estruturada CP+cidade, depois texto livre com rejeição por CP incoerente.
    """
    consultas = []
    if endereco and cidade_limpa:
        consultas.append(f"{endereco}, {cidade_limpa}, Portugal")
    if codpost_limpo and cidade_limpa:
        consultas.append(f"{codpost_limpo} {cidade_limpa} Portugal")
    if codpost_limpo:
        consultas.append(f"{codpost_limpo} Portugal")

    tentativas = []
    if codpost_limpo and cidade_limpa:
        tentativas.append(
            ("structured_pc_city", {"postalcode": codpost_limpo, "city": cidade_limpa, "countrycodes": "pt"}),
        )
    for q in consultas:
        tentativas.append(("free_text", q))

    for entrada in tentativas:
        _throttle_nominatim()
        if entrada[0] == "structured_pc_city":
            params = {"format": "json", "limit": 3, "addressdetails": 1, **entrada[1]}
            q_label = f"structured:{entrada[1].get('postalcode', '')}|{entrada[1].get('city', '')}"
        else:
            params = {
                "q": entrada[1],
                "format": "json",
                "limit": 3,
                "countrycodes": "pt",
                "addressdetails": 1,
            }
            q_label = entrada[1][:200]
        try:
            resp = http_requests.get(NOMINATIM_URL, params=params, headers=NOMINATIM_HEADERS, timeout=10)
            resp.raise_for_status()
            resultados = resp.json()
        except http_requests.RequestException as exc:
            logger.warning("Geocoding rescue falhou para '%s': %s", q_label, exc)
            continue
        except ValueError:
            logger.warning("Geocoding rescue retornou JSON inválido para '%s'", q_label)
            continue

        if not resultados:
            continue
        melhor = _selecionar_melhor_resultado(
            resultados, codpost_limpo, cidade_limpa, endereco, modo_rescue=True, area_ref=area_ref,
        )
        if not melhor:
            continue
        r, precision = melhor
        if _rescue_deve_ignorar_candidato(r, precision, codpost_limpo, area_ref):
            continue
        return float(r["lat"]), float(r["lon"]), (r.get("display_name", "") or ""), precision

    return None, None, None, None


def geocodificar(endereco, codpost, cidade, *, permitir_rescue=True):
    codpost_limpo = (codpost or "").strip()
    cidade_limpa = (cidade or "").strip()
    area_ref = None
    consultas = []
    if endereco and cidade_limpa:
        consultas.append(f"{endereco}, {cidade_limpa}, Portugal")
    if codpost_limpo and cidade_limpa:
        consultas.append(f"{codpost_limpo} {cidade_limpa} Portugal")
    if codpost_limpo:
        consultas.append(f"{codpost_limpo} Portugal")

    for query_index, q in enumerate(consultas):
        _throttle_nominatim()
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
        melhor = _selecionar_melhor_resultado(
            resultados, codpost_limpo, cidade_limpa, endereco, area_ref=area_ref,
        )
        if not melhor:
            continue
        r, precision = melhor
        lat, lng = float(r["lat"]), float(r["lon"])
        display = (r.get("display_name", "") or "")
        if precision == "muito_impreciso" and permitir_rescue:
            if area_ref is None:
                area_ref = _obter_area_referencia_cp(codpost_limpo)
            rescued = _geocodificar_rescue_apos_muito_impreciso(
                endereco, codpost_limpo, cidade_limpa, area_ref=area_ref,
            )
            if rescued[0] is not None:
                return rescued
        return lat, lng, display, precision

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
    melhor = _selecionar_melhor_resultado(
        resultados,
        pedido.codpost_dest,
        pedido.cidade_dest,
        pedido.endereco_dest,
        area_ref=_obter_area_referencia_cp((pedido.codpost_dest or "").strip()),
    )
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
    geocode_cache = {}
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
        cache_key = (
            (pedido.endereco_dest or "").strip().lower(),
            (pedido.codpost_dest or "").strip().lower(),
            (pedido.cidade_dest or "").strip().lower(),
        )
        geocode_item_t0 = time.monotonic()
        if cache_key in geocode_cache:
            lat, lng, display_name, precision = geocode_cache[cache_key]
        else:
            lat, lng, display_name, precision = geocodificar(
                pedido.endereco_dest, pedido.codpost_dest, pedido.cidade_dest, permitir_rescue=False,
            )
            geocode_cache[cache_key] = (lat, lng, display_name, precision)
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
    pedidos_com_devolucao = set()
    if pedido_ids:
        pedidos_com_devolucao = set(
            Devolucao.objects
            .filter(pedido_id__in=pedido_ids, pedido__filial=filial)
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
                "tem_devolucao": pedido.id in pedidos_com_devolucao,
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


def coordenadas_deposito_filial(filial):
    """Retorna {'lat': ..., 'lng': ...} do depósito da filial, ou None se não configurado."""
    if filial is None:
        return None
    lat = filial.lat_deposito
    lng = filial.lng_deposito
    if lat is None or lng is None:
        return None
    return {"lat": float(lat), "lng": float(lng)}


def _haversine_metros(lat1, lng1, lat2, lng2):
    raio_terra = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return raio_terra * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _distancia_haversine_waypoints(pontos):
    total = 0.0
    for i in range(1, len(pontos)):
        p0, p1 = pontos[i - 1], pontos[i]
        total += _haversine_metros(p0["lat"], p0["lng"], p1["lat"], p1["lng"])
    return total


def calcular_rota_osrm(pontos):
    """
    Calcula rota rodoviária via OSRM público.

    pontos: lista de dicts {'lat': float, 'lng': float}
    Retorna dict com geometry, distancia_metros, duracao_segundos, fallback.
    """
    if len(pontos) < 2:
        raise ValueError("Mínimo 2 pontos para traçar rota.")

    coordenadas = [[p["lng"], p["lat"]] for p in pontos]
    coords_str = ";".join(f"{lng},{lat}" for lng, lat in coordenadas)
    try:
        resp = http_requests.get(
            f"{OSRM_ROUTE_URL}/{coords_str}",
            params={"overview": "full", "geometries": "geojson"},
            headers=NOMINATIM_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        rota = data["routes"][0]
        return {
            "geometry": rota["geometry"],
            "distancia_metros": float(rota["distance"]),
            "duracao_segundos": float(rota["duration"]),
            "fallback": False,
        }
    except http_requests.RequestException as exc:
        logger.warning("OSRM rota falhou: %s", exc)
        return {
            "geometry": {"type": "LineString", "coordinates": coordenadas},
            "distancia_metros": _distancia_haversine_waypoints(pontos),
            "duracao_segundos": None,
            "fallback": True,
        }
