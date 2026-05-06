import json
import logging

import jwt
import requests as http_requests
from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone as dj_timezone
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from datetime import datetime, time as dt_time

from pages.pedidos.models import Pedido, TentativaEntrega, estado_segue_para_entrega
from pages.pedidos.services.mapa_service import (
    buscar_local_para_pedido,
    cor_carro,
    geocodificar,
    montar_payload_mapa,
)
from sac_base.permissions_utils import build_action_permissions
from sac_base.sisvar_builders import build_sisvar_payload

logger = logging.getLogger(__name__)

PERMISSOES_MAPA = {
    "acessar": "pedidos.view_tentativaentrega",
    "editar": "pedidos.change_tentativaentrega",
    "editar_carro": "pedidos.change_carro_tentativaentrega",
}

NOMINATIM_HEADERS = {"User-Agent": "sac-base-mapa/1.0"}


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
    """Retorna os pontos GeoJSON para a data solicitada."""
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
    lock_key = f"mapa_geocode_lock:{filial_ativa.id}:{dt.isoformat()}"
    if not cache.add(lock_key, "1", timeout=120):
        return JsonResponse(
            {"success": False, "mensagem": "Geocodificação já está em andamento para esta data. Aguarde e tente novamente."},
            status=429,
        )

    payload = montar_payload_mapa(filial_ativa, dt)

    try:
        return JsonResponse({
            "success": True,
            "geojson": payload["geojson"],
            "total": payload["total"],
            "sem_coord": payload["sem_coord"],
            "pendentes_sem_coord": payload.get("pendentes_sem_coord", 0),
            "limite_atingido": payload.get("limite_atingido", False),
            "deposito": _coordenadas_deposito(request),
        })
    finally:
        cache.delete(lock_key)


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

    lat, lng, display_name, precision = geocodificar(
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
def mapa_buscar_local_view(request):
    try:
        body = json.loads(request.body)
        pedido_id = int(body["pedido_id"])
        query = str(body.get("query", "")).strip()
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"success": False, "mensagem": "Dados inválidos."}, status=400)

    if not query:
        return JsonResponse({"success": False, "mensagem": "Informe um endereço para busca."}, status=400)

    filial_ativa = getattr(request, "filial_ativa", None)
    if not filial_ativa:
        return JsonResponse({"success": False, "mensagem": "Filial ativa não encontrada."}, status=403)

    try:
        pedido = Pedido.objects.get(pk=pedido_id, filial=filial_ativa)
    except Pedido.DoesNotExist:
        return JsonResponse({"success": False, "mensagem": "Pedido não encontrado."}, status=404)

    resultado = buscar_local_para_pedido(pedido, query)
    if not resultado:
        return JsonResponse({"success": False, "mensagem": "Endereço não encontrado."}, status=404)
    return JsonResponse({"success": True, **resultado})


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
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"success": False, "mensagem": "Dados inválidos."}, status=400)
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        return JsonResponse({"success": False, "mensagem": "Coordenadas fora da faixa válida."}, status=400)

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
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
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
    except http_requests.RequestException as exc:
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


def _gerar_token_carro(carro: int, data, filial_id: int) -> str:
    """Gera JWT com carro + data da rota. Expira às 23:59:59 desse mesmo dia."""
    payload = {
        "carro": int(carro),
        "filial_id": int(filial_id),
        "data": str(data),          # YYYY-MM-DD
        "exp": _fim_do_dia(data),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=_ALGO_JWT)


def _validar_token_carro(token: str):
    """Valida JWT e retorna (carro, data). Levanta jwt.PyJWTError se inválido."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[_ALGO_JWT])
    carro = int(payload["carro"])
    filial_id = int(payload["filial_id"])
    from datetime import date as _date
    data = _date.fromisoformat(payload["data"])
    return carro, data, filial_id


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

    filial_ativa = getattr(request, "filial_ativa", None)
    if not filial_ativa:
        return JsonResponse({"success": False, "mensagem": "Filial ativa não encontrada."}, status=403)

    token = _gerar_token_carro(carro, data, filial_ativa.id)
    url = request.build_absolute_uri(reverse("mapa_publico", kwargs={"token": token}))
    return JsonResponse({"success": True, "url": url, "carro": carro, "data": str(data)})


@require_http_methods(["GET"])
def mapa_publico_view(request, token):
    """Renderiza a página pública do mapa para o carro embutido no token."""
    erro = None
    carro = None
    data_fmt = ""
    try:
        carro, data, _filial_id = _validar_token_carro(token)
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
        carro, data, filial_id = _validar_token_carro(token)
    except Exception:
        return JsonResponse({"success": False, "mensagem": "Link inválido ou expirado."}, status=403)
    movs = list(
        TentativaEntrega.objects
        .filter(data_tentativa=data, carro=carro, pedido__filial_id=filial_id)
        .select_related("pedido")
        .order_by("pedido__codpost_dest")
    )
    pedido_ids = {m.pedido_id for m in movs}
    pedidos_com_tentativa_posterior = set()
    if pedido_ids:
        pedidos_com_tentativa_posterior = set(
            TentativaEntrega.objects
            .filter(pedido_id__in=pedido_ids, data_tentativa__gt=data, pedido__filial_id=filial_id)
            .values_list("pedido_id", flat=True)
            .distinct()
        )

    features = []
    linhas = []
    periodo_atual = None
    cor = cor_carro(carro)
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
                    estado_segue_para_entrega(mov.estado)
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
        carro, data, filial_id = _validar_token_carro(token)
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
    qs = TentativaEntrega.objects.filter(data_tentativa=data, carro=carro, pedido__filial_id=filial_id)
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
