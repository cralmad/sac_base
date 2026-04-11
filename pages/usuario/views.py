import json
from django.http import JsonResponse
from django.contrib.auth.decorators import permission_required
from django.contrib.auth import authenticate, get_user_model, update_session_auth_hash
from django.shortcuts import render, redirect
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.hashers import make_password
from pages.auditoria.models import AuditEvent
from pages.auditoria.utils import diff_snapshots, registrar_auditoria, snapshot_instance
from pages.filial.services import ACTIVE_FILIAL_COOKIE, FILIAL_NO_ACCESS_PATH, FILIAL_SELECT_PATH, listar_filiais_permitidas
from pages.usuario.models import Usuarios
from sac_base.form_validador import SchemaValidator
from sac_base.sisvar_builders import build_error_payload, build_form_response, build_form_state, build_records_response, build_sisvar_payload

User = get_user_model()


PERMISSOES_USUARIO = {
    "acessar": "usuario.view_usuarios",
    "consultar": "usuario.view_usuarios",
    "incluir": "usuario.add_usuarios",
    "editar": "usuario.change_usuarios",
    "excluir": "usuario.delete_usuarios",
}


def obter_acoes_permitidas_usuario(usuario):
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return {acao: False for acao in PERMISSOES_USUARIO}

    return {
        acao: usuario.has_perm(codename)
        for acao, codename in PERMISSOES_USUARIO.items()
    }


def resposta_sem_permissao(mensagem, status=403):
    return JsonResponse(build_error_payload(mensagem), status=status)

def login_view(request):
    
    request.sisvar_extra = build_sisvar_payload()

    schema = { "loginForm": {
        'username': {'type': 'string', 'maxlength': 50, 'required': True},
        'password': {'type': 'password', 'required': True}
        }
    }

    formulario = {"loginForm": {"estado": "novo", "update": None, "campos": {}}}
    
    # ---------- GET ----------
    if request.method == "GET":

        # Usuário já autenticado: redireciona para home
        if request.user.is_authenticated:
            return redirect("/app/home/")

        request.sisvar_extra |= build_sisvar_payload(schema=schema, forms=formulario)
        return render(request, "login.html")

    # ---------- POST ----------
    try:
        payload = request.sisvar_front
        form = payload["form"]["loginForm"].get("campos")
        username = form.get("username")
        password = form.get("password")
    except (KeyError, json.JSONDecodeError):
        return JsonResponse(build_error_payload("Payload inválido"), status=400)

    user = authenticate(username=username, password=password)
    if not user:
        return JsonResponse(build_error_payload("Credenciais inválidas"), status=401)

    refresh = RefreshToken.for_user(user)

    filiais_permitidas = listar_filiais_permitidas(user)
    if not filiais_permitidas:
        redirect_path = FILIAL_NO_ACCESS_PATH
        filial_automatica = None
    elif len(filiais_permitidas) == 1:
        redirect_path = "/app/home/"
        filial_automatica = filiais_permitidas[0]
    else:
        redirect_path = FILIAL_SELECT_PATH
        filial_automatica = None

    response = JsonResponse({
        "success": True,
        "redirect": redirect_path,
        "user": {
            "id": user.id,
            "username": user.username
        }
    })

    response.set_cookie(
        "access_token",
        str(refresh.access_token),
        httponly=True,
        samesite="Lax"
    )
    response.set_cookie(
        "refresh_token",
        str(refresh),
        httponly=True,
        samesite="Lax",
        max_age=60 * 60 * 24 * 7
    )

    if filial_automatica is not None:
        response.set_cookie(
            ACTIVE_FILIAL_COOKIE,
            str(filial_automatica.id),
            httponly=True,
            samesite="Lax"
        )

    return response

def logout_view(request):
    response = redirect("/app/usuario/login/")
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    response.delete_cookie(ACTIVE_FILIAL_COOKIE)
    return response


