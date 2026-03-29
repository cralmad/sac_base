from django.middleware.csrf import get_token

def sisvar_global(request):
    base = {
        "usuario": {
            "autenticado": request.user.is_authenticated,
            "id": request.user.id if request.user.is_authenticated else None,
            "nome": request.user.username if request.user.is_authenticated else None,
        },
        "schema": {},
        "form": {},
        "mensagens": {},
        "others": {'csrf_token_value': get_token(request)},
    }

    # Se a view já tiver colocado algo em request.sisvar_extra, mescla
    if hasattr(request, "sisvar_extra"):
        for key, value in request.sisvar_extra.items():
            # "others" recebe merge profundo para preservar csrf_token_value
            if key == "others" and isinstance(value, dict):
                base["others"] = {**base["others"], **value}
            else:
                base[key] = value

    return {"sisVar": base}