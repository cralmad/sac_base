"""Carrega o JSON da service account Google (Sheets, Gmail, etc.).

Variável GOOGLE_SHEETS_CREDENTIALS: JSON directo, caminho de ficheiro, ou base64.
"""
from __future__ import annotations

import base64
import json
import os


def load_google_service_account_info() -> dict:
    raw = os.environ.get("GOOGLE_SHEETS_CREDENTIALS", "").strip()
    if not raw:
        raise ValueError(
            "Variável de ambiente GOOGLE_SHEETS_CREDENTIALS não está configurada."
        )

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    if os.path.isfile(raw):
        try:
            with open(raw, encoding="utf-8") as f:
                return json.load(f)
        except OSError as exc:
            raise ValueError(
                f"Não foi possível ler o ficheiro de credenciais '{raw}': {exc}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"JSON inválido no ficheiro de credenciais '{raw}'."
            ) from exc

    try:
        return json.loads(base64.b64decode(raw).decode())
    except (ValueError, json.JSONDecodeError):
        pass

    raise ValueError(
        "GOOGLE_SHEETS_CREDENTIALS deve conter o JSON das credenciais, "
        "o caminho para o ficheiro JSON, ou o conteúdo em base64."
    )
