from datetime import datetime, timedelta
import json

import jwt
from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from pages.filial.models import FilialConfig
from pages.pedidos.models import AvaliacaoPedido, Pedido, ESTADOS_ENTREGA_EFETIVAMENTE_CONCLUIDA, estado_label
from sac_base.email_avaliacao_service import enviar_email_avaliacao, montar_email_avaliacao

_ALGO_JWT = "HS256"

PERMISSOES_AVALIACAO = {
    "acessar": "pedidos.view_relatorio_avaliacao",
    "enviar": "pedidos.send_email_avaliacao",
    "gerar_fila": "pedidos.generate_email_queue_avaliacao",
}


def _parse_nota_1_5(payload: dict, chave: str):
    try:
        valor = int(payload.get(chave))
    except (TypeError, ValueError):
        return None
    if 1 <= valor <= 5:
        return valor
    return None


def _gerar_token_avaliacao(avaliacao_id: int) -> str:
    payload = {
        "avaliacao_id": int(avaliacao_id),
        "exp": timezone.now() + timedelta(days=180),
    }
    return jwt.encode(payload, settings.AVALIACAO_TOKEN_SECRET, algorithm=_ALGO_JWT)


def _validar_token_avaliacao(token: str) -> int:
    payload = jwt.decode(token, settings.AVALIACAO_TOKEN_SECRET, algorithms=[_ALGO_JWT])
    return int(payload["avaliacao_id"])


def _garantir_token_avaliacao(avaliacao: AvaliacaoPedido):
    if not avaliacao.token_publico:
        avaliacao.token_publico = _gerar_token_avaliacao(avaliacao.id)
        avaliacao.save(update_fields=["token_publico", "updated_at"])
    else:
        try:
            _validar_token_avaliacao(avaliacao.token_publico)
        except Exception:
            avaliacao.token_publico = _gerar_token_avaliacao(avaliacao.id)
            avaliacao.save(update_fields=["token_publico", "updated_at"])
    return avaliacao


def _montar_link_publico(request, token: str) -> str:
    base = (settings.APP_BASE_URL or "").rstrip("/")
    if base:
        return f"{base}/app/logistica/avaliacao/{token}/"
    if request is not None:
        return request.build_absolute_uri(f"/app/logistica/avaliacao/{token}/")
    return f"{base}/app/logistica/avaliacao/{token}/"


def enviar_email_pedido_avaliacao(*, avaliacao: AvaliacaoPedido, request=None) -> dict:
    pedido = avaliacao.pedido
    if not pedido.email_dest:
        return {"sucesso": False, "erro": "Pedido sem e-mail do destinatário."}
    if pedido.estado not in ESTADOS_ENTREGA_EFETIVAMENTE_CONCLUIDA:
        return {"sucesso": False, "erro": "Pedido ainda não está concluído para envio de pesquisa."}
    if not avaliacao.selecionado_para_envio:
        return {"sucesso": False, "erro": "Avaliação não está selecionada para envio."}
    app_base_url = (settings.APP_BASE_URL or "").strip().lower()
    usa_dominio_remoto = app_base_url.startswith("http") and "127.0.0.1" not in app_base_url and "localhost" not in app_base_url
    if usa_dominio_remoto and settings.AVALIACAO_TOKEN_SECRET == "django-dev-sac-base-insecure-key":
        return {
            "sucesso": False,
            "erro": "Configuração inválida: defina AVALIACAO_TOKEN_SECRET (ou DJANGO_SECRET_KEY) para assinar links de avaliação destinados a domínio remoto.",
        }

    avaliacao = _garantir_token_avaliacao(avaliacao)
    filial = pedido.filial
    cfg = FilialConfig.objects.filter(filial=filial).first()
    link = _montar_link_publico(request, avaliacao.token_publico)
    assunto, corpo = montar_email_avaliacao(pedido=pedido, filial=filial, link_avaliacao=link, config=cfg)
    nome_remetente = (getattr(cfg, "email_nome_remetente", "") or "").strip() or None

    envio = enviar_email_avaliacao(
        destinatario=pedido.email_dest.strip(),
        assunto=assunto,
        corpo=corpo,
        nome_remetente=nome_remetente,
        link_avaliacao=link,
        nome_cliente=(pedido.nome_dest or "Cliente"),
        filial_nome=getattr(filial, "nome", "SacBase"),
    )

    avaliacao.email_tentativas += 1
    if envio.get("sucesso"):
        avaliacao.email_enviado = True
        avaliacao.email_enviado_em = timezone.now()
    avaliacao.save(update_fields=["email_tentativas", "email_enviado", "email_enviado_em", "updated_at"])
    return envio


