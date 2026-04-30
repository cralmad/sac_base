import json
import time
import logging
import unicodedata

import jwt
import requests as http_requests
from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone as dj_timezone
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from datetime import datetime, time as dt_time

from pages.pedidos.models import Pedido, TentativaEntrega, ESTADOS_SEGUE_PARA_ENTREGA
from sac_base.permissions_utils import build_action_permissions
from sac_base.sisvar_builders import build_sisvar_payload

logger = logging.getLogger(__name__)

PERMISSOES_MAPA = {
    "acessar": "pedidos.view_tentativaentrega",
    "editar": "pedidos.change_tentativaentrega",
    "editar_carro": "pedidos.change_carro_tentativaentrega",
}

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_HEADERS = {"User-Agent": "sac-base-mapa/1.0"}

# Paleta de cores por número de carro (índice 0 = carro 1, etc.)
CORES_CARRO = [
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
    "#42d4f4", "#f032e6", "#bfef45", "#fabed4", "#469990",
    "#dcbeff", "#9A6324", "#fffac8", "#800000", "#aaffc3",
    "#808000", "#ffd8b1", "#000075", "#a9a9a9", "#ffffff",
]


def _cor_carro(carro):
    """Retorna cor hex estável para um número de carro."""
    if carro is None:
        return "#6c757d"
    try:
        idx = (int(carro) - 1) % len(CORES_CARRO)
        return CORES_CARRO[idx]
    except (ValueError, TypeError):
        return "#6c757d"


_GEOCODING_TIPOS_MUITO_IMPRECISOS = frozenset({
    "postcode", "city", "town", "village", "county",
    "municipality", "state", "country", "region",
})
_GEOCODING_CLASSES_IMPRECISAS = frozenset({"highway", "place"})
_GEOCODING_CLASSES_MUITO_IMPRECISAS = frozenset({"landuse", "boundary", "natural"})

# Palavras genéricas de endereço que não ajudam a identificar a rua
_PALAVRAS_GENERICAS_END = frozenset({
    "rua", "avenida", "av", "travessa", "largo", "praca", "praceta",
    "alameda", "beco", "calcada", "estrada", "est", "lugar", "quinta",
    "lote", "bloco", "andar", "esq", "dto", "dir", "apartamento", "apt",
    "edificio", "edif", "portugal", "loja", "zona", "urbanizacao", "urb",
    "bairro", "s/n", "sem", "numero", "casa", "fracao", "fraccao",
})


def _normalizar_texto(texto):
    """Lowercase, remove acentos, mantém apenas alfanumérico."""
    nfkd = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _palavras_significativas(texto):
    """Extrai palavras com ≥4 chars que não sejam genéricas de endereço."""
    partes = _normalizar_texto(texto).split()
    return {p for p in partes if len(p) >= 4 and not p.isdigit() and p not in _PALAVRAS_GENERICAS_END}


