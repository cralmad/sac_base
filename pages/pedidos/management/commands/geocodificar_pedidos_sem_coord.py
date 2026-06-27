"""
Management command: geocodificar_pedidos_sem_coord

Geocodifica pedidos sem coordenadas via codigo-postal.pt, em lotes com pausas
na mesma execução (várias rondas até esgotar pendentes ou timeout de 1 h).

Heroku Scheduler — recomendado: 1× ao dia (ex.: 03:00 Europe/Lisbon)
    python manage.py geocodificar_pedidos_sem_coord

Flags:
    --filial-id=N   Apenas uma filial
    --dry-run       Conta pendentes sem geocodificar
"""

from django.core.management.base import BaseCommand

from pages.pedidos.services.codigo_postal_pt import executar_geocodificacao_diaria


class Command(BaseCommand):
    help = "Geocodifica pedidos sem coordenadas via codigo-postal.pt (lotes noturnos)."

    def add_arguments(self, parser):
        parser.add_argument("--filial-id", type=int, default=None)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        resumo = executar_geocodificacao_diaria(
            filial_id=options.get("filial_id"),
            dry_run=options.get("dry_run"),
        )

        if resumo.get("dry_run"):
            self.stdout.write(f"[dry-run] Pendentes: {resumo.get('pendentes', 0)}")
            return

        if resumo.get("erro"):
            self.stdout.write(self.style.WARNING(resumo["erro"]))
            return

        self.stdout.write(
            f"Lotes: {resumo.get('lotes', 0)} | "
            f"Atribuídas: {resumo.get('coords_atribuidas_total', 0)} | "
            f"Restantes: {resumo.get('restantes_global', 0)}"
        )
        if resumo.get("abortado_site"):
            self.stdout.write(self.style.ERROR("Abortado: estrutura codigo-postal.pt alterada."))
        if resumo.get("timeout"):
            self.stdout.write(self.style.WARNING("Timeout diário atingido; restantes amanhã."))
