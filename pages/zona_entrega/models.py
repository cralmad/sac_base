import re

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.functions import Upper

from pages.auditoria.models import AuditFieldsMixin, SoftDeleteMixin
from pages.filial.models import Filial


REGEX_CP7_PORTUGAL = re.compile(r"^\d{4}-\d{3}$")


def normalizar_codigo_postal(sigla_pais, codigo_postal):
    valor = (codigo_postal or "").strip().upper()
    if sigla_pais == "PRT":
        if not REGEX_CP7_PORTUGAL.match(valor):
            raise ValidationError("Código postal inválido para Portugal. Utilize o formato XXXX-XXX.")
        return {
            "codigo_postal": valor,
            "cp4": valor[:4],
            "cp7_num": int(valor.replace("-", "")),
        }

    digitos = "".join(char for char in valor if char.isdigit())
    if not digitos:
        raise ValidationError("Código postal inválido.")

    return {
        "codigo_postal": valor,
        "cp4": digitos[:4],
        "cp7_num": int(digitos),
    }


class ZonaEntrega(AuditFieldsMixin, SoftDeleteMixin, models.Model):
    id = models.BigAutoField(primary_key=True)
    filial = models.ForeignKey(Filial, on_delete=models.PROTECT, related_name="zonas_entrega")
    codigo = models.CharField(max_length=20)
    descricao = models.CharField(max_length=100)
    prioridade = models.PositiveIntegerField(default=0)
    ativa = models.BooleanField(default=True)
    valor_cobranca_unitario_pedido = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valor_pagamento_unitario_entrega = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valor_pagamento_fixo_rota = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    observacao = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        db_table = "zona_entrega"
        ordering = ["filial__nome", "descricao"]
        base_manager_name = "all_objects"
        constraints = [
            models.UniqueConstraint(
                fields=["filial", "codigo"],
                condition=Q(is_deleted=False),
                name="unique_zona_entrega_codigo_ativo_por_filial",
            ),
            models.UniqueConstraint(
                Upper("descricao"), "filial",
                condition=Q(is_deleted=False),
                name="unique_zona_entrega_descricao_upper_ativa_por_filial",
            ),
        ]

    def clean(self):
        if not self.filial_id:
            raise ValidationError({"filial": "Selecione a matriz/filial da zona de entrega."})

        filial = self.filial
        if not filial.pais_atuacao_id:
            raise ValidationError({"filial": "A matriz/filial selecionada não possui país de atuação cadastrado."})

    def save(self, *args, **kwargs):
        self.codigo = (self.codigo or "").strip().upper()
        self.descricao = (self.descricao or "").strip().upper()
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.codigo} - {self.descricao}"


