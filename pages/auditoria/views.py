from datetime import datetime, time

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import permission_required
from django.core.paginator import EmptyPage, Paginator
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from pages.auditoria.models import AuditEvent
from sac_base.form_validador import SchemaValidator
from sac_base.sisvar_builders import build_error_payload, build_form_state, build_sisvar_payload, build_sisvar_response

User = get_user_model()


PERMISSOES_AUDITORIA = {
    "acessar": "auditoria.acessar_consulta_auditoria",
    "consultar": "auditoria.acessar_consulta_auditoria",
}


def obter_acoes_permitidas_auditoria(usuario):
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return {acao: False for acao in PERMISSOES_AUDITORIA}

    return {
        acao: usuario.has_perm(codename)
        for acao, codename in PERMISSOES_AUDITORIA.items()
    }


def resposta_sem_permissao(mensagem, status=403):
    return JsonResponse(build_error_payload(mensagem), status=status)


def listar_atores_auditoria():
    atores_ids = AuditEvent.objects.exclude(actor__isnull=True).values_list("actor_id", flat=True).distinct()
    atores = User.objects.filter(id__in=atores_ids).order_by("first_name", "username")
    return [
        {
            "id": ator.id,
            "nome": ator.first_name or ator.username,
            "username": ator.username,
        }
        for ator in atores
    ]


def listar_entidades_auditoria():
    entidades = {}
    for app_label, model in (
        AuditEvent.objects.values_list("content_type__app_label", "content_type__model")
        .distinct()
        .order_by("content_type__app_label", "content_type__model")
    ):
        entidades.setdefault(app_label, []).append(model)

    return [
        {
            "app_label": app_label,
            "models": models,
        }
        for app_label, models in entidades.items()
    ]


def montar_opcoes_auditoria():
    return {
        "atores": listar_atores_auditoria(),
        "acoes": [
            {"value": value, "label": label}
            for value, label in AuditEvent.ACTION_CHOICES
        ],
        "entidades": listar_entidades_auditoria(),
    }


