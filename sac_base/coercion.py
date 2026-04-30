"""
Coerção de valores vindos de formulários web (SisVar) ou CSV (importação).
Evita duplicar parse_int/parse_date entre views e importador.
"""
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from django.utils import timezone

Context = Literal["form", "csv"]

_DATETIME_FORMATS_FORM = ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M")
_DATETIME_FORMATS_CSV = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d")


def parse_int(valor, *, context: Context = "form"):
    """Inteiro opcional. `csv` aceita decimais na string (ex.: \"10.0\")."""
    if context == "form":
        if valor in (None, ""):
            return None
        try:
            return int(valor)
        except (TypeError, ValueError):
            return None
    s = (str(valor).strip() if valor is not None else "")
    if not s:
        return None
    try:
        return int(float(s.replace(",", ".")))
    except (ValueError, TypeError):
        return None


def parse_date(valor, fmt: str = "%Y-%m-%d"):
    """Data opcional; string vazia ou só espaços → None."""
    if valor in (None, ""):
        return None
    s = str(valor).strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, fmt).date()
    except ValueError:
        return None


def parse_decimal(valor, *, context: Context = "form"):
    if context == "form":
        if valor in (None, ""):
            return None
        try:
            return Decimal(str(valor).replace(",", "."))
        except (InvalidOperation, ValueError):
            return None
    s = (str(valor).strip() if valor is not None else "")
    if not s:
        return None
    try:
        return Decimal(s.replace(",", "."))
    except InvalidOperation:
        return None


def parse_datetime(valor, *, context: Context = "form"):
    """Datetime com timezone Django; formatos dependem do contexto."""
    formats = _DATETIME_FORMATS_CSV if context == "csv" else _DATETIME_FORMATS_FORM
    if valor in (None, ""):
        return None
    texto = str(valor).strip()
    if not texto:
        return None
    for fmt in formats:
        try:
            dt = datetime.strptime(texto, fmt)
            return timezone.make_aware(dt) if timezone.is_naive(dt) else dt
        except ValueError:
            continue
    return None
