from django.apps import AppConfig


class FinanceiroConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "pages.financeiro"
    verbose_name = "Financeiro"

    def ready(self):
        from pages.agenda.registry_materializacao import registrar_materialization_provider
        from pages.agenda.registry_providers import registrar_period_alert_provider
        from pages.financeiro.agenda_materialization.registro_financeiro import (
            RegistroFinanceiroMaterializationProvider,
        )
        from pages.financeiro.providers.agenda_periodo import (
            FinanceiroRegistroFinanceiroPeriodProvider,
        )

        registrar_period_alert_provider(FinanceiroRegistroFinanceiroPeriodProvider())
        registrar_materialization_provider(RegistroFinanceiroMaterializationProvider())
