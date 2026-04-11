from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("cad_grupo_cli", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="grupocli",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, blank=True, null=True),
        ),
        migrations.AddField(
            model_name="grupocli",
            name="created_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="grupocli_created", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="grupocli",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, blank=True, null=True),
        ),
        migrations.AddField(
            model_name="grupocli",
            name="updated_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="grupocli_updated", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="grupocli",
            name="is_deleted",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="grupocli",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="grupocli",
            name="deleted_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="grupocli_deleted", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="grupocli",
            name="delete_reason",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]