from django.db import models

from pages.auditoria.models import AuditFieldsMixin
from pages.cad_cliente.models import Cliente
from pages.filial.models import Filial
from pages.motorista.models import Motorista


TIPO_CHOICES = [
    ("ENTREGA", "Entrega"),
    ("RECOLHA", "Recolha"),
]

INCIDENCIA_CHOICE = [
    # (valor_tipo, filtro_origem)  filtro_origem="" → exibido para todas as origens
    ("Acondicionamento/Embalagem", "cliente"),
    ("Peso/Volume",               "cliente"),
    ("Data/Horário",              "cliente"),
    ("Outros",                    ""),
    ("Artigo Danificado",         "filial"),
    ("Artigo Extraviado",         "filial"),
]

INCIDENCIA_ORIG_CHOICE = [
    ("Cliente", "Cliente"),
    ("Filial",  "Filial"),
]

# Choices planos para o campo tipo (valor, label)
INCIDENCIA_TIPO_CHOICES = [(v, v) for v, _ in INCIDENCIA_CHOICE]

MOTIVO_CHOICES = [
    ("Pedido Cancelado p/ Cliente", "Pedido Cancelado p/ Cliente"),
    ("Entrega Recusada", "Entrega Recusada"),
    ("Artigos Danificados", "Artigos Danificados"),
    ("Cliente Ausente", "Cliente Ausente"),
    ("Tipologia de Entrega Errada (Passeio/Domicilio/Grua)", "Tipologia de Entrega Errada (Passeio/Domicilio/Grua)"),
    ("Morada Errada", "Morada Errada"),
    ("Pedido Adiado", "Pedido Adiado"),
    ("Artigos Errados", "Artigos Errados"),
    ("Transportadora Errada", "Transportadora Errada"),
    ("Outros", "Outros"),
    ("Pedido cancelado", "Pedido cancelado"),
]

ORIGEM_CHOICES = [
    ("IMPORTADO", "Importado"),
    ("MANUAL", "Manual"),
]

PERIODO_CHOICES = [
    ("MANHA", "MANHÃ"),
    ("TARDE", "TARDE"),
]

ESTADO_DEFINITIONS = [# valor, label, entrega_efetivamente_concluida, segue_para_entrega
    ("created", "Criado", 0, 1),
    ("assigned", "Atribuído", 0, 1),
    ("pending", "Em distribuição", 0, 1),
    ("completed", "Concluído", 1, 0),
    ("EA", "Entrada em armazém e está OK", 0, 1),
    ("CA", "Cliente ausente", 0, 1),
    ("R", "Entrega recusada", 0, 0),
    ("DA", "Difícil acesso (rua)", 0, 1),
    ("EM", "Erro de morada", 0, 1),
    ("DVP", "Entrega com danos visíveis", 1, 0),
    ("DVR", "Entrada em armazém: danos visíveis", 0, 1),
    ("cancelled", "Cancelado", 0, 0),
    ("A", "Pedido Cancelado", 0, 0),
    ("CI", "Entrega com artigos em falta", 1, 0),
    ("AO", "Incumprimento do dia de entrega", 0, 1),
    ("PNR", "Pedido não rececionado", 0, 0),
    ("RCD", "Recolha com danos visíveis (casa cliente)", 1, 0),
    ("PIT", "Pedido incompleto: responsabilidade da transportadora", 1, 1),
    ("reschedule_client", "Reagendamento Responsabilidade Cliente", 0, 1),
    ("reschedule_logisticOperator", "Reagendamento Responsabilidade Transportador", 0, 1),
    ("orders_vonzu", "Entrada em Vonzu", 0, 1),
    ("(orders_vonzu)", "CONTACTO CONFIRMADO", 0, 1),
    ("(orders_vonzu))", "PENDENTE CONTACTO", 0, 1),
    ("ExtraviadoOperador", "Extraviado no Operador", 1, 0),
    ("danos_visiveis_embalagem", "Receção Transportadora: danos visíveis (embalagem)", 0, 1),
    ("3799", "Reagendado Zona Sem entregas dia Planeado", 0, 0),
    ("recusa_parcial", "Recusa parcial (artigos danificados)", 0, 0),
    ("conferencia_condicionada", "Conferência condicionada", 0, 1),
    ("reactivar", "Reactivar (Reagendamento responsabilidade Leroy Merlin)", 0, 1),
    ("Reagendamento_Leroy_Merlin", "Reagendamento responsabilidade Leroy Merlin", 0, 1),
    ("returned_to_sender", "Devolvido ao Cliente", 0, 0),
    ("UNKNOWN", "Estado desconhecido", 0, 0),
]

# Django choices deve conter pares (valor, label)
ESTADO_CHOICES = [(valor, label) for valor, label, *_ in ESTADO_DEFINITIONS]

# Estados marcados para uso futuro em identificação de entrega efetivamente concluída
ESTADOS_ENTREGA_EFETIVAMENTE_CONCLUIDA = {
    valor for valor, _label, concluida, _segue in ESTADO_DEFINITIONS if bool(concluida)
}

