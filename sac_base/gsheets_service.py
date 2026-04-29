"""
Utilitário para integração com o Google Sheets via Service Account.

Configuração:
  - Variável de ambiente GOOGLE_SHEETS_CREDENTIALS: conteúdo JSON do arquivo
    de credenciais da Service Account (ou o mesmo conteúdo em base64).
  - Por filial: campos gsheets_spreadsheet_id e gsheets_sheet_name em FilialConfig.
"""
from __future__ import annotations

import base64
import json
import os

import gspread
from google.oauth2.service_account import Credentials

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]


def _load_credentials_dict() -> dict:
    raw = os.environ.get("GOOGLE_SHEETS_CREDENTIALS", "").strip()
    if not raw:
        raise ValueError(
            "Variável de ambiente GOOGLE_SHEETS_CREDENTIALS não está configurada."
        )

    # 1. Tenta JSON directo
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 2. Tenta como caminho de ficheiro
    if os.path.isfile(raw):
        try:
            with open(raw, encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            raise ValueError(
                f"Não foi possível ler o ficheiro de credenciais '{raw}': {exc}"
            )

    # 3. Tenta base64
    try:
        return json.loads(base64.b64decode(raw).decode())
    except Exception:
        pass

    raise ValueError(
        "GOOGLE_SHEETS_CREDENTIALS deve conter o JSON das credenciais, "
        "o caminho para o ficheiro JSON, ou o conteúdo em base64."
    )


def _build_client() -> gspread.Client:
    creds_dict = _load_credentials_dict()
    creds = Credentials.from_service_account_info(creds_dict, scopes=_SCOPES)
    return gspread.authorize(creds)


def append_devolucao_rows(
    spreadsheet_id: str,
    sheet_name: str,
    rows: list[list],
) -> int:
    """
    Acrescenta linhas à planilha indicada.

    Formato de cada linha:
      [None, referencia, tipo, motivo, palete, volume, data, obs]
      (None → coluna A vazia; dados nas colunas B–H)

    Retorna o número de linhas enviadas.
    """
    if not rows:
        return 0
    client = _build_client()
    sheet = client.open_by_key(spreadsheet_id).worksheet(sheet_name)

    # Busca todas as linhas existentes
    all_values = sheet.get_all_values()

    def is_row_filled_ah(row):
        # Considera preenchida se pelo menos uma das colunas A-H tem valor não vazio
        return any((str(row[i]).strip() != "" if i < len(row) else False) for i in range(8))

    # Procura de baixo para cima a última linha preenchida (A-H)
    last_filled_idx = None
    for idx in range(len(all_values) - 1, -1, -1):
        if is_row_filled_ah(all_values[idx]):
            last_filled_idx = idx
            break

    # Se não encontrou nenhuma linha preenchida, começa na primeira linha
    if last_filled_idx is None:
        last_filled_idx = -1

    # Calcula o range para update
    start_row = last_filled_idx + 2  # 1-based, linha após a última preenchida
    end_row = start_row + len(rows) - 1
    cell_range = f"A{start_row}:H{end_row}"

    # Prepara os dados para 8 colunas
    values_to_write = [r[:8] + [""] * (8 - len(r)) if len(r) < 8 else r[:8] for r in rows]
    sheet.update(cell_range, values_to_write, value_input_option="USER_ENTERED")
    return len(rows)
