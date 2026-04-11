from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render

from sac_base.sisvar_builders import build_error_payload, build_form_state, build_sisvar_payload, build_success_payload

from .services import (
    ACTIVE_FILIAL_COOKIE,
    FILIAL_NO_ACCESS_PATH,
    listar_filiais_permitidas,
    obter_filial_unica_se_existir,
    serializar_filial,
    validar_filial_ativa,
)


@login_required
def selecionar_filial_view(request):
    if getattr(request, "filial_ativa", None) is not None:
        return redirect("/app/home/")

    filiais = listar_filiais_permitidas(request.user)

    if not filiais:
        return redirect(FILIAL_NO_ACCESS_PATH)

    filial_unica = obter_filial_unica_se_existir(request.user)
    if filial_unica:
        response = redirect("/app/home/")
        response.set_cookie(ACTIVE_FILIAL_COOKIE, str(filial_unica.id), httponly=True, samesite="Lax")
        return response

    if request.method == "GET":
        request.sisvar_extra = build_sisvar_payload(
            forms={
                "selecionarFilialForm": build_form_state(
                    estado="novo",
                    campos={"filial_id": None},
                )
            },
            datasets={
                "availableFiliais": [serializar_filial(filial) for filial in filiais],
            },
        )
        return render(request, "filial_selecionar.html")

    return JsonResponse(build_error_payload("Método não permitido."), status=405)


@login_required
def ativar_filial_view(request):
    if getattr(request, "filial_ativa", None) is not None:
        return JsonResponse(build_error_payload("Já existe uma matriz/filial ativa para a sessão atual."), status=409)

    if request.method != "POST":
        return JsonResponse(build_error_payload("Método não permitido."), status=405)

    filial_id = request.sisvar_front.get("form", {}).get("selecionarFilialForm", {}).get("campos", {}).get("filial_id")
    filial = validar_filial_ativa(request.user, filial_id)

    if not filial:
        return JsonResponse(build_error_payload("Matriz/filial inválida para o usuário autenticado."), status=403)

    response = JsonResponse(build_success_payload(extra_payload={"redirect": "/app/home/"}))
    response.set_cookie(ACTIVE_FILIAL_COOKIE, str(filial.id), httponly=True, samesite="Lax")
    return response


@login_required
def sem_acesso_filial_view(request):
    if getattr(request, "filial_ativa", None) is not None:
        return redirect("/app/home/")

    filiais = listar_filiais_permitidas(request.user)
    if filiais:
        filial_unica = obter_filial_unica_se_existir(request.user)
        if filial_unica:
            response = redirect("/app/home/")
            response.set_cookie(ACTIVE_FILIAL_COOKIE, str(filial_unica.id), httponly=True, samesite="Lax")
            return response

        return redirect("/app/usuario/filial/selecionar/")

    return render(request, "filial_sem_acesso.html")
