"""Regenera tokens JWT/longos de avaliação para tokens opacos curtos."""

from django.core.management.base import BaseCommand

from pages.pedidos.models import AvaliacaoPedido
from pages.pedidos.services.avaliacao_link import garantir_token_para_envio, token_precisa_upgrade


class Command(BaseCommand):
    help = (
        "Substitui tokens longos/JWT de avaliações pendentes por tokens opacos curtos. "
        "Por defeito só processa email_enviado=False (não invalida links já enviados)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Inclui avaliações com email_enviado=True (invalida links antigos na inbox).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Lista contagens sem gravar.",
        )

    def handle(self, *args, **options):
        force = options["force"]
        dry_run = options["dry_run"]

        qs = AvaliacaoPedido.objects.filter(link_ativo=True, respondido_em__isnull=True)
        if not force:
            qs = qs.filter(email_enviado=False)

        candidatos = [a for a in qs.iterator() if token_precisa_upgrade(a.token_publico)]
        ja_enviados = sum(1 for a in candidatos if a.email_enviado)

        self.stdout.write(
            f"[regenerar_tokens_avaliacao_curtos] candidatos={len(candidatos)} "
            f"(já enviados por e-mail={ja_enviados}, force={force}, dry_run={dry_run})"
        )
        if force and ja_enviados:
            self.stdout.write(
                self.style.WARNING(
                    f"  Atenção: {ja_enviados} link(s) já enviado(s) por e-mail deixarão de funcionar."
                )
            )

        if dry_run:
            self.stdout.write("  [DRY-RUN] Nenhuma alteração gravada.")
            return

        regenerados = 0
        for avaliacao in candidatos:
            antigo = avaliacao.token_publico or ""
            garantir_token_para_envio(avaliacao)
            regenerados += 1
            self.stdout.write(
                f"  id={avaliacao.id}: {len(antigo)} chars → {len(avaliacao.token_publico or '')} chars"
            )

        self.stdout.write(self.style.SUCCESS(f"Regenerados: {regenerados}"))
