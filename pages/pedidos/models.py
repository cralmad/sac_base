from django.db import models

from pages.auditoria.models import AuditFieldsMixin
from pages.cad_cliente.models import Cliente
from pages.filial.models import Filial
from pages.motorista.models import Motorista


TIPO_CHOICES = [
    ("ENTREGA", "Entrega"),
    ("RECOLHA", "Recolha"),
]

ORIGEM_CHOICES = [
    ("IMPORTADO", "Importado"),
    ("MANUAL", "Manual"),
]

PERIODO_CHOICES = [
    ("MANHA", "MANHÃ"),
    ("TARDE", "TARDE"),
]

ESTADO_CHOICES = [
    ("created", "Criado"),
    ("assigned", "Atribuído"),
    ("pending", "Em distribuição"),
    ("completed", "Concluído"),
    ("EA", "Entrada em armazém e está OK"),
    ("CA", "Cliente ausente"),
    ("R", "Entrega recusada"),
    ("DA", "Difícil acesso (rua)"),
    ("EM", "Erro de morada"),
    ("DVP", "Entrega com danos visíveis"),
    ("DVR", "Entrada em armazém: danos visíveis"),
    ("cancelled", "Cancelado"),
    ("A", "Pedido Cancelado"),
    ("CI", "Entrega com artigos em falta"),
    ("AO", "Incumprimento do dia de entrega"),
    ("PNR", "Pedido não rececionado"),
    ("RCD", "Recolha com danos visíveis (casa cliente)"),
    ("PIT", "Pedido incompleto: responsabilidade da transportadora"),
    ("reschedule_client", "Reagendamento Responsabilidade Cliente"),
    ("reschedule_logisticOperator", "Reagendamento Responsabilidade Transportador"),
    ("orders_vonzu", "Entrada em Vonzu"),
    ("(orders_vonzu)", "CONTACTO CONFIRMADO"),
    ("(orders_vonzu))", "PENDENTE CONTACTO"),
    ("ExtraviadoOperador", "Extraviado no Operador"),
    ("danos_visiveis_embalagem", "Receção Transportadora: danos visíveis (embalagem)"),
    ("3799", "Reagendado Zona Sem entregas dia Planeado"),
    ("recusa_parcial", "Recusa parcial (artigos danificados)"),
    ("conferencia_condicionada", "Conferência condicionada"),
    ("reactivar", "Reactivar (Reagendamento responsabilidade Leroy Merlin)"),
    ("Reagendamento_Leroy_Merlin", "Reagendamento responsabilidade Leroy Merlin"),
    ("returned_to_sender", "Devolvido ao Cliente"),
    ("UNKNOWN", "Estado desconhecido"),
]


class Pedido(AuditFieldsMixin, models.Model):
    id = models.BigAutoField(primary_key=True)
    filial = models.ForeignKey(
        Filial,
        on_delete=models.PROTECT,
        db_column="filial_id",
        related_name="pedidos",
    )
    origem = models.CharField(max_length=10, choices=ORIGEM_CHOICES, default="IMPORTADO")
    id_vonzu = models.BigIntegerField()
    pedido = models.CharField(max_length=100, null=True, blank=True)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    criado = models.DateTimeField()
    atualizacao = models.DateTimeField()
    prev_entrega = models.DateField(null=True, blank=True)
    dt_entrega = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=50, choices=ESTADO_CHOICES, null=True, blank=True)
    volume = models.SmallIntegerField(null=True, blank=True)
    nome_dest = models.CharField(max_length=150, null=True, blank=True)
    email_dest = models.CharField(max_length=150, null=True, blank=True)
    fone_dest = models.CharField(max_length=30, null=True, blank=True)
    fone_dest2 = models.CharField(max_length=30, null=True, blank=True)
    endereco_dest = models.CharField(max_length=300, null=True, blank=True)
    codpost_dest = models.CharField(max_length=20, null=True, blank=True)
    cidade_dest = models.CharField(max_length=100, null=True, blank=True)
    obs = models.TextField(null=True, blank=True)
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="cliente_id",
        related_name="pedidos",
    )
    motorista = models.ForeignKey(
        Motorista,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="motorista_id",
        related_name="pedidos",
    )
    peso = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    expresso = models.BooleanField(default=False)

    class Meta:
        db_table = "pedido"
        constraints = [
            models.UniqueConstraint(
                fields=["filial", "id_vonzu"],
                name="unique_pedido_filial_vonzu",
            ),
        ]
        indexes = [
            models.Index(fields=["filial", "id_vonzu"]),
            models.Index(fields=["prev_entrega"]),
            models.Index(fields=["estado"]),
        ]

    def __str__(self):
        return str(self.pedido or self.id_vonzu)


class TentativaEntrega(models.Model):
    id = models.BigAutoField(primary_key=True)
    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.CASCADE,
        db_column="pedido_id",
        related_name="tentativas",
    )
    data_tentativa = models.DateField()
    estado = models.CharField(max_length=50, choices=ESTADO_CHOICES, null=True, blank=True)
    carro = models.SmallIntegerField(null=True, blank=True)
    motorista = models.ForeignKey(
        Motorista,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="motorista_id",
        related_name="tentativas_entrega",
    )
    periodo = models.CharField(max_length=5, choices=PERIODO_CHOICES, null=True, blank=True)
    faturado = models.BooleanField(default=False)
    interno = models.BooleanField(default=False)
    dt_entrega = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "tentativa_entrega"
        indexes = [
            models.Index(fields=["pedido", "data_tentativa"]),
            models.Index(fields=["data_tentativa", "faturado"]),
        ]

    def __str__(self):
        return f"Tentativa {self.data_tentativa} — Pedido {self.pedido_id}"