# Estados em que o pedido segue para nova tentativa de entrega
ESTADOS_SEGUE_PARA_ENTREGA = {
    valor for valor, _label, _concluida, segue in ESTADO_DEFINITIONS if bool(segue)
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
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    geocoding_display = models.CharField(max_length=300, null=True, blank=True)
    geocoding_precision = models.CharField(max_length=20, null=True, blank=True)

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


class AvaliacaoPedido(models.Model):
    id = models.BigAutoField(primary_key=True)
    pedido = models.OneToOneField(
        Pedido,
        on_delete=models.CASCADE,
        db_column="pedido_id",
        related_name="avaliacao",
    )
    token_publico = models.CharField(max_length=512, unique=True, null=True, blank=True)
    link_ativo = models.BooleanField(default=True)
    email_enviado = models.BooleanField(default=False)
    email_enviado_em = models.DateTimeField(null=True, blank=True)
    email_tentativas = models.PositiveSmallIntegerField(default=0)
    respondido_em = models.DateTimeField(null=True, blank=True)
    p1_entrega_no_prazo = models.CharField(max_length=3, null=True, blank=True)
    p2_aviso_antes_chegada = models.CharField(max_length=3, null=True, blank=True)
    p3_educacao_simpatia = models.PositiveSmallIntegerField(null=True, blank=True)
    p4_cuidado_encomenda = models.PositiveSmallIntegerField(null=True, blank=True)
    p5_equipa_identificada = models.CharField(max_length=3, null=True, blank=True)
    p6_facilidade_processo = models.PositiveSmallIntegerField(null=True, blank=True)
    p7_veiculo_limpo = models.CharField(max_length=3, null=True, blank=True)
    p8_esclareceu_duvidas = models.CharField(max_length=3, null=True, blank=True)
    p9_satisfacao_geral = models.PositiveSmallIntegerField(null=True, blank=True)
    p10_recomendaria = models.CharField(max_length=3, null=True, blank=True)
    comentario = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "avaliacao_pedido"
        indexes = [
            models.Index(fields=["email_enviado"]),
            models.Index(fields=["link_ativo"]),
            models.Index(fields=["respondido_em"]),
        ]

    def __str__(self):
        return f"Avaliação Pedido {self.pedido_id}"


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
    sms_enviado = models.BooleanField(default=False)
    dt_entrega = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tentativa_entrega"
        permissions = [
            ("change_carro_tentativaentrega", "Pode alterar o campo Carro na conferência de volumes"),
            ("send_sms_tentativaentrega", "Pode enviar SMS de notificação de entrega"),
            ("view_relatorio_gerencial", "Pode acessar o Relatório Gerencial de Pedidos"),
            ("view_relatorio_avaliacao", "Pode acessar o Relatório de Avaliações"),
            ("send_email_avaliacao", "Pode enviar e-mails de avaliação"),
        ]
        indexes = [
            models.Index(fields=["pedido", "data_tentativa"]),
            models.Index(fields=["data_tentativa", "faturado"]),
        ]

    def __str__(self):
        return f"Tentativa {self.data_tentativa} — Pedido {self.pedido_id}"


class Devolucao(models.Model):
    id = models.BigAutoField(primary_key=True)
    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.CASCADE,
        db_column="pedido_id",
        related_name="devolucoes",
    )
    data = models.DateField()
    palete = models.SmallIntegerField(null=True, blank=True)
    volume = models.SmallIntegerField(null=True, blank=True)
    motivo = models.CharField(max_length=100, choices=MOTIVO_CHOICES)
    obs = models.TextField(null=True, blank=True)
    driver = models.BooleanField(default=False)
    fotos = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "devolucao"
        permissions = [
            ("view_relatorio_devolucao", "Pode acessar o Relatório de Devoluções"),
        ]
        indexes = [
            models.Index(fields=["pedido"]),
            models.Index(fields=["data"]),
        ]

    def __str__(self):
        return f"Devolução {self.data} — Pedido {self.pedido_id}"


class Incidencia(models.Model):
    id = models.BigAutoField(primary_key=True)
    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.CASCADE,
        db_column="pedido_id",
        related_name="incidencias",
    )
    data = models.DateField()
    origem = models.CharField(max_length=10, choices=INCIDENCIA_ORIG_CHOICE)
    tipo = models.CharField(max_length=50, choices=INCIDENCIA_TIPO_CHOICES)
    artigo = models.CharField(max_length=200, null=True, blank=True)
    valor = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    motorista = models.ForeignKey(
        Motorista,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="motorista_id",
        related_name="incidencias",
    )
    obs = models.TextField(null=True, blank=True)
    fotos = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "incidencia"
        indexes = [
            models.Index(fields=["pedido"]),
            models.Index(fields=["data"]),
            models.Index(fields=["origem"]),
        ]

    def __str__(self):
        return f"Incidência {self.tipo} — Pedido {self.pedido_id}"
