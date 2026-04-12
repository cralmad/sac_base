from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pedidos", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="pedido",
            name="origem",
            field=models.CharField(
                choices=[("IMPORTADO", "Importado"), ("MANUAL", "Manual")],
                default="IMPORTADO",
                max_length=10,
            ),
        ),
    ]