@permission_required(PERMISSOES_USUARIO["acessar"], raise_exception=True)
def cadastro_view(request):
    template = "usuario.html"
    nomeForm = "cadUsuario"
    nomeFormCons = "consUsuario"
    acoes_permitidas = obter_acoes_permitidas_usuario(getattr(request, "user", None))

    schema = {
        nomeForm: {
            "username":    {'type': 'string',  'maxlength': 20, 'minlength': 3, 'required': True,  'value': ''},
            "first_name":  {'type': 'string',  'maxlength': 30, 'minlength': 3, 'required': True,  'value': ''},
            "email":       {'type': 'string',  'maxlength': 60, 'required': True,  'value': ''},
            "password":    {'type': 'password', 'required': True,  'value': ''},
            "confirmpass": {'type': 'password', 'required': True,  'value': ''},
            "ativo":       {'type': 'boolean', 'required': False, 'value': None}
        },
        nomeFormCons: {
            "username_cons": {'type': 'string', 'maxlength': 20},
            "first_name_cons":{'type': 'string', 'maxlength': 30},
            "email_cons": {'type': 'string', 'maxlength': 60},
            "ativo_cons": {'type': 'boolean'},
            "id_selecionado": {'type': 'integer'}
        }
    }

    # ---------- GET ----------
    if request.method == "GET":
        request.sisvar_extra = build_sisvar_payload(
            schema=schema,
            forms={
                nomeForm: build_form_state(
                    estado="novo" if acoes_permitidas["incluir"] else "visualizar",
                    campos={
                        "id": None,
                        "username": "",
                        "first_name": "",
                        "email": "",
                        "password": "",
                        "confirmpass": "",
                        "ativo": None,
                    },
                ),
                nomeFormCons: build_form_state(
                    campos={
                        "username_cons": "",
                        "first_name_cons": "",
                        "email_cons": "",
                        "ativo_cons": None,
                        "id_selecionado": None,
                    },
                ),
            },
            permissions={
                "usuario": acoes_permitidas,
            },
        )
        return render(request, template)

    # ---------- POST ----------
    dataFront = request.sisvar_front
    form      = dataFront.get("form", {}).get(nomeForm, {})
    campos    = form.get("campos", {})
    estado    = form.get("estado", "")

    if estado == "novo" and not acoes_permitidas["incluir"]:
        return resposta_sem_permissao("Você não possui permissão para incluir usuários.")

    if estado == "editar" and not acoes_permitidas["editar"]:
        return resposta_sem_permissao("Você não possui permissão para editar usuários.")

    # Validação de schema #####################################################
    validator = SchemaValidator(schema[nomeForm])
    if not validator.validate(campos):
        errosForm = [
            f"{campo} - {', '.join(erros)}"
            for campo, erros in validator.get_errors().items()
        ]
        return JsonResponse(build_error_payload(errosForm), status=400)
    ###########################################################################

    id_user     = campos.get("id")
    nome_user   = campos.get("username")
    nome        = campos.get("first_name")
    email       = campos.get("email")
    password    = campos.get("password")
    confirmpass = campos.get("confirmpass")
    ativo       = campos.get("ativo")
    usuario     = None

    # Carrega o registro existente quando há ID (editar) ######################
    if id_user:
        try:
            usuario = Usuarios.objects.get(id=id_user)
        except Usuarios.DoesNotExist:
            return JsonResponse(build_error_payload("Registro não encontrado"), status=404)
    ###########################################################################

    # Validações de negócio ###################################################

    # Username duplicado — exclui o próprio registro na edição
    qs_username = User.objects.filter(username=nome_user)
    if id_user:
        qs_username = qs_username.exclude(id=id_user)
    if qs_username.exists():
        return JsonResponse(build_error_payload("Usuário já existe"), status=422)

    # Senhas coincidem (obrigatório em 'novo'; opcional em 'editar' se informada)
    if estado == 'novo' or password:
        if password != confirmpass:
            return JsonResponse(build_error_payload("Senha e confirmação de senha não coincidem"), status=422)

    ###########################################################################

    match estado:

        case 'novo':
            usuario = Usuarios.objects.create(
                username=nome_user,
                first_name=nome,
                email=email,
                password=make_password(password),
                is_active=bool(ativo)
            )
            registrar_auditoria(
                actor=request.user,
                action=AuditEvent.ACTION_CREATE,
                instance=usuario,
                changed_fields=diff_snapshots({}, snapshot_instance(usuario)),
            )

        case 'editar':
            before = snapshot_instance(usuario)
            usuario.username   = nome_user
            usuario.first_name = nome
            usuario.email      = email
            usuario.is_active  = bool(ativo)

            # Senha só é alterada se o usuário informou um novo valor
            if password:
                usuario.password = make_password(password)

            usuario.save()
            changed_fields = diff_snapshots(before, snapshot_instance(usuario))
            if changed_fields:
                registrar_auditoria(
                    actor=request.user,
                    action=AuditEvent.ACTION_UPDATE,
                    instance=usuario,
                    changed_fields=changed_fields,
                )

        case _:
            return JsonResponse(build_error_payload(f"Estado inválido: '{estado}'"), status=400)

    # ===== RESPOSTA JSON =====
    return JsonResponse(build_form_response(
        form_id=nomeForm,
        estado="visualizar",
        update=usuario.date_joined,
        campos={
            "id": usuario.id,
            "username": usuario.username,
            "first_name": usuario.first_name,
            "email": usuario.email,
            "password": "",
            "confirmpass": "",
            "ativo": usuario.is_active,
        },
        mensagem_sucesso="Operação realizada com sucesso!",
    ))

