from __future__ import annotations

import logging
from decimal import Decimal
from django.utils import timezone

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, transaction

from pages.auditoria.models import AuditEvent
from pages.auditoria.utils import diff_snapshots, registrar_auditoria, snapshot_instance
from pages.cad_cliente.models import Cliente
from pages.filial.services import get_filiais_escrita_queryset, obter_filial_escrita
from pages.financeiro.models import (
    FaturamentoRegistroFinanceiro,
    PlanoContas,
    RegistroFinanceiro,
    RegistroFinanceiroStatus,
    RegistroFinanceiroTipo,
    TipoClassificacaoPlano,
)
from pages.motorista.models import Motorista
from sac_base.coercion import parse_date, parse_decimal, parse_int

logger = logging.getLogger(__name__)


def _formatar_decimal_br(valor: Decimal) -> str:
    return f"{valor:.2f}".replace(".", ",")


def registro_tem_faturamento_vinculado(registro_id: int) -> bool:
    return FaturamentoRegistroFinanceiro.objects.filter(registro_financeiro_id=registro_id).exists()


def registro_eh_lancamento_manual_sem_referencia(registro: RegistroFinanceiro) -> bool:
    """UI manual não define referencia (GFK); demais fluxos devem preencher referencia obrigatoriamente."""
    return registro.referencia_content_type_id is None and registro.referencia_object_id is None


def _flags_acoes_ui(registro: RegistroFinanceiro) -> dict:
    tem_fat = registro_tem_faturamento_vinculado(registro.id)
    manual = registro_eh_lancamento_manual_sem_referencia(registro)
    st = registro.status
    vfat = registro.valor_fat
    bloqueado_fat = tem_fat or vfat > Decimal("0")
    pode_editar = (
        manual
        and st not in (RegistroFinanceiroStatus.CANCELADO, RegistroFinanceiroStatus.LIQUIDADO)
        and not bloqueado_fat
    )
    pode_cancelar = st != RegistroFinanceiroStatus.CANCELADO and not bloqueado_fat
    pode_excluir = manual and not bloqueado_fat and st in (
        RegistroFinanceiroStatus.ABERTO,
        RegistroFinanceiroStatus.CANCELADO,
    )
    return {
        "permite_editar": pode_editar,
        "permite_cancelar": pode_cancelar,
        "permite_excluir_permanente": pode_excluir,
    }


def listar_filiais_escrita(usuario):
    return [
        {
            "id": filial.id,
            "codigo": filial.codigo,
            "nome": filial.nome,
        }
        for filial in get_filiais_escrita_queryset(usuario).order_by("nome")
    ]


def listar_planos_nivel4():
    return [
        {
            "id": plano.id,
            "codigo": plano.codigo,
            "nome": plano.nome,
            "tipo_classificacao": plano.tipo_classificacao,
        }
        for plano in PlanoContas.objects.filter(nivel=4).order_by("codigo")
    ]


def listar_planos_cascata():
    planos = list(PlanoContas.objects.select_related("pai").order_by("codigo"))
    por_id = {p.id: p for p in planos}

    def descricao_hierarquia(plano: PlanoContas):
        nomes = []
        atual = plano
        while atual:
            nomes.append(atual.nome)
            atual = por_id.get(atual.pai_id)
        return " - ".join(reversed(nomes))

    return [
        {
            "id": plano.id,
            "pai_id": plano.pai_id,
            "nivel": plano.nivel,
            "nome": plano.nome,
            "tipo_classificacao": plano.tipo_classificacao,
            "descricao_hierarquia": descricao_hierarquia(plano),
        }
        for plano in planos
    ]


def campos_iniciais_registro():
    hoje = timezone.localdate().isoformat()
    return {
        "id": None,
        "filial_id": None,
        "tipo": RegistroFinanceiroTipo.ENTRADA,
        "contraparte_tipo": "",
        "contraparte_id": "",
        "plano_n2_id": "",
        "plano_n3_id": "",
        "plano_n4_id": "",
        "plano_contas_id": None,
        "data_emissao": hoje,
        "data_vencimento": hoje,
        "valor": "",
        "observacao": "",
        "status": RegistroFinanceiroStatus.ABERTO,
        "permite_editar": True,
        "permite_cancelar": True,
        "permite_excluir_permanente": False,
    }


def serializar_registro(registro: RegistroFinanceiro):
    contraparte_tipo = ""
    contraparte_id = ""
    if registro.contraparte_content_type_id:
        model_name = (registro.contraparte_content_type.model or "").lower()
        if model_name == "cliente":
            contraparte_tipo = "cliente"
        elif model_name == "motorista":
            contraparte_tipo = "motorista"
        contraparte_id = str(registro.contraparte_object_id or "")
    flags = _flags_acoes_ui(registro)
    return {
        "id": registro.id,
        "filial_id": registro.filial_id,
        "tipo": registro.tipo,
        "contraparte_tipo": contraparte_tipo,
        "contraparte_id": contraparte_id,
        "plano_contas_id": registro.plano_contas_id,
        "data_emissao": registro.data_emissao.isoformat() if registro.data_emissao else "",
        "data_vencimento": registro.data_vencimento.isoformat() if registro.data_vencimento else "",
        "valor": _formatar_decimal_br(registro.valor),
        "valor_fat": _formatar_decimal_br(registro.valor_fat),
        "valor_rest": _formatar_decimal_br(registro.valor_rest),
        "status": registro.status,
        "observacao": registro.observacao or "",
        **flags,
    }


