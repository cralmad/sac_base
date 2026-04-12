from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("auditoria", "0001_initial"),
        ("filial", "0002_filial_paises"),
    ]

    operations = [
        migrations.CreateModel(
            name="Motorista",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True, blank=True, null=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("delete_reason", models.CharField(blank=True, default="", max_length=255)),
                ("nome", models.CharField(max_length=100)),
                ("telefone", models.CharField(max_length=20)),
                ("ativa", models.BooleanField(default=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="motorista_created", to="usuario.usuarios")),
                ("deleted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="motorista_deleted", to="usuario.usuarios")),
                ("filial", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="motoristas", to="filial.filial")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="motorista_updated", to="usuario.usuarios")),
            ],
            options={
                "db_table": "motorista",
                "ordering": ["filial__nome", "nome"],
                "base_manager_name": "all_objects",
            },
        ),
        migrations.AddConstraint(
            model_name="motorista",
            constraint=models.UniqueConstraint(fields=("filial", "nome"), condition=Q(("is_deleted", False)), name="unique_motorista_nome_ativo_por_filial"),
        ),
    ]