def _determinar_precisao(resultado, codpost_original, cidade_original=None, endereco_original=None):
    """
    Classifica a precisão do resultado Nominatim.
    Retorna: 'ok' | 'impreciso' | 'muito_impreciso'

    Fluxo:
    A) Nominatim devolveu CP:
       A1. CPs iguais  → verifica rua; sem overlap → 'impreciso'.
       A2. CPs divergem → combina magnitude da divergência com cidade.
    B) Nominatim NÃO devolveu CP:
       B1. Tipo muito genérico  → 'muito_impreciso'.
       B2. Rua sem overlap      → 'impreciso'.
       B3. Cidade sem overlap   → 'impreciso'.
       B4. Caso contrário       → 'ok'.
    """
    tipo = resultado.get("type", "")
    classe = resultado.get("class", "")
    address = resultado.get("address", {})
    display_name_norm = _normalizar_texto(resultado.get("display_name") or "")

    logger.debug(
        "geocoding precision check | tipo=%s classe=%s postcode=%s road=%s city=%s display=%s",
        tipo, classe,
        address.get("postcode"),
        address.get("road") or address.get("pedestrian") or address.get("path"),
        address.get("city") or address.get("town") or address.get("village") or address.get("municipality"),
        resultado.get("display_name", "")[:80],
    )

    # ── Helpers reutilizáveis ─────────────────────────────────────────────────
    cp_ref = "".join(c for c in (codpost_original or "") if c.isdigit())[:4]
    cp_geo = "".join(c for c in (address.get("postcode") or "") if c.isdigit())[:4]

    road_geo = address.get("road") or address.get("pedestrian") or address.get("path") or ""
    palavras_geo  = _palavras_significativas(road_geo)
    palavras_ref  = _palavras_significativas(endereco_original or "")
    rua_sem_match = bool(palavras_ref and palavras_geo and not palavras_ref & palavras_geo)

    cidade_ref = _normalizar_texto(cidade_original or "").strip()
    cidade_geo = _normalizar_texto(
        address.get("city") or address.get("town") or
        address.get("village") or address.get("municipality") or ""
    ).strip()
    cidade_no_display = bool(cidade_ref and cidade_ref in display_name_norm)
    cidade_diverge = bool(
        cidade_ref and not cidade_no_display and
        cidade_geo and cidade_ref not in cidade_geo and cidade_geo not in cidade_ref
    )

    # ════ Ramo A: Nominatim devolveu CP ══════════════════════════════════════
    if cp_geo:
        # A1 — CPs iguais
        if cp_ref == cp_geo:
            # Se o resultado é genérico (apenas a área postal, sem rua específica)
            # e o pedido tem rua especificada → não confirmável → impreciso
            if tipo in _GEOCODING_TIPOS_MUITO_IMPRECISOS:
                return "impreciso" if palavras_ref else "ok"
            # Resultado tem rua mas pedido não → ok (sem base para comparar)
            # Pedido tem rua mas resultado não → não confirmável → impreciso
            if palavras_ref and not palavras_geo:
                return "impreciso"
            # Ambos têm rua mas sem palavras em comum → rua diferente
            if rua_sem_match:
                return "impreciso"
            return "ok"

        # A2 — CPs diferentes
        cp_diverge = cp_ref != cp_geo if cp_ref else False
        cp_muito_diverge = cp_diverge and bool(cp_ref) and cp_ref[0] != cp_geo[0]

        if cp_muito_diverge or (cp_diverge and cidade_diverge):
            return "muito_impreciso"
        if cp_diverge or cidade_diverge:
            return "impreciso"
        if classe in _GEOCODING_CLASSES_IMPRECISAS:
            return "impreciso"
        return "ok"

    # ════ Ramo B: Nominatim NÃO devolveu CP ══════════════════════════════════
    # Sem CP não podemos confirmar a localização; usamos rua + cidade + tipo.
    if tipo in _GEOCODING_TIPOS_MUITO_IMPRECISOS or classe == "boundary":
        return "muito_impreciso"
    if classe in _GEOCODING_CLASSES_MUITO_IMPRECISAS:
        return "muito_impreciso"
    # Se o pedido tem rua mas Nominatim não devolveu nenhuma → impreciso
    if palavras_ref and not palavras_geo:
        return "impreciso"
    if rua_sem_match:
        return "impreciso"
    if cidade_diverge:
        return "impreciso"
    if classe in _GEOCODING_CLASSES_IMPRECISAS:
        return "impreciso"
    return "ok"


def _geocodificar(endereco, codpost, cidade):
    """
    Chama Nominatim para geocodificar. Respeita rate-limit (1 req/s).
    Tenta primeiro com código postal + cidade, depois com endereço completo.
    Retorna (lat, lng) como float ou (None, None) em caso de falha.
    """
    consultas = []
    # Mais específico primeiro: rua + cidade aumenta chance de acertar
    if endereco and cidade:
        consultas.append(f"{endereco}, {cidade}, Portugal")
    if codpost and cidade:
        consultas.append(f"{codpost} {cidade} Portugal")
    if codpost:
        consultas.append(f"{codpost} Portugal")

    for q in consultas:
        try:
            time.sleep(1.1)  # Nominatim: máx 1 req/s
            resp = http_requests.get(
                NOMINATIM_URL,
                params={"q": q, "format": "json", "limit": 1, "countrycodes": "pt", "addressdetails": 1},
                headers=NOMINATIM_HEADERS,
                timeout=10,
            )
            resp.raise_for_status()
            resultados = resp.json()
            if resultados:
                r = resultados[0]
                display_name = r.get("display_name", "")
                precision = _determinar_precisao(r, codpost, cidade, endereco)
                return float(r["lat"]), float(r["lon"]), display_name, precision
        except Exception as exc:
            logger.warning("Geocoding falhou para '%s': %s", q, exc)

    return None, None, None, None


