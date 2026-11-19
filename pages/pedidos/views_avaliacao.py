import json

from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from pages.pedidos.models import AvaliacaoPedido, estado_label
from pages.pedidos.services.avaliacao_envio import (
    CANAL_EMAIL,
    CANAIS_VALIDOS,
    canais_permitidos_user,
    enviar_avaliacao_canais,
    filtrar_canais_pedidos,
    pedido_canais_disponiveis,
    pedido_telefone_sms,
    pedido_tem_email,
    pedido_tem_telefone,
    qs_pedidos_elegiveis_fila,
)
from pages.pedidos.services.avaliacao_link import resolver_avaliacao_por_token

PERMISSOES_AVALIACAO = {
    "acessar": "pedidos.view_relatorio_avaliacao",
    "enviar_email": "pedidos.send_email_avaliacao",
    "enviar_sms": "pedidos.send_sms_avaliacao",
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


def _user_tem_algum_canal(user) -> bool:
    return bool(canais_permitidos_user(user))


def _parse_canais_lista(raw) -> tuple[list[str] | None, str | None]:
    if not isinstance(raw, list) or not raw:
        return None, "Informe pelo menos um canal (email e/ou sms)."
    canais = []
    for item in raw:
        c = str(item or "").strip().lower()
        if c not in CANAIS_VALIDOS:
            return None, "Canal inválido. Use apenas email e/ou sms."
        if c not in canais:
            canais.append(c)
    if not canais:
        return None, "Informe pelo menos um canal (email e/ou sms)."
    return canais, None


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
                qs_pedidos_elegiveis_fila(filial_ativa, data_ref=data_ref).order_by("pedido", "id")
            )
        pedidos_payload = []
        pedidos_ids = [p.id for p in pedidos]
        pedidos_na_fila_ids = set()
        if pedidos_ids:
            pedidos_na_fila_ids = set(
                AvaliacaoPedido.objects.filter(pedido_id__in=pedidos_ids).values_list("pedido_id", flat=True)
            )
        for pedido in pedidos:
            canais = pedido_canais_disponiveis(pedido)
            pedidos_payload.append(
                {
                    "id": pedido.id,
                    "referencia": pedido.pedido or pedido.id_vonzu,
                    "nome_dest": pedido.nome_dest or "",
                    "email_dest": pedido.email_dest or "",
                    "telefone": pedido_telefone_sms(pedido),
                    "canais": ", ".join(canais),
                    "estado": estado_label(pedido.estado),
                    "ja_na_fila": pedido.id in pedidos_na_fila_ids,
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

    pedidos_list = list(qs_pedidos_elegiveis_fila(filial_ativa, ids=ids))

    pedidos_ids = [p.id for p in pedidos_list]
    existentes_qs = AvaliacaoPedido.objects.filter(pedido_id__in=pedidos_ids).only(
        "id", "pedido_id", "selecionado_para_envio", "token_publico"
    )
    existentes_map = {a.pedido_id: a for a in existentes_qs}
    existentes = len(existentes_map)

    faltantes_ids = [pid for pid in pedidos_ids if pid not in existentes_map]
    criados = 0
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
            "resumo": {
                "selecionados": len(ids),
                "processados": len(pedidos_list),
                "criados": criados,
                "existentes": existentes,
            },
        }
    )


@require_GET
def avaliacao_publica_view(request, token):
    try:
        avaliacao = resolver_avaliacao_por_token(token)
    except Exception:
        return render(request, "avaliacao_publica.html", {"erro": "invalido"})

    if not avaliacao.link_ativo or avaliacao.respondido_em:
        return render(request, "avaliacao_publica.html", {"erro": "respondido"})

    return render(request, "avaliacao_publica.html", {"avaliacao": avaliacao, "token": token})


@csrf_exempt
@require_POST
def avaliacao_publica_enviar_view(request, token):
    try:
        avaliacao = resolver_avaliacao_por_token(token)
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
        elif status == "email_enviado":
            qs = qs.filter(email_enviado=True)
        elif status == "email_nao_enviado":
            qs = qs.filter(email_enviado=False)
        elif status == "sms_enviado":
            qs = qs.filter(sms_enviado=True)
        elif status == "sms_nao_enviado":
            qs = qs.filter(sms_enviado=False)
        elif status == "enviado":
            qs = qs.filter(email_enviado=True)
        elif status == "nao_enviado":
            qs = qs.filter(email_enviado=False)
        registros = list(qs[:200])
        for av in registros:
            av.telefone_display = pedido_telefone_sms(av.pedido) or "-"
            av.tem_email = pedido_tem_email(av.pedido)
            av.tem_telefone = pedido_tem_telefone(av.pedido)

    pode_enviar_email = bool(request.user.has_perm(PERMISSOES_AVALIACAO["enviar_email"]))
    pode_enviar_sms = bool(request.user.has_perm(PERMISSOES_AVALIACAO["enviar_sms"]))
    pode_enviar = pode_enviar_email or pode_enviar_sms
    pode_gerar = bool(request.user.has_perm(PERMISSOES_AVALIACAO["gerar_fila"]))
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
            "pode_enviar_email": pode_enviar_email,
            "pode_enviar_sms": pode_enviar_sms,
            "pode_gerar": pode_gerar,
        },
    )


