# Generated manually — seeds obrigatórios (plano de contas + formas básicas).

from django.db import migrations


def forwards_seed(apps, schema_editor):
    Plano = apps.get_model("financeiro", "PlanoContas")
    Filial = apps.get_model("filial", "Filial")
    Conta = apps.get_model("financeiro", "ContaFinanceira")
    Forma = apps.get_model("financeiro", "FormaPagamento")

    if not Plano.objects.filter(codigo="1.1.1.1").exists():
        p1 = Plano.objects.create(
            codigo="1",
            nome="ENTRADAS",
            nivel=1,
            tipo_classificacao="receita",
            pai=None,
        )
        p11 = Plano.objects.create(
            codigo="1.1",
            nome="RECEITAS",
            nivel=2,
            tipo_classificacao="receita",
            pai=p1,
        )
        p111 = Plano.objects.create(
            codigo="1.1.1",
            nome="OPERACIONAL",
            nivel=3,
            tipo_classificacao="receita",
            pai=p11,
        )
        Plano.objects.create(
            codigo="1.1.1.1",
            nome="Receita operacional",
            nivel=4,
            tipo_classificacao="receita",
            pai=p111,
        )
        p12 = Plano.objects.create(
            codigo="1.2",
            nome="ADIANTAMENTOS",
            nivel=2,
            tipo_classificacao="receita",
            pai=p1,
        )
        p121 = Plano.objects.create(
            codigo="1.2.1",
            nome="Cliente",
            nivel=3,
            tipo_classificacao="receita",
            pai=p12,
        )
        Plano.objects.create(
            codigo="1.2.1.1",
            nome="Adiantamento de clientes",
            nivel=4,
            tipo_classificacao="receita",
            pai=p121,
        )

    if not Plano.objects.filter(codigo="2.1.1.1").exists():
        s1 = Plano.objects.create(
            codigo="2",
            nome="SAIDAS",
            nivel=1,
            tipo_classificacao="despesa",
            pai=None,
        )
        s11 = Plano.objects.create(
            codigo="2.1",
            nome="DESPESAS",
            nivel=2,
            tipo_classificacao="despesa",
            pai=s1,
        )
        s111 = Plano.objects.create(
            codigo="2.1.1",
            nome="OPERACIONAL",
            nivel=3,
            tipo_classificacao="despesa",
            pai=s11,
        )
        Plano.objects.create(
            codigo="2.1.1.1",
            nome="Despesa operacional",
            nivel=4,
            tipo_classificacao="despesa",
            pai=s111,
        )

    if not Plano.objects.filter(codigo="3.1.1.1").exists():
        t1 = Plano.objects.create(
            codigo="3",
            nome="NEUTRO",
            nivel=1,
            tipo_classificacao="neutro",
            pai=None,
        )
        t11 = Plano.objects.create(
            codigo="3.1",
            nome="DISPONIBILIDADE",
            nivel=2,
            tipo_classificacao="neutro",
            pai=t1,
        )
        t111 = Plano.objects.create(
            codigo="3.1.1",
            nome="TRANSFERENCIAS",
            nivel=3,
            tipo_classificacao="neutro",
            pai=t11,
        )
        Plano.objects.create(
            codigo="3.1.1.1",
            nome="Transferências de disponibilidade",
            nivel=4,
            tipo_classificacao="neutro",
            pai=t111,
        )

    filial = Filial.objects.order_by("id").first()
    if not filial:
        return
    caixa, _ = Conta.objects.get_or_create(
        filial=filial,
        nome="Caixa geral",
        defaults={"codigo": "CX", "ativo": True},
    )
    Forma.objects.get_or_create(
        codigo="DINHEIRO",
        defaults={
            "nome": "Dinheiro",
            "aceita_parcelamento": False,
            "conta_custodia_padrao": caixa,
            "ordem": 1,
            "ativo": True,
        },
    )
    Forma.objects.get_or_create(
        codigo="PIX",
        defaults={
            "nome": "PIX",
            "aceita_parcelamento": False,
            "conta_custodia_padrao": caixa,
            "ordem": 2,
            "ativo": True,
        },
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("financeiro", "0001_initial"),
        ("filial", "0010_filialconfig_email_fields"),
    ]

    operations = [
        migrations.RunPython(forwards_seed, noop_reverse),
    ]
