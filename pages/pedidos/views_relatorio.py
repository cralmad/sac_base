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

from pages.pedidos.models import TentativaEntrega, Pedido
from sac_base.permissions_utils import build_action_permissions
from sac_base.sisvar_builders import build_sisvar_payload

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
