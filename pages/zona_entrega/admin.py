from django.contrib import admin

from .models import ZonaEntrega, ZonaEntregaExcecaoPostal, ZonaEntregaFaixaPostal


class ZonaEntregaFaixaPostalInline(admin.TabularInline):
    model = ZonaEntregaFaixaPostal
    extra = 0


class ZonaEntregaExcecaoPostalInline(admin.TabularInline):
    model = ZonaEntregaExcecaoPostal
    extra = 0


@admin.register(ZonaEntrega)
class ZonaEntregaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "descricao", "filial", "ativa", "prioridade")
    list_filter = ("ativa", "filial__pais_atuacao")
    search_fields = ("codigo", "descricao", "filial__codigo", "filial__nome")
    inlines = [ZonaEntregaFaixaPostalInline, ZonaEntregaExcecaoPostalInline]
