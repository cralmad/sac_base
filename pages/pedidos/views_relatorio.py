from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import F
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods, require_POST
from datetime import datetime
from itertools import groupby

from pages.pedidos.models import TentativaEntrega, Pedido, ESTADOS_SEGUE_PARA_ENTREGA, ESTADO_DEFINITIONS
from sac_base.permissions_utils import build_action_permissions
from sac_base.sisvar_builders import build_sisvar_payload
from sac_base.sms_service import montar_mensagem, enviar_sms_bulkgate, HORARIO_PERIODO as _SMS_HORARIO_PERIODO
from sac_base.smart_filter import apply_smart_number_filter, apply_smart_text_filter

PERMISSOES_RELATORIO = {
    "acessar": "pedidos.view_tentativaentrega",
    "editar": "pedidos.change_tentativaentrega",
    "editar_carro": "pedidos.change_carro_tentativaentrega",
}

@login_required
@permission_required(PERMISSOES_RELATORIO["acessar"], raise_exception=True)
@csrf_protect
@require_http_methods(["GET", "POST"])
def relatorio_conferencia_view(request):
    if request.method == "GET":
        request.sisvar_extra = build_sisvar_payload(
            permissions={"relatorio": build_action_permissions(request.user, PERMISSOES_RELATORIO)}
        )
        return render(request, "relatorio_conferencia.html")

    # POST: busca paginada para scroll infinito
    data = request.sisvar_front or {}
    filtros = data.get("filtros", {})
    data_tentativa = filtros.get("data_tentativa")

    referencia = filtros.get("referencia", "").strip()
    tipo = filtros.get("tipo", "").strip()
    conferido = filtros.get("conferido", "").strip().lower()
    pagina = int(data.get("pagina", 1))
    page_size = int(data.get("page_size", 30))

    if not data_tentativa:
        return JsonResponse({"success": False, "mensagem": "A data de entrega é obrigatória."}, status=400)

    qs = TentativaEntrega.objects.select_related("pedido", "motorista")
    try:
        dt = datetime.strptime(data_tentativa, "%Y-%m-%d").date()
        qs = qs.filter(data_tentativa=dt)
    except ValueError:
        return JsonResponse({"success": False, "mensagem": "Data inválida."}, status=400)
    if referencia:
        qs = qs.filter(pedido__pedido__icontains=referencia)
    if tipo:
        qs = qs.filter(pedido__tipo=tipo)
    if conferido == "sim":
        qs = qs.filter(pedido__volume_conf=F("pedido__volume"))
    elif conferido == "nao":
        qs = qs.exclude(pedido__volume_conf=F("pedido__volume"))
    qs = qs.order_by("pedido__codpost_dest", "-data_tentativa", "-id")

    paginator = Paginator(qs, page_size)
    page = paginator.get_page(pagina)
    registros = []
    for mov in page.object_list:
        pedido = mov.pedido
        registros.append({
            "id": mov.id,
            "pedido_id": pedido.id,
            "data_tentativa": mov.data_tentativa.isoformat(),
            "referencia": pedido.pedido or pedido.id_vonzu,
            "codpost_dest": pedido.codpost_dest or "",
            "cidade_dest": pedido.cidade_dest or "",
            "obs": pedido.obs or "",
            "volume": pedido.volume,
            "peso": str(pedido.peso) if pedido.peso is not None else "",
            "carro": mov.carro,
            "obs_rota": pedido.obs_rota or "",
            "volume_conf": pedido.volume_conf,
            "periodo": mov.periodo or "",
            "updated_at": mov.updated_at.isoformat(),
        })
    return JsonResponse({
        "success": True,
        "registros": registros,
        "has_next": page.has_next(),
        "pagina": pagina,
    })


# ─── Relatório de impressão ───────────────────────────────────────────────────

def _build_qs_relatorio(filtros):
    """Constrói e retorna o queryset com os filtros do relatório."""
    data_tentativa = filtros.get("data_tentativa")
    referencia = filtros.get("referencia", "").strip()
    tipo = filtros.get("tipo", "").strip()
    conferido = filtros.get("conferido", "").strip().lower()

    if not data_tentativa:
        return None, "A data de entrega é obrigatória."

    qs = TentativaEntrega.objects.select_related("pedido")
    try:
        dt = datetime.strptime(data_tentativa, "%Y-%m-%d").date()
        qs = qs.filter(data_tentativa=dt)
    except ValueError:
        return None, "Data inválida."

    if referencia:
        qs = qs.filter(pedido__pedido__icontains=referencia)
    if tipo:
        qs = qs.filter(pedido__tipo=tipo)
    if conferido == "sim":
        qs = qs.filter(pedido__volume_conf=F("pedido__volume"))
    elif conferido == "nao":
        qs = qs.exclude(pedido__volume_conf=F("pedido__volume"))

    # Ordem para agrupamento: carro → codpost_dest
    qs = qs.order_by("carro", "pedido__codpost_dest", "pedido__pedido")
    return qs, None