@login_required
@permission_required(PERMISSOES_MAPA["acessar"], raise_exception=True)
@csrf_protect
@require_http_methods(["GET"])
def mapa_conferencia_view(request):
    data_tentativa = request.GET.get("data", "")
    request.sisvar_extra = build_sisvar_payload(
        permissions={"mapa": build_action_permissions(request.user, PERMISSOES_MAPA)}
    )
    return render(request, "mapa_conferencia.html", {"data_tentativa": data_tentativa})


def _coordenadas_deposito(request):
    """Retorna {'lat': ..., 'lng': ...} da filial ativa, ou None se não configurado."""
    filial = getattr(request, "filial_ativa", None)
    if filial is None:
        return None
    lat = filial.lat_deposito
    lng = filial.lng_deposito
    if lat is None or lng is None:
        return None
    return {"lat": float(lat), "lng": float(lng)}


@login_required
@permission_required(PERMISSOES_MAPA["acessar"], raise_exception=True)
@csrf_protect
@require_POST
def mapa_pontos_view(request):
    """Retorna os pontos GeoJSON para a data solicitada, geocodificando se necessário."""
    try:
        body = json.loads(request.body)
        data_str = str(body.get("data", "")).strip()
    except Exception:
        return JsonResponse({"success": False, "mensagem": "JSON inválido."}, status=400)

    if not data_str:
        return JsonResponse({"success": False, "mensagem": "Data obrigatória."}, status=400)

    try:
        dt = datetime.strptime(data_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"success": False, "mensagem": "Data inválida."}, status=400)

    filial_ativa = getattr(request, "filial_ativa", None)
    if not filial_ativa:
        return JsonResponse({"success": False, "mensagem": "Filial ativa não encontrada."}, status=403)

    movs = (
        TentativaEntrega.objects
        .filter(data_tentativa=dt, pedido__filial=filial_ativa)
        .select_related("pedido")
        .order_by("carro", "pedido__codpost_dest")
    )

    features = []
    pedidos_sem_coord = []

    for mov in movs:
        pedido = mov.pedido
        if pedido is None:
            continue

        lat = float(pedido.lat) if pedido.lat is not None else None
        lng = float(pedido.lng) if pedido.lng is not None else None

        if lat is None or lng is None:
            pedidos_sem_coord.append((mov, pedido))

    # Geocodifica em lote os que ainda não têm coordenadas
    geocoding_falhou = 0
    for mov, pedido in pedidos_sem_coord:
        lat, lng, display_name, precision = _geocodificar(
            pedido.endereco_dest,
            pedido.codpost_dest,
            pedido.cidade_dest,
        )
        if lat is not None:
            pedido.lat = lat
            pedido.lng = lng
            pedido.geocoding_display = display_name or ""
            pedido.geocoding_precision = precision or ""
            pedido.save(update_fields=["lat", "lng", "geocoding_display", "geocoding_precision"])
        else:
            geocoding_falhou += 1

    # Re-carrega com coordenadas atualizadas
    movs = list(
        TentativaEntrega.objects
        .filter(data_tentativa=dt, pedido__filial=filial_ativa)
        .select_related("pedido")
        .order_by("carro", "pedido__codpost_dest")
    )
    pedido_ids = {m.pedido_id for m in movs}
    pedidos_com_tentativa_posterior = set()
    if pedido_ids:
        pedidos_com_tentativa_posterior = set(
            TentativaEntrega.objects
            .filter(pedido_id__in=pedido_ids, data_tentativa__gt=dt)
            .values_list("pedido_id", flat=True)
            .distinct()
        )

    for mov in movs:
        pedido = mov.pedido
        if pedido is None:
            continue

        lat = float(pedido.lat) if pedido.lat is not None else None
        lng = float(pedido.lng) if pedido.lng is not None else None

        if lat is None or lng is None:
            continue  # Sem coordenadas mesmo após geocoding

        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
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
                "cor": _cor_carro(mov.carro),
                "geocoding_display": pedido.geocoding_display or "",
                "geocoding_precision": pedido.geocoding_precision or "",
                "segue_para_entrega": (
                    (pedido.estado in ESTADOS_SEGUE_PARA_ENTREGA)
                    and (pedido.id not in pedidos_com_tentativa_posterior)
                ),
                "updated_at": mov.updated_at.isoformat(),
            },
        })

    return JsonResponse({
        "success": True,
        "geojson": {"type": "FeatureCollection", "features": features},
        "total": len(features),
        "sem_coord": geocoding_falhou,
        "deposito": _coordenadas_deposito(request),
    })


