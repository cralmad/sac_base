from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("filial", "0012_filialconfig_gmail_usuario"),
    ]

    operations = [
        migrations.AddField(
            model_name="filialconfig",
            name="sms_padrao_avaliacao",
            field=models.TextField(
                blank=True,
                help_text="Template SMS da pesquisa de satisfação. Use {nome}, {pedido}, {filial} e {link_avaliacao}.",
                null=True,
            ),
        ),
    ]