def montar_paginacao(page=1, per_page=20, total_registros=0):
    total_paginas = max(1, (total_registros + per_page - 1) // per_page) if per_page else 1
    pagina_atual = min(max(1, page), total_paginas)
    return {
        "page": pagina_atual,
        "per_page": per_page,
        "total_registros": total_registros,
        "total_paginas": total_paginas,
        "has_previous": pagina_atual > 1,
        "has_next": pagina_atual < total_paginas,
    }


def resumir_alteracoes(changed_fields, extra_data):
    if changed_fields:
        campos = list(changed_fields.keys())
        if len(campos) <= 3:
            return ", ".join(campos)
        return f"{', '.join(campos[:3])} +{len(campos) - 3}"

    if extra_data:
        chaves = list(extra_data.keys())
        if len(chaves) <= 3:
            return ", ".join(chaves)
        return f"{', '.join(chaves[:3])} +{len(chaves) - 3}"

    return "Sem detalhes"


def serializar_evento(evento):
    actor = evento.actor
    actor_nome = "Sistema"
    if actor:
        actor_nome = actor.first_name or actor.username

    return {
        "id": evento.id,
        "created_at": timezone.localtime(evento.created_at).isoformat(),
        "actor": actor_nome,
        "action": evento.action,
        "entity": f"{evento.content_type.app_label}.{evento.content_type.model}",
        "object_id": evento.object_id,
        "object_repr": evento.object_repr,
        "summary": resumir_alteracoes(evento.changed_fields, evento.extra_data),
        "changed_fields": evento.changed_fields,
        "extra_data": evento.extra_data,
    }


def parse_data_filtro(data_str, fim=False):
    if not data_str:
        return None

    try:
        data_base = datetime.strptime(data_str, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("Data inválida. Use o formato AAAA-MM-DD.")

    horario = time.max if fim else time.min
    return timezone.make_aware(datetime.combine(data_base, horario), timezone.get_current_timezone())


def parse_inteiro_positivo(valor, campo, padrao):
    if valor in (None, ""):
        return padrao

    try:
        numero = int(valor)
    except (TypeError, ValueError):
        raise ValueError(f"Valor inválido para {campo}.")

    if numero < 1:
        raise ValueError(f"Valor inválido para {campo}.")

    return numero


def consultar_eventos(campos):
    qs = AuditEvent.objects.select_related("actor", "content_type")

    actor_id = campos.get("actor_id")
    action = (campos.get("action") or "").strip()
    app_label = (campos.get("app_label") or "").strip()
    model = (campos.get("model") or "").strip()
    object_id = (campos.get("object_id") or "").strip()
    data_inicio = (campos.get("data_inicio") or "").strip()
    data_fim = (campos.get("data_fim") or "").strip()
    page = parse_inteiro_positivo(campos.get("page"), "page", 1)
    per_page = parse_inteiro_positivo(campos.get("per_page"), "per_page", 20)

    per_page = min(per_page, 100)

    if actor_id:
        qs = qs.filter(actor_id=actor_id)

    if action:
        qs = qs.filter(action=action)

    if app_label:
        qs = qs.filter(content_type__app_label=app_label)

    if model:
        qs = qs.filter(content_type__model=model)

    if object_id:
        qs = qs.filter(object_id__icontains=object_id)

    inicio = parse_data_filtro(data_inicio)
    if inicio:
        qs = qs.filter(created_at__gte=inicio)

    fim = parse_data_filtro(data_fim, fim=True)
    if fim:
        qs = qs.filter(created_at__lte=fim)

    paginator = Paginator(qs.order_by("-created_at", "-id"), per_page)
    try:
        pagina = paginator.page(page)
    except EmptyPage:
        pagina = paginator.page(paginator.num_pages or 1)

    return {
        "registros": [serializar_evento(evento) for evento in pagina.object_list],
        "paginacao": montar_paginacao(
            page=pagina.number,
            per_page=per_page,
            total_registros=paginator.count,
        ),
    }


@permission_required(PERMISSOES_AUDITORIA["acessar"], raise_exception=True)
def auditoria_view(request):
    template = "auditoria.html"
    nome_form = "consAuditoria"
    acoes_permitidas = obter_acoes_permitidas_auditoria(getattr(request, "user", None))

    schema = {
        nome_form: {
            "actor_id": {"type": "integer", "required": False, "value": None},
            "action": {"type": "string", "maxlength": 40, "required": False, "value": ""},
            "app_label": {"type": "string", "maxlength": 50, "required": False, "value": ""},
            "model": {"type": "string", "maxlength": 50, "required": False, "value": ""},
            "object_id": {"type": "string", "maxlength": 64, "required": False, "value": ""},
            "data_inicio": {"type": "string", "maxlength": 10, "required": False, "value": ""},
            "data_fim": {"type": "string", "maxlength": 10, "required": False, "value": ""},
        }
    }

    if request.method == "GET":
        request.sisvar_extra = build_sisvar_payload(
            schema=schema,
            forms={
                nome_form: build_form_state(
                    campos={
                        "actor_id": None,
                        "action": "",
                        "app_label": "",
                        "model": "",
                        "object_id": "",
                        "data_inicio": "",
                        "data_fim": "",
                        "page": 1,
                        "per_page": 20,
                    },
                )
            },
            permissions={
                "auditoria": acoes_permitidas,
            },
            datasets={
                "auditoria": {
                    **montar_opcoes_auditoria(),
                    "registros": [],
                    "paginacao": montar_paginacao(),
                },
            },
        )
        return render(request, template)

    return JsonResponse(build_error_payload("Método não permitido."), status=405)


@permission_required(PERMISSOES_AUDITORIA["consultar"], raise_exception=True)
def auditoria_cons_view(request):
    nome_form = "consAuditoria"

    if request.method != "POST":
        return JsonResponse(build_error_payload("Método não permitido."), status=405)

    campos = request.sisvar_front.get("form", {}).get(nome_form, {}).get("campos", {})

    validator = SchemaValidator({
        "action": {"type": "string", "maxlength": 40, "required": False},
        "app_label": {"type": "string", "maxlength": 50, "required": False},
        "model": {"type": "string", "maxlength": 50, "required": False},
        "object_id": {"type": "string", "maxlength": 64, "required": False},
        "data_inicio": {"type": "string", "maxlength": 10, "required": False},
        "data_fim": {"type": "string", "maxlength": 10, "required": False},
        "page": {"type": "string", "maxlength": 10, "required": False},
        "per_page": {"type": "string", "maxlength": 3, "required": False},
    })
    if not validator.validate(campos):
        erros = [
            f"{campo} - {', '.join(msgs)}"
            for campo, msgs in validator.get_errors().items()
        ]
        return JsonResponse(build_error_payload(erros), status=400)

    try:
        resultado_consulta = consultar_eventos(campos)
    except ValueError as exc:
        return JsonResponse(build_error_payload(str(exc)), status=422)

    return JsonResponse(build_sisvar_response(
        datasets={
            "auditoria": {
                **montar_opcoes_auditoria(),
                "registros": resultado_consulta["registros"],
                "paginacao": resultado_consulta["paginacao"],
            }
        },
    ))