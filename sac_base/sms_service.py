"""
Serviço de envio de SMS via BulkGate Simple Transactional API.

Credenciais obrigatórias (variáveis de ambiente):
  BULKGATE_APP_ID    — Application ID gerado no portal BulkGate
  BULKGATE_APP_TOKEN — Application Token gerado no portal BulkGate
"""

import logging
import os
import re
import time
from collections.abc import Callable
from datetime import date

import requests

logger = logging.getLogger(__name__)

BULKGATE_URL = "https://portal.bulkgate.com/api/1.0/simple/transactional"

# Nomes dos dias da semana por sigla ISO 3166-1 alpha-3 do país de atuação.
# 0 = segunda-feira … 6 = domingo  (alinhado com date.weekday())
_DIAS_PT = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
_DIAS_SEMANA: dict[str, list[str]] = {
    "PRT": _DIAS_PT,
    "BRA": _DIAS_PT,
    # aliases alpha-2 por precaução
    "PT":  _DIAS_PT,
    "BR":  _DIAS_PT,
    "ESP": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"],
    "ES":  ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"],
    "FRA": ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"],
    "FR":  ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"],
    "DEU": ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"],
    "DE":  ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"],
    "ITA": ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"],
    "IT":  ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"],
    "GBR": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "USA": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "GB":  ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "US":  ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
}
# Fallback: português (país mais comum no projeto)
_DIAS_DEFAULT = _DIAS_PT

HORARIO_PERIODO = {
    "MANHA": "09:00 as 14:00",
    "TARDE": "14:00 as 20:00",
}

# DDI padrão caso o pais_atuacao não esteja configurado
_DDI_FALLBACK = "351"

# Reintentos HTTP (manual + automático + resumo) para erros típicos de quota/rede.
MAX_TENTATIVAS_HTTP_BULKGATE = 8
_BACKOFF_SEGUNDOS_BULKGATE = (2, 4, 8, 16, 24, 45, 75, 120)
_TRANSIENT_ERR_MARKERS = (
    "quota",
    "rate",
    "429",
    "timeout",
    "timed out",
    "temporar",
    "temporary",
    "connection",
    "try again",
    "hourly",
    "503",
    "502",
    "504",
    "exhausted",
)

# BulkGate: quando o erro é explicitamente "quota horária/diária de mensagens esgotada",
# retries com backoff curto na mesma execução não recuperam — só consomem tempo e chamadas.
_QUOTA_PERIODO_SEM_RETRY_CURTO = (
    "hourly transaction messages quota",
    "daily transaction messages quota",
)


def erro_sms_transiente_para_retry(mensagem_erro: str) -> bool:
    if not mensagem_erro:
        return False
    m = mensagem_erro.lower()
    if any(marker in m for marker in _QUOTA_PERIODO_SEM_RETRY_CURTO):
        return False
    return any(k in m for k in _TRANSIENT_ERR_MARKERS)


def normalizar_numero(numero: str, ddi_padrao: str = _DDI_FALLBACK) -> str | None:
    """
    Normaliza um número de telefone para o formato internacional exigido pela
    BulkGate (apenas dígitos, sem '+', com DDI).

    Regras aplicadas (nesta ordem):
      1. Remove espaços, hífens, parênteses e pontos.
      2. Se começa com '+' → remove o '+', mantém o restante (DDI já incluso).
      3. Se começa com '00' → remove o '00', mantém o restante (DDI já incluso).
      4. Se o número já começa com o DDI padrão (sem '+') → mantém como está.
      5. Caso contrário → prefixa com o DDI padrão (número local sem DDI).

    O ddi_padrao deve ser somente os dígitos do DDI, sem '+' (ex.: "351", "55").

    Retorna None se o resultado não contiver pelo menos 7 dígitos.
    """
    if not numero:
        return None

    # Limpa separadores comuns
    limpo = re.sub(r"[\s\-\(\)\.]", "", numero)

    # Garante que ddi_padrao seja apenas dígitos
    ddi = re.sub(r"\D", "", ddi_padrao or _DDI_FALLBACK)

    if limpo.startswith("+"):
        # Ex.: +351912345678 → 351912345678
        normalizado = limpo[1:]
    elif limpo.startswith("00"):
        # Ex.: 00351912345678 → 351912345678
        normalizado = limpo[2:]
    elif ddi and limpo.startswith(ddi):
        # Ex.: 351912345678 (já tem DDI) → mantém
        normalizado = limpo
    else:
        # Ex.: 912345678 → 351912345678
        normalizado = ddi + limpo

    # Valida: apenas dígitos e comprimento mínimo
    if not re.fullmatch(r"\d{7,}", normalizado):
        logger.warning("BulkGate: número ignorado após normalização: %r → %r", numero, normalizado)
        return None

    return normalizado


