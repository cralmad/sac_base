from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

from pages.agenda.constants import CategoriaAgenda
from pages.agenda.providers.base import AgendaMaterializationProvider, MaterializacaoFormSchema
from pages.financeiro.models import RegistroFinanceiroTipo
from pages.financeiro.services.registro_manual import (
    listar_contrapartes,
    listar_planos_cascata,
    listar_planos_nivel4,
    salvar_registro_manual,
)
from sac_base.coercion import parse_decimal, parse_int
from sac_base.form_validador import SchemaValidator

MATERIALIZATION_KEY = "financeiro.registro_financeiro_manual"
FORM_ID = "agenda_mat_financeiro"


class RegistroFinanceiroMaterializationProvider:
    materialization_key = MATERIALIZATION_KEY
    label = "Registro financeiro (manual)"
    permission_codename = "financeiro.add_registrofinanceiro"
    categoria_agenda = CategoriaAgenda.FINANCEIRO

    def get_form_schema(self, *, filial_id: int, usuario) -> MaterializacaoFormSchema:
        return MaterializacaoFormSchema(
            form_id=FORM_ID,
            schema={
                "tipo": {"required": True, "type": "string"},
                "valor": {"required": False, "type": "string"},
                "plano_n2_id": {"type": "integer"},
                "plano_n3_id": {"type": "integer"},
                "plano_n4_id": {"required": True, "type": "integer"},
                "contraparte_tipo": {"required": True, "type": "string"},
                "contraparte_id": {"required": True, "type": "integer"},
                "observacao": {"type": "string", "maxlength": 2000},
            },
            datasets_keys=("planos_contas", "planos_nivel4", "contraparte_tipos", "contrapartes_por_tipo", "tipos_registro_financeiro"),
        )

    def build_datasets(self, *, filial_id: int, usuario) -> dict:
        from pages.financeiro.models import RegistroFinanceiroTipo

        contraparte = listar_contrapartes()
        return {
            "planos_nivel4": listar_planos_nivel4(),
            "planos_contas": listar_planos_cascata(),
            "tipos_registro_financeiro": [
                {"value": val, "label": label}
                for val, label in RegistroFinanceiroTipo.choices
                if val != RegistroFinanceiroTipo.TRANSFERENCIA
            ],
            "contraparte_tipos": contraparte["tipos"],
            "contrapartes_por_tipo": contraparte["por_tipo"],
        }

    def validate_payload(
        self,
        payload: dict,
        *,
        filial_id: int,
        usuario,
    ) -> tuple[dict | None, list[str]]:
        schema = self.get_form_schema(filial_id=filial_id, usuario=usuario).schema
        validator = SchemaValidator(schema)
        if not validator.validate(payload or {}):
            return None, [
                f"{campo} - {', '.join(erros)}"
                for campo, erros in validator.get_errors().items()
            ]
        tipo = (payload.get("tipo") or "").strip()
        if tipo not in (RegistroFinanceiroTipo.ENTRADA, RegistroFinanceiroTipo.SAIDA):
            return None, ["Tipo de registro financeiro inválido."]
        valor_flutuante = bool(payload.get("valor_flutuante"))
        raw_valor = payload.get("valor")
        if raw_valor in (None, "") and not valor_flutuante:
            valor_flutuante = True
        valor = parse_decimal(raw_valor, context="form") if raw_valor not in (None, "") else None
        if valor_flutuante or valor is None or valor == Decimal("0"):
            valor_flutuante = True
            valor = Decimal("0")
        elif valor < Decimal("0"):
            return None, ["Valor não pode ser negativo."]
        plano_n4 = parse_int(payload.get("plano_n4_id"), context="form")
        if not plano_n4:
            return None, ["Selecione o plano de contas (nível 4)."]
        contraparte_id = parse_int(payload.get("contraparte_id"), context="form")
        if not contraparte_id:
            return None, ["Selecione a contraparte."]
        return {
            "tipo": tipo,
            "valor": "" if valor_flutuante else str(valor),
            "valor_flutuante": valor_flutuante,
            "plano_n2_id": parse_int(payload.get("plano_n2_id"), context="form"),
            "plano_n3_id": parse_int(payload.get("plano_n3_id"), context="form"),
            "plano_n4_id": plano_n4,
            "plano_contas_id": plano_n4,
            "contraparte_tipo": (payload.get("contraparte_tipo") or "").strip(),
            "contraparte_id": contraparte_id,
            "observacao": (payload.get("observacao") or "").strip(),
        }, []

    def materialize(
        self,
        *,
        payload: dict,
        filial_id: int,
        data_ocorrencia: date,
        agenda_manual_id: int,
        usuario,
    ) -> object:
        hoje = timezone.localdate().isoformat()
        valor_flutuante = bool(payload.get("valor_flutuante"))
        valor_envio = payload.get("valor") if not valor_flutuante else "0"
        campos = {
            "filial_id": filial_id,
            "tipo": payload.get("tipo"),
            "valor": valor_envio,
            "plano_n4_id": payload.get("plano_n4_id"),
            "plano_contas_id": payload.get("plano_contas_id"),
            "contraparte_tipo": payload.get("contraparte_tipo"),
            "contraparte_id": payload.get("contraparte_id"),
            "observacao": payload.get("observacao") or "",
            "data_emissao": hoje,
            "data_vencimento": data_ocorrencia.isoformat(),
        }
        from pages.filial.services import get_filiais_escrita_queryset

        filiais_ids = list(get_filiais_escrita_queryset(usuario).values_list("id", flat=True))
        return salvar_registro_manual(
            usuario=usuario,
            campos=campos,
            estado="novo",
            filiais_escrita_ids=filiais_ids,
            permitir_valor_flutuante=valor_flutuante,
        )