@require_POST
@csrf_protect
@login_required
@permission_required(PERMISSOES_RELATORIO["acessar"], raise_exception=True)
def relatorio_conferencia_imprimir_view(request):
    data = request.sisvar_front or {}
    filtros = data.get("filtros", {})

    qs, erro = _build_qs_relatorio(filtros)
    if erro:
        return JsonResponse({"success": False, "mensagem": erro}, status=400)

    # Monta grupos
    grupos = []
    for carro_val, items in groupby(qs, key=lambda m: m.carro):
        linhas = []
        data_tent = None
        for mov in items:
            pedido = mov.pedido
            if data_tent is None:
                data_tent = mov.data_tentativa.strftime("%d/%m/%Y")
            vol = pedido.volume
            vol_conf = pedido.volume_conf
            if vol is not None and vol == vol_conf:
                conferido = "SIM"
            else:
                conferido = f"NÃO ({vol_conf})"
            linhas.append({
                "pedido": pedido.pedido or str(pedido.id_vonzu),
                "tipo": pedido.tipo or "",
                "codpost_dest": pedido.codpost_dest or "",
                "cidade_dest": pedido.cidade_dest or "",
                "volume": str(vol) if vol is not None else "",
                "peso": str(pedido.peso) if pedido.peso is not None else "",
                "obs_rota": pedido.obs_rota or "",
                "conferido": conferido,
            })
        grupos.append({
            "carro": str(carro_val) if carro_val is not None else "—",
            "data_tentativa": data_tent or "",
            "linhas": linhas,
        })

    return JsonResponse({"success": True, "grupos": grupos, "filtros": filtros})


# ─── Relatório de Rotas por Carro ─────────────────────────────────────────────

PERMISSOES_ROTAS = {
    "acessar": "pedidos.view_tentativaentrega",
}

@login_required
@permission_required(PERMISSOES_ROTAS["acessar"], raise_exception=True)
@csrf_protect
@require_http_methods(["GET", "POST"])
def relatorio_rotas_view(request):
    if request.method == "GET":
        request.sisvar_extra = build_sisvar_payload(
            permissions={"rotas": build_action_permissions(request.user, PERMISSOES_ROTAS)}
        )
        return render(request, "relatorio_rotas.html")

    # POST: retorna grupos por carro
    data = request.sisvar_front or {}
    filtros = data.get("filtros", {})
    data_tentativa = filtros.get("data_tentativa", "").strip()
    carro_filtro = filtros.get("carro", "").strip()

    if not data_tentativa:
        return JsonResponse({"success": False, "mensagem": "A data é obrigatória."}, status=400)

    try:
        dt = datetime.strptime(data_tentativa, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"success": False, "mensagem": "Data inválida."}, status=400)

    qs = (
        TentativaEntrega.objects
        .select_related("pedido")
        .filter(data_tentativa=dt)
    )
    if carro_filtro:
        try:
            qs = qs.filter(carro=int(carro_filtro))
        except ValueError:
            pass

    qs = qs.order_by("carro", "pedido__codpost_dest", "pedido__pedido")

    grupos = []
    for carro_val, items in groupby(qs, key=lambda m: m.carro):
        linhas = []
        data_str = None
        for mov in items:
            p = mov.pedido
            if data_str is None:
                data_str = mov.data_tentativa.strftime("%d/%m/%Y")
            tipo_abrev = "R" if (p.tipo or "").upper() == "RECOLHA" else "E"
            fones = " / ".join(f for f in [p.fone_dest or "", p.fone_dest2 or ""] if f)
            peso_str = ""
            if p.peso is not None:
                try:
                    peso_str = str(int(p.peso))
                except Exception:
                    peso_str = str(p.peso)
            linhas.append({
                "pedido": p.pedido or str(p.id_vonzu),
                "tipo": tipo_abrev,
                "nome_dest": p.nome_dest or "",
                "fones": fones,
                "endereco_dest": p.endereco_dest or "",
                "cidade_dest": p.cidade_dest or "",
                "codpost_dest": p.codpost_dest or "",
                "volumes": f"{p.volume_conf or 0}/{p.volume or 0}",
                "peso": peso_str,
                "periodo": mov.periodo or "",
                "obs_rota": p.obs_rota or "",
                "segue_para_entrega": p.estado in ESTADOS_SEGUE_PARA_ENTREGA,
            })
        grupos.append({
            "carro": str(carro_val) if carro_val is not None else "—",
            "data_tentativa": data_str or dt.strftime("%d/%m/%Y"),
            "total": len(linhas),
            "linhas": linhas,
        })

    return JsonResponse({
        "success": True,
        "grupos": grupos,
        "data_fmt": dt.strftime("%d/%m/%Y"),
    })


