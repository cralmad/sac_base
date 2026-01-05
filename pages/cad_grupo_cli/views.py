import json
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .models import GrupoCli

def CadGrupoCli(request):
    return render(request, 'cadgrupocli.html')


@require_http_methods(["POST"])
def salvar_grupo_cliente(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))

        sisVar = payload.get("sisVar")
        if not sisVar:
            return JsonResponse(
                {"success": False, "error": "sisVar não enviado"},
                status=400
            )

        form = sisVar.get("form", {}).get("cadForm")
        if not form:
            return JsonResponse(
                {"success": False, "error": "Formulário cadForm não encontrado em sisVar"},
                status=400
            )

        descricao = form.get("descricao")

        if not descricao:
            return JsonResponse(
                {"success": False, "error": "Descrição é obrigatória"},
                status=400
            )

        grupo = GrupoCli.objects.create(
            descricao=descricao
        )

        return JsonResponse({
            "success": True,
            "id": grupo.id,
            "descricao": grupo.descricao
        })

    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "error": "JSON inválido"},
            status=400
        )

    except Exception as e:
        return JsonResponse(
            {"success": False, "error": str(e)},
            status=500
        )