def dia_semana_para_pais(dt: date, sigla_pais: str) -> str:
    """Retorna o nome do dia da semana na língua do país (sigla ISO 3166-1 alpha-3)."""
    dias = _DIAS_SEMANA.get((sigla_pais or "").upper(), _DIAS_DEFAULT)
    return dias[dt.weekday()]


def montar_mensagem(template: str, dt: date, periodo: str, sigla_pais: str) -> str:
    """
    Substitui os 3 placeholders no template FilialConfig.sms_padrao_1:
      #dia_da_semana# → nome do dia da semana (idioma do país de atuação)
      #dd/mm/aaaa#    → data no formato dd/mm/aaaa  (ex.: 25/04/2026)
      #periodo#       → horário do período ("09:00 as 14:00" ou "14:00 as 20:00")
    """
    dia = dia_semana_para_pais(dt, sigla_pais)
    data_fmt = dt.strftime("%d/%m/%Y")
    horario = HORARIO_PERIODO.get(periodo, "")

    resultado = template
    resultado = resultado.replace("#dia_da_semana#", dia)
    resultado = resultado.replace("#dd/mm/aaaa#", data_fmt)
    resultado = resultado.replace("#periodo#", horario)
    return resultado


def enviar_sms_bulkgate(numero: str, mensagem: str, ddi_padrao: str = _DDI_FALLBACK) -> dict:
    """
    Envia um SMS via BulkGate Simple Transactional API.

    O número é normalizado automaticamente antes do envio (veja normalizar_numero).
    ddi_padrao deve ser os dígitos do DDI sem '+' (ex.: "351" para Portugal).

    Retorna dict com:
      {"sucesso": True,  "sms_id": "..."}   — em caso de sucesso
      {"sucesso": False, "erro": "..."}      — em caso de falha
    """
    app_id = os.environ.get("BULKGATE_APP_ID", "")
    app_token = os.environ.get("BULKGATE_APP_TOKEN", "")

    if not app_id or not app_token:
        logger.error(
            "BulkGate: credenciais não configuradas "
            "(defina BULKGATE_APP_ID e BULKGATE_APP_TOKEN)."
        )
        return {"sucesso": False, "erro": "Credenciais BulkGate não configuradas."}

    numero_norm = normalizar_numero(numero, ddi_padrao)
    if not numero_norm:
        return {"sucesso": False, "erro": f"Número inválido: {numero!r}"}

    payload = {
        "application_id": app_id,
        "application_token": app_token,
        "number": numero_norm,
        "text": mensagem,
    }
    try:
        resp = requests.post(BULKGATE_URL, json=payload, timeout=15)
        try:
            data = resp.json()
        except ValueError as json_exc:
            # resp.json() pode lançar ValueError/JSONDecodeError (não é RequestException)
            logger.error("BulkGate: resposta não-JSON para %s (status %s)", numero_norm, resp.status_code)
            return {"sucesso": False, "erro": f"Resposta inválida da BulkGate (não-JSON): {json_exc}"}
        if resp.status_code == 200 and "data" in data:
            return {"sucesso": True, "sms_id": data["data"].get("sms_id")}
        erro = data.get("error", "Erro desconhecido.")
        logger.error("BulkGate erro para %s: %s", numero_norm, data)
        return {"sucesso": False, "erro": erro}
    except requests.RequestException as exc:
        logger.exception("BulkGate: falha na requisição para %s", numero_norm)
        return {"sucesso": False, "erro": str(exc)}


def enviar_sms_bulkgate_resiliente(
    numero: str,
    mensagem: str,
    ddi_padrao: str = _DDI_FALLBACK,
    *,
    log_prefix: str = "",
    on_retry: Callable[[int, str, int], None] | None = None,
) -> dict:
    """
    Chama BulkGate com reintentos e backoff para erros considerados transientes
    (quota, rate limit, timeouts, 5xx). Erros definitivos (credenciais, número inválido)
    não repetem.
    """
    ultimo: dict = {"sucesso": False, "erro": ""}
    for tentativa in range(MAX_TENTATIVAS_HTTP_BULKGATE):
        ultimo = enviar_sms_bulkgate(numero, mensagem, ddi_padrao)
        if ultimo.get("sucesso"):
            return ultimo
        erro = ultimo.get("erro") or ""
        if not erro_sms_transiente_para_retry(erro):
            return ultimo
        if tentativa >= MAX_TENTATIVAS_HTTP_BULKGATE - 1:
            break
        espera = _BACKOFF_SEGUNDOS_BULKGATE[min(tentativa, len(_BACKOFF_SEGUNDOS_BULKGATE) - 1)]
        if on_retry:
            on_retry(tentativa + 1, erro, espera)
        logger.warning(
            "%sBulkGate retry %s/%s após erro transiente; espera %ss: %s",
            log_prefix,
            tentativa + 1,
            MAX_TENTATIVAS_HTTP_BULKGATE,
            espera,
            erro[:300],
        )
        time.sleep(espera)
    return ultimo