def alterar_senha_view(request):
    template = "alterarsenha.html"
    nomeForm = "alterarSenhaForm"

    schema = {
        nomeForm: {
            'senha_atual':     {'type': 'password', 'required': True},
            'nova_senha':      {'type': 'password', 'required': True},
            'confirmar_senha': {'type': 'password', 'required': True}
        }
    }

    # ---------- GET ----------
    if request.method == "GET":
        request.sisvar_extra = build_sisvar_payload(
            schema=schema,
            forms={
                nomeForm: build_form_state(
                    estado="editar",
                    campos={
                        "senha_atual": "",
                        "nova_senha": "",
                        "confirmar_senha": "",
                    },
                )
            },
        )
        return render(request, template)

    # ---------- POST ----------

    # Defesa em profundidade: o middleware já garante autenticação,
    # mas verificamos aqui como salvaguarda adicional.
    user = request.user
    if not user.is_authenticated:
        return JsonResponse(build_error_payload("Usuário não autenticado"), status=401)

    try:
        payload       = request.sisvar_front
        form          = payload.get("form", {}).get(nomeForm, {})
        campos        = form.get("campos", {})
        senha_atual   = campos.get("senha_atual")
        nova_senha    = campos.get("nova_senha")
        confirmar     = campos.get("confirmar_senha")
    except (KeyError, json.JSONDecodeError, AttributeError):
        return JsonResponse(build_error_payload("Payload inválido"), status=400)

    # Validação de schema #####################################################
    validator = SchemaValidator(schema[nomeForm])
    if not validator.validate(campos):
        errosForm = [
            f"{campo} - {', '.join(erros)}"
            for campo, erros in validator.get_errors().items()
        ]
        return JsonResponse(build_error_payload(errosForm), status=400)
    ###########################################################################

    mensagens_erro = []

    if not user.check_password(senha_atual):
        mensagens_erro.append("Senha atual inválida.")

    if nova_senha != confirmar:
        mensagens_erro.append("Nova senha e confirmação não coincidem.")

    if nova_senha:
        try:
            validate_password(nova_senha, user)
        except ValidationError as e:
            mensagens_erro.extend(e.messages)

    if mensagens_erro:
        return JsonResponse(build_error_payload(mensagens_erro), status=400)

    user.set_password(nova_senha)
    user.save()
    update_session_auth_hash(request, user)
    registrar_auditoria(
        actor=request.user,
        action=AuditEvent.ACTION_PASSWORD_CHANGE,
        instance=user,
        extra_data={"target_user_id": user.id},
    )

    return JsonResponse(build_form_response(
        form_id=nomeForm,
        estado="editar",
        update=None,
        campos={
            "senha_atual": "",
            "nova_senha": "",
            "confirmar_senha": "",
        },
        mensagem_sucesso="Senha alterada com sucesso.",
    ))


@permission_required(PERMISSOES_USUARIO["consultar"], raise_exception=True)
def cadastro_cons_view(request):
    nomeForm     = "cadUsuario"
    nomeFormCons = "consUsuario"

    if request.method != "POST":
        return JsonResponse(build_error_payload("Método não permitido."), status=405)

    dataFront = request.sisvar_front
    form      = dataFront.get("form", {}).get(nomeFormCons, {})
    campos    = form.get("campos", {})

    id_selecionado = int(campos.get('id_selecionado') or 0)

    if id_selecionado:
        try:
            # is_superuser=False garante que superusuários nunca sejam retornados
            usuario = Usuarios.objects.get(id=id_selecionado, is_superuser=False)
            return JsonResponse(build_form_response(
                form_id=nomeForm,
                estado="visualizar",
                update=usuario.date_joined,
                campos={
                    "id": usuario.id,
                    "username": usuario.username,
                    "first_name": usuario.first_name,
                    "email": usuario.email,
                    "password": "",
                    "confirmpass": "",
                    "ativo": usuario.is_active,
                },
            ))
        except Usuarios.DoesNotExist:
            return JsonResponse(build_error_payload("Registro não encontrado"), status=404)

    nome      = campos.get('first_name_cons', '').strip()
    username  = campos.get('username_cons', '').strip()
    userAtivo = campos.get('ativo_cons', False)
    email     = campos.get('email_cons', '').strip()

    filtros = {}
    if nome:
        filtros['first_name__icontains'] = nome
    if username:
        filtros['username__icontains'] = username
    if email:
        filtros['email'] = email
    filtros['is_active'] = userAtivo
    filtros['is_superuser'] = False

    usuarios = Usuarios.objects.filter(**filtros).values(
        'id', 'first_name', 'username', 'email', 'is_active'
    )

    return JsonResponse(build_records_response(list(usuarios)))