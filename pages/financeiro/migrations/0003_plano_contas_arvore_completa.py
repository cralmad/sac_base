# Data migration — Plano de Contas completo (4 níveis: Receita, Despesa, Neutro).

from django.db import migrations


def _ensure(Plano, *, codigo: str, nome: str, nivel: int, tipo: str, pai_codigo: str | None):
    pai = Plano.objects.filter(codigo=pai_codigo).first() if pai_codigo else None
    obj, _created = Plano.objects.update_or_create(
        codigo=codigo,
        defaults={
            "nome": nome,
            "nivel": nivel,
            "tipo_classificacao": tipo,
            "pai": pai,
        },
    )
    return obj


def forwards_plano_contas(apps, schema_editor):
    Plano = apps.get_model("financeiro", "PlanoContas")
    RegistroFinanceiro = apps.get_model("financeiro", "RegistroFinanceiro")

    # --- Ramo 4 (adiantamentos): criar antes de remover 1.2.x legado da seed antiga ---
    _ensure(Plano, codigo="4", nome="Adiantamentos e Ajustes (Neutro)", nivel=1, tipo="neutro", pai_codigo=None)
    _ensure(Plano, codigo="4.1", nome="Créditos de Terceiros", nivel=2, tipo="neutro", pai_codigo="4")
    _ensure(Plano, codigo="4.1.1", nome="Clientes", nivel=3, tipo="neutro", pai_codigo="4.1")
    n_4111 = _ensure(
        Plano,
        codigo="4.1.1.1",
        nome="Adiantamentos de Clientes (Crédito a Utilizar)",
        nivel=4,
        tipo="neutro",
        pai_codigo="4.1.1",
    )
    _ensure(Plano, codigo="4.1.2", nome="Fornecedores", nivel=3, tipo="neutro", pai_codigo="4.1")
    _ensure(
        Plano,
        codigo="4.1.2.1",
        nome="Adiantamentos a Fornecedores",
        nivel=4,
        tipo="neutro",
        pai_codigo="4.1.2",
    )

    # Remapear títulos que apontavam para o código antigo de adiantamento (1.2.1.1 na seed MVP).
    legado_adiant = Plano.objects.filter(codigo="1.2.1.1").first()
    if legado_adiant and legado_adiant.pk != n_4111.pk:
        RegistroFinanceiro.objects.filter(plano_contas_id=legado_adiant.pk).update(plano_contas_id=n_4111.pk)
        # Remover nós legados 1.2.x se não houver mais referências
        for cod in ("1.2.1.1", "1.2.1", "1.2"):
            alvo = Plano.objects.filter(codigo=cod).first()
            if not alvo:
                continue
            if RegistroFinanceiro.objects.filter(plano_contas_id=alvo.pk).exists():
                continue
            if Plano.objects.filter(pai_id=alvo.pk).exists():
                continue
            alvo.delete()

    # --- Raízes 1, 2, 3 ---
    _ensure(Plano, codigo="1", nome="Entradas (Receitas)", nivel=1, tipo="receita", pai_codigo=None)
    _ensure(Plano, codigo="2", nome="Saídas (Despesas)", nivel=1, tipo="despesa", pai_codigo=None)
    _ensure(Plano, codigo="3", nome="Transferências (Neutro)", nivel=1, tipo="neutro", pai_codigo=None)

    # --- Grupo 1 ---
    _ensure(Plano, codigo="1.1", nome="Comercial", nivel=2, tipo="receita", pai_codigo="1")
    _ensure(Plano, codigo="1.1.1", nome="Vendas de Serviços", nivel=3, tipo="receita", pai_codigo="1.1")
    _ensure(Plano, codigo="1.1.1.1", nome="Fretes e Entregas", nivel=4, tipo="receita", pai_codigo="1.1.1")
    _ensure(
        Plano,
        codigo="1.1.1.2",
        nome="Serviços de Logística (Armazenagem/Montagem)",
        nivel=4,
        tipo="receita",
        pai_codigo="1.1.1",
    )
    _ensure(Plano, codigo="1.1.2", nome="Vendas de Produtos", nivel=3, tipo="receita", pai_codigo="1.1")
    _ensure(
        Plano,
        codigo="1.1.2.1",
        nome="Venda de Mercadorias/Materiais",
        nivel=4,
        tipo="receita",
        pai_codigo="1.1.2",
    )
    _ensure(Plano, codigo="1.2", nome="Financeiras", nivel=2, tipo="receita", pai_codigo="1")
    _ensure(Plano, codigo="1.2.1", nome="Receitas Acessórias", nivel=3, tipo="receita", pai_codigo="1.2")
    _ensure(
        Plano,
        codigo="1.2.1.1",
        nome="Juros e Multas Recebidos",
        nivel=4,
        tipo="receita",
        pai_codigo="1.2.1",
    )
    _ensure(
        Plano,
        codigo="1.2.1.2",
        nome="Recuperação de Despesas",
        nivel=4,
        tipo="receita",
        pai_codigo="1.2.1",
    )

    # --- Grupo 2 ---
    _ensure(Plano, codigo="2.1", nome="Operacionais", nivel=2, tipo="despesa", pai_codigo="2")
    _ensure(Plano, codigo="2.1.1", nome="Logística e Frota", nivel=3, tipo="despesa", pai_codigo="2.1")
    _ensure(
        Plano,
        codigo="2.1.1.1",
        nome="Combustíveis e Lubrificantes",
        nivel=4,
        tipo="despesa",
        pai_codigo="2.1.1",
    )
    _ensure(
        Plano,
        codigo="2.1.1.2",
        nome="Manutenção e Peças (Veículos)",
        nivel=4,
        tipo="despesa",
        pai_codigo="2.1.1",
    )
    _ensure(
        Plano,
        codigo="2.1.1.3",
        nome="Pedágios e Estadias",
        nivel=4,
        tipo="despesa",
        pai_codigo="2.1.1",
    )
    _ensure(Plano, codigo="2.1.2", nome="Pessoal Operacional", nivel=3, tipo="despesa", pai_codigo="2.1")
    _ensure(
        Plano,
        codigo="2.1.2.1",
        nome="Diárias e Ajuda de Custo (Motoristas)",
        nivel=4,
        tipo="despesa",
        pai_codigo="2.1.2",
    )
    _ensure(
        Plano,
        codigo="2.1.2.2",
        nome="Comissões sobre Entregas",
        nivel=4,
        tipo="despesa",
        pai_codigo="2.1.2",
    )
    _ensure(Plano, codigo="2.2", nome="Administrativas", nivel=2, tipo="despesa", pai_codigo="2")
    _ensure(Plano, codigo="2.2.1", nome="Ocupação e Utilidades", nivel=3, tipo="despesa", pai_codigo="2.2")
    _ensure(
        Plano,
        codigo="2.2.1.1",
        nome="Aluguel e Condomínio",
        nivel=4,
        tipo="despesa",
        pai_codigo="2.2.1",
    )
    _ensure(
        Plano,
        codigo="2.2.1.2",
        nome="Energia, Água e Internet",
        nivel=4,
        tipo="despesa",
        pai_codigo="2.2.1",
    )
    _ensure(Plano, codigo="2.3", nome="Financeiras", nivel=2, tipo="despesa", pai_codigo="2")
    _ensure(Plano, codigo="2.3.1", nome="Taxas e Tarifas", nivel=3, tipo="despesa", pai_codigo="2.3")
    _ensure(
        Plano,
        codigo="2.3.1.1",
        nome="Tarifas Bancárias",
        nivel=4,
        tipo="despesa",
        pai_codigo="2.3.1",
    )
    _ensure(
        Plano,
        codigo="2.3.1.2",
        nome="Taxas de Administradora de Cartão (Custo da Venda)",
        nivel=4,
        tipo="despesa",
        pai_codigo="2.3.1",
    )

    # --- Grupo 3 ---
    _ensure(Plano, codigo="3.1", nome="Movimentações Internas", nivel=2, tipo="neutro", pai_codigo="3")
    _ensure(Plano, codigo="3.1.1", nome="Disponibilidades", nivel=3, tipo="neutro", pai_codigo="3.1")
    _ensure(
        Plano,
        codigo="3.1.1.1",
        nome="Transferência entre Contas (Caixa/Banco)",
        nivel=4,
        tipo="neutro",
        pai_codigo="3.1.1",
    )
    _ensure(
        Plano,
        codigo="3.1.1.2",
        nome="Sangria e Suprimento de Caixa",
        nivel=4,
        tipo="neutro",
        pai_codigo="3.1.1",
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("financeiro", "0002_seed_plano_contas_e_formas"),
    ]

    operations = [
        migrations.RunPython(forwards_plano_contas, noop_reverse),
    ]
