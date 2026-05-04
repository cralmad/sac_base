"""
Fluxo automático de SMS (management command `enviar_sms_automatico`).

- Pendentes do dia: mesma queryset que o manual (`sms_relatorio.qs_tentativas_sms_pendentes_envio`).
- Rondas e pausas entre rondas: ver comando; chamadas HTTP usam
  `sac_base.sms_service.enviar_sms_bulkgate_resiliente`.
"""

from __future__ import annotations

from pages.pedidos.models import TentativaEntrega
from pages.pedidos.services.sms_relatorio import qs_tentativas_sms_pendentes_envio

# Rondas de re-leitura de pendentes na BD (filial + dia).
MAX_RONDAS_FILIAL = 60
# Se uma ronda completa não marcou nenhum sucesso mas ainda há pendentes, pausa (quota/rede).
MAX_PAUSAS_SEM_PROGRESSO = 12
PAUSA_SEM_PROGRESSO_SEG = 90


def pedido_tem_telefone_para_sms(pedido) -> bool:
    return bool(
        (pedido.fone_dest or "").strip() or (pedido.fone_dest2 or "").strip()
    )


def listar_pendentes_com_telefone(filial, today) -> list[TentativaEntrega]:
    """Pendentes elegíveis ao automático com pelo menos um telefone no pedido."""
    qs = qs_tentativas_sms_pendentes_envio(filial, today).select_related(
        "pedido", "pedido__filial"
    )
    return [m for m in qs if pedido_tem_telefone_para_sms(m.pedido)]


def contar_pendentes_sem_telefone(filial, today) -> int:
    qs = qs_tentativas_sms_pendentes_envio(filial, today).select_related("pedido")
    return sum(1 for m in qs if not pedido_tem_telefone_para_sms(m.pedido))
