from django.http import JsonResponse

from sac_base.sisvar_builders import build_error_payload


def build_action_permissions(usuario, permissions_map):
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return {acao: False for acao in permissions_map}

    return {
        acao: usuario.has_perm(codename)
        for acao, codename in permissions_map.items()
    }


def permission_denied_response(mensagem, status=403):
    return JsonResponse(build_error_payload(mensagem), status=status)


def extract_validation_messages(exc):
    if hasattr(exc, "message_dict"):
        return [
            f"{campo} - {mensagem}"
            for campo, mensagens in exc.message_dict.items()
            for mensagem in mensagens
        ]

    if hasattr(exc, "messages"):
        return list(exc.messages)

    return [str(exc)]