@login_required
@permission_required(PERMISSOES_MAPA["editar"], raise_exception=True)
@csrf_protect
@require_POST
def mapa_regeocodificar_view(request):
    """Re-executa o geocoding para um pedido já existente e atualiza os campos de precisão."""
    try:
        body = json.loads(request.body)
        pedido_id = int(body["pedido_id"])
    except Exception:
        return JsonResponse({"success": False, "mensagem": "Dados inválidos."}, status=400)

    filial_ativa = getattr(request, "filial_ativa", None)
    if not filial_ativa:
        return JsonResponse({"success": False, "mensagem": "Filial ativa não encontrada."}, status=403)

    try:
        pedido = Pedido.objects.get(pk=pedido_id, filial=filial_ativa)
    except Pedido.DoesNotExist:
        return JsonResponse({"success": False, "mensagem": "Pedido não encontrado."}, status=404)

    lat, lng, display_name, precision = _geocodificar(
        pedido.endereco_dest,
        pedido.codpost_dest,
        pedido.cidade_dest,
    )

    if lat is None:
        return JsonResponse({"success": False, "mensagem": "Não foi possível geocodificar o endereço."}, status=422)

    pedido.lat = lat
    pedido.lng = lng
    pedido.geocoding_display = display_name or ""
    pedido.geocoding_precision = precision or ""
    pedido.save(update_fields=["lat", "lng", "geocoding_display", "geocoding_precision"])

    return JsonResponse({
        "success": True,
        "lat": lat,
        "lng": lng,
        "geocoding_display": pedido.geocoding_display,
        "geocoding_precision": pedido.geocoding_precision,
    })


@login_required
@permission_required(PERMISSOES_MAPA["acessar"], raise_exception=True)
@csrf_protect
@require_POST
def mapa_salvar_coord_view(request):
    """Salva lat/lng corrigido pelo usuário ao arrastar o pin."""
    try:
        body = json.loads(request.body)
        pedido_id = int(body["pedido_id"])
        lat = float(body["lat"])
        lng = float(body["lng"])
        geocoding_display = str(body.get("geocoding_display", "") or "")[:300]
        geocoding_precision = str(body.get("geocoding_precision", "") or "")[:20]
    except Exception:
        return JsonResponse({"success": False, "mensagem": "Dados inválidos."}, status=400)

    filial_ativa = getattr(request, "filial_ativa", None)
    if not filial_ativa:
        return JsonResponse({"success": False, "mensagem": "Filial ativa não encontrada."}, status=403)

    try:
        pedido = Pedido.objects.get(pk=pedido_id, filial=filial_ativa)
    except Pedido.DoesNotExist:
        return JsonResponse({"success": False, "mensagem": "Pedido não encontrado."}, status=404)

    pedido.lat = lat
    pedido.lng = lng
    pedido.geocoding_display = geocoding_display
    pedido.geocoding_precision = geocoding_precision
    pedido.save(update_fields=["lat", "lng", "geocoding_display", "geocoding_precision"])
    return JsonResponse({"success": True})


