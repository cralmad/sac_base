from django.db import models

from pages.filial.models import Filial


class ConfiguracaoLogistica(models.Model):
    """Parâmetros de capacidade e valores unitários por filial (um registo por filial)."""

    id = models.BigAutoField(primary_key=True)
    filial = models.OneToOneField(
        Filial,
        on_delete=models.CASCADE,
        db_column="filial_id",
        related_name="configuracao_logistica",
    )
    pedidos_pesado = models.PositiveSmallIntegerField(default=0)
    pesado_reservado = models.PositiveSmallIntegerField(default=0)
    valor_unitario_pesado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pedidos_ligeiro = models.PositiveSmallIntegerField(default=0)
    ligeiro_reservado = models.PositiveSmallIntegerField(default=0)
    valor_unitario_ligeiro = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    valor_excedente = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        db_table = "configuracao_logistica"
        verbose_name = "Configuração de Logística"
        verbose_name_plural = "Configurações de Logística"

    def __str__(self):
        return f"Config logística — {self.filial_id}"


class DataExcecaoConfigLogistica(models.Model):
    """Substituição de vagas reservadas (ligeiro/pesado) para uma data específica."""

    id = models.BigAutoField(primary_key=True)
    configuracao = models.ForeignKey(
        ConfiguracaoLogistica,
        on_delete=models.CASCADE,
        db_column="configuracao_id",
        related_name="datas_excecao",
    )
    data = models.DateField()
    pesado_reservado = models.PositiveSmallIntegerField(default=0)
    ligeiro_reservado = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "data_excecao_config_logistica"
        verbose_name = "Data de exceção (logística)"
        verbose_name_plural = "Datas de exceção (logística)"
        constraints = [
            models.UniqueConstraint(
                fields=["configuracao", "data"],
                name="unique_excecao_config_data",
            ),
        ]
        indexes = [
            models.Index(fields=["configuracao", "data"]),
        ]

    def __str__(self):
        return f"Exceção {self.data} — config {self.configuracao_id}"
