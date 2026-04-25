# Generated manually on 2026-04-25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pedidos', '0011_add_relatorio_gerencial_permission'),
    ]

    operations = [
        migrations.AddField(
            model_name='devolucao',
            name='fotos',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
