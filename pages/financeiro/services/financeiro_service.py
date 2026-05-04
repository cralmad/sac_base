"""
Executor financeiro: transações, filial_id, hierarquia RF → Faturamento → Parcela,
recalc de agregados e validações do plano.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any, Iterable, Sequence

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from pages.financeiro import constants as fin_constants
from pages.financeiro.models import (
    Faturamento,
    FaturamentoFormaPagamento,
    FaturamentoRegistroFinanceiro,
    ParcelaFaturamento,
    ParcelaFaturamentoStatus,
    RegistroFinanceiro,
    RegistroFinanceiroStatus,
)
from pages.financeiro.registry import merge_regras
from pages.financeiro.services import transferencia as transferencia_svc

logger = logging.getLogger(__name__)

METADADOS_OBSERVACAO_MAX = 4000


class FinanceiroService:
    """Fachada única para persistência consistente do módulo financeiro."""

    # --- Metadados (contrato §9.5) ---

    @staticmethod
    def montar_observacao_com_metadados(
        observacao_base: str,
        metadados: dict[str, Any] | None,
    ) -> str:
        """
        Anexa metadados de domínio à observação (chaves sem prefixo fin__).
        Chaves `fin__*` são reservadas ao executor e podem alterar comportamento futuro.
        """
        base = (observacao_base or "").strip()
        if not metadados:
            return base
        dominio = {
            k: v
            for k, v in metadados.items()
            if not str(k).startswith(fin_constants.FIN_META_PREFIX)
        }
        if not dominio:
            return base
        try:
            extra = json.dumps(dominio, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            extra = str(dominio)
        if len(extra) > METADADOS_OBSERVACAO_MAX:
            extra = extra[:METADADOS_OBSERVACAO_MAX] + "…"
        if base:
            return f"{base}\n[metadados]{extra}"
        return f"[metadados]{extra}"

    # --- Agregados ---

    @staticmethod
    @transaction.atomic
    def recalcular_agregados_registro(registro_id: int) -> None:
        """
        valor_fat = soma dos abatimentos no through; valor_rest = valor - valor_fat.
        MVP: apenas through (parcelas liquidadas adicionais podem somar em evolução).
        """
        reg = (
            RegistroFinanceiro.objects.select_for_update()
            .filter(pk=registro_id)
            .first()
        )
        if not reg:
            return
        total = (
            FaturamentoRegistroFinanceiro.objects.filter(registro_financeiro_id=registro_id).aggregate(
                t=Sum("valor_abatido")
            )["t"]
            or Decimal("0")
        )
        reg.valor_fat = total.quantize(Decimal("0.01"))
        reg.valor_rest = (reg.valor - reg.valor_fat).quantize(Decimal("0.01"))
        if reg.valor_rest < 0:
            logger.error("valor_rest negativo para RF %s", registro_id)
            raise ValidationError("Inconsistência: valor faturado supera o valor do título.")
        if reg.valor_rest == 0 and reg.valor > 0:
            reg.status = RegistroFinanceiroStatus.LIQUIDADO
        elif reg.valor_fat > 0:
            reg.status = RegistroFinanceiroStatus.PARCIAL
        else:
            reg.status = RegistroFinanceiroStatus.ABERTO
        reg.save(update_fields=["valor_fat", "valor_rest", "status", "updated_at"])

    @classmethod
    def recalcular_agregados_varios(cls, registro_ids: Iterable[int]) -> None:
        for rid in set(registro_ids):
            cls.recalcular_agregados_registro(rid)

    # --- Contraparte pagamento ---

    @staticmethod
    def contar_contrapartes_distintas(registros: Sequence[RegistroFinanceiro]) -> int:
        chaves: set[tuple[int | None, int | None]] = set()
        for r in registros:
            chaves.add((r.contraparte_content_type_id, r.contraparte_object_id))
        chaves.discard((None, None))
        return len(chaves)

    @staticmethod
    def validar_contraparte_pagamento_obrigatoria(
        faturamento: Faturamento,
        registros: Sequence[RegistroFinanceiro],
    ) -> None:
        if FinanceiroService.contar_contrapartes_distintas(registros) > 1:
            if not faturamento.contraparte_pagamento_object_id:
                raise ValidationError(
                    "Faturamento com títulos de contrapartes distintas exige contraparte_pagamento."
                )

    # --- Parcelas vs formas ---

    @classmethod
    @transaction.atomic
    def gerar_parcelas_para_faturamento(cls, faturamento_id: int) -> list[ParcelaFaturamento]:
        """
        MVP: uma parcela por linha de FaturamentoFormaPagamento com valor integral.
        Dinheiro/PIX sem parcelamento: status LIQUIDADO se conta de custodia existir (senao ABERTO).
        """
        fat = Faturamento.objects.get(pk=faturamento_id)
        ParcelaFaturamento.objects.filter(faturamento=fat).delete()
        criadas: list[ParcelaFaturamento] = []
        for linha in fat.linhas_forma_pagamento.select_related("forma_pagamento", "forma_pagamento__conta_custodia_padrao"):
            forma = linha.forma_pagamento
            conta = forma.conta_custodia_padrao
            status = ParcelaFaturamentoStatus.ABERTO
            if not forma.aceita_parcelamento and conta is not None:
                status = ParcelaFaturamentoStatus.LIQUIDADO
            p = ParcelaFaturamento.objects.create(
                faturamento=fat,
                faturamento_forma_pagamento=linha,
                forma_pagamento=forma,
                valor=linha.valor,
                conta_custodia=conta,
                status=status,
            )
            criadas.append(p)
        cls.validar_soma_parcelas_vs_formas(faturamento_id)
        return criadas

    @staticmethod
    def validar_soma_parcelas_vs_formas(faturamento_id: int) -> None:
        teto = (
            FaturamentoFormaPagamento.objects.filter(faturamento_id=faturamento_id).aggregate(
                t=Sum("valor")
            )["t"]
            or Decimal("0")
        )
        soma_parcelas = (
            ParcelaFaturamento.objects.filter(faturamento_id=faturamento_id).aggregate(t=Sum("valor"))["t"]
            or Decimal("0")
        )
        if soma_parcelas > teto + Decimal("0.0001"):
            raise ValidationError(
                f"Soma das parcelas ({soma_parcelas}) ultrapassa o total das formas de pagamento ({teto})."
            )

    # --- Waterfall through ---

    @staticmethod
    def calcular_waterfall_abatimentos(
        pool: Decimal,
        sequencia_registros: Sequence[tuple[int, int]],
        filial_id: int,
    ) -> list[dict[str, Any]]:
        """
        sequencia_registros: lista (registro_financeiro_id, ordem) já na ordem do usuário.
        Retorna apenas linhas com valor_abatido > 0.
        """
        restante = pool.quantize(Decimal("0.01"))
        saida: list[dict[str, Any]] = []
        nova_ordem = 0
        for reg_id, _ordem_usuario in sequencia_registros:
            if restante <= 0:
                break
            reg = (
                RegistroFinanceiro.objects.select_for_update()
                .filter(pk=reg_id, filial_id=filial_id)
                .first()
            )
            if not reg:
                raise ValidationError(f"Registro financeiro {reg_id} inexistente ou fora da filial.")
            disponivel = reg.valor_rest.quantize(Decimal("0.01"))
            abate = min(restante, disponivel)
            if abate > 0:
                nova_ordem += 1
                saida.append(
                    {
                        "registro_financeiro_id": reg_id,
                        "ordem": nova_ordem,
                        "valor_abatido": abate,
                    }
                )
                restante -= abate
        return saida

    @classmethod
    @transaction.atomic
    def aplicar_waterfall_e_salvar_through(
        cls,
        faturamento: Faturamento,
        pool: Decimal,
        sequencia_registros: Sequence[tuple[int, int]],
    ) -> list[FaturamentoRegistroFinanceiro]:
        """
        Remove vínculos anteriores do faturamento, grava novos (só valor > 0), recalcula agregados.
        """
        filial_id = faturamento.filial_id
        FaturamentoRegistroFinanceiro.objects.filter(faturamento=faturamento).delete()
        linhas = cls.calcular_waterfall_abatimentos(pool, sequencia_registros, filial_id)
        criados: list[FaturamentoRegistroFinanceiro] = []
        rf_ids: set[int] = set()
        for linha in linhas:
            obj = FaturamentoRegistroFinanceiro.objects.create(
                faturamento=faturamento,
                registro_financeiro_id=linha["registro_financeiro_id"],
                filial_id=filial_id,
                ordem=linha["ordem"],
                valor_abatido=linha["valor_abatido"],
            )
            criados.append(obj)
            rf_ids.add(linha["registro_financeiro_id"])
        cls.recalcular_agregados_varios(rf_ids)
        return criados

    # --- Registry merge (exposto para o cérebro) ---

    @staticmethod
    def obter_regras_mescladas(content_type_id: int, overrides: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        return merge_regras(content_type_id, overrides)

    # --- Transferência ---

    @staticmethod
    @transaction.atomic
    def registrar_transferencia_interna(
        *,
        filial_id: int,
        valor: Decimal,
        conta_origem_id: int,
        conta_destino_id: int,
        plano_codigo: str,
        observacao: str = "",
        usuario=None,
    ) -> RegistroFinanceiro:
        return transferencia_svc.registrar_transferencia_interna(
            filial_id=filial_id,
            valor=valor,
            conta_origem_id=conta_origem_id,
            conta_destino_id=conta_destino_id,
            plano_codigo=plano_codigo,
            observacao=observacao,
            usuario=usuario,
        )