@login_required
@permission_required(PERMISSOES_AVALIACAO["gerar_fila"], raise_exception=True)
@require_http_methods(["GET", "POST"])
def relatorio_avaliacao_geracao_view(request):
    filial_ativa = getattr(request, "filial_ativa", None)
    if not filial_ativa:
        return JsonResponse({"success": False, "mensagem": "Filial ativa não encontrada."}, status=403)

    if request.method == "GET":
        data_ref = (request.GET.get("data_ref") or "").strip()
        pedidos = []
        if data_ref:
            pedidos = list(
                Pedido.objects.filter(
                    filial=filial_ativa,
                    prev_entrega=data_ref,
                    estado__in=ESTADOS_ENTREGA_EFETIVAMENTE_CONCLUIDA,
                )
                .exclude(email_dest__isnull=True)
                .exclude(email_dest="")
                .order_by("pedido", "id")
            )
        pedidos_payload = []
        pedidos_ids = [p.id for p in pedidos]
        pedidos_na_fila_ids = set()
        if pedidos_ids:
            pedidos_na_fila_ids = set(
                AvaliacaoPedido.objects.filter(pedido_id__in=pedidos_ids).values_list("pedido_id", flat=True)
            )
        for pedido in pedidos:
            ja_na_fila = pedido.id in pedidos_na_fila_ids
            pedidos_payload.append(
                {
                    "id": pedido.id,
                    "referencia": pedido.pedido or pedido.id_vonzu,
                    "nome_dest": pedido.nome_dest or "",
                    "email_dest": pedido.email_dest or "",
                    "estado": estado_label(pedido.estado),
                    "ja_na_fila": ja_na_fila,
                }
            )
        return render(
            request,
            "relatorio_avaliacao_geracao.html",
            {"data_ref": data_ref, "pedidos": pedidos_payload},
        )

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "mensagem": "JSON inválido."}, status=400)

    ids = payload.get("ids") or []
    if not isinstance(ids, list) or not ids:
        return JsonResponse({"success": False, "mensagem": "Selecione pelo menos um pedido."}, status=400)

    try:
        ids = [int(i) for i in ids]
    except (TypeError, ValueError):
        return JsonResponse({"success": False, "mensagem": "Lista de IDs inválida."}, status=400)
    pedidos = (
        Pedido.objects.filter(
            id__in=ids,
            filial=filial_ativa,
            estado__in=ESTADOS_ENTREGA_EFETIVAMENTE_CONCLUIDA,
        )
        .exclude(email_dest__isnull=True)
        .exclude(email_dest="")
    )
    pedidos_list = list(pedidos)

    criados = 0
    existentes = 0
    pedidos_ids = [p.id for p in pedidos_list]
    existentes_qs = AvaliacaoPedido.objects.filter(pedido_id__in=pedidos_ids).only("id", "pedido_id", "selecionado_para_envio", "token_publico")
    existentes_map = {a.pedido_id: a for a in existentes_qs}
    existentes = len(existentes_map)

    faltantes_ids = [pid for pid in pedidos_ids if pid not in existentes_map]
    if faltantes_ids:
        AvaliacaoPedido.objects.bulk_create(
            [
                AvaliacaoPedido(
                    pedido_id=pid,
                    origem_geracao="MANUAL_RELATORIO",
                    selecionado_para_envio=True,
                )
                for pid in faltantes_ids
            ]
        )
        criados = len(faltantes_ids)

    AvaliacaoPedido.objects.filter(
        pedido_id__in=list(existentes_map.keys()),
        selecionado_para_envio=False,
    ).update(selecionado_para_envio=True, updated_at=timezone.now())

    return JsonResponse(
        {
            "success": True,
            "mensagem": f"Fila gerada: {criados} criado(s), {existentes} já existente(s).",
            "resumo": {"selecionados": len(ids), "processados": pedidos.count(), "criados": criados, "existentes": existentes},
        }
    )


