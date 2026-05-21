from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('filial', '0010_filialconfig_email_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='filialconfig',
            name='gsheets_sheet_name_2',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='filialconfig',
            name='gsheets_spreadsheet_id_2',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
    ]
