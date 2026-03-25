from django.db import models
from django.core.validators import MinLengthValidator
from pages.cad_grupo_cli.models import GrupoCli


class Cliente(models.Model):
    id = models.BigAutoField(primary_key=True)

    grupo = models.ForeignKey(
        GrupoCli,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column='grupo_id'
    )

    nome = models.CharField(
        max_length=100,
        null=False,
        blank=False,
        validators=[MinLengthValidator(3)]
    )

    logradouro  = models.CharField(max_length=20,  null=True, blank=True)
    endereco    = models.CharField(max_length=150, null=True, blank=True)
    numero      = models.CharField(max_length=10,  null=True, blank=True)
    complemento = models.CharField(max_length=50,  null=True, blank=True)
    bairro      = models.CharField(max_length=60,  null=True, blank=True)
    pais        = models.CharField(max_length=20,  null=False, blank=False)
    uf          = models.CharField(max_length=10,  null=False, blank=False)
    cidade      = models.CharField(max_length=50,  null=False, blank=False)
    codpostal   = models.CharField(max_length=8,   null=True, blank=True)

    atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'cliente'

    def __str__(self):
        return self.nome
