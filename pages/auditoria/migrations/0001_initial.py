from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("action", models.CharField(choices=[("create", "create"), ("update", "update"), ("delete", "delete"), ("soft_delete", "soft_delete"), ("restore", "restore"), ("password_change", "password_change"), ("permission_assign", "permission_assign")], max_length=40)),
                ("object_id", models.CharField(db_index=True, max_length=64)),
                ("object_repr", models.CharField(blank=True, default="", max_length=255)),
                ("changed_fields", models.JSONField(blank=True, default=dict)),
                ("extra_data", models.JSONField(blank=True, default=dict)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="audit_events", to=settings.AUTH_USER_MODEL)),
                ("content_type", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="contenttypes.contenttype")),
            ],
            options={
                "db_table": "audit_event",
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]