@require_GET
def avaliacao_publica_view(request, token):
    try:
        avaliacao_id = _validar_token_avaliacao(token)
        avaliacao = AvaliacaoPedido.objects.select_related("pedido").get(id=avaliacao_id, token_publico=token)
    except Exception:
        return render(request, "avaliacao_publica.html", {"erro": "invalido"})

    if not avaliacao.link_ativo or avaliacao.respondido_em:
        return render(request, "avaliacao_publica.html", {"erro": "respondido"})

    return render(request, "avaliacao_publica.html", {"avaliacao": avaliacao, "token": token})


@csrf_exempt
@require_POST
def avaliacao_publica_enviar_view(request, token):
    try:
        avaliacao_id = _validar_token_avaliacao(token)
        avaliacao = AvaliacaoPedido.objects.select_related("pedido").get(id=avaliacao_id, token_publico=token)
    except Exception:
        return JsonResponse({"success": False, "mensagem": "Link inválido ou expirado."}, status=403)

    if not avaliacao.link_ativo or avaliacao.respondido_em:
        return JsonResponse({"success": False, "mensagem": "Esta avaliação já foi finalizada."}, status=409)

    payload = json.loads(request.body or "{}")
    campos_obrigatorios = ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9", "p10"]
    faltantes = [k for k in campos_obrigatorios if not str(payload.get(k, "")).strip()]
    if faltantes:
        return JsonResponse({"success": False, "mensagem": "Preencha todas as perguntas obrigatórias."}, status=400)

    nota_p3 = _parse_nota_1_5(payload, "p3")
    nota_p4 = _parse_nota_1_5(payload, "p4")
    nota_p6 = _parse_nota_1_5(payload, "p6")
    nota_p9 = _parse_nota_1_5(payload, "p9")
    if None in (nota_p3, nota_p4, nota_p6, nota_p9):
        return JsonResponse(
            {"success": False, "mensagem": "As notas das perguntas objetivas devem estar entre 1 e 5."},
            status=400,
        )

    avaliacao.p1_entrega_no_prazo = payload.get("p1")
    avaliacao.p2_aviso_antes_chegada = payload.get("p2")
    avaliacao.p3_educacao_simpatia = nota_p3
    avaliacao.p4_cuidado_encomenda = nota_p4
    avaliacao.p5_equipa_identificada = payload.get("p5")
    avaliacao.p6_facilidade_processo = nota_p6
    avaliacao.p7_veiculo_limpo = payload.get("p7")
    avaliacao.p8_esclareceu_duvidas = payload.get("p8")
    avaliacao.p9_satisfacao_geral = nota_p9
    avaliacao.p10_recomendaria = payload.get("p10")
    avaliacao.comentario = (payload.get("comentario") or "").strip() or None
    avaliacao.respondido_em = timezone.now()
    avaliacao.link_ativo = False
    avaliacao.save()
    return JsonResponse({"success": True, "mensagem": "Agradecemos pela sua avaliação."})


