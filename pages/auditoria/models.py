from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_deleted=False)

    def deleted(self):
        return self.filter(is_deleted=True)


class ActiveManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).active()


class AuditFieldsMixin(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="%(class)s_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="%(class)s_updated",
    )

    class Meta:
        abstract = True


class SoftDeleteMixin(models.Model):
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="%(class)s_deleted",
    )
    delete_reason = models.CharField(max_length=255, blank=True, default="")

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def soft_delete(self, user=None, reason=""):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = user if getattr(user, "is_authenticated", False) else None
        self.delete_reason = reason or ""
        if hasattr(self, "updated_by"):
            self.updated_by = user if getattr(user, "is_authenticated", False) else getattr(self, "updated_by", None)


class AuditEvent(models.Model):
    ACTION_CREATE = "create"
    ACTION_UPDATE = "update"
    ACTION_DELETE = "delete"
    ACTION_SOFT_DELETE = "soft_delete"
    ACTION_RESTORE = "restore"
    ACTION_PASSWORD_CHANGE = "password_change"
    ACTION_PERMISSION_ASSIGN = "permission_assign"

    ACTION_CHOICES = [
        (ACTION_CREATE, "create"),
        (ACTION_UPDATE, "update"),
        (ACTION_DELETE, "delete"),
        (ACTION_SOFT_DELETE, "soft_delete"),
        (ACTION_RESTORE, "restore"),
        (ACTION_PASSWORD_CHANGE, "password_change"),
        (ACTION_PERMISSION_ASSIGN, "permission_assign"),
    ]

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="audit_events",
    )
    action = models.CharField(max_length=40, choices=ACTION_CHOICES)
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.CharField(max_length=64, db_index=True)
    object_repr = models.CharField(max_length=255, blank=True, default="")
    changed_fields = models.JSONField(default=dict, blank=True)
    extra_data = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "audit_event"
        ordering = ["-created_at", "-id"]
        permissions = [
            ("acessar_consulta_auditoria", "Pode acessar a tela de consulta de auditoria"),
        ]

    def __str__(self):
        return f"{self.action} {self.content_type.app_label}.{self.content_type.model}#{self.object_id}"
