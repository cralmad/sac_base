from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("motorista", "0001_initial"),
        ("pedidos", "0002_pedido_origem"),
    ]

    operations = [
        migrations.AddField(
            model_name="pedido",
            name="expresso",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="tentativaentrega",
            name="carro",
            field=models.SmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tentativaentrega",
            name="motorista",
            field=models.ForeignKey(blank=True, db_column="motorista_id", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="tentativas_entrega", to="motorista.motorista"),
        ),
        migrations.AddField(
            model_name="tentativaentrega",
            name="periodo",
            field=models.CharField(blank=True, choices=[("MANHA", "MANHÃ"), ("TARDE", "TARDE")], max_length=5, null=True),
        ),
    ]
