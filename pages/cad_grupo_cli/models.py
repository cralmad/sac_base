from django.db import models
from django.core.validators import MinLengthValidator
from django.db.models.functions import Upper

class GrupoCli(models.Model):
    id = models.BigAutoField(primary_key=True)

    descricao = models.CharField(
        max_length=30,
        unique=True,
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

        constraints = [
            models.UniqueConstraint(
                Upper('descricao'),
                name='unique_descricao_upper'
            )
        ]

    def __str__(self):
        return self.descricao