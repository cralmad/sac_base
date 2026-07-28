"""Probe de headers HTTP para testes de embed (iframe) — hosts em allowlist."""

from __future__ import annotations

from urllib.parse import urlparse

import requests

# Apenas estes hosts podem ser sondados (evita SSRF).
HOSTS_PERMITIDOS = frozenset(
    {
        "app.vonzu.es",
        "vonzu.es",
        "3dboxportugal.enovotms.com",
        "enovotms.com",
    }
)

HEADERS_INTERESSE = (
    "x-frame-options",
    "content-security-policy",
    "content-security-policy-report-only",
    "access-control-allow-origin",
    "access-control-allow-credentials",
    "set-cookie",
    "content-type",
    "www-authenticate",
)


def _host_permitido(hostname: str | None) -> bool:
    if not hostname:
        return False
    host = hostname.lower().rstrip(".")
    if host in HOSTS_PERMITIDOS:
        return True
    return any(host.endswith(f".{permitido}") for permitido in HOSTS_PERMITIDOS)


def validar_url_probe(url: str) -> tuple[str | None, str | None]:
    """
    Valida URL para probe. Retorna (url_normalizada, erro).
    Apenas https e hosts da allowlist.
    """
    raw = (url or "").strip()
    if not raw:
        return None, "URL obrigatória."
    parsed = urlparse(raw)
    if parsed.scheme != "https":
        return None, "Apenas HTTPS é permitido."
    if not _host_permitido(parsed.hostname):
        return None, "Host fora da allowlist de teste."
    if parsed.username or parsed.password:
        return None, "URL com credenciais não é permitida."
    return raw, None


def interpretar_embed(headers_lower: dict[str, str]) -> dict:
    """Heurística legível sobre possibilidade de iframe (sem sessão)."""
    xfo = (headers_lower.get("x-frame-options") or "").strip().lower()
    csp = headers_lower.get("content-security-policy") or ""
    csp_ro = headers_lower.get("content-security-policy-report-only") or ""

    bloqueios = []
    if xfo in ("deny", "sameorigin"):
        bloqueios.append(f"X-Frame-Options: {xfo}")
    elif xfo:
        bloqueios.append(f"X-Frame-Options (valor não standard): {xfo}")

    for label, policy in (("CSP", csp), ("CSP-Report-Only", csp_ro)):
        if "frame-ancestors" not in policy.lower():
            continue
        # Extração grosseira: se frame-ancestors existe e não é *, pode bloquear
        parte = policy.lower()
        idx = parte.find("frame-ancestors")
        trecho = policy[idx : idx + 120] if idx >= 0 else policy
        if "frame-ancestors *" in parte or "frame-ancestors'*'" in parte.replace(" ", ""):
            continue
        if "frame-ancestors 'none'" in parte or 'frame-ancestors "none"' in parte:
            bloqueios.append(f"{label}: frame-ancestors 'none'")
        elif "frame-ancestors 'self'" in parte and "*" not in trecho.lower():
            bloqueios.append(f"{label}: frame-ancestors provavelmente só 'self' ({trecho!r})")
        else:
            bloqueios.append(f"{label}: frame-ancestors presente ({trecho!r})")

    if bloqueios:
        veredicto = "provavelmente_bloqueado"
        detalhe = "O alvo envia cabeçalhos que tipicamente impedem embed cross-origin."
    else:
        veredicto = "sem_bloqueio_explicito"
        detalhe = (
            "Sem X-Frame-Options / frame-ancestors restritivo na resposta sondada. "
            "Ainda assim cookies SameSite, login e CSP do browser podem impedir o embed útil."
        )

    return {
        "veredicto": veredicto,
        "detalhe": detalhe,
        "bloqueios": bloqueios,
        "nota_same_origin": (
            "Mesmo com iframe a carregar, o JS desta página NÃO pode ler nem clicar "
            "no DOM do site externo (same-origin policy)."
        ),
    }


def sondar_headers_url(url: str, *, timeout: float = 12.0) -> dict:
    """
    Faz GET (seguido de HEAD se necessário) e devolve status + headers de interesse.
    """
    url_ok, erro = validar_url_probe(url)
    if erro:
        return {"ok": False, "erro": erro}

    try:
        resp = requests.get(
            url_ok,
            timeout=timeout,
            allow_redirects=True,
            headers={"User-Agent": "SacBase-IframeEmbedProbe/1.0"},
        )
    except requests.RequestException as exc:
        return {"ok": False, "erro": f"Falha de rede ao contactar o alvo: {exc.__class__.__name__}."}

    # Normalizar headers (última ocorrência; Set-Cookie pode ser múltiplo)
    headers_lower: dict[str, str] = {}
    for chave, valor in resp.headers.items():
        k = chave.lower()
        if k == "set-cookie":
            # Mascarar valor sensível; só indicar presença / atributos grosseiros
            raw = str(valor)
            attrs = []
            low = raw.lower()
            for atr in ("httponly", "secure", "samesite=none", "samesite=lax", "samesite=strict"):
                if atr in low:
                    attrs.append(atr)
            headers_lower[k] = f"(presente; attrs~{','.join(attrs) or 'n/d'})"
        elif k in HEADERS_INTERESSE or k.startswith("x-"):
            headers_lower[k] = str(valor)

    interesse = {h: headers_lower[h] for h in HEADERS_INTERESSE if h in headers_lower}

    return {
        "ok": True,
        "url_pedida": url_ok,
        "url_final": resp.url,
        "status_code": resp.status_code,
        "headers_interesse": interesse,
        "headers_x": {k: v for k, v in headers_lower.items() if k.startswith("x-")},
        "interpretacao": interpretar_embed(headers_lower),
    }
