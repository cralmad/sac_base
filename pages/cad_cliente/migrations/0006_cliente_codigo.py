from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cad_cliente", "0005_soft_delete_unique_constraints"),
    ]

    operations = [
        migrations.AddField(
            model_name="cliente",
            name="codigo",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
    ]
