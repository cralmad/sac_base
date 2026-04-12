from decimal import Decimal

from django.contrib.contenttypes.models import ContentType

from .models import AuditEvent


AUDIT_EXCLUDED_FIELDS = {
    "password",
    "last_login",
    "updated_at",
    "created_at",
    "deleted_at",
}


def snapshot_instance(instance, exclude_fields=None):
    exclude = set(AUDIT_EXCLUDED_FIELDS)
    if exclude_fields:
        exclude.update(exclude_fields)

    data = {}
    for field in instance._meta.concrete_fields:
        if field.name in exclude:
            continue

        value = getattr(instance, field.name)
        if hasattr(field, "target_field"):
            data[field.name] = value.pk if value is not None else None
        elif isinstance(value, Decimal):
            data[field.name] = str(value)
        else:
            data[field.name] = value.isoformat() if hasattr(value, "isoformat") and value is not None else value
    return data


def diff_snapshots(before, after):
    before = before or {}
    after = after or {}
    changed = {}

    for key in sorted(set(before.keys()) | set(after.keys())):
        if before.get(key) != after.get(key):
            changed[key] = {
                "from": before.get(key),
                "to": after.get(key),
            }
    return changed


def registrar_auditoria(*, actor, action, instance, changed_fields=None, extra_data=None):
    AuditEvent.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        content_type=ContentType.objects.get_for_model(instance.__class__),
        object_id=str(instance.pk),
        object_repr=str(instance),
        changed_fields=changed_fields or {},
        extra_data=extra_data or {},
    )