def _validar_tipo_plano(tipo: str, plano: PlanoContas):
    if tipo == RegistroFinanceiroTipo.TRANSFERENCIA and plano.tipo_classificacao != TipoClassificacaoPlano.NEUTRO:
        raise ValidationError("Transferência exige plano de contas com classificação neutro.")
    if tipo == RegistroFinanceiroTipo.ENTRADA and plano.tipo_classificacao == TipoClassificacaoPlano.DESPESA:
        raise ValidationError("Entrada não pode usar plano classificado como despesa.")
    if tipo == RegistroFinanceiroTipo.SAIDA and plano.tipo_classificacao == TipoClassificacaoPlano.RECEITA:
        raise ValidationError("Saída não pode usar plano classificado como receita.")


def listar_contrapartes():
    clientes = [
        {"id": c.id, "label": f"{(c.codigo or '').strip()} - {c.nome}".strip(" -")}
        for c in Cliente.objects.filter(is_deleted=False).order_by("nome")[:500]
    ]
    motoristas = [
        {"id": m.id, "label": f"{(m.codigo or '').strip()} - {m.nome}".strip(" -")}
        for m in Motorista.objects.filter(is_deleted=False, ativa=True).order_by("nome")[:500]
    ]
    return {
        "tipos": [
            {"value": "cliente", "label": "Cliente"},
            {"value": "motorista", "label": "Motorista"},
        ],
        "por_tipo": {
            "cliente": clientes,
            "motorista": motoristas,
        },
    }


def _resolver_contraparte(campos: dict, filial_id: int):
    tipo = (campos.get("contraparte_tipo") or "").strip().lower()
    if not tipo:
        raise ValidationError("Selecione o tipo de contraparte.")
    object_id = parse_int(campos.get("contraparte_id"), context="form")
    if not object_id:
        raise ValidationError("Selecione a contraparte informada.")
    if tipo == "cliente":
        obj = Cliente.objects.filter(id=object_id, is_deleted=False).first()
        if not obj:
            raise ValidationError("Cliente inválido para contraparte.")
        ct = ContentType.objects.get_for_model(Cliente)
        return ct.id, obj.id
    if tipo == "motorista":
        obj = Motorista.objects.filter(id=object_id, is_deleted=False, ativa=True, filial_id=filial_id).first()
        if not obj:
            raise ValidationError("Motorista inválido para contraparte da filial.")
        ct = ContentType.objects.get_for_model(Motorista)
        return ct.id, obj.id
    raise ValidationError("Tipo de contraparte inválido.")


