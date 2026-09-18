"""
Utilitário para integração com o Google Sheets via Service Account.

Configuração:
  - Variável de ambiente GOOGLE_SHEETS_CREDENTIALS: conteúdo JSON do arquivo
    de credenciais da Service Account (ou o mesmo conteúdo em base64).
  - Por filial (FilialConfig): gsheets_spreadsheet_id / gsheets_sheet_name (ex.: devoluções);
    gsheets_spreadsheet_id_2 / gsheets_sheet_name_2 (segunda planilha/aba).
"""
from __future__ import annotations

import gspread
from google.oauth2.service_account import Credentials

from sac_base.google_credentials import load_google_service_account_info

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]


def _build_client() -> gspread.Client:
    creds_dict = load_google_service_account_info()
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


def _ultima_linha_com_coluna_b_preenchida(all_values: list[list]) -> int | None:
    """Índice 0-based da última linha com coluna B (índice 1) não vazia."""
    for idx in range(len(all_values) - 1, -1, -1):
        row = all_values[idx]
        if len(row) > 1 and str(row[1]).strip():
            return idx
    return None


def append_logistica_motorista_rows(
    spreadsheet_id: str,
    sheet_name: str,
    rows: list[list],
) -> int:
    """
    Acrescenta linhas à planilha (relatório logística motorista).

    Formato de cada linha (colunas A–E):
      [data_tentativa_fmt, referencia_pedido, "Outro", "", estado_e_obs]

    A próxima linha vazia é calculada apenas pela coluna B (referência).
    """
    if not rows:
        return 0
    client = _build_client()
    sheet = client.open_by_key(spreadsheet_id).worksheet(sheet_name)
    all_values = sheet.get_all_values()
    last_filled_idx = _ultima_linha_com_coluna_b_preenchida(all_values)
    if last_filled_idx is None:
        last_filled_idx = -1
    start_row = last_filled_idx + 2
    end_row = start_row + len(rows) - 1
    cell_range = f"A{start_row}:E{end_row}"
    values_to_write = [r[:5] + [""] * (5 - len(r)) if len(r) < 5 else r[:5] for r in rows]
    sheet.update(cell_range, values_to_write, value_input_option="USER_ENTERED")
    return len(rows)
