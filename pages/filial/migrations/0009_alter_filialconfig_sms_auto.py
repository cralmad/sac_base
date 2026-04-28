from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('filial', '0008_filialconfig_sms_auto'),
    ]

    operations = [
        migrations.AlterField(
            model_name='filialconfig',
            name='sms_auto',
            field=models.TimeField(
                blank=True,
                null=True,
                help_text=(
                    "Horário (Lisboa) para envio automático de SMS. "
                    "Formato 24h — ex.: 08:00. Deixe em branco para desativar."
                ),
            ),
        ),
    ]