@transaction.atomic
def salvar_registro_manual(*, usuario, campos: dict, estado: str, filiais_escrita_ids: list[int]) -> RegistroFinanceiro:
    filial = obter_filial_escrita(campos.get("filial_id"), usuario)
    if not filial:
        raise ValidationError("Filial inválida ou sem permissão de escrita.")

    registro_id = parse_int(campos.get("id"), context="form")
    tipo = (campos.get("tipo") or "").strip()
    if tipo not in RegistroFinanceiroTipo.values:
        raise ValidationError("Tipo de registro financeiro inválido.")
    if tipo == RegistroFinanceiroTipo.TRANSFERENCIA:
        raise ValidationError("Transferência não está disponível neste cadastro manual.")

    plano_n4_id = parse_int(campos.get("plano_n4_id"), context="form")
    plano_id = parse_int(campos.get("plano_contas_id"), context="form")
    if not plano_n4_id or plano_n4_id != plano_id:
        raise ValidationError("Selecione o Ativo (nível final do plano de contas).")
    plano = PlanoContas.objects.filter(id=plano_id, nivel=4).first()
    if not plano:
        raise ValidationError("Plano de contas inválido para lançamento manual.")
    _validar_tipo_plano(tipo, plano)

    valor = parse_decimal(campos.get("valor"), context="form")
    if valor is None or valor <= Decimal("0"):
        raise ValidationError("Informe um valor maior que zero.")
    data_emissao = parse_date(campos.get("data_emissao"))
    data_vencimento = parse_date(campos.get("data_vencimento"))
    if not data_emissao:
        raise ValidationError("Informe a data de emissão.")
    if not data_vencimento:
        raise ValidationError("Informe a data de vencimento.")

    observacao = (campos.get("observacao") or "").strip()
    contraparte_content_type_id, contraparte_object_id = _resolver_contraparte(campos, filial.id)
    before = {}
    if estado == "novo":
        registro = RegistroFinanceiro(
            filial=filial,
            tipo=tipo,
            status=RegistroFinanceiroStatus.ABERTO,
            plano_contas=plano,
            valor=valor,
            valor_fat=Decimal("0"),
            valor_rest=valor,
            data_emissao=data_emissao,
            data_vencimento=data_vencimento,
            observacao=observacao,
            contraparte_content_type_id=contraparte_content_type_id,
            contraparte_object_id=contraparte_object_id,
        )
    elif estado == "editar":
        registro = RegistroFinanceiro.objects.filter(
            id=registro_id,
            filial_id__in=filiais_escrita_ids,
        ).first()
        if not registro:
            raise ValidationError("Registro financeiro não encontrado.")
        if not registro_eh_lancamento_manual_sem_referencia(registro):
            raise ValidationError("Somente lançamentos sem referência de origem (cadastro manual) podem ser alterados nesta tela.")
        if registro.status == RegistroFinanceiroStatus.CANCELADO:
            raise ValidationError("Não é permitido editar registro cancelado.")
        if registro.status == RegistroFinanceiroStatus.LIQUIDADO:
            raise ValidationError("Não é permitido editar registro liquidado.")
        before = snapshot_instance(registro)
        if registro.valor_fat > 0:
            raise ValidationError("Não é permitido editar títulos já abatidos/faturados.")
        if registro_tem_faturamento_vinculado(registro.id):
            raise ValidationError("Não é permitido editar título com faturamento vinculado.")
        registro.filial = filial
        registro.tipo = tipo
        registro.plano_contas = plano
        registro.valor = valor
        registro.valor_rest = valor
        registro.data_emissao = data_emissao
        registro.data_vencimento = data_vencimento
        registro.observacao = observacao
        registro.contraparte_content_type_id = contraparte_content_type_id
        registro.contraparte_object_id = contraparte_object_id
    else:
        raise ValidationError(f"Estado inválido: {estado}")

    try:
        registro.save()
    except (IntegrityError, DatabaseError) as exc:
        logger.error(exc, exc_info=True)
        raise ValidationError("Falha ao salvar registro financeiro.")

    registrar_auditoria(
        actor=usuario,
        action=AuditEvent.ACTION_CREATE if estado == "novo" else AuditEvent.ACTION_UPDATE,
        instance=registro,
        changed_fields=diff_snapshots(before, snapshot_instance(registro)),
    )
    return registro


@transaction.atomic
def cancelar_registro_manual(*, usuario, registro_id: int, filiais_escrita_ids: list[int]) -> RegistroFinanceiro:
    rid = parse_int(registro_id, context="form")
    if not rid:
        raise ValidationError("Registro financeiro inválido.")
    registro = RegistroFinanceiro.objects.filter(
        id=rid,
        filial_id__in=filiais_escrita_ids,
    ).first()
    if not registro:
        raise ValidationError("Registro financeiro não encontrado.")
    if registro.status == RegistroFinanceiroStatus.CANCELADO:
        raise ValidationError("Este registro já está cancelado.")
    if registro.valor_fat > 0 or registro_tem_faturamento_vinculado(registro.id):
        raise ValidationError("Não é permitido cancelar título com faturamento vinculado.")
    before = snapshot_instance(registro)
    registro.status = RegistroFinanceiroStatus.CANCELADO
    registro.save(update_fields=["status", "updated_at"])
    registrar_auditoria(
        actor=usuario,
        action=AuditEvent.ACTION_SOFT_DELETE,
        instance=registro,
        changed_fields=diff_snapshots(before, snapshot_instance(registro)),
    )
    return registro


@transaction.atomic
def excluir_registro_manual_permanente(*, usuario, registro_id: int, filiais_escrita_ids: list[int]) -> None:
    rid = parse_int(registro_id, context="form")
    if not rid:
        raise ValidationError("Registro financeiro inválido.")
    registro = RegistroFinanceiro.objects.filter(
        id=rid,
        filial_id__in=filiais_escrita_ids,
    ).first()
    if not registro:
        raise ValidationError("Registro financeiro não encontrado.")
    if not registro_eh_lancamento_manual_sem_referencia(registro):
        raise ValidationError(
            "Exclusão permanente é permitida apenas para títulos sem referência de origem (cadastro manual)."
        )
    if registro.valor_fat > 0 or registro_tem_faturamento_vinculado(registro.id):
        raise ValidationError("Não é permitido excluir título com faturamento vinculado.")
    if registro.status not in (
        RegistroFinanceiroStatus.ABERTO,
        RegistroFinanceiroStatus.CANCELADO,
    ):
        raise ValidationError("Exclusão permanente só é permitida para títulos abertos ou cancelados.")
    before = snapshot_instance(registro)
    registrar_auditoria(
        actor=usuario,
        action=AuditEvent.ACTION_DELETE,
        instance=registro,
        changed_fields=diff_snapshots(before, {}),
    )
    registro.delete()
