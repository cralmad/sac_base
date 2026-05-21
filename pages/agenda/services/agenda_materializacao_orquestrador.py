from __future__ import annotations

import logging
from datetime import date

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction

from pages.agenda.constants import ModoEventoAgenda, TipoVinculoMaterializacao
from pages.agenda.models import AgendaManual, AgendaMaterializacao
from pages.agenda.registry_materializacao import (
    listar_materialization_providers,
    obter_materialization_provider,
)

logger = logging.getLogger(__name__)


def _usuario_tem_permissao(usuario, codename: str) -> bool:
    if not usuario or not usuario.is_authenticated:
        return False
    if usuario.is_superuser:
        return True
    return usuario.has_perm(codename)


def listar_tipos_materializacao(usuario) -> list[dict]:
    out = []
    for prov in listar_materialization_providers():
        if _usuario_tem_permissao(usuario, prov.permission_codename):
            out.append({
                "value": prov.materialization_key,
                "label": prov.label,
                "categoria": getattr(prov, "categoria_agenda", ""),
            })
    return sorted(out, key=lambda x: x["label"])


def obter_schema_materializacao(
    *,
    tipo_materializacao: str,
    filial_id: int,
    usuario,
) -> dict:
    prov = obter_materialization_provider(tipo_materializacao)
    if not prov:
        raise ValidationError("Tipo de materialização inválido.")
    if not _usuario_tem_permissao(usuario, prov.permission_codename):
        raise ValidationError("Sem permissão para este tipo de lançamento.")
    form_schema = prov.get_form_schema(filial_id=filial_id, usuario=usuario)
    datasets = prov.build_datasets(filial_id=filial_id, usuario=usuario) if hasattr(prov, "build_datasets") else {}
    return {
        "tipo_materializacao": tipo_materializacao,
        "form_id": form_schema.form_id,
        "schema": form_schema.schema,
        "datasets": datasets,
        "datasets_keys": list(form_schema.datasets_keys),
    }


def validar_payload_template(
    *,
    tipo_materializacao: str,
    payload: dict,
    filial_id: int,
    usuario,
) -> dict:
    prov = obter_materialization_provider(tipo_materializacao)
    if not prov:
        raise ValidationError("Tipo de materialização inválido.")
    normalizado, erros = prov.validate_payload(payload or {}, filial_id=filial_id, usuario=usuario)
    if erros:
        raise ValidationError(erros[0] if len(erros) == 1 else erros)
    return normalizado or {}


@transaction.atomic
def executar_materializacao(
    *,
    agenda: AgendaManual,
    data_ocorrencia: date,
    usuario,
    payload_override: dict | None = None,
) -> AgendaMaterializacao:
    if agenda.modo_evento != ModoEventoAgenda.MATERIALIZAVEL:
        raise ValidationError("Somente regras materializáveis podem gerar lançamento.")
    tipo = (agenda.tipo_materializacao or "").strip()
    prov = obter_materialization_provider(tipo)
    if not prov:
        raise ValidationError("Tipo de materialização não configurado.")
    if not _usuario_tem_permissao(usuario, prov.permission_codename):
        raise ValidationError("Sem permissão para materializar este tipo.")

    if AgendaMaterializacao.objects.filter(
        agenda_manual_id=agenda.id,
        data_ocorrencia=data_ocorrencia,
    ).exists():
        raise ValidationError("Esta ocorrência já foi materializada ou confirmada.")

    payload = dict(agenda.payload_template or {})
    if payload_override:
        payload.update(payload_override)
    normalizado, erros = prov.validate_payload(payload, filial_id=agenda.filial_id, usuario=usuario)
    if erros:
        raise ValidationError(erros[0] if len(erros) == 1 else erros)

    instance = prov.materialize(
        payload=normalizado or {},
        filial_id=agenda.filial_id,
        data_ocorrencia=data_ocorrencia,
        agenda_manual_id=agenda.id,
        usuario=usuario,
    )
    ct = ContentType.objects.get_for_model(instance.__class__)
    mat = AgendaMaterializacao.objects.create(
        agenda_manual=agenda,
        data_ocorrencia=data_ocorrencia,
        tipo_vinculo=TipoVinculoMaterializacao.MATERIALIZADO,
        content_type=ct,
        object_id=instance.pk,
        created_by=usuario if usuario and usuario.is_authenticated else None,
    )
    return mat
