import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('cad_grupo_cli', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Cliente',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('grupo', models.ForeignKey(
                    blank=True,
                    db_column='grupo_id',
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    to='cad_grupo_cli.grupocli',
                )),
                ('nome', models.CharField(
                    max_length=100,
                    validators=[django.core.validators.MinLengthValidator(3)],
                )),
                ('logradouro', models.CharField(blank=True, max_length=20, null=True)),
                ('endereco', models.CharField(blank=True, max_length=150, null=True)),
                ('numero', models.CharField(blank=True, max_length=10, null=True)),
                ('complemento', models.CharField(blank=True, max_length=50, null=True)),
                ('bairro', models.CharField(blank=True, max_length=60, null=True)),
                ('pais', models.CharField(max_length=20)),
                ('uf', models.CharField(max_length=10)),
                ('cidade', models.CharField(max_length=50)),
                ('codpostal', models.CharField(blank=True, max_length=8, null=True)),
                ('atualizacao', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'cliente',
            },
        ),
    ]
