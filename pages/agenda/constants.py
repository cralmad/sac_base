"""Constantes do módulo agenda / previsibilidade."""

PERIODO_MAXIMO_AGENDA_DIAS = 366
MAX_OCORRENCIAS_POR_REGRA = 500

# dia_semana: 1=segunda .. 7=domingo (alinha com date.weekday() + 1)
DIAS_SEMANA_AGENDA = (
    (1, "Segunda-feira"),
    (2, "Terça-feira"),
    (3, "Quarta-feira"),
    (4, "Quinta-feira"),
    (5, "Sexta-feira"),
    (6, "Sábado"),
    (7, "Domingo"),
)

class ModoEventoAgenda:
    AVISO = "aviso"
    AVISO_CONFIRMAVEL = "aviso_confirmavel"
    MATERIALIZAVEL = "materializavel"


class RecorrenciaAgenda:
    NENHUMA = "nenhuma"
    DIARIA = "diaria"
    SEMANAL = "semanal"
    MENSAL = "mensal"
    ANUAL = "anual"


class CategoriaAgenda:
    FINANCEIRO = "financeiro"
    OPERACIONAL = "operacional"
    LEMBRETE = "lembrete"


CATEGORIA_CHOICES = [
    (CategoriaAgenda.FINANCEIRO, "Financeiro"),
    (CategoriaAgenda.OPERACIONAL, "Operacional"),
    (CategoriaAgenda.LEMBRETE, "Lembrete"),
]

# Categorias que não permitem modo_evento materializavel (lançamento vinculado).
CATEGORIAS_SEM_LANCAMENTO_VINCULADO = frozenset({CategoriaAgenda.LEMBRETE})

MODO_EVENTO_CHOICES = [
    (ModoEventoAgenda.AVISO, "Aviso simples"),
    (ModoEventoAgenda.AVISO_CONFIRMAVEL, "Aviso com confirmação"),
    (ModoEventoAgenda.MATERIALIZAVEL, "Lançamento vinculado"),
]

RECORRENCIA_CHOICES = [
    (RecorrenciaAgenda.NENHUMA, "Nenhuma (evento único)"),
    (RecorrenciaAgenda.DIARIA, "Diária"),
    (RecorrenciaAgenda.SEMANAL, "Semanal"),
    (RecorrenciaAgenda.MENSAL, "Mensal"),
    (RecorrenciaAgenda.ANUAL, "Anual"),
]

class TipoVinculoMaterializacao:
    CONCLUIDO_CONFIRMADO = "concluido_confirmado"
    MATERIALIZADO = "materializado"


# provider_key -> permission codename (view)
PERIOD_PROVIDER_PERMISSIONS = {
    "financeiro.registro_financeiro": "financeiro.view_registrofinanceiro",
}
