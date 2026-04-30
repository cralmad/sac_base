from datetime import datetime
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand

from pages.filial.models import FilialConfig
from pages.pedidos.models import Pedido, ESTADOS_ENTREGA_EFETIVAMENTE_CONCLUIDA
from pages.pedidos.views_avaliacao import enviar_email_pedido_avaliacao

LISBON_TZ = ZoneInfo("Europe/Lisbon")


class Command(BaseCommand):
    help = "Envia e-mails automáticos de avaliação para pedidos concluídos."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Ignora o horário configurado da filial.")
        parser.add_argument("--dry-run", action="store_true", help="Simula envios sem disparar e-mail.")

    def handle(self, *args, **options):
        force = options["force"]
        dry_run = options["dry_run"]

        now_lisbon = datetime.now(LISBON_TZ)
        now_time = now_lisbon.replace(second=0, microsecond=0).time()
        self.stdout.write(f"[enviar_email_avaliacao_automatico] {now_lisbon.strftime('%d/%m/%Y %H:%M')} (Lisboa)")

        configs = FilialConfig.objects.select_related("filial").exclude(email_auto__isnull=True)
        if not configs.exists():
            self.stdout.write("Nenhuma filial com email_auto configurado. Saindo.")
            return

        for cfg in configs:
            filial = cfg.filial
            if not force and now_time < cfg.email_auto:
                self.stdout.write(
                    f"  ↷ Filial '{filial}': horário configurado {cfg.email_auto.strftime('%H:%M')} ainda não chegou."
                )
                continue

            self.stdout.write(f"  → Filial '{filial}': processando pedidos concluídos.")
            pedidos = (
                Pedido.objects.select_related("filial")
                .filter(filial=filial, estado__in=ESTADOS_ENTREGA_EFETIVAMENTE_CONCLUIDA)
                .exclude(email_dest__isnull=True)
                .exclude(email_dest="")
            )

            enviados = 0
            erros = 0
            for pedido in pedidos:
                avaliacao = getattr(pedido, "avaliacao", None)
                if avaliacao and (avaliacao.email_enviado or avaliacao.respondido_em):
                    continue

                if dry_run:
                    self.stdout.write(f"    [DRY-RUN] Pedido {pedido.pedido or pedido.id_vonzu}: elegível para envio.")
                    enviados += 1
                    continue

                retorno = enviar_email_pedido_avaliacao(pedido=pedido)
                if retorno.get("sucesso"):
                    enviados += 1
                    self.stdout.write(f"    Pedido {pedido.pedido or pedido.id_vonzu}: e-mail enviado.")
                else:
                    erros += 1
                    self.stderr.write(
                        f"    Pedido {pedido.pedido or pedido.id_vonzu}: falha no envio ({retorno.get('erro')})."
                    )

            self.stdout.write(
                f"  Filial '{filial}': {enviados} {'simulado(s)' if dry_run else 'enviado(s)'}, {erros} erro(s)."
            )