# ─── Relatório de Envio de SMS ────────────────────────────────────────────────

PERMISSOES_SMS = {
    "acessar": "pedidos.view_tentativaentrega",
    "enviar": "pedidos.send_sms_tentativaentrega",
}


@login_required
@permission_required(PERMISSOES_SMS["acessar"], raise_exception=True)
@csrf_protect
@require_http_methods(["GET", "POST"])
def relatorio_sms_view(request):
    if request.method == "GET":
        request.sisvar_extra = build_sisvar_payload(
            permissions={"sms": build_action_permissions(request.user, PERMISSOES_SMS)}
        )
        return render(request, "relatorio_sms.html")

    # POST: busca tentativas de entrega por data
    data = request.sisvar_front or {}
    filtros = data.get("filtros", {})
    data_tentativa = filtros.get("data_tentativa", "").strip()

    if not data_tentativa:
        return JsonResponse({"success": False, "mensagem": "A data é obrigatória."}, status=400)

    try:
        dt = datetime.strptime(data_tentativa, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"success": False, "mensagem": "Data inválida."}, status=400)

    qs = (
        TentativaEntrega.objects
        .select_related("pedido")
        .filter(data_tentativa=dt)
        .order_by("pedido__codpost_dest", "pedido__pedido")
    )

    registros = []
    for mov in qs:
        pedido = mov.pedido
        fones = [f for f in [pedido.fone_dest or "", pedido.fone_dest2 or ""] if f]
        registros.append({
            "id": mov.id,
            "sms_enviado": mov.sms_enviado,
            "referencia": pedido.pedido or str(pedido.id_vonzu),
            "tipo": pedido.tipo or "",
            "fones": fones,
            "codpost_dest": pedido.codpost_dest or "",
            "volume": pedido.volume,
            "peso": str(pedido.peso) if pedido.peso is not None else "",
            "periodo": mov.periodo or "",
        })

    return JsonResponse({"success": True, "registros": registros, "data_fmt": dt.strftime("%d/%m/%Y")})


