"""Constantes do módulo financeiro (códigos de plano, prefixos de metadados)."""

# Prefixo reservado para chaves consumidas pelo executor (metadados).
FIN_META_PREFIX = "fin__"

# Folhas do plano de contas (seed + migration 0003_plano_contas_arvore_completa).
# Receitas — Comercial — Serviços
PLANO_FRETE_ENTREGA = "1.1.1.1"
PLANO_SERVICO_LOGISTICA_ARMAZENAGEM = "1.1.1.2"
# Receitas — Comercial — Produtos
PLANO_VENDA_MERCADORIAS = "1.1.2.1"
# Receitas — Financeiras
PLANO_JUROS_MULTAS_RECEBIDOS = "1.2.1.1"
PLANO_RECUPERACAO_DESPESAS = "1.2.1.2"

# Despesas — Operacionais — Frota
PLANO_COMBUSTIVEIS_LUBRIFICANTES = "2.1.1.1"
PLANO_MANUTENCAO_PECAS_VEICULOS = "2.1.1.2"
PLANO_PEDAGIOS_ESTADIAS = "2.1.1.3"
# Despesas — Operacionais — Pessoal
PLANO_DIARIAS_MOTORISTAS = "2.1.2.1"
PLANO_COMISSOES_ENTREGAS = "2.1.2.2"
# Despesas — Administrativas
PLANO_ALUGUEL_CONDOMINIO = "2.2.1.1"
PLANO_ENERGIA_AGUA_INTERNET = "2.2.1.2"
# Despesas — Financeiras
PLANO_TARIFAS_BANCARIAS = "2.3.1.1"
PLANO_TAXAS_ADMINISTRADORA_CARTAO = "2.3.1.2"

# Neutro — transferências internas
PLANO_TRANSFERENCIA_CONTAS_CAIXA_BANCO = "3.1.1.1"
PLANO_SANGRIA_SUPRIMENTO_CAIXA = "3.1.1.2"

# Neutro — adiantamentos
PLANO_ADIANTAMENTO_CLIENTE = "4.1.1.1"
PLANO_ADIANTAMENTO_FORNECEDOR = "4.1.2.1"

# Aliases legíveis para código existente (executor / exemplos).
PLANO_RECEITA_OPERACIONAL = PLANO_FRETE_ENTREGA
PLANO_DESPESA_OPERACIONAL = PLANO_COMBUSTIVEIS_LUBRIFICANTES
PLANO_NEUTRO_TRANSFERENCIA = PLANO_TRANSFERENCIA_CONTAS_CAIXA_BANCO
PLANO_PASSIVO_ADIANTAMENTO = PLANO_ADIANTAMENTO_CLIENTE
