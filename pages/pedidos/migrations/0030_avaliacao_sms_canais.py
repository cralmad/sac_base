from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pedidos", "0029_pedido_incidencia_resolvida"),
    ]

    operations = [
        migrations.AddField(
            model_name="avaliacaopedido",
            name="sms_enviado",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="avaliacaopedido",
            name="sms_enviado_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="avaliacaopedido",
            name="sms_tentativas",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddIndex(
            model_name="avaliacaopedido",
            index=models.Index(fields=["sms_enviado"], name="avaliacao_p_sms_env_idx"),
        ),
        migrations.AlterModelOptions(
            name="tentativaentrega",
            options={
                "permissions": [
                    ("change_carro_tentativaentrega", "Pode alterar o campo Carro na conferência de volumes"),
                    ("send_sms_tentativaentrega", "Pode enviar SMS de notificação de entrega"),
                    ("view_relatorio_gerencial", "Pode acessar o Relatório Gerencial de Pedidos"),
                    ("view_relatorio_fechamento", "Pode acessar o Relatório de Fechamento (logística)"),
                    ("view_relatorio_avaliacao", "Pode acessar o Relatório de Avaliações"),
                    ("send_email_avaliacao", "Pode enviar e-mails de avaliação"),
                    ("send_sms_avaliacao", "Pode enviar SMS de avaliação"),
                    ("generate_email_queue_avaliacao", "Pode gerar fila de e-mails de avaliação"),
                    ("download_anexo_gmail_gerencial", "Pode descarregar anexos Gmail no Relatório Gerencial"),
                ]
            },
        ),
    ]
