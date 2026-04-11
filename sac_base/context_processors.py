from django.middleware.csrf import get_token
from sac_base.sisvar_builders import build_legacy_others, build_meta


def _merge_dict(base, extra):
    merged = dict(base)
    for key, value in (extra or {}).items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _meta_from_others(others):
    others = others or {}
    return build_meta(
        security={"csrfTokenValue": others.get("csrf_token_value", "")},
        permissions=others.get("permissoes", {}) if isinstance(others.get("permissoes"), dict) else {},
        options=others.get("opcoes", {}) if isinstance(others.get("opcoes"), dict) else {},
        datasets={
            key: value
            for key, value in others.items()
            if key not in {"csrf_token_value", "permissoes", "opcoes"}
        },
    )


def _others_from_meta(meta):
    return build_legacy_others(meta or build_meta())

def sisvar_global(request):
    permissoes_usuario = []
    if request.user.is_authenticated:
        permissoes_usuario = list(request.user.get_all_permissions())

    filial_ativa = getattr(request, "filial_ativa", None)
    filial_payload = None
    if filial_ativa is not None:
        filial_payload = {
            "id": filial_ativa.id,
            "codigo": filial_ativa.codigo,
            "nome": filial_ativa.nome,
            "isMatriz": filial_ativa.is_matriz,
        }

    csrf_token_value = get_token(request)

    base = {
        "usuario": {
            "autenticado": request.user.is_authenticated,
            "id": request.user.id if request.user.is_authenticated else None,
            "nome": request.user.username if request.user.is_authenticated else None,
            "permissoes": permissoes_usuario,
            "superusuario": request.user.is_superuser if request.user.is_authenticated else False,
        },
        "schema": {},
        "form": {},
        "mensagens": {},
        "meta": {
            "security": {
                "csrfTokenValue": csrf_token_value,
                "activeFilial": filial_payload,
            },
            "permissions": {},
            "options": {},
            "datasets": {},
        },
        "others": {'csrf_token_value': csrf_token_value},
    }

    # Se a view já tiver colocado algo em request.sisvar_extra, mescla
    if hasattr(request, "sisvar_extra"):
        for key, value in request.sisvar_extra.items():
            # "others" recebe merge profundo para preservar csrf_token_value
            if key == "others" and isinstance(value, dict):
                base["others"] = {**base["others"], **value}
            elif key == "meta" and isinstance(value, dict):
                base["meta"] = _merge_dict(base["meta"], value)
            else:
                base[key] = value

    base["meta"] = _merge_dict(_meta_from_others(base.get("others", {})), base.get("meta", {}))
    base["others"] = _others_from_meta(base["meta"])

    return {"sisVar": base}