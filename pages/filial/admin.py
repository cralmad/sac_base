from django.contrib import admin

from .models import Filial, UsuarioFilial


@admin.register(Filial)
class FilialAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "is_matriz", "ativa")
    list_filter = ("is_matriz", "ativa")
    search_fields = ("codigo", "nome")


@admin.register(UsuarioFilial)
class UsuarioFilialAdmin(admin.ModelAdmin):
    list_display = ("usuario", "filial", "pode_consultar", "pode_escrever", "ativo")
    list_filter = ("pode_consultar", "pode_escrever", "ativo")
    search_fields = ("usuario__username", "usuario__first_name", "filial__nome", "filial__codigo")
