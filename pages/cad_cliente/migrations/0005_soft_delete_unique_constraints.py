from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cad_cliente", "0004_cliente_auditoria_soft_delete"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="cliente",
            name="unique_identificador",
        ),
        migrations.AddConstraint(
            model_name="cliente",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_deleted=False, identificador__isnull=False) & ~models.Q(identificador=""),
                fields=("identificador",),
                name="unique_identificador_active",
            ),
        ),
    ]