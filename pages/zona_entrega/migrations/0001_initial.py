from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q
from django.db.models.functions.text import Upper


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("auditoria", "0001_initial"),
        ("filial", "0002_filial_paises"),
    ]

    operations = [
        migrations.CreateModel(
            name="ZonaEntrega",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True, blank=True, null=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("delete_reason", models.CharField(blank=True, default="", max_length=255)),
                ("codigo", models.CharField(max_length=20)),
                ("descricao", models.CharField(max_length=100)),
                ("prioridade", models.PositiveIntegerField(default=0)),
                ("ativa", models.BooleanField(default=True)),
                ("valor_cobranca_unitario_pedido", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("valor_pagamento_unitario_entrega", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("valor_pagamento_fixo_rota", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("observacao", models.CharField(blank=True, default="", max_length=500)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="zonaentrega_created", to="usuario.usuarios")),
                ("deleted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="zonaentrega_deleted", to="usuario.usuarios")),
                ("filial", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="zonas_entrega", to="filial.filial")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="zonaentrega_updated", to="usuario.usuarios")),
            ],
            options={
                "db_table": "zona_entrega",
                "ordering": ["filial__nome", "descricao"],
                "base_manager_name": "all_objects",
            },
        ),
        migrations.CreateModel(
            name="ZonaEntregaExcecaoPostal",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("codigo_postal", models.CharField(max_length=8)),
                ("cp4", models.CharField(db_index=True, max_length=4)),
                ("cp7_num", models.PositiveIntegerField(db_index=True)),
                ("tipo_excecao", models.CharField(choices=[("EXCLUIR", "Excluir"), ("INCLUIR", "Incluir")], default="EXCLUIR", max_length=7)),
                ("ativa", models.BooleanField(default=True)),
                ("observacao", models.CharField(blank=True, default="", max_length=200)),
                ("zona_entrega", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="excecoes_postais", to="zona_entrega.zonaentrega")),
            ],
            options={
                "db_table": "zona_entrega_excecao_postal",
                "ordering": ["codigo_postal"],
            },
        ),
        migrations.CreateModel(
            name="ZonaEntregaFaixaPostal",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("tipo_intervalo", models.CharField(choices=[("CP4", "CP4"), ("CP7", "CP7")], default="CP7", max_length=3)),
                ("codigo_postal_inicial", models.CharField(max_length=8)),
                ("codigo_postal_final", models.CharField(max_length=8)),
                ("cp4_inicial", models.CharField(db_index=True, max_length=4)),
                ("cp4_final", models.CharField(db_index=True, max_length=4)),
                ("cp7_inicial_num", models.PositiveIntegerField(db_index=True)),
                ("cp7_final_num", models.PositiveIntegerField(db_index=True)),
                ("ativa", models.BooleanField(default=True)),
                ("zona_entrega", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="faixas_postais", to="zona_entrega.zonaentrega")),
            ],
            options={
                "db_table": "zona_entrega_faixa_postal",
                "ordering": ["tipo_intervalo", "codigo_postal_inicial"],
            },
        ),
        migrations.AddConstraint(
            model_name="zonaentrega",
            constraint=models.UniqueConstraint(fields=("filial", "codigo"), condition=Q(("is_deleted", False)), name="unique_zona_entrega_codigo_ativo_por_filial"),
        ),
        migrations.AddConstraint(
            model_name="zonaentrega",
            constraint=models.UniqueConstraint(Upper("descricao"), models.F("filial"), condition=Q(("is_deleted", False)), name="unique_zona_entrega_descricao_upper_ativa_por_filial"),
        ),
        migrations.AddConstraint(
            model_name="zonaentregaexcecaopostal",
            constraint=models.UniqueConstraint(fields=("zona_entrega", "codigo_postal", "tipo_excecao"), condition=Q(("ativa", True)), name="unique_zona_excecao_ativa"),
        ),
    ]