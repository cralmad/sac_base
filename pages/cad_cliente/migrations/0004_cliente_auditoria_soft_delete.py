from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("cad_cliente", "0003_cliente_observacao"),
    ]

    operations = [
        migrations.AddField(
            model_name="cliente",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, blank=True, null=True),
        ),
        migrations.AddField(
            model_name="cliente",
            name="created_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="cliente_created", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="cliente",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, blank=True, null=True),
        ),
        migrations.AddField(
            model_name="cliente",
            name="updated_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="cliente_updated", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="cliente",
            name="is_deleted",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="cliente",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="cliente",
            name="deleted_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="cliente_deleted", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="cliente",
            name="delete_reason",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]