class ZonaEntregaFaixaPostal(models.Model):
    TIPO_CP4 = "CP4"
    TIPO_CP7 = "CP7"
    TIPO_INTERVALO_CHOICES = [
        (TIPO_CP4, "CP4"),
        (TIPO_CP7, "CP7"),
    ]

    id = models.BigAutoField(primary_key=True)
    zona_entrega = models.ForeignKey(ZonaEntrega, on_delete=models.CASCADE, related_name="faixas_postais")
    tipo_intervalo = models.CharField(max_length=3, choices=TIPO_INTERVALO_CHOICES, default=TIPO_CP7)
    codigo_postal_inicial = models.CharField(max_length=8)
    codigo_postal_final = models.CharField(max_length=8)
    cp4_inicial = models.CharField(max_length=4, db_index=True)
    cp4_final = models.CharField(max_length=4, db_index=True)
    cp7_inicial_num = models.PositiveIntegerField(db_index=True)
    cp7_final_num = models.PositiveIntegerField(db_index=True)
    ativa = models.BooleanField(default=True)

    class Meta:
        db_table = "zona_entrega_faixa_postal"
        ordering = ["tipo_intervalo", "codigo_postal_inicial"]

    def clean(self):
        if not self.zona_entrega_id:
            raise ValidationError({"zona_entrega": "Zona de entrega inválida para a faixa postal."})

        pais_sigla = self.zona_entrega.filial.pais_atuacao.sigla if self.zona_entrega.filial.pais_atuacao_id else ""
        inicio = normalizar_codigo_postal(pais_sigla, self.codigo_postal_inicial)
        fim = normalizar_codigo_postal(pais_sigla, self.codigo_postal_final)

        self.codigo_postal_inicial = inicio["codigo_postal"]
        self.codigo_postal_final = fim["codigo_postal"]
        self.cp4_inicial = inicio["cp4"]
        self.cp4_final = fim["cp4"]
        self.cp7_inicial_num = inicio["cp7_num"]
        self.cp7_final_num = fim["cp7_num"]

        if self.tipo_intervalo == self.TIPO_CP4:
            if int(self.cp4_inicial) > int(self.cp4_final):
                raise ValidationError("Faixa CP4 inválida: o início não pode ser maior que o fim.")
        elif self.cp7_inicial_num > self.cp7_final_num:
            raise ValidationError("Faixa CP7 inválida: o início não pode ser maior que o fim.")

        if not self.ativa:
            return

        conflitos = ZonaEntregaFaixaPostal.objects.filter(
            zona_entrega__filial=self.zona_entrega.filial,
            zona_entrega__is_deleted=False,
            tipo_intervalo=self.tipo_intervalo,
            ativa=True,
        )
        if self.pk:
            conflitos = conflitos.exclude(pk=self.pk)

        if self.tipo_intervalo == self.TIPO_CP4:
            faixa_inicio = int(self.cp4_inicial)
            faixa_fim = int(self.cp4_final)
            for conflito in conflitos:
                if faixa_inicio <= int(conflito.cp4_final) and faixa_fim >= int(conflito.cp4_inicial):
                    raise ValidationError("Existe sobreposição de faixa CP4 para a mesma matriz/filial.")
        else:
            for conflito in conflitos:
                if self.cp7_inicial_num <= conflito.cp7_final_num and self.cp7_final_num >= conflito.cp7_inicial_num:
                    raise ValidationError("Existe sobreposição de faixa CP7 para a mesma matriz/filial.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.zona_entrega} [{self.codigo_postal_inicial} - {self.codigo_postal_final}]"


class ZonaEntregaExcecaoPostal(models.Model):
    TIPO_EXCLUIR = "EXCLUIR"
    TIPO_INCLUIR = "INCLUIR"
    TIPO_EXCECAO_CHOICES = [
        (TIPO_EXCLUIR, "Excluir"),
        (TIPO_INCLUIR, "Incluir"),
    ]

    id = models.BigAutoField(primary_key=True)
    zona_entrega = models.ForeignKey(ZonaEntrega, on_delete=models.CASCADE, related_name="excecoes_postais")
    codigo_postal = models.CharField(max_length=8)
    cp4 = models.CharField(max_length=4, db_index=True)
    cp7_num = models.PositiveIntegerField(db_index=True)
    tipo_excecao = models.CharField(max_length=7, choices=TIPO_EXCECAO_CHOICES, default=TIPO_EXCLUIR)
    ativa = models.BooleanField(default=True)
    observacao = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        db_table = "zona_entrega_excecao_postal"
        ordering = ["codigo_postal"]
        constraints = [
            models.UniqueConstraint(
                fields=["zona_entrega", "codigo_postal", "tipo_excecao"],
                condition=Q(ativa=True),
                name="unique_zona_excecao_ativa",
            )
        ]

    def clean(self):
        if not self.zona_entrega_id:
            raise ValidationError({"zona_entrega": "Zona de entrega inválida para a exceção postal."})

        pais_sigla = self.zona_entrega.filial.pais_atuacao.sigla if self.zona_entrega.filial.pais_atuacao_id else ""
        normalizado = normalizar_codigo_postal(pais_sigla, self.codigo_postal)
        self.codigo_postal = normalizado["codigo_postal"]
        self.cp4 = normalizado["cp4"]
        self.cp7_num = normalizado["cp7_num"]

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.zona_entrega} [{self.tipo_excecao} {self.codigo_postal}]"
