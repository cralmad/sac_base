from django.db import migrations, models

import pages.pedidos.models


class Migration(migrations.Migration):

    dependencies = [
        ("pedidos", "0023_incidencia_resolvido"),
    ]

    operations = [
        migrations.AddField(
            model_name="pedido",
            name="conferencia_volumes",
            field=models.JSONField(
                blank=True,
                default=pages.pedidos.models.conferencia_volumes_padrao,
                help_text=(
                    "Conferência por QR ENOVO: "
                    '{"TRK": int, "total_volume": int, "total_vol_conferido": int, '
                    '"conferido": {"conf_n": ["DD/MM/AAAA", n_volume]}}'
                ),
            ),
        ),
    ]
