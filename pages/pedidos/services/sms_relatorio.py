"""
Regras de elegibilidade, verificação e execução do envio SMS do relatório (filial + data).

Critério de elegibilidade (alinhado com o automático): `TentativaEntrega` na data,
`pedido__filial`, `estado` em `ESTADOS_SEGUE_PARA_ENTREGA`, período preenchido,
`exclude_tentativas_com_data_posterior`, e `sms_enviado=False` no envio.
"""

from __future__ import annotations

import logging
from datetime import date

from django.db.models import QuerySet

from pages.filial.models import Filial
from pages.pedidos.models import (
    ESTADOS_SEGUE_PARA_ENTREGA,
    TentativaEntrega,
    exclude_tentativas_com_data_posterior,
)
from sac_base.sms_service import HORARIO_PERIODO, montar_mensagem, enviar_sms_bulkgate_resiliente

logger = logging.getLogger(__name__)


def ler_templates_sms_filial(filial) -> tuple[str, str]:
    """sms_padrao_1 (MANHÃ) e sms_padrao_2 (TARDE; fallback = manhã)."""
    try:
        manha = filial.config.sms_padrao_1 or ""
        tarde = filial.config.sms_padrao_2 or manha
        return manha, tarde
    except Exception:
        return "", ""


def sigla_pais_operacao_filial(filial) -> str:
    if getattr(filial, "pais_atuacao", None):
        return filial.pais_atuacao.sigla or ""
    return ""


def ddi_padrao_operacao_filial(filial) -> str:
    if getattr(filial, "pais_atuacao", None):
        codigo_tel = (filial.pais_atuacao.codigo_tel or "").strip().lstrip("+")
        if codigo_tel:
            return codigo_tel
    return "351"


def qs_tentativas_sms_regra_base(filial, dt) -> QuerySet[TentativaEntrega]:
    """Tentativas na data com período e estado elegíveis (sem filtrar sms_enviado)."""
    return exclude_tentativas_com_data_posterior(
        TentativaEntrega.objects.filter(
            data_tentativa=dt,
            pedido__filial=filial,
            estado__in=ESTADOS_SEGUE_PARA_ENTREGA,
        )
        .exclude(periodo__isnull=True)
        .exclude(periodo="")
        .select_related("pedido")
    )


def qs_tentativas_sms_pendentes_envio(filial, dt) -> QuerySet[TentativaEntrega]:
    """Conjunto que o envio manual ainda pode processar (sms_enviado=False)."""
    return qs_tentativas_sms_regra_base(filial, dt).filter(sms_enviado=False)


def estado_verificacao_sms_dia(filial, dt) -> dict:
    """
    Estado agregado do dia para SMS: quantos ainda faltam (com telefone),
    quantos sem telefone, e se todos os “válidos com telefone” já têm sms_enviado.
    """
    qs = qs_tentativas_sms_regra_base(filial, dt)
    total_regra = 0
    sem_telefone = 0
    com_telefone = 0
    com_telefone_pendentes: list[int] = []

    for mov in qs.iterator():
        total_regra += 1
        pedido = mov.pedido
        tem_tel = bool(
            (pedido.fone_dest or "").strip() or (pedido.fone_dest2 or "").strip()
        )
        if not tem_tel:
            sem_telefone += 1
            continue
        com_telefone += 1
        if not mov.sms_enviado:
            com_telefone_pendentes.append(mov.id)

    ids_pendentes = com_telefone_pendentes[:200]
    dia_completo = len(com_telefone_pendentes) == 0

    mensagens: list[str] = []
    if sem_telefone:
        mensagens.append(
            f"{sem_telefone} registro(s) sem telefone no pedido (não enviáveis por SMS)."
        )
    if com_telefone_pendentes:
        mensagens.append(
            f"{len(com_telefone_pendentes)} registro(s) com telefone ainda sem SMS enviado para esta data."
        )
    if dia_completo and com_telefone:
        mensagens.append(
            "Todos os registros válidos com telefone para esta data já têm SMS enviado."
        )

    return {
        "data": dt.isoformat(),
        "filial_id": getattr(filial, "id", None),
        "total_elegiveis_estado_periodo": total_regra,
        "com_telefone": com_telefone,
        "sem_telefone": sem_telefone,
        "pendentes_com_telefone": len(com_telefone_pendentes),
        "ids_pendentes_com_telefone": ids_pendentes,
        "dia_completo_todos_com_telefone_enviados": dia_completo,
        "mensagens": mensagens,
    }


def queryset_tentativas_envio_manual_por_ids(filial_ativa, dt: date, ids) -> QuerySet[TentativaEntrega]:
    """Pendentes na data `dt` ∩ ids (mesma regra que o automático + filtro de data explícito)."""
    if not ids:
        return TentativaEntrega.objects.none()
    return (
        qs_tentativas_sms_pendentes_envio(filial_ativa, dt)
        .filter(id__in=ids)
        .select_related(
            "pedido",
            "pedido__filial",
            "pedido__filial__config",
            "pedido__filial__pais_atuacao",
        )
    )


