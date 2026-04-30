from django.http import JsonResponse

from sac_base.sisvar_builders import build_error_payload


def json_method_not_allowed():
    """Resposta JSON padronizada para método HTTP não permitido (405)."""
    return JsonResponse(build_error_payload("Método não permitido."), status=405)
