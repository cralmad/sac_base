from copy import deepcopy

from django.db import models
from django.db.models import Exists, OuterRef, Q

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
    ("Pedido incompleto",         "cliente"),
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

# valor, label, entrega_efetivamente_concluida, segue_para_entrega[, label_enovo]
# label_enovo: texto da coluna "Último Estado" no XLSX ENOVO → valor canónico.
# Importação ENOVO só aceita labels presentes neste 5.º campo (sem fallback UNKNOWN).
ESTADO_DEFINITIONS = [
    ("created", "Criado", 0, 1),
    ("assigned", "Atribuído", 0, 1, "Atribuido Motorista"),
    ("pending", "Em distribuição", 0, 1, "Em distribuição"),
    ("completed", "Concluído", 1, 0, "Entregue"),
    ("EA", "Entrada em armazém e está OK", 0, 1, "Entrada Armazém"),
    ("CA", "Cliente ausente", 0, 1),
    ("R", "Entrega recusada", 0, 0),
    ("DA", "Difícil acesso (rua)", 0, 1),
    ("EM", "Erro de morada", 0, 1),
    ("DVP", "Entrega com danos visíveis", 1, 0),
    ("DVR", "Entrada em armazém: danos visíveis", 0, 1),
    ("cancelled", "Cancelado", 0, 0),
    ("A", "Pedido Cancelado", 0, 0, "Anulado"),
    ("CI", "Entrega com artigos em falta", 1, 0, "Entregue Parcial"),
    ("AO", "Incumprimento do dia de entrega", 0, 1),
    ("PNR", "Pedido não rececionado", 0, 0),
    ("RCD", "Recolha com danos visíveis (casa cliente)", 1, 0),
    ("PIT", "Pedido incompleto: responsabilidade da transportadora", 1, 1),
    ("reschedule_client", "Reagendamento Responsabilidade Cliente", 0, 1),
    ("reschedule_logisticOperator", "Reagendamento Responsabilidade Transportador", 0, 1),
    ("orders_vonzu", "Entrada em Vonzu", 0, 1, "Pendente"),
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
    ("Incidência", "Incidência", 0, 1, "Incidência"),
    ("Agendado", "Agendado", 0, 1, "Agendado"),
    ("Aceite", "Aceite", 0, 1, "Aceite"),
    ("Recolhido", "Recolhido", 1, 0, "Recolhido"),
]

# Django choices deve conter pares (valor, label)
ESTADO_CHOICES = [(valor, label) for valor, label, *_ in ESTADO_DEFINITIONS]
ESTADO_LABEL_POR_VALOR = {valor: label for valor, label, *_ in ESTADO_DEFINITIONS}

# label ENOVO (5.º campo) → valor canónico; só labels explícitos entram no mapa
ESTADO_ENOVO_PARA_CANONICO = {
    str(rest[0]).strip(): valor
    for valor, _label, _concluida, _segue, *rest in ESTADO_DEFINITIONS
    if rest and str(rest[0]).strip()
}

# Estados marcados para uso futuro em identificação de entrega efetivamente concluída
ESTADOS_ENTREGA_EFETIVAMENTE_CONCLUIDA = {
    valor
    for valor, _label, concluida, _segue, *_ in ESTADO_DEFINITIONS
    if bool(concluida)
}

# Estados em que o pedido segue para nova tentativa de entrega
ESTADOS_SEGUE_PARA_ENTREGA = {
    valor
    for valor, _label, _concluida, segue, *_ in ESTADO_DEFINITIONS
    if bool(segue)
}

# Motivos ENOVO (coluna "Motivo Incidência") que impedem seguir para entrega,
# mesmo se o estado (ex. Incidência) estiver em ESTADOS_SEGUE_PARA_ENTREGA.
MOTIVO_INCIDENCIA_NAO_SEGUE_LABELS = (
    "Anulado / Cancelado",
    "Recolha com danos visíveis",
    "Pedido Recusado Danificado",
    "Recusa parcial (artigos danificados)",
    "Não rececionado pela transportadora",
    "Entrega com artigos em falta (infor pelo Cliente)",
    "Extraviado no Operador",
    "Entrega recusada",
    "Fora da zona",
    "Recusa Parcial",
)

_MOTIVOS_INCIDENCIA_NAO_SEGUE = frozenset(
    lab.strip().casefold() for lab in MOTIVO_INCIDENCIA_NAO_SEGUE_LABELS
)


