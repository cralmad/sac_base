"""Geocodificação de pedidos via scraping de codigo-postal.pt (Portugal)."""

import logging
import re
import time
import unicodedata
from decimal import Decimal

import requests
from django.core.cache import cache
from django.db.models import Q

from pages.pedidos.models import Pedido
from pages.pedidos.services.zona_entrega_pedido import normalizar_cp7_num

logger = logging.getLogger(__name__)

CODIGO_POSTAL_PT_BASE = "https://www.codigo-postal.pt"
CP_REFERENCIA_ESTRUTURA = "7580-610"
USER_AGENT = "Mozilla/5.0 (compatible; sac-base-geocode/1.0)"

GEOCODE_SYNC_MAX_PEDIDOS = 30
GEOCODE_INTERVALO_CP_SEG = 1.0
GEOCODE_LOTE_PEDIDOS = 25
GEOCODE_INTERVALO_LOTE_SEG = 45
GEOCODE_TIMEOUT_SYNC_SEG = 90
GEOCODE_TIMEOUT_DIARIO_SEG = 3600

GPS_TOLERANCIA = 1e-5
_SITE_CHECK_TTL_SEG = 900
_MAX_AVISOS_RELATORIO = 20

_RE_MARCADOR_GPS = re.compile(r"class=['\"]pull-right gps['\"]", re.I)
_RE_MARCADOR_GPS_TAG = re.compile(r"<b>GPS:</b>", re.I)
_RE_MARCADOR_RUA = re.compile(r'class=["\']search-title["\']', re.I)
_RE_BLOCO_CANDIDATO = re.compile(
    r'class=["\']search-title["\'][^>]*>([^<]+)</a>.*?'
    r"class=['\"]pull-right gps['\"][^>]*>\s*<b>GPS:</b>\s*([-\d.]+)\s*,\s*([-\d.]+)",
    re.I | re.S,
)
_RE_GPS_ORFAO = re.compile(
    r"class=['\"]pull-right gps['\"][^>]*>\s*<b>GPS:</b>\s*([-\d.]+)\s*,\s*([-\d.]+)",
    re.I,
)

_PALAVRAS_GENERICAS_END = frozenset({
    "rua", "avenida", "av", "travessa", "largo", "praca", "praceta",
    "alameda", "beco", "calcada", "estrada", "est", "lugar", "quinta",
    "lote", "bloco", "andar", "esq", "dto", "dir", "apartamento", "apt",
    "edificio", "edif", "portugal", "loja", "zona", "urbanizacao", "urb",
    "bairro", "sem", "numero", "casa", "fracao", "fraccao",
})

_SITE_CHECK_CACHE = {"expira_em": 0.0, "resultado": None}


def _stats_vazias():
    return {
        "coords_atribuidas": 0,
        "coords_cp_pt": 0,
        "coords_cp_pt_rua": 0,
        "coords_cp_pt_fallback": 0,
        "coords_sem_cp": 0,
        "coords_ignoradas_ja_possuiam": 0,
        "coords_cp_nao_encontrado": 0,
        "coords_falha_site": 0,
        "coords_enfileiradas": 0,
        "coords_restantes_filial": 0,
        "modo": "sync",
        "site_ok": True,
        "avisos": [],
    }


def _normalizar_texto(texto):
    nfkd = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _palavras_significativas(texto):
    partes = _normalizar_texto(texto).split()
    return {
        p for p in partes
        if len(p) >= 4 and not p.isdigit() and p not in _PALAVRAS_GENERICAS_END
    }


def _cp_para_url(codpost):
    _cp4, cp7 = normalizar_cp7_num(codpost)
    if cp7 is None:
        return None
    s = str(cp7).zfill(7)
    return f"{s[:4]}-{s[4:7]}"


def _gps_iguais(lat1, lng1, lat2, lng2):
    return abs(lat1 - lat2) < GPS_TOLERANCIA and abs(lng1 - lng2) < GPS_TOLERANCIA


def _http_get(url):
    return requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)


