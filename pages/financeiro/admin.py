from django.contrib import admin

from pages.financeiro import models as fin_models


@admin.register(fin_models.PlanoContas)
class PlanoContasAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "nivel", "tipo_classificacao", "pai_id")


@admin.register(fin_models.ContaFinanceira)
class ContaFinanceiraAdmin(admin.ModelAdmin):
    list_display = ("nome", "filial", "ativo")


@admin.register(fin_models.FormaPagamento)
class FormaPagamentoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "aceita_parcelamento", "ativo")


@admin.register(fin_models.RegistroFinanceiro)
class RegistroFinanceiroAdmin(admin.ModelAdmin):
    list_display = ("id", "filial", "tipo", "valor", "valor_fat", "valor_rest", "status")


@admin.register(fin_models.Faturamento)
class FaturamentoAdmin(admin.ModelAdmin):
    list_display = ("id", "filial", "created_at")
