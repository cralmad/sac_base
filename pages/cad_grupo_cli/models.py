from django.db import models
from django.db.models import Q
from django.core.validators import MinLengthValidator
from django.db.models.functions import Upper
from pages.auditoria.models import AuditFieldsMixin, SoftDeleteMixin

class GrupoCli(AuditFieldsMixin, SoftDeleteMixin, models.Model):
    id = models.BigAutoField(primary_key=True)

    descricao = models.CharField(
        max_length=30,
        null=False,
        blank=False,
        validators=[MinLengthValidator(3)]
    )
    atualizacao = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.descricao:
            self.descricao = self.descricao.upper()
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'grupo_cli'
        base_manager_name = 'all_objects'

        constraints = [
            models.UniqueConstraint(
                Upper('descricao'),
                condition=Q(is_deleted=False),
                name='unique_descricao_upper_active'
            )
        ]

    def __str__(self):
        return self.descricao