def verificar_estrutura_codigo_postal_pt(*, forcar=False):
    agora = time.monotonic()
    if not forcar and _SITE_CHECK_CACHE["resultado"] is not None:
        if agora < _SITE_CHECK_CACHE["expira_em"]:
            return _SITE_CHECK_CACHE["resultado"]

    url = f"{CODIGO_POSTAL_PT_BASE}/{CP_REFERENCIA_ESTRUTURA}/"
    try:
        resp = _http_get(url)
        resp.raise_for_status()
        html = resp.text
    except requests.RequestException as exc:
        logger.warning("Health-check codigo-postal.pt falhou: %s", exc)
        resultado = {
            "ok": False,
            "codigo": "site_indisponivel",
            "mensagem": "Não foi possível contactar codigo-postal.pt.",
        }
        _SITE_CHECK_CACHE["resultado"] = resultado
        _SITE_CHECK_CACHE["expira_em"] = agora + 60
        return resultado

    if not (_RE_MARCADOR_GPS.search(html) and _RE_MARCADOR_GPS_TAG.search(html)):
        resultado = {
            "ok": False,
            "codigo": "site_alterado",
            "mensagem": "Estrutura HTML de codigo-postal.pt alterada (marcador GPS ausente).",
        }
    else:
        resultado = {"ok": True, "codigo": "ok", "mensagem": ""}

    _SITE_CHECK_CACHE["resultado"] = resultado
    _SITE_CHECK_CACHE["expira_em"] = agora + _SITE_CHECK_TTL_SEG
    return resultado


def _parse_candidatos_html(html):
    candidatos = []
    vistos = set()
    for m in _RE_BLOCO_CANDIDATO.finditer(html):
        rua = (m.group(1) or "").strip()
        lat = float(m.group(2))
        lng = float(m.group(3))
        chave = (rua, lat, lng)
        if chave in vistos:
            continue
        vistos.add(chave)
        candidatos.append({"rua": rua, "gps_lat": lat, "gps_lng": lng, "localidade": ""})

    if candidatos:
        return candidatos

    for m in _RE_GPS_ORFAO.finditer(html):
        lat = float(m.group(1))
        lng = float(m.group(2))
        chave = ("", lat, lng)
        if chave in vistos:
            continue
        vistos.add(chave)
        candidatos.append({"rua": "", "gps_lat": lat, "gps_lng": lng, "localidade": ""})
    return candidatos


def consultar_codigo_postal_pt(codpost, *, cache_cp=None, aplicar_sleep=True):
    """Retorna {ok, candidatos, codigo_erro} para um código postal."""
    cp_url = _cp_para_url(codpost)
    if not cp_url:
        return {"ok": False, "candidatos": [], "codigo_erro": "cp_invalido"}

    if cache_cp is not None and cp_url in cache_cp:
        return cache_cp[cp_url]

    url = f"{CODIGO_POSTAL_PT_BASE}/{cp_url}/"
    try:
        resp = _http_get(url)
        if resp.status_code == 404:
            resultado = {"ok": False, "candidatos": [], "codigo_erro": "cp_nao_encontrado"}
        else:
            resp.raise_for_status()
            candidatos = _parse_candidatos_html(resp.text)
            if candidatos:
                resultado = {"ok": True, "candidatos": candidatos, "codigo_erro": None}
            else:
                resultado = {"ok": False, "candidatos": [], "codigo_erro": "sem_candidatos"}
        if aplicar_sleep:
            time.sleep(GEOCODE_INTERVALO_CP_SEG)
    except requests.RequestException as exc:
        logger.warning("Consulta codigo-postal.pt falhou para %s: %s", cp_url, exc)
        resultado = {"ok": False, "candidatos": [], "codigo_erro": "rede"}

    if cache_cp is not None:
        cache_cp[cp_url] = resultado
    return resultado


def _rua_coincide(endereco, rua):
    palavras_end = _palavras_significativas(endereco)
    palavras_rua = _palavras_significativas(rua)
    if not palavras_end or not palavras_rua:
        return False
    return bool(palavras_end & palavras_rua)