# Conferência de volumes por QR de etiqueta ENOVO (cadastro / futura leitura).
# QR 18 dígitos: TRK(12) + total_volume(3) + volume(3), ex. 008007108629003001
# → TRK 8007108629 (id_vonzu, sem zeros à esquerda), total 3, volume 1.
# conferido: {"conf_1": ["DD/MM/AAAA", n_volume], ...}
QR_ETIQUETA_ENOVO_LEN = 18
QR_ETIQUETA_ENOVO_TRK_LEN = 12
QR_ETIQUETA_ENOVO_BLOCO_LEN = 3


def conferencia_volumes_padrao():
    return {
        "TRK": None,
        "total_volume": 0,
        "total_vol_conferido": 0,
        "conferido": {},
    }


def montar_conferencia_volumes_inicial(id_vonzu, volume=None):
    dados = conferencia_volumes_padrao()
    if id_vonzu is not None:
        dados["TRK"] = int(id_vonzu)
    if volume is not None:
        dados["total_volume"] = int(volume)
    return dados


def conferencia_volumes_para_exibicao(pedido):
    """Cópia segura do JSON para o cadastro; preenche TRK/total a partir do pedido se vazios."""
    dados = pedido.conferencia_volumes
    if not isinstance(dados, dict):
        dados = conferencia_volumes_padrao()
    else:
        dados = deepcopy(dados)
        for chave, valor in conferencia_volumes_padrao().items():
            dados.setdefault(chave, valor)
    if dados.get("TRK") is None and pedido.id_vonzu is not None:
        dados["TRK"] = int(pedido.id_vonzu)
    if not dados.get("total_volume") and pedido.volume is not None:
        dados["total_volume"] = int(pedido.volume)
    return dados


def parse_qr_etiqueta_enovo(codigo):
    """Parseia o QR da etiqueta ENOVO. Retorna dict ou None se inválido."""
    raw = "".join(str(codigo or "").split())
    if not raw.isdigit() or len(raw) != QR_ETIQUETA_ENOVO_LEN:
        return None
    trk_len = QR_ETIQUETA_ENOVO_TRK_LEN
    bloco = QR_ETIQUETA_ENOVO_BLOCO_LEN
    trk = int(raw[:trk_len])
    total_volume = int(raw[trk_len : trk_len + bloco])
    volume = int(raw[trk_len + bloco :])
    if trk <= 0 or total_volume <= 0 or volume <= 0 or volume > total_volume:
        return None
    return {
        "TRK": trk,
        "total_volume": total_volume,
        "volume": volume,
    }


def motivo_incidencia_bloqueia_entrega(motivo: str | None) -> bool:
    """True se o motivo de incidência (ENOVO) impede seguir para entrega."""
    if not motivo:
        return False
    return str(motivo).strip().casefold() in _MOTIVOS_INCIDENCIA_NAO_SEGUE


def estado_segue_para_entrega(estado: str | None, motivo_incidencia: str | None = None) -> bool:
    """True se estado permite entrega e o motivo de incidência não bloqueia.

    Se o estado não segue, o resultado é False mesmo com motivo vazio ou não bloqueante.
    Se o motivo bloqueia, o resultado é False mesmo com estado em ESTADOS_SEGUE_PARA_ENTREGA.
    """
    if (estado or "") not in ESTADOS_SEGUE_PARA_ENTREGA:
        return False
    if motivo_incidencia_bloqueia_entrega(motivo_incidencia):
        return False
    return True


def motivo_incidencia_de_tentativa(mov) -> str | None:
    """Motivo na tentativa; se vazio, usa o do pedido."""
    raw = getattr(mov, "motivo_incidencia", None)
    if raw and str(raw).strip():
        return str(raw).strip()
    pedido = getattr(mov, "pedido", None)
    if pedido is not None:
        raw_p = getattr(pedido, "motivo_incidencia", None)
        if raw_p and str(raw_p).strip():
            return str(raw_p).strip()
    return None


def tentativa_segue_para_entrega(mov) -> bool:
    return estado_segue_para_entrega(
        getattr(mov, "estado", None),
        motivo_incidencia_de_tentativa(mov),
    )


def q_motivo_incidencia_bloqueia_entrega() -> Q:
    bloqueio = Q()
    for lab in MOTIVO_INCIDENCIA_NAO_SEGUE_LABELS:
        bloqueio |= Q(motivo_incidencia__iexact=lab)
        bloqueio |= Q(
            Q(motivo_incidencia__isnull=True) | Q(motivo_incidencia=""),
            pedido__motivo_incidencia__iexact=lab,
        )
    return bloqueio