@login_required
@permission_required(PERMISSOES_SMS["enviar"], raise_exception=True)
@csrf_protect
@require_POST
def relatorio_sms_enviar_view(request):
    data = request.sisvar_front or {}
    ids = data.get("ids", [])
    data_tentativa = data.get("data_tentativa", "").strip()

    if not ids:
        return JsonResponse({"success": False, "mensagem": "Nenhum registro selecionado."}, status=400)

    if not data_tentativa:
        return JsonResponse({"success": False, "mensagem": "Data não informada."}, status=400)

    try:
        dt = datetime.strptime(data_tentativa, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"success": False, "mensagem": "Data inválida."}, status=400)

    qs = (
        TentativaEntrega.objects
        .select_related(
            "pedido",
            "pedido__filial",
            "pedido__filial__config",
            "pedido__filial__pais_atuacao",
        )
        .filter(id__in=ids, sms_enviado=False)
        .exclude(periodo__isnull=True)
        .exclude(periodo="")
    )

    # Carrega configuração da filial a partir do primeiro registro
    tentativas = list(qs)
    if not tentativas:
        return JsonResponse({"success": False, "mensagem": "Nenhum registro elegível encontrado."}, status=400)

    filial = tentativas[0].pedido.filial
    try:
        template_msg = filial.config.sms_padrao_1 or ""
    except Exception:
        template_msg = ""

    if not template_msg:
        return JsonResponse(
            {"success": False, "mensagem": "Mensagem padrão (sms_padrao_1) não configurada para esta filial."},
            status=400,
        )

    sigla_pais = ""
    ddi_padrao = "351"  # fallback: Portugal
    if filial.pais_atuacao:
        sigla_pais = filial.pais_atuacao.sigla or ""
        # codigo_tel armazenado como "+351", "+55", etc.
        codigo_tel = (filial.pais_atuacao.codigo_tel or "").strip().lstrip("+")
        if codigo_tel:
            ddi_padrao = codigo_tel

    enviados = 0
    erros = 0
    ids_enviados = []
    erros_detalhe: list[str] = []
    contagem_periodo: dict[str, int] = {}

    for mov in tentativas:
        pedido = mov.pedido
        referencia = pedido.pedido or str(pedido.id_vonzu)
        fones = [f.strip() for f in [pedido.fone_dest or "", pedido.fone_dest2 or ""] if f.strip()]
        if not fones:
            erros += 1
            erros_detalhe.append(f"{referencia}: sem número de telefone.")
            continue

        try:
            mensagem = montar_mensagem(template_msg, dt, mov.periodo, sigla_pais)
        except Exception as exc:
            erros += 1
            erros_detalhe.append(f"{referencia}: erro na montagem da mensagem — {exc}")
            continue

        sucesso_algum = False
        for fone in fones:
            resultado = enviar_sms_bulkgate(fone, mensagem, ddi_padrao)
            if resultado.get("sucesso"):
                sucesso_algum = True
            else:
                erros += 1
                erros_detalhe.append(f"{referencia} ({fone}): {resultado.get('erro', 'Erro desconhecido.')}")

        if sucesso_algum:
            mov.sms_enviado = True
            mov.save(update_fields=["sms_enviado"])
            enviados += 1
            ids_enviados.append(mov.id)
            contagem_periodo[mov.periodo] = contagem_periodo.get(mov.periodo, 0) + 1

    # Resumo para a filial (sms_confirm)
    if filial.sms_confirm and filial.numero and enviados > 0:
        partes_resumo = [f"SMS enviados em {dt.strftime('%d/%m/%Y')}:"]
        for periodo, qtd in sorted(contagem_periodo.items()):
            horario = _SMS_HORARIO_PERIODO.get(periodo, periodo)
            partes_resumo.append(f"  {periodo} ({horario}): {qtd}")
        partes_resumo.append(f"Total: {enviados}")
        resumo = "\n".join(partes_resumo)
        enviar_sms_bulkgate(filial.numero, resumo, ddi_padrao)

    return JsonResponse({
        "success": True,
        "enviados": enviados,
        "erros": erros,
        "erros_detalhe": erros_detalhe,
        "ids_enviados": ids_enviados,
        "mensagem": f"{enviados} SMS enviado(s) com sucesso." + (f" {erros} erro(s)." if erros else ""),
    })


@login_required
@permission_required(PERMISSOES_SMS["acessar"], raise_exception=True)
@csrf_protect
@require_POST
def relatorio_sms_preview_view(request):
    """Retorna um preview das mensagens MANHÃ/TARDE para a data informada."""
    data = request.sisvar_front or {}
    data_tentativa = data.get("data_tentativa", "").strip()

    if not data_tentativa:
        return JsonResponse({"success": False, "mensagem": "Data não informada."}, status=400)

    try:
        dt = datetime.strptime(data_tentativa, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"success": False, "mensagem": "Data inválida."}, status=400)

    filial = getattr(request, "filial_ativa", None)

    if not filial:
        return JsonResponse({"success": False, "mensagem": "Nenhuma filial ativa na sessão."}, status=400)

    template_msg = ""
    sigla_pais = ""
    try:
        template_msg = filial.config.sms_padrao_1 or ""
        if filial.pais_atuacao:
            sigla_pais = filial.pais_atuacao.sigla or ""
    except Exception:
        pass

    if not template_msg:
        return JsonResponse({"success": False, "mensagem": "Mensagem padrão (sms_padrao_1) não configurada para a filial ativa."}, status=400)

    previews = {}
    for periodo in ("MANHA", "TARDE"):
        try:
            previews[periodo] = montar_mensagem(template_msg, dt, periodo, sigla_pais)
        except Exception as exc:
            previews[periodo] = f"[Erro: {exc}]"

    return JsonResponse({"success": True, "previews": previews})


# ─── Relatório Gerencial de Pedidos ──────────────────────────────────────────