@login_required
@require_POST
def relatorio_avaliacao_enviar_view(request, avaliacao_id):
    if not _user_tem_algum_canal(request.user):
        return JsonResponse({"success": False, "mensagem": "Sem permissão para enviar avaliação."}, status=403)

    filial_ativa = getattr(request, "filial_ativa", None)
    if not filial_ativa:
        return JsonResponse({"success": False, "mensagem": "Filial ativa não encontrada."}, status=403)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "mensagem": "JSON inválido."}, status=400)

    canal = str(payload.get("canal") or "").strip().lower()
    if canal not in CANAIS_VALIDOS:
        return JsonResponse({"success": False, "mensagem": "Informe canal email ou sms no JSON."}, status=400)

    canais = filtrar_canais_pedidos([canal], canais_permitidos_user(request.user))
    if not canais:
        return JsonResponse({"success": False, "mensagem": "Sem permissão para o canal solicitado."}, status=403)

    qs = AvaliacaoPedido.objects.select_related("pedido", "pedido__filial").filter(
        pedido__filial=filial_ativa
    )
    avaliacao = get_object_or_404(qs, pk=avaliacao_id)

    resultado = enviar_avaliacao_canais(avaliacao=avaliacao, canais=canais, request=request)
    if resultado.get("status_linha") == "enviado":
        label = "E-mail" if canal == CANAL_EMAIL else "SMS"
        return JsonResponse({"success": True, "mensagem": f"{label} enviado com sucesso.", "detalhe": resultado})
    if resultado.get("status_linha") == "ignorado":
        motivo = resultado.get("motivo") or (
            (resultado.get("canais") or [{}])[0].get("motivo") if resultado.get("canais") else "Ignorado."
        )
        return JsonResponse({"success": False, "mensagem": motivo, "detalhe": resultado}, status=400)

    motivo = ""
    for d in resultado.get("canais") or []:
        if d.get("status") == "falha":
            motivo = d.get("motivo") or "Falha no envio."
            break
    return JsonResponse(
        {"success": False, "mensagem": motivo or "Falha no envio.", "detalhe": resultado},
        status=400,
    )


@login_required
@require_POST
def relatorio_avaliacao_enviar_lote_view(request):
    if not _user_tem_algum_canal(request.user):
        return JsonResponse({"success": False, "mensagem": "Sem permissão para enviar avaliação."}, status=403)

    filial_ativa = getattr(request, "filial_ativa", None)
    if not filial_ativa:
        return JsonResponse({"success": False, "mensagem": "Filial ativa não encontrada."}, status=403)

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

    canais_pedidos, err = _parse_canais_lista(payload.get("canais"))
    if err:
        return JsonResponse({"success": False, "mensagem": err}, status=400)

    canais = filtrar_canais_pedidos(canais_pedidos, canais_permitidos_user(request.user))
    if not canais:
        return JsonResponse({"success": False, "mensagem": "Sem permissão para os canais solicitados."}, status=403)

    qs = AvaliacaoPedido.objects.select_related("pedido", "pedido__filial").filter(
        pk__in=ids, pedido__filial=filial_ativa
    )

    registros = list(qs)
    enviados = 0
    falhas = 0
    ignorados = 0
    parciais = 0
    detalhes = []

    for avaliacao in registros:
        resultado = enviar_avaliacao_canais(avaliacao=avaliacao, canais=canais, request=request)
        status_linha = resultado.get("status_linha")
        detalhes.append(
            {
                "id": avaliacao.id,
                "referencia": resultado.get("referencia"),
                "status": status_linha,
                "canais": resultado.get("canais"),
                "motivo": resultado.get("motivo"),
            }
        )
        if status_linha == "enviado":
            enviados += 1
        elif status_linha == "falha":
            falhas += 1
        elif status_linha == "parcial":
            parciais += 1
        else:
            ignorados += 1

    return JsonResponse(
        {
            "success": True,
            "mensagem": (
                f"Processamento concluído: {enviados} enviado(s), {parciais} parcial(is), "
                f"{falhas} falha(s), {ignorados} ignorado(s)."
            ),
            "resumo": {
                "total_selecionados": len(ids),
                "processados": len(registros),
                "enviados": enviados,
                "parciais": parciais,
                "falhas": falhas,
                "ignorados": ignorados,
                "canais": canais,
            },
            "detalhes": detalhes,
        }
    )
