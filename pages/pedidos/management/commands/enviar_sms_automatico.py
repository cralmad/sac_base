"""
Management command: enviar_sms_automatico

Para cada FilialConfig com sms_auto configurado, verifica se a hora actual
de Lisboa já ultrapassou o horário configurado e, se ainda houver
TentativaEntrega elegíveis com sms_enviado=False, envia os SMS.

A guarda contra duplo envio é natural: após o envio os registos ficam com
sms_enviado=True e o command seguinte não encontra mais nada para enviar.

Uso:
    python manage.py enviar_sms_automatico

Heroku Scheduler — recomendado: a cada 10 minutos
    python manage.py enviar_sms_automatico

Flags de teste:
    --force    Ignora a verificação de horário (envia independente da hora).
    --dry-run  Simula sem chamar a API BulkGate nem gravar sms_enviado=True.
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand

from pages.filial.models import FilialConfig
from pages.pedidos.models import TentativaEntrega, ESTADOS_SEGUE_PARA_ENTREGA
from sac_base.sms_service import (
    HORARIO_PERIODO,
    enviar_sms_bulkgate,
    montar_mensagem,
)

logger = logging.getLogger(__name__)

LISBON_TZ = ZoneInfo("Europe/Lisbon")


class Command(BaseCommand):
    help = "Envia SMS automáticos para as filiais com sms_auto configurado."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Ignora a verificação de horário e envia imediatamente para todas as filiais "
                "com sms_auto configurado. ATENÇÃO: envia SMS reais — use --dry-run para testar."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simula o envio sem chamar a API BulkGate nem gravar sms_enviado=True.",
        )

    def handle(self, *args, **options):
        force = options["force"]
        dry_run = options["dry_run"]

        now_lisbon = datetime.now(LISBON_TZ)
        today = now_lisbon.date()
        now_time = now_lisbon.replace(second=0, microsecond=0).time()

        modo = []
        if force:
            modo.append("--force")
        if dry_run:
            modo.append("--dry-run")
        modo_str = f" [{', '.join(modo)}]" if modo else ""

        self.stdout.write(
            f"[enviar_sms_automatico{modo_str}] {now_lisbon.strftime('%d/%m/%Y %H:%M')} (Lisboa)"
        )

        configs = (
            FilialConfig.objects
            .select_related(
                "filial",
                "filial__pais_atuacao",
            )
            .exclude(sms_auto__isnull=True)
        )

        if not configs.exists():
            self.stdout.write("Nenhuma filial com sms_auto configurado. Saindo.")
            return

        total_filiais_enviadas = 0

        for cfg in configs:
            filial = cfg.filial
            sms_time = cfg.sms_auto  # datetime.time (TimeField)

            if not force:
                # Só envia se a hora actual de Lisboa já ultrapassou sms_auto
                if now_time < sms_time:
                    self.stdout.write(
                        f"  ↷ Filial '{filial}': horário configurado {sms_time.strftime('%H:%M')} "
                        f"ainda não chegou (agora {now_time.strftime('%H:%M')}). Ignorando."
                    )
                    continue

            self.stdout.write(
                f"  → Filial '{filial}': horário {sms_time.strftime('%H:%M')} "
                f"{'(forçado) ' if force else ''}Iniciando envio..."
            )
            total_filiais_enviadas += 1
            self._enviar_para_filial(cfg, filial, today, dry_run=dry_run)

        if total_filiais_enviadas == 0:
            self.stdout.write("Nenhuma filial no horário de envio agora.")

    def _enviar_para_filial(self, cfg, filial, today, dry_run=False):
        # Templates por período: sms_padrao_1 → MANHÃ, sms_padrao_2 → TARDE.
        # Se sms_padrao_2 não estiver configurado, usa sms_padrao_1 como fallback.
        template_manha = cfg.sms_padrao_1 or ""
        template_tarde = cfg.sms_padrao_2 or template_manha

        if not template_manha and not template_tarde:
            self.stderr.write(
                f"  [ERRO] Filial '{filial}': nenhum template SMS configurado (sms_padrao_1/2). Ignorando."
            )
            return

        sigla_pais = ""
        ddi_padrao = "351"  # fallback Portugal
        if filial.pais_atuacao:
            sigla_pais = filial.pais_atuacao.sigla or ""
            codigo_tel = (filial.pais_atuacao.codigo_tel or "").strip().lstrip("+")
            if codigo_tel:
                ddi_padrao = codigo_tel

        qs = (
            TentativaEntrega.objects
            .select_related("pedido", "pedido__filial")
            .filter(
                pedido__filial=filial,
                data_tentativa=today,
                sms_enviado=False,
                pedido__estado__in=ESTADOS_SEGUE_PARA_ENTREGA,
            )
            .exclude(periodo__isnull=True)
            .exclude(periodo="")
        )

        tentativas = list(qs)
        if not tentativas:
            self.stdout.write(
                f"  Filial '{filial}': sem tentativas elegíveis para {today.strftime('%d/%m/%Y')}."
            )
            return

        enviados = 0
        erros = 0
        contagem_periodo: dict[str, int] = {}

        for mov in tentativas:
            pedido = mov.pedido
            referencia = pedido.pedido or str(getattr(pedido, "id_vonzu", pedido.pk))
            fones = [f.strip() for f in [pedido.fone_dest or "", pedido.fone_dest2 or ""] if f.strip()]

            if not fones:
                self.stderr.write(f"    [{referencia}] Sem telefone. Ignorado.")
                erros += 1
                continue

            # Seleciona template pelo período
            if mov.periodo == "TARDE":
                template_msg = template_tarde
            else:
                template_msg = template_manha

            if not template_msg:
                self.stderr.write(f"    [{referencia}] Template para período '{mov.periodo}' não configurado. Ignorado.")
                erros += 1
                continue

            try:
                mensagem = montar_mensagem(template_msg, today, mov.periodo, sigla_pais)
            except Exception as exc:
                self.stderr.write(f"    [{referencia}] Erro ao montar mensagem: {exc}")
                erros += 1
                continue

            if dry_run:
                self.stdout.write(
                    f"    [{referencia}] [DRY-RUN] Mensagem para {', '.join(fones)}:\n"
                    f"      {mensagem}"
                )
                enviados += 1
                contagem_periodo[mov.periodo] = contagem_periodo.get(mov.periodo, 0) + 1
                continue

            sucesso_algum = False
            for fone in fones:
                resultado = enviar_sms_bulkgate(fone, mensagem, ddi_padrao)
                if resultado.get("sucesso"):
                    sucesso_algum = True
                    self.stdout.write(f"    [{referencia}] SMS enviado para {fone}.")
                else:
                    self.stderr.write(
                        f"    [{referencia}] Falha para {fone}: {resultado.get('erro')}"
                    )
                    erros += 1

            if sucesso_algum:
                mov.sms_enviado = True
                mov.save(update_fields=["sms_enviado"])
                enviados += 1
                contagem_periodo[mov.periodo] = contagem_periodo.get(mov.periodo, 0) + 1

        self.stdout.write(
            f"  Filial '{filial}': {enviados} {'simulado(s)' if dry_run else 'enviado(s)'}, {erros} erro(s)."
        )
        logger.info(
            "enviar_sms_automatico | filial=%s | date=%s | enviados=%d | erros=%d | dry_run=%s",
            filial,
            today,
            enviados,
            erros,
            dry_run,
        )

        # SMS de confirmação para a filial (sms_confirm) — ignorado em dry-run
        if not dry_run and getattr(filial, "sms_confirm", False) and getattr(filial, "numero", None) and enviados > 0:
            partes = [f"SMS automáticos {today.strftime('%d/%m/%Y')}:"]
            for periodo, qtd in sorted(contagem_periodo.items()):
                horario = HORARIO_PERIODO.get(periodo, periodo)
                partes.append(f"  {periodo} ({horario}): {qtd}")
            partes.append(f"Total: {enviados}")
            enviar_sms_bulkgate(filial.numero, "\n".join(partes), ddi_padrao)