PERMISSOES_GERENCIAL = {
    "acessar": "pedidos.view_relatorio_gerencial",
}


@login_required
@permission_required(PERMISSOES_GERENCIAL["acessar"], raise_exception=True)
@csrf_protect
@require_http_methods(["GET", "POST"])
def relatorio_gerencial_view(request):
    if request.method == "GET":
        estados_choices = [
            {"value": v, "label": l}
            for v, l, *_ in ESTADO_DEFINITIONS
        ]
        request.sisvar_extra = build_sisvar_payload(
            permissions={"gerencial": build_action_permissions(request.user, PERMISSOES_GERENCIAL)},
            options={"estados": estados_choices},
        )
        return render(request, "relatorio_gerencial.html")

    # POST: aplica smart filters e agrupa por carro
    data = request.sisvar_front or {}
    filtros = data.get("filtros", {})

    data_inicial   = filtros.get("data_inicial", "").strip()
    data_final     = filtros.get("data_final", "").strip()
    id_vonzu_str   = filtros.get("id_vonzu", "").strip()
    referencia_str = filtros.get("referencia", "").strip()
    estados_lista  = filtros.get("estados", [])
    if not isinstance(estados_lista, list):
        estados_lista = []

    if not data_inicial:
        return JsonResponse({"success": False, "mensagem": "A data inicial é obrigatória."}, status=400)
    if not data_final:
        return JsonResponse({"success": False, "mensagem": "A data final é obrigatória."}, status=400)

    try:
        dt_ini = datetime.strptime(data_inicial, "%Y-%m-%d").date()
        dt_fim = datetime.strptime(data_final, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"success": False, "mensagem": "Data inválida."}, status=400)

    if dt_ini > dt_fim:
        return JsonResponse({"success": False, "mensagem": "A data inicial não pode ser maior que a data final."}, status=400)

    if (dt_fim - dt_ini).days > 90:
        return JsonResponse({"success": False, "mensagem": "O período máximo é de 90 dias."}, status=400)

    qs = (
        TentativaEntrega.objects
        .select_related("pedido")
        .filter(data_tentativa__range=(dt_ini, dt_fim))
    )

    qs = apply_smart_number_filter(qs, "pedido__id_vonzu", id_vonzu_str)
    qs = apply_smart_text_filter(qs, "pedido__pedido", referencia_str)

    if estados_lista:
        qs = qs.filter(pedido__estado__in=estados_lista)

    qs = qs.order_by("carro", "data_tentativa", "pedido__codpost_dest", "pedido__pedido")

    grupos = []
    for carro_val, items in groupby(qs, key=lambda m: m.carro):
        linhas = []
        for mov in items:
            p = mov.pedido
            tipo_abrev = "R" if (p.tipo or "").upper() == "RECOLHA" else "E"
            fones = " / ".join(f for f in [p.fone_dest or "", p.fone_dest2 or ""] if f)
            peso_str = ""
            if p.peso is not None:
                try:
                    peso_str = str(int(p.peso))
                except Exception:
                    peso_str = str(p.peso)
            linhas.append({
                "pedido":         p.pedido or str(p.id_vonzu),
                "id_vonzu":       p.id_vonzu,
                "tipo":           tipo_abrev,
                "data_tentativa": mov.data_tentativa.strftime("%d/%m/%Y"),
                "nome_dest":      p.nome_dest or "",
                "fones":          fones,
                "endereco_dest":  p.endereco_dest or "",
                "cidade_dest":    p.cidade_dest or "",
                "codpost_dest":   p.codpost_dest or "",
                "volumes":        f"{p.volume_conf or 0}/{p.volume or 0}",
                "peso":           peso_str,
                "periodo":        mov.periodo or "",
                "estado":         p.estado or "",
                "obs_rota":       p.obs_rota or "",
                "segue_para_entrega": p.estado in ESTADOS_SEGUE_PARA_ENTREGA,
            })
        grupos.append({
            "carro": str(carro_val) if carro_val is not None else "—",
            "total": len(linhas),
            "linhas": linhas,
        })

    data_fmt = dt_ini.strftime("%d/%m/%Y")
    if dt_ini != dt_fim:
        data_fmt = f"{dt_ini.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')}"

    return JsonResponse({
        "success": True,
        "grupos": grupos,
        "data_fmt": data_fmt,
        "total_pedidos": sum(g["total"] for g in grupos),
    })
