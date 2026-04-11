def build_form_state(*, estado="novo", campos=None, update=None):
    return {
        "estado": estado,
        "update": update,
        "campos": campos or {},
    }


def build_meta(*, permissions=None, options=None, datasets=None, security=None):
    return {
        "security": security or {},
        "permissions": permissions or {},
        "options": options or {},
        "datasets": datasets or {},
    }


def build_legacy_others(meta=None):
    meta = meta or build_meta()
    return {
        "csrf_token_value": meta.get("security", {}).get("csrfTokenValue", ""),
        "permissoes": meta.get("permissions", {}),
        "opcoes": meta.get("options", {}),
        **meta.get("datasets", {}),
    }


def build_sisvar_payload(*, schema=None, forms=None, mensagens=None, usuario=None, permissions=None, options=None, datasets=None, meta=None):
    payload = {}

    if schema is not None:
        payload["schema"] = schema

    if forms is not None:
        payload["form"] = forms

    if mensagens is not None:
        payload["mensagens"] = mensagens

    if usuario is not None:
        payload["usuario"] = usuario

    final_meta = meta or build_meta(
        permissions=permissions,
        options=options,
        datasets=datasets,
    )

    payload["meta"] = final_meta
    payload["others"] = build_legacy_others(final_meta)

    return payload


def build_message_entry(conteudo=None, *, ignorar=True):
    if conteudo is None:
        return {"conteudo": [], "ignorar": ignorar}

    mensagens = conteudo if isinstance(conteudo, list) else [conteudo]
    return {
        "conteudo": mensagens,
        "ignorar": ignorar,
    }


def build_messages(*, sucesso=None, erro=None, aviso=None, info=None):
    mensagens = {}

    if sucesso is not None:
        mensagens["sucesso"] = build_message_entry(sucesso, ignorar=True)

    if erro is not None:
        mensagens["erro"] = build_message_entry(erro, ignorar=False)

    if aviso is not None:
        mensagens["aviso"] = build_message_entry(aviso, ignorar=True)

    if info is not None:
        mensagens["info"] = build_message_entry(info, ignorar=True)

    return mensagens


def build_form_response(*, form_id, estado, campos, update=None, mensagem_sucesso=None, extra_payload=None):
    payload = {
        "success": True,
        "form": {
            form_id: build_form_state(estado=estado, campos=campos, update=update),
        },
        "mensagens": build_messages(sucesso=mensagem_sucesso) if mensagem_sucesso else {},
    }

    if extra_payload:
        payload.update(extra_payload)

    return payload


def build_forms_response(*, forms, mensagem_sucesso=None, extra_payload=None, success=True):
    payload = {
        "success": success,
        "form": forms,
        "mensagens": build_messages(sucesso=mensagem_sucesso) if mensagem_sucesso else {},
    }

    if extra_payload:
        payload.update(extra_payload)

    return payload


def build_records_response(registros, *, mensagens=None, success=True, extra_payload=None):
    payload = {
        "success": success,
        "registros": registros,
        "mensagens": mensagens or {},
    }

    if extra_payload:
        payload.update(extra_payload)

    return payload


def build_success_payload(mensagem=None, *, extra_payload=None, success=True):
    payload = {
        "success": success,
        "mensagens": build_messages(sucesso=mensagem) if mensagem else {},
    }

    if extra_payload:
        payload.update(extra_payload)

    return payload


def build_error_payload(mensagem, *, success=False):
    return {
        "success": success,
        "mensagens": build_messages(erro=mensagem),
    }


def build_sisvar_response(*, success=True, schema=None, forms=None, mensagens=None, usuario=None, permissions=None, options=None, datasets=None, meta=None, extra_payload=None):
    payload = {
        "success": success,
        **build_sisvar_payload(
            schema=schema,
            forms=forms,
            mensagens=mensagens,
            usuario=usuario,
            permissions=permissions,
            options=options,
            datasets=datasets,
            meta=meta,
        ),
    }

    if extra_payload:
        payload.update(extra_payload)

    return payload