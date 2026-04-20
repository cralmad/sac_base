import json
import time
import logging

import requests as http_requests
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods, require_POST
from datetime import datetime

from pages.pedidos.models import Pedido, TentativaEntrega
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


def _geocodificar(endereco, codpost, cidade):
    """
    Chama Nominatim para geocodificar. Respeita rate-limit (1 req/s).
    Tenta primeiro com código postal + cidade, depois com endereço completo.
    Retorna (lat, lng) como float ou (None, None) em caso de falha.
    """
    consultas = []
    if codpost and cidade:
        consultas.append(f"{codpost} {cidade} Portugal")
    if endereco and cidade:
        consultas.append(f"{endereco}, {cidade}, Portugal")
    if codpost:
        consultas.append(f"{codpost} Portugal")

    for q in consultas:
        try:
            time.sleep(1.1)  # Nominatim: máx 1 req/s
            resp = http_requests.get(
                NOMINATIM_URL,
                params={"q": q, "format": "json", "limit": 1, "countrycodes": "pt"},
                headers=NOMINATIM_HEADERS,
                timeout=10,
            )
            resp.raise_for_status()
            resultados = resp.json()
            if resultados:
                return float(resultados[0]["lat"]), float(resultados[0]["lon"])
        except Exception as exc:
            logger.warning("Geocoding falhou para '%s': %s", q, exc)

    return None, None


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

    movs = (
        TentativaEntrega.objects
        .filter(data_tentativa=dt)
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
        lat, lng = _geocodificar(
            pedido.endereco_dest,
            pedido.codpost_dest,
            pedido.cidade_dest,
        )
        if lat is not None:
            pedido.lat = lat
            pedido.lng = lng
            pedido.save(update_fields=["lat", "lng"])
        else:
            geocoding_falhou += 1

    # Re-carrega com coordenadas atualizadas
    movs = (
        TentativaEntrega.objects
        .filter(data_tentativa=dt)
        .select_related("pedido")
        .order_by("carro", "pedido__codpost_dest")
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
    except Exception:
        return JsonResponse({"success": False, "mensagem": "Dados inválidos."}, status=400)

    try:
        pedido = Pedido.objects.get(pk=pedido_id)
    except Pedido.DoesNotExist:
        return JsonResponse({"success": False, "mensagem": "Pedido não encontrado."}, status=404)

    pedido.lat = lat
    pedido.lng = lng
    pedido.save(update_fields=["lat", "lng"])
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
