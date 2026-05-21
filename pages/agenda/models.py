from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models

from pages.agenda.constants import (
    CATEGORIA_CHOICES,
    MODO_EVENTO_CHOICES,
    ModoEventoAgenda,
    RECORRENCIA_CHOICES,
    RecorrenciaAgenda,
    TipoVinculoMaterializacao,
)
from pages.auditoria.models import AuditFieldsMixin
from pages.filial.models import Filial


class AgendaManual(AuditFieldsMixin, models.Model):
    """Regra de agenda manual com recorrência e modo de evento."""

    id = models.BigAutoField(primary_key=True)
    filial = models.ForeignKey(
        Filial,
        on_delete=models.PROTECT,
        db_column="filial_id",
        related_name="agendas_manuais",
    )
    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True, default="")
    categoria = models.CharField(max_length=40, choices=CATEGORIA_CHOICES, default="lembrete")
    modo_evento = models.CharField(
        max_length=30,
        choices=MODO_EVENTO_CHOICES,
        default=ModoEventoAgenda.AVISO,
    )
    tipo_materializacao = models.CharField(max_length=80, null=True, blank=True)
    payload_template = models.JSONField(default=dict, blank=True)
    payload_schema_version = models.PositiveSmallIntegerField(default=1)
    data_ancora = models.DateField()
    recorrencia = models.CharField(max_length=20, choices=RECORRENCIA_CHOICES, default=RecorrenciaAgenda.MENSAL)
    intervalo = models.PositiveSmallIntegerField(default=1)
    dia_semana = models.PositiveSmallIntegerField(null=True, blank=True)
    dia_mes_fixo = models.PositiveSmallIntegerField(null=True, blank=True)
    antecipar_fim_semana = models.BooleanField(default=False)
    data_fim_serie = models.DateField(null=True, blank=True)
    ativa = models.BooleanField(default=True)

    class Meta:
        db_table = "agenda_manual"
        ordering = ["filial_id", "titulo", "id"]
        indexes = [
            models.Index(fields=["filial", "ativa"]),
            models.Index(fields=["filial", "data_ancora"]),
            models.Index(fields=["filial", "tipo_materializacao"]),
        ]
        permissions = [
            ("view_relatorio_previsibilidade", "Ver relatório de previsibilidade"),
            ("confirmar_ocorrencia_agendamanual", "Confirmar ocorrência de agenda"),
            ("materializar_agendamanual", "Materializar ocorrência de agenda"),
        ]

    def __str__(self):
        return f"{self.titulo} ({self.filial_id})"


class AgendaMaterializacao(AuditFieldsMixin, models.Model):
    """Vínculo por ocorrência: confirmação ou registro materializado."""

    id = models.BigAutoField(primary_key=True)
    agenda_manual = models.ForeignKey(
        AgendaManual,
        on_delete=models.CASCADE,
        related_name="materializacoes",
    )
    data_ocorrencia = models.DateField()
    tipo_vinculo = models.CharField(max_length=40)
    content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    object_id = models.PositiveBigIntegerField(null=True, blank=True)
    registro_gerado = GenericForeignKey("content_type", "object_id")
    observacao = models.TextField(blank=True, default="")

    class Meta:
        db_table = "agenda_materializacao"
        ordering = ["-data_ocorrencia", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["agenda_manual", "data_ocorrencia"],
                name="uq_agenda_materializacao_manual_data",
            ),
        ]
        indexes = [
            models.Index(fields=["agenda_manual", "data_ocorrencia"]),
        ]

    def __str__(self):
        return f"Mat {self.agenda_manual_id} @ {self.data_ocorrencia}"