def estado_label(estado: str | None) -> str:
    """Retorna o label do estado; fallback para o valor bruto."""
    if not estado:
        return ""
    return ESTADO_LABEL_POR_VALOR.get(estado, estado)


def exclude_tentativas_com_data_posterior(qs):
    """Exclui linhas que possuem outra TentativaEntrega do mesmo pedido em data estritamente posterior."""
    posteriores = TentativaEntrega.objects.filter(
        pedido_id=OuterRef("pedido_id"),
        data_tentativa__gt=OuterRef("data_tentativa"),
    )
    return qs.exclude(Exists(posteriores))


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
    motivo_incidencia = models.CharField(max_length=120, null=True, blank=True)
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
    conferencia_volumes = models.JSONField(
        default=conferencia_volumes_padrao,
        blank=True,
        help_text=(
            "Conferência por QR ENOVO: "
            '{"TRK": int, "total_volume": int, "total_vol_conferido": int, '
            '"conferido": {"conf_n": ["DD/MM/AAAA", n_volume]}}'
        ),
    )
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
        permissions = [
            ("conferir_etiqueta_enovo", "Pode conferir etiquetas ENOVO"),
        ]

    def __str__(self):
        return str(self.pedido or self.id_vonzu)


class AvaliacaoPedido(models.Model):
    ORIGEM_GERACAO_CHOICES = [
        ("MANUAL_RELATORIO", "Manual via Relatório"),
    ]

    id = models.BigAutoField(primary_key=True)
    pedido = models.OneToOneField(
        Pedido,
        on_delete=models.CASCADE,
        db_column="pedido_id",
        related_name="avaliacao",
    )
    token_publico = models.CharField(max_length=512, unique=True, null=True, blank=True)
    origem_geracao = models.CharField(max_length=30, choices=ORIGEM_GERACAO_CHOICES, default="MANUAL_RELATORIO")
    selecionado_para_envio = models.BooleanField(default=True)
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
            models.Index(fields=["selecionado_para_envio"]),
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
    motivo_incidencia = models.CharField(max_length=120, null=True, blank=True)
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
            ("view_relatorio_fechamento", "Pode acessar o Relatório de Fechamento (logística)"),
            ("view_relatorio_avaliacao", "Pode acessar o Relatório de Avaliações"),
            ("send_email_avaliacao", "Pode enviar e-mails de avaliação"),
            ("generate_email_queue_avaliacao", "Pode gerar fila de e-mails de avaliação"),
            ("download_anexo_gmail_gerencial", "Pode descarregar anexos Gmail no Relatório Gerencial"),
        ]
        indexes = [
            models.Index(fields=["pedido", "data_tentativa"]),
            models.Index(fields=["data_tentativa", "faturado"]),
        ]

    def invalidar_sms_se_janela_mudou(self, nova_data, novo_periodo=None):
        """SMS vale só para a data/período em que foi enviado; não herdar a flag."""
        if not self.pk:
            return
        periodo_atual = (self.periodo or None)
        novo_periodo = (novo_periodo or None)
        if self.data_tentativa != nova_data or periodo_atual != novo_periodo:
            self.sms_enviado = False

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
    resolvido = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "incidencia"
        permissions = [
            ("view_relatorio_incidencia", "Pode acessar o Relatório de Incidências"),
        ]
        indexes = [
            models.Index(fields=["pedido"]),
            models.Index(fields=["data"]),
            models.Index(fields=["origem"]),
        ]

    def __str__(self):
        return f"Incidência {self.tipo} — Pedido {self.pedido_id}"


class ProdutoCritico(models.Model):
    """Catálogo de produtos críticos (código + descrição)."""

    id = models.BigAutoField(primary_key=True)
    codigo = models.CharField(max_length=20)
    descricao = models.CharField(max_length=100)

    class Meta:
        db_table = "produto_critico"
        verbose_name = "Produto crítico"
        verbose_name_plural = "Produtos críticos"
        ordering = ["codigo"]
        constraints = [
            models.UniqueConstraint(
                fields=["codigo"],
                name="unique_produto_critico_codigo",
            ),
        ]

    def __str__(self):
        return f"{self.codigo} — {self.descricao}"
