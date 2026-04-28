from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('filial', '0007_add_driver_and_gsheets_config'),
    ]

    operations = [
        migrations.AddField(
            model_name='filialconfig',
            name='sms_auto',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
