from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
        ("filial", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="filial",
            name="pais_atuacao",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="filiais_atuacao", to="core.pais"),
        ),
        migrations.AddField(
            model_name="filial",
            name="pais_endereco",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="filiais_endereco", to="core.pais"),
        ),
    ]