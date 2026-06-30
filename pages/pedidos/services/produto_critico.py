import logging

from django.db import DatabaseError, IntegrityError, transaction

from pages.pedidos.models import ProdutoCritico

logger = logging.getLogger(__name__)


def listar_codigos_produtos_criticos():
    """Códigos cadastrados na lista de produtos críticos."""
    return list(ProdutoCritico.objects.values_list("codigo", flat=True))


def cadastrar_produto_critico(*, codigo: str, descricao: str):
    """
    Cadastra um produto na lista de críticos.
    Retorna (instância, None) em sucesso ou (None, mensagem_erro).
    """
    codigo = (codigo or "").strip()
    descricao = (descricao or "").strip()
    if not codigo:
        return None, "Código do produto é obrigatório."
    if not descricao:
        return None, "Descrição do produto é obrigatória."
    if len(codigo) > 20:
        return None, "Código excede 20 caracteres."
    if len(descricao) > 100:
        descricao = descricao[:100]

    try:
        if ProdutoCritico.objects.filter(codigo=codigo).exists():
            return None, f"O produto {codigo} já está cadastrado como crítico."
        with transaction.atomic():
            obj = ProdutoCritico.objects.create(codigo=codigo, descricao=descricao)
        return obj, None
    except IntegrityError:
        return None, f"O produto {codigo} já está cadastrado como crítico."
    except DatabaseError as exc:
        logger.error(exc, exc_info=True)
        return None, "Erro ao cadastrar produto crítico."
