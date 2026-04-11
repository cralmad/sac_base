from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Filial",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("codigo", models.CharField(max_length=20, unique=True)),
                ("nome", models.CharField(max_length=100, unique=True)),
                ("is_matriz", models.BooleanField(default=False)),
                ("ativa", models.BooleanField(default=True)),
            ],
            options={
                "db_table": "filial",
                "ordering": ["nome"],
            },
        ),
        migrations.CreateModel(
            name="UsuarioFilial",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("pode_consultar", models.BooleanField(default=True)),
                ("pode_escrever", models.BooleanField(default=False)),
                ("ativo", models.BooleanField(default=True)),
                ("filial", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="usuarios_vinculados", to="filial.filial")),
                ("usuario", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="filiais_vinculadas", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "usuario_filial",
            },
        ),
        migrations.AddConstraint(
            model_name="filial",
            constraint=models.UniqueConstraint(fields=("is_matriz",), condition=Q(("is_matriz", True)), name="unique_matriz_true"),
        ),
        migrations.AddConstraint(
            model_name="usuariofilial",
            constraint=models.UniqueConstraint(fields=("usuario", "filial"), name="unique_usuario_filial"),
        ),
    ]