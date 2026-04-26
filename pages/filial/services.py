from pages.filial.models import Filial, UsuarioFilial


ACTIVE_FILIAL_COOKIE = "active_filial_id"


def get_filiais_escrita_queryset(usuario):
    """Retorna QuerySet de filiais ativas com vínculo de escrita para o usuário."""
    queryset = Filial.objects.filter(ativa=True, pais_atuacao__isnull=False).select_related("pais_atuacao")
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return queryset.none()
    if getattr(usuario, "is_superuser", False):
        return queryset
    return queryset.filter(
        usuarios_vinculados__usuario=usuario,
        usuarios_vinculados__ativo=True,
        usuarios_vinculados__pode_escrever=True,
    ).distinct()


def obter_filial_escrita(filial_id, usuario):
    """Retorna a filial se o usuário tiver vínculo de escrita, ou None."""
    try:
        filial_id = int(filial_id)
    except (TypeError, ValueError):
        return None
    return get_filiais_escrita_queryset(usuario).filter(id=filial_id).first()
FILIAL_SELECT_PATH = "/app/usuario/filial/selecionar/"
FILIAL_ACTIVATE_PATH = "/app/usuario/filial/ativar/"
FILIAL_NO_ACCESS_PATH = "/app/usuario/filial/sem-acesso/"


def serializar_filial(filial):
    return {
        "id": filial.id,
        "codigo": filial.codigo,
        "nome": filial.nome,
        "isMatriz": filial.is_matriz,
    }


def listar_filiais_permitidas(usuario):
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return []

    queryset = Filial.objects.filter(ativa=True).order_by("nome")
    if getattr(usuario, "is_superuser", False):
        return list(queryset)

    return list(
        queryset.filter(
            usuarios_vinculados__usuario=usuario,
            usuarios_vinculados__ativo=True,
        ).distinct()
    )


def obter_filial_por_id(filial_id):
    return Filial.objects.filter(id=filial_id, ativa=True).first()


def validar_filial_ativa(usuario, filial_id):
    if not filial_id:
        return None

    try:
        filial_id = int(filial_id)
    except (TypeError, ValueError):
        return None

    if getattr(usuario, "is_superuser", False):
        return obter_filial_por_id(filial_id)

    return Filial.objects.filter(
        id=filial_id,
        ativa=True,
        usuarios_vinculados__usuario=usuario,
        usuarios_vinculados__ativo=True,
    ).first()


def obter_nivel_acesso(usuario, filial):
    if not usuario or not getattr(usuario, "is_authenticated", False) or not filial:
        return {"consultar": False, "escrever": False}

    if getattr(usuario, "is_superuser", False):
        return {"consultar": True, "escrever": True}

    vinculo = UsuarioFilial.objects.filter(
        usuario=usuario,
        filial=filial,
        ativo=True,
    ).first()

    if not vinculo:
        return {"consultar": False, "escrever": False}

    return {
        "consultar": bool(vinculo.pode_consultar or vinculo.pode_escrever),
        "escrever": bool(vinculo.pode_escrever),
    }


def obter_filial_unica_se_existir(usuario):
    filiais = listar_filiais_permitidas(usuario)
    return filiais[0] if len(filiais) == 1 else None
