from django.contrib import admin

from .models import Motorista


@admin.register(Motorista)
class MotoristaAdmin(admin.ModelAdmin):
    list_display = ("nome", "categoria", "telefone", "filial", "ativa")
    list_filter = ("ativa", "categoria", "filial__pais_atuacao")
    search_fields = ("nome", "telefone", "filial__nome", "filial__codigo")
