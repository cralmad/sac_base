from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zona_entrega", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="zonaentrega",
            name="valor_pagamento_fixo_rota_pesado",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="zonaentrega",
            name="valor_pagamento_unitario_entrega_pesado",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]
