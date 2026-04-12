from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("motorista", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="motorista",
            name="codigo",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddConstraint(
            model_name="motorista",
            constraint=models.UniqueConstraint(
                condition=Q(is_deleted=False, codigo__isnull=False) & ~Q(codigo=""),
                fields=("filial", "codigo"),
                name="unique_motorista_codigo_ativo_por_filial",
            ),
        ),
    ]
