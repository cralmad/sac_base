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

ESTADO_DEFINITIONS = [
    ("created", "Criado", 0),
    ("assigned", "Atribuído", 0),
    ("pending", "Em distribuição", 0),
    ("completed", "Concluído", 1),
    ("EA", "Entrada em armazém e está OK", 0),
    ("CA", "Cliente ausente", 0),
    ("R", "Entrega recusada", 0),
    ("DA", "Difícil acesso (rua)", 0),
    ("EM", "Erro de morada", 0),
    ("DVP", "Entrega com danos visíveis", 1),
    ("DVR", "Entrada em armazém: danos visíveis", 0),
    ("cancelled", "Cancelado", 0),
    ("A", "Pedido Cancelado", 0),
    ("CI", "Entrega com artigos em falta", 1),
    ("AO", "Incumprimento do dia de entrega", 0),
    ("PNR", "Pedido não rececionado", 0),
    ("RCD", "Recolha com danos visíveis (casa cliente)", 1),
    ("PIT", "Pedido incompleto: responsabilidade da transportadora", 1),
    ("reschedule_client", "Reagendamento Responsabilidade Cliente", 0),
    ("reschedule_logisticOperator", "Reagendamento Responsabilidade Transportador", 0),
    ("orders_vonzu", "Entrada em Vonzu", 0),
    ("(orders_vonzu)", "CONTACTO CONFIRMADO", 0),
    ("(orders_vonzu))", "PENDENTE CONTACTO", 0),
    ("ExtraviadoOperador", "Extraviado no Operador", 1),
    ("danos_visiveis_embalagem", "Receção Transportadora: danos visíveis (embalagem)", 0),
    ("3799", "Reagendado Zona Sem entregas dia Planeado", 0),
    ("recusa_parcial", "Recusa parcial (artigos danificados)", 0),
    ("conferencia_condicionada", "Conferência condicionada", 0),
    ("reactivar", "Reactivar (Reagendamento responsabilidade Leroy Merlin)", 0),
    ("Reagendamento_Leroy_Merlin", "Reagendamento responsabilidade Leroy Merlin", 0),
    ("returned_to_sender", "Devolvido ao Cliente", 0),
    ("UNKNOWN", "Estado desconhecido", 0),
]

# Django choices deve conter pares (valor, label)
ESTADO_CHOICES = [(valor, label) for valor, label, _ in ESTADO_DEFINITIONS]

# Estados marcados para uso futuro em identificação de entrega efetivamente concluída
ESTADOS_ENTREGA_EFETIVAMENTE_CONCLUIDA = {
    valor for valor, _label, concluida in ESTADO_DEFINITIONS if bool(concluida)
}


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
    obs_rota = models.TextField(null=True, blank=True)
    volume_conf = models.SmallIntegerField(default=0)
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