@login_required
@permission_required(PERMISSOES_AVALIACAO["acessar"], raise_exception=True)
@require_GET
def relatorio_avaliacao_view(request):
    filial_ativa = getattr(request, "filial_ativa", None)
    pedido_ref = (request.GET.get("pedido") or "").strip()
    status = (request.GET.get("status") or "").strip()
    data_inicial = (request.GET.get("data_inicial") or "").strip()
    data_final = (request.GET.get("data_final") or "").strip()
    periodo_informado = bool(data_inicial and data_final)
    filtro_aplicado = periodo_informado

    registros = []
    if filtro_aplicado:
        qs = AvaliacaoPedido.objects.select_related("pedido").filter(selecionado_para_envio=True).order_by("-id")
        if filial_ativa:
            qs = qs.filter(pedido__filial=filial_ativa)
        if pedido_ref:
            qs = qs.filter(pedido__pedido__icontains=pedido_ref)
        if data_inicial:
            qs = qs.filter(pedido__prev_entrega__gte=data_inicial)
        if data_final:
            qs = qs.filter(pedido__prev_entrega__lte=data_final)
        if status == "respondido":
            qs = qs.filter(respondido_em__isnull=False)
        elif status == "pendente":
            qs = qs.filter(respondido_em__isnull=True)
        elif status == "enviado":
            qs = qs.filter(email_enviado=True)
        elif status == "nao_enviado":
            qs = qs.filter(email_enviado=False)
        registros = qs[:200]

    pode_enviar = bool(getattr(request.user, "has_perm", lambda *_: False)("pedidos.send_email_avaliacao"))
    pode_gerar = bool(getattr(request.user, "has_perm", lambda *_: False)("pedidos.generate_email_queue_avaliacao"))
    return render(
        request,
        "relatorio_avaliacao.html",
        {
            "registros": registros,
            "filtros": {
                "pedido": pedido_ref,
                "status": status,
                "data_inicial": data_inicial,
                "data_final": data_final,
            },
            "filtro_aplicado": filtro_aplicado,
            "periodo_informado": periodo_informado,
            "pode_enviar": pode_enviar,
            "pode_gerar": pode_gerar,
        },
    )


@login_required
@permission_required(PERMISSOES_AVALIACAO["enviar"], raise_exception=True)
@require_POST
def relatorio_avaliacao_enviar_view(request, avaliacao_id):
    avaliacao = get_object_or_404(AvaliacaoPedido.objects.select_related("pedido"), pk=avaliacao_id)
    envio = enviar_email_pedido_avaliacao(avaliacao=avaliacao, request=request)
    if not envio.get("sucesso"):
        return JsonResponse({"success": False, "mensagem": envio.get("erro") or "Falha no envio."}, status=400)
    return JsonResponse({"success": True, "mensagem": "E-mail reenviado com sucesso."})


@login_required
@permission_required(PERMISSOES_AVALIACAO["enviar"], raise_exception=True)
@require_POST
def relatorio_avaliacao_enviar_lote_view(request):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "mensagem": "JSON inválido."}, status=400)

    ids = payload.get("ids") or []
    if not isinstance(ids, list) or not ids:
        return JsonResponse({"success": False, "mensagem": "Selecione pelo menos uma avaliação."}, status=400)

    try:
        ids = [int(i) for i in ids]
    except (TypeError, ValueError):
        return JsonResponse({"success": False, "mensagem": "Lista de IDs inválida."}, status=400)

    filial_ativa = getattr(request, "filial_ativa", None)
    qs = AvaliacaoPedido.objects.select_related("pedido").filter(pk__in=ids)
    if filial_ativa:
        qs = qs.filter(pedido__filial=filial_ativa)

    registros = list(qs)
    enviados = 0
    falhas = 0
    ignorados = 0
    detalhes = []

    for avaliacao in registros:
        pedido = avaliacao.pedido
        referencia = pedido.pedido or str(getattr(pedido, "id_vonzu", pedido.pk))

        if avaliacao.respondido_em:
            ignorados += 1
            detalhes.append({"id": avaliacao.id, "referencia": referencia, "status": "ignorado", "motivo": "Avaliação já respondida."})
            continue

        retorno = enviar_email_pedido_avaliacao(avaliacao=avaliacao, request=request)
        if retorno.get("sucesso"):
            enviados += 1
            detalhes.append({"id": avaliacao.id, "referencia": referencia, "status": "enviado"})
        else:
            falhas += 1
            detalhes.append(
                {
                    "id": avaliacao.id,
                    "referencia": referencia,
                    "status": "falha",
                    "motivo": retorno.get("erro") or "Falha no envio.",
                }
            )

    return JsonResponse(
        {
            "success": True,
            "mensagem": f"Processamento concluído: {enviados} enviado(s), {falhas} falha(s), {ignorados} ignorado(s).",
            "resumo": {"total_selecionados": len(ids), "processados": len(registros), "enviados": enviados, "falhas": falhas, "ignorados": ignorados},
            "detalhes": detalhes,
        }
    )