@login_required
@permission_required(PERMISSOES_MAPA["acessar"], raise_exception=True)
@csrf_protect
@require_POST
def mapa_rota_view(request):
    """
    Recebe lista de pontos {lat, lng} e retorna geometria de rota
    via OpenRouteService (free tier, sem chave necessária para tráfego básico).
    Fallback: linha reta entre pontos (polyline simples).
    """
    try:
        body = json.loads(request.body)
        pontos = body["pontos"]  # [{lat, lng}, ...]
        carro = body.get("carro", "")
    except Exception:
        return JsonResponse({"success": False, "mensagem": "Dados inválidos."}, status=400)

    if len(pontos) < 2:
        return JsonResponse({"success": False, "mensagem": "Mínimo 2 pontos para traçar rota."}, status=400)

    coordenadas = [[p["lng"], p["lat"]] for p in pontos]
    # OSRM público — gratuito, sem chave de API
    # Formato: lng,lat;lng,lat;...
    coords_str = ";".join(f"{lng},{lat}" for lng, lat in coordenadas)
    try:
        resp = http_requests.get(
            f"https://router.project-osrm.org/route/v1/driving/{coords_str}",
            params={"overview": "full", "geometries": "geojson"},
            headers=NOMINATIM_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        geometry = data["routes"][0]["geometry"]
        return JsonResponse({"success": True, "geometry": geometry, "carro": carro})
    except Exception as exc:
        logger.warning("OSRM rota falhou: %s", exc)
        # Fallback: retorna polyline reta entre os pontos
        return JsonResponse({
            "success": True,
            "geometry": {"type": "LineString", "coordinates": coordenadas},
            "carro": carro,
            "fallback": True,
        })


# ─── Mapa Público (link por carro, sem login) ────────────────────────────────

_ALGO_JWT = "HS256"
_PERIODOS_VALIDOS = {"MANHA", "TARDE", ""}


def _fim_do_dia(data) -> datetime:
    """Retorna datetime aware (UTC) correspondente a 23:59:59 do dia indicado."""
    fim_local = datetime.combine(data, dt_time(23, 59, 59))
    return dj_timezone.make_aware(fim_local, dj_timezone.get_current_timezone())


def _gerar_token_carro(carro: int, data) -> str:
    """Gera JWT com carro + data da rota. Expira às 23:59:59 desse mesmo dia."""
    payload = {
        "carro": int(carro),
        "data": str(data),          # YYYY-MM-DD
        "exp": _fim_do_dia(data),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=_ALGO_JWT)


def _validar_token_carro(token: str):
    """Valida JWT e retorna (carro, data). Levanta jwt.PyJWTError se inválido."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[_ALGO_JWT])
    carro = int(payload["carro"])
    from datetime import date as _date
    data = _date.fromisoformat(payload["data"])
    return carro, data


@login_required
@permission_required(PERMISSOES_MAPA["acessar"], raise_exception=True)
@require_http_methods(["GET"])
def mapa_publico_gerar_link_view(request):
    """Gera e retorna o link público para um carro e data (padrão: hoje)."""
    try:
        carro = int(request.GET.get("carro", ""))
        if carro <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return JsonResponse({"success": False, "mensagem": "Parâmetro 'carro' inválido."}, status=400)

    data_str = request.GET.get("data", "").strip()
    if data_str:
        try:
            from datetime import date as _date
            data = _date.fromisoformat(data_str)
        except ValueError:
            return JsonResponse({"success": False, "mensagem": "Parâmetro 'data' inválido."}, status=400)
    else:
        data = dj_timezone.localdate()

    token = _gerar_token_carro(carro, data)
    url = request.build_absolute_uri(reverse("mapa_publico", kwargs={"token": token}))
    return JsonResponse({"success": True, "url": url, "carro": carro, "data": str(data)})


@require_http_methods(["GET"])
def mapa_publico_view(request, token):
    """Renderiza a página pública do mapa para o carro embutido no token."""
    erro = None
    carro = None
    data_fmt = ""
    try:
        carro, data = _validar_token_carro(token)
        data_fmt = data.strftime("%d/%m/%Y")
    except jwt.ExpiredSignatureError:
        erro = "expirado"
    except Exception:
        erro = "invalido"

    return render(request, "mapa_publico.html", {
        "carro": carro,
        "token": token,
        "data_fmt": data_fmt,
        "erro": erro,
    })


@csrf_exempt
@require_POST
def mapa_publico_pontos_view(request, token):
    """Retorna GeoJSON dos pontos para o carro e data do token (sem login)."""
    try:
        carro, data = _validar_token_carro(token)
    except Exception:
        return JsonResponse({"success": False, "mensagem": "Link inválido ou expirado."}, status=403)
    movs = list(
        TentativaEntrega.objects
        .filter(data_tentativa=data, carro=carro)
        .select_related("pedido")
        .order_by("pedido__codpost_dest")
    )
    pedido_ids = {m.pedido_id for m in movs}
    pedidos_com_tentativa_posterior = set()
    if pedido_ids:
        pedidos_com_tentativa_posterior = set(
            TentativaEntrega.objects
            .filter(pedido_id__in=pedido_ids, data_tentativa__gt=data)
            .values_list("pedido_id", flat=True)
            .distinct()
        )

    features = []
    linhas = []
    periodo_atual = None
    cor = _cor_carro(carro)
    total_pedidos = 0
    sem_coord = 0

    for mov in movs:
        pedido = mov.pedido
        if pedido is None:
            continue

        total_pedidos += 1

        if periodo_atual is None:
            periodo_atual = mov.periodo

        fones = " / ".join(f for f in [pedido.fone_dest or "", pedido.fone_dest2 or ""] if f)
        linhas.append({
            "mov_id": mov.id,
            "referencia": str(pedido.pedido or pedido.id_vonzu),
            "tipo": "R" if (pedido.tipo or "").upper() == "RECOLHA" else "E",
            "nome_dest": pedido.nome_dest or "",
            "fones": fones,
            "endereco_dest": pedido.endereco_dest or "",
            "cidade_dest": pedido.cidade_dest or "",
            "codpost_dest": pedido.codpost_dest or "",
            "volume": pedido.volume,
            "peso": pedido.peso,
            "obs_rota": pedido.obs_rota or "",
            "periodo": mov.periodo or "",
        })

        lat = float(pedido.lat) if pedido.lat is not None else None
        lng = float(pedido.lng) if pedido.lng is not None else None
        if lat is None or lng is None:
            sem_coord += 1
            continue

        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "mov_id": mov.id,
                "referencia": str(pedido.pedido or pedido.id_vonzu),
                "tipo": pedido.tipo or "",
                "endereco": pedido.endereco_dest or "",
                "codpost": pedido.codpost_dest or "",
                "cidade": pedido.cidade_dest or "",
                "volume": pedido.volume,
                "obs": pedido.obs or "",
                "obs_rota": pedido.obs_rota or "",
                "periodo": mov.periodo or "",
                "cor": cor,
                "segue_para_entrega": (
                    (pedido.estado in ESTADOS_SEGUE_PARA_ENTREGA)
                    and (pedido.id not in pedidos_com_tentativa_posterior)
                ),
            },
        })

    return JsonResponse({
        "success": True,
        "geojson": {"type": "FeatureCollection", "features": features},
        "linhas": linhas,
        "total": total_pedidos,
        "total_mapa": len(features),
        "sem_coord": sem_coord,
        "periodo_atual": periodo_atual or "",
    })


@csrf_exempt
@require_POST
def mapa_publico_periodo_view(request, token):
    """Atualiza o período de TODAS as TentativaEntrega do carro+data do token."""
    try:
        carro, data = _validar_token_carro(token)
    except Exception:
        return JsonResponse({"success": False, "mensagem": "Link inválido ou expirado."}, status=403)

    try:
        body = json.loads(request.body)
        periodo = str(body.get("periodo", "")).strip().upper()
    except Exception:
        return JsonResponse({"success": False, "mensagem": "JSON inválido."}, status=400)

    if periodo not in _PERIODOS_VALIDOS:
        return JsonResponse({"success": False, "mensagem": "Período inválido. Use 'MANHA' ou 'TARDE'."}, status=400)

    mov_ids = body.get("mov_ids")
    qs = TentativaEntrega.objects.filter(data_tentativa=data, carro=carro)
    if mov_ids is not None:
        try:
            mov_ids = [int(i) for i in mov_ids]
        except (ValueError, TypeError):
            return JsonResponse({"success": False, "mensagem": "mov_ids inválido."}, status=400)
        qs = qs.filter(id__in=mov_ids)

    if qs.filter(sms_enviado=True).exists():
        return JsonResponse(
            {"success": False, "mensagem": "Não é possível alterar o período: SMS já enviado para um ou mais pedidos desta rota."},
            status=409,
        )

    atualizados = qs.update(periodo=periodo or None)
    return JsonResponse({"success": True, "atualizados": atualizados, "periodo": periodo})
