from django.db import models

class Pais(models.Model):
    nome = models.CharField(max_length=60, unique=True)
    sigla = models.CharField(max_length=3, unique=True) # Ex: BRA, PRT
    codigo_tel = models.CharField(max_length=5, blank=True) # Ex: +55, +351

    class Meta:
        db_table = 'global_pais'
        verbose_name = "País"

    def __str__(self):
        return self.nome

class Regiao(models.Model):
    """Representa Estados (BR) ou Distritos/Regiões Autónomas (PT)"""
    id_uf = models.IntegerField(null=False, blank=False) # Ex: IBGE para estados brasileiros, ou código de distrito para regiões portuguesas
    nome = models.CharField(max_length=100)
    sigla = models.CharField(max_length=2) # Ex: SP, RJ ou códigos de distrito
    pais = models.ForeignKey(Pais, on_delete=models.CASCADE, related_name='regioes')

    class Meta:
        db_table = 'global_regiao'
        verbose_name = "Estado/Região"
        constraints = [
            models.UniqueConstraint(
                fields=['id_uf', 'pais'], 
                name='unique_regiao_por_pais',
                violation_error_message="Esta região já está cadastrada neste país."
            )
        ]

    def __str__(self):
        return f"{self.nome} ({self.pais.sigla})"

class Cidade(models.Model):
    id_cid = models.IntegerField(blank=False, null=False) # Ex: IBGE para cidades brasileiras, ou código de distrito para cidades portuguesas
    nome = models.CharField(max_length=100)
    regiao = models.ForeignKey(Regiao, on_delete=models.CASCADE, related_name='cidades')
    codigo_postal = models.CharField(max_length=10, blank=True, null=True)

    class Meta:
        db_table = 'global_cidade'
        verbose_name = "Cidade"
        ordering = ['nome']
        constraints = [
            models.UniqueConstraint(
                fields=['id_cid', 'regiao'], 
                name='unique_cidade_por_regiao',
                violation_error_message="Esta cidade já está cadastrada neste estado/distrito."
            )
        ]

    def __str__(self):
        return f"{self.nome} - {self.regiao.sigla}"