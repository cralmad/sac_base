import django.core.validators
from django.db import migrations, models
import django.db.models.functions.text


class Migration(migrations.Migration):

    dependencies = [
        ("cad_grupo_cli", "0002_grupocli_auditoria_soft_delete"),
    ]

    operations = [
        migrations.AlterField(
            model_name="grupocli",
            name="descricao",
            field=models.CharField(max_length=30, validators=[django.core.validators.MinLengthValidator(3)]),
        ),
        migrations.RemoveConstraint(
            model_name="grupocli",
            name="unique_descricao_upper",
        ),
        migrations.AddConstraint(
            model_name="grupocli",
            constraint=models.UniqueConstraint(
                django.db.models.functions.text.Upper("descricao"),
                condition=models.Q(is_deleted=False),
                name="unique_descricao_upper_active",
            ),
        ),
    ]