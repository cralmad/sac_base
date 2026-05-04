from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models

from pages.auditoria.models import AuditFieldsMixin
from pages.filial.models import Filial


class TipoClassificacaoPlano(models.TextChoices):
    RECEITA = "receita", "Receita"
    DESPESA = "despesa", "Despesa"
    NEUTRO = "neutro", "Neutro"


class PlanoContas(models.Model):
    """Plano de contas hierárquico (até 4 níveis)."""

    id = models.BigAutoField(primary_key=True)
    codigo = models.CharField(max_length=40, unique=True, db_index=True)
    nome = models.CharField(max_length=200)
    nivel = models.PositiveSmallIntegerField()
    tipo_classificacao = models.CharField(
        max_length=20,
        choices=TipoClassificacaoPlano.choices,
        default=TipoClassificacaoPlano.RECEITA,
    )
    pai = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="filhos",
    )

    class Meta:
        db_table = "plano_contas"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} — {self.nome}"


class ContaFinanceira(models.Model):
    """Conta de custódia (caixa, banco, administradora, etc.)."""

    id = models.BigAutoField(primary_key=True)
    filial = models.ForeignKey(
        Filial,
        on_delete=models.PROTECT,
        db_column="filial_id",
        related_name="contas_financeiras",
    )
    codigo = models.CharField(max_length=30, blank=True, default="")
    nome = models.CharField(max_length=120)
    ativo = models.BooleanField(default=True)

    class Meta:
        db_table = "conta_financeira"
        ordering = ["filial_id", "nome"]

    def __str__(self):
        return f"{self.nome} ({self.filial_id})"


class AdministradoraCartao(models.Model):
    id = models.BigAutoField(primary_key=True)
    nome = models.CharField(max_length=120)
    cnpj = models.CharField(max_length=18, blank=True, default="")
    conta_custodia = models.ForeignKey(
        ContaFinanceira,
        on_delete=models.PROTECT,
        related_name="administradoras_cartao",
    )

    class Meta:
        db_table = "administradora_cartao"

    def __str__(self):
        return self.nome


class FormaPagamento(models.Model):
    id = models.BigAutoField(primary_key=True)
    codigo = models.CharField(max_length=30, unique=True)
    nome = models.CharField(max_length=120)
    aceita_parcelamento = models.BooleanField(default=True)
    conta_custodia_padrao = models.ForeignKey(
        ContaFinanceira,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="formas_pagamento_padrao",
    )
    administradora = models.ForeignKey(
        AdministradoraCartao,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="formas_pagamento",
    )
    ativo = models.BooleanField(default=True)
    ordem = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "forma_pagamento"
        ordering = ["ordem", "nome"]

    def __str__(self):
        return self.nome


class RegistroFinanceiroTipo(models.TextChoices):
    ENTRADA = "ENTRADA", "Entrada"
    SAIDA = "SAIDA", "Saída"
    TRANSFERENCIA = "TRANSFERENCIA", "Transferência"


class RegistroFinanceiroStatus(models.TextChoices):
    ABERTO = "aberto", "Aberto"
    PARCIAL = "parcial", "Parcial"
    LIQUIDADO = "liquidado", "Liquidado"
    CANCELADO = "cancelado", "Cancelado"


class RegistroFinanceiro(AuditFieldsMixin, models.Model):
    """Título financeiro (fato gerador)."""

    id = models.BigAutoField(primary_key=True)
    filial = models.ForeignKey(
        Filial,
        on_delete=models.PROTECT,
        db_column="filial_id",
        related_name="registros_financeiros",
    )
    tipo = models.CharField(max_length=20, choices=RegistroFinanceiroTipo.choices)
    status = models.CharField(
        max_length=20,
        choices=RegistroFinanceiroStatus.choices,
        default=RegistroFinanceiroStatus.ABERTO,
    )
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    valor_fat = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    valor_rest = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    plano_contas = models.ForeignKey(
        PlanoContas,
        on_delete=models.PROTECT,
        related_name="registros_financeiros",
    )
    observacao = models.TextField(blank=True, default="")

    contraparte_content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    contraparte_object_id = models.PositiveBigIntegerField(null=True, blank=True)
    contraparte = GenericForeignKey("contraparte_content_type", "contraparte_object_id")

    referencia_content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    referencia_object_id = models.PositiveBigIntegerField(null=True, blank=True)
    referencia = GenericForeignKey("referencia_content_type", "referencia_object_id")

    class Meta:
        db_table = "registro_financeiro"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["filial", "-created_at"]),
            models.Index(fields=["contraparte_content_type", "contraparte_object_id"]),
            models.Index(fields=["referencia_content_type", "referencia_object_id"]),
        ]

    def __str__(self):
        return f"RF {self.pk} {self.tipo} {self.valor}"


