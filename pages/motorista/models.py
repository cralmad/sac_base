from django.db import models
from django.db.models import Q

from pages.auditoria.models import AuditFieldsMixin, SoftDeleteMixin
from pages.filial.models import Filial


class Motorista(AuditFieldsMixin, SoftDeleteMixin, models.Model):
    class Categoria(models.TextChoices):
        LIGEIRO = "LIGEIRO", "Ligeiro"
        PESADO = "PESADO", "Pesado"

    id = models.BigAutoField(primary_key=True)
    filial = models.ForeignKey(Filial, on_delete=models.PROTECT, related_name="motoristas")
    codigo = models.CharField(max_length=20, null=True, blank=True)
    nome = models.CharField(max_length=100)
    telefone = models.CharField(max_length=20)
    categoria = models.CharField(
        max_length=10,
        choices=Categoria.choices,
        default=Categoria.LIGEIRO,
    )
    ativa = models.BooleanField(default=True)

    class Meta:
        db_table = "motorista"
        ordering = ["filial__nome", "nome"]
        base_manager_name = "all_objects"
        constraints = [
            models.UniqueConstraint(
                fields=["filial", "codigo"],
                condition=Q(is_deleted=False) & ~Q(codigo="") & Q(codigo__isnull=False),
                name="unique_motorista_codigo_ativo_por_filial",
            ),
            models.UniqueConstraint(
                fields=["filial", "nome"],
                condition=Q(is_deleted=False),
                name="unique_motorista_nome_ativo_por_filial",
            )
        ]

    def save(self, *args, **kwargs):
        self.codigo = (self.codigo or "").strip().upper()
        self.nome = (self.nome or "").strip().upper()
        self.telefone = (self.telefone or "").strip()
        if self.categoria:
            self.categoria = str(self.categoria).strip().upper()
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome
