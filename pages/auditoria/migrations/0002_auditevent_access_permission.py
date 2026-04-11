from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="auditevent",
            options={
                "ordering": ["-created_at", "-id"],
                "permissions": [
                    ("acessar_consulta_auditoria", "Pode acessar a tela de consulta de auditoria"),
                ],
            },
        ),
    ]