from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('pedidos', '0010_add_send_sms_permission'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='tentativaentrega',
            options={
                'permissions': [
                    ('change_carro_tentativaentrega', 'Pode alterar o campo Carro na conferência de volumes'),
                    ('send_sms_tentativaentrega', 'Pode enviar SMS de notificação de entrega'),
                    ('view_relatorio_gerencial', 'Pode acessar o Relatório Gerencial de Pedidos'),
                ],
            },
        ),
    ]