def executar_envio_sms_relatorio_manual(
    filial_ativa,
    dt: date,
    tentativas: list[TentativaEntrega],
) -> dict:
    """
    Executa envio BulkGate + marca `sms_enviado` + SMS de resumo (se configurado).

    Retorno em caso de sucesso: ``{"ok": True, ...}`` com chaves alinhadas ao JsonResponse.
    Em falha de negócio (templates): ``{"ok": False, "mensagem": str}``.
    """
    if not tentativas:
        return {"ok": False, "mensagem": "Nenhum registro elegível encontrado."}

    filial = tentativas[0].pedido.filial
    template_manha, template_tarde = ler_templates_sms_filial(filial)

    if not template_manha and not template_tarde:
        return {
            "ok": False,
            "mensagem": "Nenhum template SMS configurado (sms_padrao_1/2) para esta filial.",
        }

    sigla_pais = sigla_pais_operacao_filial(filial)
    ddi_padrao = ddi_padrao_operacao_filial(filial)

    enviados = 0
    erros = 0
    ids_enviados: list[int] = []
    erros_detalhe: list[str] = []
    contagem_periodo: dict[str, int] = {}

    for mov in tentativas:
        pedido = mov.pedido
        referencia = pedido.pedido or str(pedido.id_vonzu)
        fones = [f.strip() for f in [pedido.fone_dest or "", pedido.fone_dest2 or ""] if f.strip()]
        if not fones:
            erros += 1
            erros_detalhe.append(f"{referencia}: sem número de telefone.")
            continue

        if mov.periodo == "TARDE":
            template_msg = template_tarde
        else:
            template_msg = template_manha

        if not template_msg:
            erros += 1
            erros_detalhe.append(f"{referencia}: template para período '{mov.periodo}' não configurado.")
            continue

        try:
            mensagem = montar_mensagem(template_msg, dt, mov.periodo, sigla_pais)
        except Exception as exc:
            erros += 1
            erros_detalhe.append(f"{referencia}: erro na montagem da mensagem — {exc}")
            continue

        sucesso_algum = False
        for fone in fones:
            resultado = enviar_sms_bulkgate_resiliente(
                fone,
                mensagem,
                ddi_padrao,
                log_prefix=f"[{referencia}] ",
            )
            if resultado.get("sucesso"):
                sucesso_algum = True
            else:
                erros += 1
                erros_detalhe.append(
                    f"{referencia} ({fone}): {resultado.get('erro', 'Erro desconhecido.')}"
                )

        if sucesso_algum:
            mov.sms_enviado = True
            mov.save(update_fields=["sms_enviado"])
            enviados += 1
            ids_enviados.append(mov.id)
            contagem_periodo[mov.periodo] = contagem_periodo.get(mov.periodo, 0) + 1

    try:
        filial_resumo = Filial.objects.only("numero", "sms_confirm", "id").get(pk=filial_ativa.pk)
    except Filial.DoesNotExist:
        filial_resumo = filial
    numero_resumo = (filial_resumo.numero or "").strip()

    resumo_filial: dict = {"tentado": False, "ok": None, "detalhe": None}
    if filial_resumo.sms_confirm and numero_resumo and enviados > 0:
        partes_resumo = [f"SMS enviados em {dt.strftime('%d/%m/%Y')}:"]
        for periodo, qtd in sorted(contagem_periodo.items()):
            horario = HORARIO_PERIODO.get(periodo, periodo)
            partes_resumo.append(f"  {periodo} ({horario}): {qtd}")
        partes_resumo.append(f"Total: {enviados}")
        resumo = "\n".join(partes_resumo)
        _resumo_resultado = enviar_sms_bulkgate_resiliente(
            numero_resumo,
            resumo,
            ddi_padrao,
            log_prefix="[resumo_filial] ",
        )
        if _resumo_resultado.get("sucesso"):
            resumo_filial = {"tentado": True, "ok": True, "detalhe": None}
        else:
            _erro_resumo = _resumo_resultado.get("erro") or "Erro desconhecido."
            resumo_filial = {"tentado": True, "ok": False, "detalhe": _erro_resumo}
            logger.warning(
                "SMS resumo filial falhou (filial_id=%s): %s",
                getattr(filial_resumo, "id", None),
                _erro_resumo,
            )
    else:
        _msgs_omissao = []
        if not filial_resumo.sms_confirm:
            _msgs_omissao.append("confirmação por SMS da filial está desativada")
        if not numero_resumo:
            _msgs_omissao.append("número da filial não está configurado")
        if enviados <= 0:
            _msgs_omissao.append("não houve envios com sucesso nesta operação")
        resumo_filial = {
            "tentado": False,
            "ok": None,
            "detalhe": "; ".join(_msgs_omissao) if _msgs_omissao else "resumo não enviado",
        }

    return {
        "ok": True,
        "enviados": enviados,
        "erros": erros,
        "erros_detalhe": erros_detalhe,
        "ids_enviados": ids_enviados,
        "mensagem": f"{enviados} SMS enviado(s) com sucesso." + (f" {erros} erro(s)." if erros else ""),
        "resumo_filial": resumo_filial,
    }


def complemento_verificacao_solicitacao(
    ids_solicitados: list,
    tentativas_carregadas: list[TentativaEntrega],
) -> dict:
    """IDs pedidos pelo cliente que não entraram no lote elegível (filtro backend)."""
    try:
        solicitados = {int(x) for x in ids_solicitados}
    except (TypeError, ValueError):
        solicitados = set()
    carregados = {m.id for m in tentativas_carregadas}
    nao_elegiveis = sorted(solicitados - carregados)
    return {
        "ids_solicitados_total": len(solicitados),
        "ids_carregados_para_envio": len(carregados),
        "ids_solicitados_nao_elegiveis": nao_elegiveis[:200],
    }
