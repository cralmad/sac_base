"""
Management command: enviar_sms_automatico

Para cada FilialConfig com sms_auto configurado, verifica se a hora actual
de Lisboa já ultrapassou o horário configurado e, se ainda houver
TentativaEntrega elegíveis com sms_enviado=False, envia os SMS.

Numa única execução do comando: reintentos com backoff para erros transientes
(quota/rede) e rondas sobre a base de dados até esgotar pendentes com telefone
ou até limites de segurança (ver pages.pedidos.services.sms_envio_automatico).

A guarda contra duplo envio: após sucesso os registos ficam com sms_enviado=True.

Uso:
    python manage.py enviar_sms_automatico

Heroku Scheduler — recomendado: a cada 10 minutos
    python manage.py enviar_sms_automatico

Flags de teste:
    --force    Ignora a verificação de horário (envia independente da hora).
    --dry-run  Simula sem chamar a API BulkGate nem gravar sms_enviado=True.
"""

import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand

from pages.filial.models import FilialConfig
from pages.pedidos.services.sms_envio_automatico import (
    MAX_PAUSAS_SEM_PROGRESSO,
    MAX_RONDAS_FILIAL,
    PAUSA_SEM_PROGRESSO_SEG,
    contar_pendentes_sem_telefone,
    listar_pendentes_com_telefone,
)
from pages.pedidos.services.sms_relatorio import qs_tentativas_sms_pendentes_envio
from sac_base.sms_service import HORARIO_PERIODO, montar_mensagem, enviar_sms_bulkgate_resiliente

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
                        f"  [skip] Filial '{filial}': horário configurado {sms_time.strftime('%H:%M')} "
                        f"ainda não chegou (agora {now_time.strftime('%H:%M')}). Ignorando."
                    )
                    continue

            self.stdout.write(
                f"  [envio] Filial '{filial}': horário {sms_time.strftime('%H:%M')} "
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

        tentativas_snapshot = list(
            qs_tentativas_sms_pendentes_envio(filial, today).select_related(
                "pedido", "pedido__filial"
            )
        )
        if not tentativas_snapshot:
            self.stdout.write(
                f"  Filial '{filial}': sem tentativas elegíveis para {today.strftime('%d/%m/%Y')}."
            )
            return

        enviados = 0
        erros = 0
        contagem_periodo: dict[str, int] = {}

        if dry_run:
            for mov in tentativas_snapshot:
                pedido = mov.pedido
                referencia = pedido.pedido or str(getattr(pedido, "id_vonzu", pedido.pk))
                fones = [f.strip() for f in [pedido.fone_dest or "", pedido.fone_dest2 or ""] if f.strip()]

                if not fones:
                    self.stderr.write(f"    [{referencia}] Sem telefone. Ignorado.")
                    erros += 1
                    continue

                if mov.periodo == "TARDE":
                    template_msg = template_tarde
                else:
                    template_msg = template_manha

                if not template_msg:
                    self.stderr.write(
                        f"    [{referencia}] Template para período '{mov.periodo}' não configurado. Ignorado."
                    )
                    erros += 1
                    continue

                try:
                    mensagem = montar_mensagem(template_msg, today, mov.periodo, sigla_pais)
                except Exception as exc:
                    self.stderr.write(f"    [{referencia}] Erro ao montar mensagem: {exc}")
                    erros += 1
                    continue

                self.stdout.write(
                    f"    [{referencia}] [DRY-RUN] Mensagem para {', '.join(fones)}:\n"
                    f"      {mensagem}"
                )
                enviados += 1
                contagem_periodo[mov.periodo] = contagem_periodo.get(mov.periodo, 0) + 1
        else:
            sem_tel = contar_pendentes_sem_telefone(filial, today)
            if sem_tel:
                self.stderr.write(
                    f"  Filial '{filial}': {sem_tel} registro(s) sem telefone (não enviáveis por SMS)."
                )
                erros += sem_tel

            ronda = 0
            pausas_sem_progresso = 0
            ids_sem_retry_definitivo: set[int] = set()

            while ronda < MAX_RONDAS_FILIAL:
                ronda += 1
                tentativas = listar_pendentes_com_telefone(filial, today)
                if not tentativas:
                    break

                houve_sucesso_nesta_ronda = False

                for mov in tentativas:
                    if mov.id in ids_sem_retry_definitivo:
                        continue
                    pedido = mov.pedido
                    referencia = pedido.pedido or str(getattr(pedido, "id_vonzu", pedido.pk))
                    fones = [f.strip() for f in [pedido.fone_dest or "", pedido.fone_dest2 or ""] if f.strip()]

                    if mov.periodo == "TARDE":
                        template_msg = template_tarde
                    else:
                        template_msg = template_manha

                    if not template_msg:
                        self.stderr.write(
                            f"    [{referencia}] Template para período '{mov.periodo}' não configurado. Ignorado."
                        )
                        erros += 1
                        ids_sem_retry_definitivo.add(mov.id)
                        continue

                    try:
                        mensagem = montar_mensagem(template_msg, today, mov.periodo, sigla_pais)
                    except Exception as exc:
                        self.stderr.write(f"    [{referencia}] Erro ao montar mensagem: {exc}")
                        erros += 1
                        ids_sem_retry_definitivo.add(mov.id)
                        continue

                    sucesso_algum = False
                    for fone in fones:

                        def _on_retry(tentativa, err, seg, ref=referencia, fn=fone):
                            self.stdout.write(
                                f"    [{ref}] Reintento SMS {tentativa} para {fn} "
                                f"(espera {seg}s): {(err or '')[:120]}"
                            )

                        resultado = enviar_sms_bulkgate_resiliente(
                            fone,
                            mensagem,
                            ddi_padrao,
                            log_prefix=f"[{referencia}] ",
                            on_retry=_on_retry,
                        )
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
                        houve_sucesso_nesta_ronda = True

                pendentes_db = listar_pendentes_com_telefone(filial, today)
                ainda = [m for m in pendentes_db if m.id not in ids_sem_retry_definitivo]
                if not ainda and pendentes_db:
                    self.stdout.write(
                        f"  Filial '{filial}': {len(pendentes_db)} pendente(s) sem retry automático "
                        "(template/montagem ou limite de erros)."
                    )
                    break
                if not ainda:
                    break

                if not houve_sucesso_nesta_ronda:
                    pausas_sem_progresso += 1
                    if pausas_sem_progresso > MAX_PAUSAS_SEM_PROGRESSO:
                        self.stderr.write(
                            f"  [ERRO] Filial '{filial}': limite de pausas sem progresso atingido; "
                            f"permanecem {len(ainda)} SMS pendente(s) com telefone."
                        )
                        logger.error(
                            "enviar_sms_automatico | filial=%s | pendentes=%s após pausas sem progresso",
                            filial,
                            len(ainda),
                        )
                        break
                    self.stdout.write(
                        f"  Ronda {ronda}: {len(ainda)} pendente(s), sem sucesso nesta ronda; "
                        f"pausa {PAUSA_SEM_PROGRESSO_SEG}s (quota/rede)..."
                    )
                    time.sleep(PAUSA_SEM_PROGRESSO_SEG)

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
        _numero_resumo = (getattr(filial, "numero", None) or "").strip()
        if not dry_run and getattr(filial, "sms_confirm", False) and _numero_resumo and enviados > 0:
            partes = [f"SMS automáticos {today.strftime('%d/%m/%Y')}:"]
            for periodo, qtd in sorted(contagem_periodo.items()):
                horario = HORARIO_PERIODO.get(periodo, periodo)
                partes.append(f"  {periodo} ({horario}): {qtd}")
            partes.append(f"Total: {enviados}")
            _texto_resumo = "\n".join(partes)
            _resumo_res = enviar_sms_bulkgate_resiliente(
                _numero_resumo,
                _texto_resumo,
                ddi_padrao,
                log_prefix="[resumo_filial] ",
            )
            if not _resumo_res.get("sucesso"):
                _erro_r = _resumo_res.get("erro") or "Erro desconhecido."
                self.stderr.write(f"  [ERRO] SMS resumo para a filial falhou: {_erro_r}")
                logger.warning("enviar_sms_automatico | resumo_filial falhou | filial=%s | %s", filial, _erro_r)