def resolver_coordenadas(endereco, codpost, cidade, candidatos):
    """Retorna dict com lat, lng, precision, display, aviso ou None se impossível."""
    del cidade
    if not candidatos:
        return None

    if len(candidatos) == 1:
        c = candidatos[0]
        return {
            "lat": c["gps_lat"],
            "lng": c["gps_lng"],
            "precision": "cp_pt",
            "display": f"codigo-postal.pt: {c['rua'] or codpost or ''}"[:300],
            "aviso": None,
        }

    primeiro = candidatos[0]
    lat0, lng0 = primeiro["gps_lat"], primeiro["gps_lng"]
    if all(_gps_iguais(lat0, lng0, c["gps_lat"], c["gps_lng"]) for c in candidatos):
        return {
            "lat": lat0,
            "lng": lng0,
            "precision": "cp_pt",
            "display": f"codigo-postal.pt: {primeiro['rua'] or codpost or ''}"[:300],
            "aviso": None,
        }

    matches = [c for c in candidatos if _rua_coincide(endereco, c.get("rua"))]
    if len(matches) == 1:
        c = matches[0]
        return {
            "lat": c["gps_lat"],
            "lng": c["gps_lng"],
            "precision": "cp_pt_rua",
            "display": f"codigo-postal.pt: {c['rua']}"[:300],
            "aviso": None,
        }

    c = primeiro
    aviso = (
        f"id_vonzu fallback | CP {codpost or '-'} | morada CSV: {(endereco or '-')[:60]} | "
        f"rua usada: {c['rua'] or '-'}"
    )
    return {
        "lat": c["gps_lat"],
        "lng": c["gps_lng"],
        "precision": "cp_pt_fallback",
        "display": f"codigo-postal.pt (1ª opção): {c['rua'] or codpost or ''}"[:300],
        "aviso": aviso,
    }


def _contar_restantes_filial(filial):
    return Pedido.objects.filter(filial=filial).filter(
        Q(lat__isnull=True) | Q(lng__isnull=True),
    ).exclude(codpost_dest__isnull=True).exclude(codpost_dest="").count()


def _adquirir_lock(filial_id, origem):
    if origem == "comando":
        return cache.add("geocode_cp_pt:comando", "1", timeout=GEOCODE_TIMEOUT_DIARIO_SEG)
    return cache.add(f"geocode_cp_pt:filial:{filial_id}", "1", timeout=GEOCODE_TIMEOUT_SYNC_SEG)


def _liberar_lock(filial_id, origem):
    if origem == "comando":
        cache.delete("geocode_cp_pt:comando")
    else:
        cache.delete(f"geocode_cp_pt:filial:{filial_id}")


def listar_ids_pedidos_sem_coord(filial, *, limite=None):
    qs = (
        Pedido.objects.filter(filial=filial)
        .filter(Q(lat__isnull=True) | Q(lng__isnull=True))
        .exclude(codpost_dest__isnull=True)
        .exclude(codpost_dest="")
        .order_by("id")
    )
    if limite:
        qs = qs[:limite]
    return list(qs.values_list("id", flat=True))


def filiais_com_pedidos_sem_coord():
    return (
        Pedido.objects.filter(Q(lat__isnull=True) | Q(lng__isnull=True))
        .exclude(codpost_dest__isnull=True)
        .exclude(codpost_dest="")
        .values_list("filial_id", flat=True)
        .distinct()
    )


def existe_pendente_global():
    return (
        Pedido.objects.filter(Q(lat__isnull=True) | Q(lng__isnull=True))
        .exclude(codpost_dest__isnull=True)
        .exclude(codpost_dest="")
        .exists()
    )