class Faturamento(AuditFieldsMixin, models.Model):
    """Evento de quitação / agrupamento de pagamento."""

    id = models.BigAutoField(primary_key=True)
    filial = models.ForeignKey(
        Filial,
        on_delete=models.PROTECT,
        db_column="filial_id",
        related_name="faturamentos",
    )
    observacao = models.TextField(blank=True, default="")

    contraparte_pagamento_content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    contraparte_pagamento_object_id = models.PositiveBigIntegerField(null=True, blank=True)
    contraparte_pagamento = GenericForeignKey(
        "contraparte_pagamento_content_type",
        "contraparte_pagamento_object_id",
    )

    registros_financeiros = models.ManyToManyField(
        RegistroFinanceiro,
        through="FaturamentoRegistroFinanceiro",
        related_name="faturamentos_vinculados",
    )

    class Meta:
        db_table = "faturamento"
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["filial", "-created_at"])]

    def __str__(self):
        return f"Faturamento {self.pk}"


class FaturamentoRegistroFinanceiro(models.Model):
    """Through M2M: ordem de abatimento + valor efetivo."""

    id = models.BigAutoField(primary_key=True)
    faturamento = models.ForeignKey(
        Faturamento,
        on_delete=models.CASCADE,
        related_name="vinculos_registro",
    )
    registro_financeiro = models.ForeignKey(
        RegistroFinanceiro,
        on_delete=models.PROTECT,
        related_name="vinculos_faturamento",
    )
    filial = models.ForeignKey(
        Filial,
        on_delete=models.PROTECT,
        db_column="filial_id",
        related_name="vinculos_faturamento_registro",
    )
    ordem = models.PositiveSmallIntegerField()
    valor_abatido = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "faturamento_registro_financeiro"
        constraints = [
            models.UniqueConstraint(
                fields=["faturamento", "registro_financeiro"],
                name="unique_faturamento_registro_financeiro",
            ),
            models.UniqueConstraint(
                fields=["faturamento", "ordem"],
                name="unique_faturamento_ordem_abatimento",
            ),
        ]
        ordering = ["faturamento_id", "ordem"]


class FaturamentoFormaPagamento(models.Model):
    """Linha valor × forma no faturamento."""

    id = models.BigAutoField(primary_key=True)
    faturamento = models.ForeignKey(
        Faturamento,
        on_delete=models.CASCADE,
        related_name="linhas_forma_pagamento",
    )
    forma_pagamento = models.ForeignKey(
        FormaPagamento,
        on_delete=models.PROTECT,
        related_name="linhas_faturamento",
    )
    valor = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "faturamento_forma_pagamento"
        ordering = ["faturamento_id", "id"]


class ParcelaFaturamentoStatus(models.TextChoices):
    ABERTO = "ABERTO", "Aberto"
    LIQUIDADO = "LIQUIDADO", "Liquidado"
    REPASSADO = "REPASSADO", "Repassado"
    DEVOLVIDO = "DEVOLVIDO", "Devolvido"
    SUBSTITUIDO = "SUBSTITUIDO", "Substituído"
    ANTECIPADO = "ANTECIPADO", "Antecipado"


class ParcelaFaturamento(models.Model):
    id = models.BigAutoField(primary_key=True)
    faturamento = models.ForeignKey(
        Faturamento,
        on_delete=models.CASCADE,
        related_name="parcelas",
    )
    faturamento_forma_pagamento = models.ForeignKey(
        FaturamentoFormaPagamento,
        on_delete=models.CASCADE,
        related_name="parcelas",
    )
    forma_pagamento = models.ForeignKey(
        FormaPagamento,
        on_delete=models.PROTECT,
        related_name="parcelas_faturamento",
    )
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    valor_liquido = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    data_vencimento = models.DateField(null=True, blank=True)
    data_liquidacao = models.DateField(null=True, blank=True)
    conta_custodia = models.ForeignKey(
        ContaFinanceira,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="parcelas_custodia",
    )
    conta_destino = models.ForeignKey(
        ContaFinanceira,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="parcelas_destino",
    )
    status = models.CharField(
        max_length=20,
        choices=ParcelaFaturamentoStatus.choices,
        default=ParcelaFaturamentoStatus.ABERTO,
    )

    registro_gerado_content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    registro_gerado_object_id = models.PositiveBigIntegerField(null=True, blank=True)
    registro_gerado = GenericForeignKey(
        "registro_gerado_content_type",
        "registro_gerado_object_id",
    )

    class Meta:
        db_table = "parcela_faturamento"
        ordering = ["faturamento_id", "id"]
        indexes = [
            models.Index(fields=["faturamento", "status"]),
        ]

    def clean(self):
        super().clean()
        if self.conta_custodia_id and self.conta_destino_id:
            if self.conta_custodia.filial_id != self.conta_destino.filial_id:
                raise ValidationError("Contas de custódia e destino devem pertencer à mesma filial.")
