from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from pages.core.models import Pais


class Filial(models.Model):
    id = models.BigAutoField(primary_key=True)
    codigo = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=100, unique=True)
    pais_endereco = models.ForeignKey(
        Pais,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="filiais_endereco",
    )
    pais_atuacao = models.ForeignKey(
        Pais,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="filiais_atuacao",
    )
    is_matriz = models.BooleanField(default=False)
    ativa = models.BooleanField(default=True)
    lat_deposito = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng_deposito = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    class Meta:
        db_table = "filial"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_matriz"],
                condition=Q(is_matriz=True),
                name="unique_matriz_true",
            )
        ]

    def clean(self):
        if not self.pk and not Filial.objects.exists() and not self.is_matriz:
            raise ValidationError({"is_matriz": "O primeiro cadastro de matriz/filial deve ser a matriz."})

        matriz_qs = Filial.objects.filter(is_matriz=True)
        if self.pk:
            matriz_qs = matriz_qs.exclude(pk=self.pk)

        if self.is_matriz and matriz_qs.exists():
            raise ValidationError({"is_matriz": "Já existe uma matriz cadastrada."})

        if not self.is_matriz and not self.pk and not Filial.objects.filter(is_matriz=True).exists() and Filial.objects.exists():
            raise ValidationError({"is_matriz": "A primeira unidade deve ser cadastrada como matriz."})

    def save(self, *args, **kwargs):
        self.codigo = (self.codigo or "").strip().upper()
        self.nome = (self.nome or "").strip().upper()
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class UsuarioFilial(models.Model):
    id = models.BigAutoField(primary_key=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="filiais_vinculadas",
    )
    filial = models.ForeignKey(
        Filial,
        on_delete=models.CASCADE,
        related_name="usuarios_vinculados",
    )
    pode_consultar = models.BooleanField(default=True)
    pode_escrever = models.BooleanField(default=False)
    ativo = models.BooleanField(default=True)

    class Meta:
        db_table = "usuario_filial"
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "filial"],
                name="unique_usuario_filial",
            )
        ]

    def __str__(self):
        return f"{self.usuario} - {self.filial}"