def atribuir_coordenadas_pedidos(
    filial, pedido_ids, *, origem="importacao", max_processar=None, skip_lock=False,
):
    stats = _stats_vazias()
    stats["modo"] = "sync" if origem != "comando" else "noturno"

    if not pedido_ids:
        stats["coords_restantes_filial"] = _contar_restantes_filial(filial)
        return stats

    lock_adquirido = False
    if not skip_lock:
        if not _adquirir_lock(filial.id, origem):
            stats["site_ok"] = True
            stats["avisos"].append("Geocodificação já em execução para esta filial/comando.")
            stats["coords_restantes_filial"] = _contar_restantes_filial(filial)
            return stats
        lock_adquirido = True

    try:
        check = verificar_estrutura_codigo_postal_pt()
        if not check["ok"]:
            stats["site_ok"] = False
            stats["coords_falha_site"] = len(pedido_ids)
            stats["avisos"].append(check["mensagem"])
            stats["coords_restantes_filial"] = _contar_restantes_filial(filial)
            return stats

        qs = (
            Pedido.objects.filter(filial=filial, id__in=pedido_ids)
            .only(
                "id", "id_vonzu", "lat", "lng", "codpost_dest",
                "endereco_dest", "cidade_dest",
                "geocoding_display", "geocoding_precision",
            )
        )
        elegiveis = []
        for pedido in qs:
            if pedido.lat is not None and pedido.lng is not None:
                stats["coords_ignoradas_ja_possuiam"] += 1
                continue
            cp = (pedido.codpost_dest or "").strip()
            if not cp:
                stats["coords_sem_cp"] += 1
                continue
            elegiveis.append(pedido)

        if max_processar is not None and len(elegiveis) > max_processar:
            stats["coords_enfileiradas"] = len(elegiveis) - max_processar
            elegiveis = elegiveis[:max_processar]

        cache_cp = {}
        atualizar = []
        inicio = time.monotonic()
        processados = 0

        for pedido in elegiveis:
            if origem != "comando" and (time.monotonic() - inicio) >= GEOCODE_TIMEOUT_SYNC_SEG:
                stats["coords_enfileiradas"] += len(elegiveis) - processados
                break

            cp_url = _cp_para_url(pedido.codpost_dest)
            ja_em_cache = cp_url in cache_cp if cp_url else False
            consulta = consultar_codigo_postal_pt(
                pedido.codpost_dest,
                cache_cp=cache_cp,
                aplicar_sleep=not ja_em_cache,
            )
            processados += 1

            if not consulta["ok"]:
                cod = consulta.get("codigo_erro")
                if cod in ("cp_nao_encontrado", "sem_candidatos"):
                    stats["coords_cp_nao_encontrado"] += 1
                else:
                    stats["coords_falha_site"] += 1
                continue

            resolvido = resolver_coordenadas(
                pedido.endereco_dest,
                pedido.codpost_dest,
                pedido.cidade_dest,
                consulta["candidatos"],
            )
            if not resolvido:
                stats["coords_cp_nao_encontrado"] += 1
                continue

            pedido.lat = Decimal(str(resolvido["lat"])).quantize(Decimal("0.000001"))
            pedido.lng = Decimal(str(resolvido["lng"])).quantize(Decimal("0.000001"))
            pedido.geocoding_display = resolvido["display"]
            pedido.geocoding_precision = resolvido["precision"]
            atualizar.append(pedido)

            prec = resolvido["precision"]
            if prec == "cp_pt":
                stats["coords_cp_pt"] += 1
            elif prec == "cp_pt_rua":
                stats["coords_cp_pt_rua"] += 1
            elif prec == "cp_pt_fallback":
                stats["coords_cp_pt_fallback"] += 1
                if resolvido.get("aviso") and len(stats["avisos"]) < _MAX_AVISOS_RELATORIO:
                    stats["avisos"].append(
                        f"  vonzu={pedido.id_vonzu} | {resolvido['aviso']}"
                    )

        if atualizar:
            Pedido.objects.bulk_update(
                atualizar,
                ["lat", "lng", "geocoding_display", "geocoding_precision"],
            )
        stats["coords_atribuidas"] = len(atualizar)
        stats["coords_restantes_filial"] = _contar_restantes_filial(filial)
        return stats
    finally:
        if lock_adquirido:
            _liberar_lock(filial.id, origem)


