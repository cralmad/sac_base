from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("motorista", "0004_motorista_categoria"),
    ]

    operations = [
        migrations.AddField(
            model_name="motorista",
            name="id_enovo",
            field=models.CharField(blank=True, max_length=40, null=True),
        ),
        migrations.AddConstraint(
            model_name="motorista",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_deleted=False)
                & ~models.Q(id_enovo="")
                & models.Q(id_enovo__isnull=False),
                fields=("filial", "id_enovo"),
                name="unique_motorista_id_enovo_ativo_por_filial",
            ),
        ),
    ]
