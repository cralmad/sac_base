from django.db import models
from django.core.validators import MinLengthValidator
from pages.cad_grupo_cli.models import GrupoCli
from pages.core.models import Pais, Regiao, Cidade


class Cliente(models.Model):
    id = models.BigAutoField(primary_key=True)

    grupo = models.ForeignKey(
        GrupoCli,
        on_delete=models.PROTECT,
        null=False,
        blank=False,
        db_column='grupo_id'
    )

    nome = models.CharField(
        max_length=100,
        null=False,
        blank=False,
        validators=[MinLengthValidator(3)]
    )

    rsocial = models.CharField(
        max_length=100,
        null=False,
        blank=False,
        validators=[MinLengthValidator(3)]
    )

    pais = models.ForeignKey(
        Pais,
        on_delete=models.PROTECT,
        null=False,
        blank=False,
        db_column='pais_id'
    )
    regiao = models.ForeignKey(
        Regiao,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column='regiao_id'
    )
    cidade = models.ForeignKey(
        Cidade,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column='cidade_id'
    )
    logradouro  = models.CharField(max_length=20,  null=True, blank=True)
    endereco    = models.CharField(max_length=150, null=True, blank=True)
    numero      = models.CharField(max_length=10,  null=True, blank=True)
    complemento = models.CharField(max_length=50,  null=True, blank=True)
    bairro      = models.CharField(max_length=60,  null=True, blank=True)
    codpostal   = models.CharField(max_length=10,   null=True, blank=True)
    
    '''O identificador é um campo opcional que pode ser usado para armazenar um número de identificação fiscal, 
    como CPF ou CNPJ ou qualquer outro identificador único para o cliente.'''
    identificador  = models.CharField(max_length=20,  null=True, blank=True)

    atualizacao = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        
        self.nome = self.nome.upper()
        self.rsocial = self.rsocial.upper()

        super().save(*args, **kwargs)

    class Meta:
        db_table = 'cliente'

        constraints = [
            models.UniqueConstraint(
                fields=['identificador'],
                name='unique_identificador'
            )
        ]

    def __str__(self):
        return self.nome
