from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("pedidos", "0024_pedido_conferencia_volumes"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="pedido",
            options={
                "permissions": [
                    ("conferir_etiqueta_enovo", "Pode conferir etiquetas ENOVO"),
                ],
            },
        ),
    ]