def geocodificar_apos_importacao(filial, id_vonzus):
    """Geocodifica pedidos do CSV sem coordenadas; sync se <=30, senão modo noturno."""
    stats = _stats_vazias()
    if not id_vonzus:
        return stats

    ids = list(
        Pedido.objects.filter(filial=filial, id_vonzu__in=id_vonzus)
        .filter(Q(lat__isnull=True) | Q(lng__isnull=True))
        .exclude(codpost_dest__isnull=True)
        .exclude(codpost_dest="")
        .values_list("id", flat=True)
    )
    total = len(ids)
    if total == 0:
        return stats

    if total > GEOCODE_SYNC_MAX_PEDIDOS:
        stats["modo"] = "noturno"
        stats["coords_enfileiradas"] = total
        stats["coords_restantes_filial"] = _contar_restantes_filial(filial)
        return stats

    resultado = atribuir_coordenadas_pedidos(
        filial,
        ids,
        origem="importacao",
        max_processar=GEOCODE_SYNC_MAX_PEDIDOS,
    )
    resultado["modo"] = "sync"
    return resultado


def geocodificar_filial_manual(filial):
    """Botão manual: processa até GEOCODE_SYNC_MAX_PEDIDOS pedidos por clique."""
    ids = listar_ids_pedidos_sem_coord(filial)
    stats = _stats_vazias()
    if not ids:
        stats["coords_restantes_filial"] = 0
        return stats

    stats = atribuir_coordenadas_pedidos(
        filial,
        ids,
        origem="manual",
        max_processar=GEOCODE_SYNC_MAX_PEDIDOS,
    )
    restantes = stats.get("coords_restantes_filial", 0)
    if restantes > 0:
        stats["modo"] = "noturno"
        stats["coords_enfileiradas"] = restantes
    else:
        stats["modo"] = "sync"
        stats["coords_enfileiradas"] = 0
    return stats


def executar_geocodificacao_diaria(*, filial_id=None, dry_run=False):
    """Loop multi-lote numa única execução (Heroku Scheduler 1x/dia)."""
    resumo = {
        "lotes": 0,
        "coords_atribuidas_total": 0,
        "abortado_site": False,
        "timeout": False,
        "dry_run": dry_run,
    }

    if dry_run:
        pendentes = (
            Pedido.objects.filter(Q(lat__isnull=True) | Q(lng__isnull=True))
            .exclude(codpost_dest__isnull=True)
            .exclude(codpost_dest="")
        )
        if filial_id:
            pendentes = pendentes.filter(filial_id=filial_id)
        resumo["pendentes"] = pendentes.count()
        return resumo

    if not cache.add("geocode_cp_pt:comando", "1", timeout=GEOCODE_TIMEOUT_DIARIO_SEG):
        resumo["erro"] = "Comando já em execução."
        return resumo

    inicio = time.monotonic()
    try:
        while time.monotonic() - inicio < GEOCODE_TIMEOUT_DIARIO_SEG:
            filial_ids = list(filiais_com_pedidos_sem_coord())
            if filial_id is not None:
                filial_ids = [fid for fid in filial_ids if fid == filial_id]
            if not filial_ids:
                break

            progresso = False
            for fid in filial_ids:
                from pages.filial.models import Filial

                try:
                    filial = Filial.objects.get(pk=fid)
                except Filial.DoesNotExist:
                    continue

                ids = listar_ids_pedidos_sem_coord(filial, limite=GEOCODE_LOTE_PEDIDOS)
                if not ids:
                    continue

                stats = atribuir_coordenadas_pedidos(
                    filial,
                    ids,
                    origem="comando",
                    max_processar=GEOCODE_LOTE_PEDIDOS,
                    skip_lock=True,
                )
                resumo["lotes"] += 1
                resumo["coords_atribuidas_total"] += stats["coords_atribuidas"]
                progresso = progresso or stats["coords_atribuidas"] > 0

                if not stats["site_ok"]:
                    resumo["abortado_site"] = True
                    return resumo

            if not progresso:
                break
            if not existe_pendente_global():
                break
            time.sleep(GEOCODE_INTERVALO_LOTE_SEG)

        if time.monotonic() - inicio >= GEOCODE_TIMEOUT_DIARIO_SEG and existe_pendente_global():
            resumo["timeout"] = True
        resumo["restantes_global"] = (
            Pedido.objects.filter(Q(lat__isnull=True) | Q(lng__isnull=True))
            .exclude(codpost_dest__isnull=True)
            .exclude(codpost_dest="")
            .count()
        )
        return resumo
    finally:
        cache.delete("geocode_cp_pt:comando")
