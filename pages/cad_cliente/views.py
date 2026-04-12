from django.contrib.auth.decorators import permission_required
from django.shortcuts import render
from django.http import JsonResponse
from pages.auditoria.models import AuditEvent
from pages.auditoria.utils import diff_snapshots, registrar_auditoria, snapshot_instance
from sac_base.form_validador import SchemaValidator
from sac_base.sisvar_builders import build_error_payload, build_form_response, build_form_state, build_records_response, build_sisvar_payload
from pages.cad_grupo_cli.models import GrupoCli
from pages.core.models import Pais, Regiao, Cidade
from .models import Cliente


PERMISSOES_CLIENTE = {
    "acessar": "cad_cliente.view_cliente",
    "consultar": "cad_cliente.view_cliente",
    "incluir": "cad_cliente.add_cliente",
    "editar": "cad_cliente.change_cliente",
    "excluir": "cad_cliente.delete_cliente",
}


def obter_acoes_permitidas_cliente(usuario):
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return {acao: False for acao in PERMISSOES_CLIENTE}

    return {
        acao: usuario.has_perm(codename)
        for acao, codename in PERMISSOES_CLIENTE.items()
    }


def resposta_sem_permissao(mensagem, status=403):
    return JsonResponse(build_error_payload(mensagem), status=status)


@permission_required(PERMISSOES_CLIENTE["acessar"], raise_exception=True)
def cad_cliente_view(request):
    template     = 'cadcliente.html'
    nomeForm     = 'cadCliente'
    nomeFormCons = 'consCliente'
    acoes_permitidas = obter_acoes_permitidas_cliente(getattr(request, 'user', None))

    schema = {
        nomeForm: {
            "codigo":        {'type': 'string',  'maxlength': 20,  'required': False, 'value': ''},
            "grupo":         {'type': 'integer', 'required': True},
            "nome":          {'type': 'string',  'maxlength': 100, 'minlength': 3, 'required': True,  'value': ''},
            "rsocial":       {'type': 'string',  'maxlength': 100, 'minlength': 3, 'required': True,  'value': ''},
            "logradouro":    {'type': 'string',  'maxlength': 20,  'required': False, 'value': ''},
            "endereco":      {'type': 'string',  'maxlength': 150, 'required': False, 'value': ''},
            "numero":        {'type': 'string',  'maxlength': 10,  'required': False, 'value': ''},
            "complemento":   {'type': 'string',  'maxlength': 50,  'required': False, 'value': ''},
            "bairro":        {'type': 'string',  'maxlength': 60,  'required': False, 'value': ''},
            "pais":          {'type': 'integer', 'required': True},
            "regiao":        {'type': 'integer', 'required': False},
            "cidade":        {'type': 'integer', 'required': False},
            "codpostal":     {'type': 'string',  'maxlength': 10,  'required': False, 'value': ''},
            "identificador": {'type': 'string',  'maxlength': 20,  'required': False, 'value': ''},
            "observacao":    {'type': 'string',  'maxlength': 500, 'required': False, 'value': ''},
        },
        nomeFormCons: {
            "codigo_cons":    {'type': 'string',  'maxlength': 20},
            "nome_cons":      {'type': 'string',  'maxlength': 100},
            "id_selecionado": {'type': 'integer'},
        }
    }

    # ---------- GET ----------
    if request.method == 'GET':
        grupos  = list(GrupoCli.objects.values('id', 'descricao').order_by('descricao'))
        paises  = list(Pais.objects.values('id', 'nome', 'sigla').order_by('nome'))
        regioes = list(Regiao.objects.values('id', 'nome', 'sigla', 'pais_id').order_by('nome'))
        cidades = list(Cidade.objects.values('id', 'nome', 'regiao_id').order_by('nome'))
        estado_inicial = 'novo' if acoes_permitidas['incluir'] else 'visualizar'

        request.sisvar_extra = build_sisvar_payload(
            schema=schema,
            forms={
                nomeForm: build_form_state(
                    estado=estado_inicial,
                    campos={
                        "id": None,
                        "codigo": "",
                        "grupo": None,
                        "nome": "",
                        "rsocial": "",
                        "logradouro": "",
                        "endereco": "",
                        "numero": "",
                        "complemento": "",
                        "bairro": "",
                        "pais": None,
                        "regiao": None,
                        "cidade": None,
                        "codpostal": "",
                        "identificador": "",
                        "observacao": "",
                    },
                ),
                nomeFormCons: build_form_state(
                    campos={
                        "codigo_cons": "",
                        "nome_cons": "",
                        "id_selecionado": None,
                    },
                ),
            },
            permissions={
                "cad_cliente": acoes_permitidas,
            },
            options={
                "grupos": grupos,
                "paises": paises,
                "regioes": regioes,
                "cidades": cidades,
            },
        )
        return render(request, template)

    # ---------- POST ----------
    dataFront = request.sisvar_front
    form      = dataFront.get("form", {}).get(nomeForm, {})
    campos    = form.get("campos", {})
    estado    = form.get("estado", "")

    if estado == 'novo' and not acoes_permitidas['incluir']:
        return resposta_sem_permissao('Você não possui permissão para incluir clientes.')

    if estado == 'editar' and not acoes_permitidas['editar']:
        return resposta_sem_permissao('Você não possui permissão para editar clientes.')

    if estado == 'excluir' and not acoes_permitidas['excluir']:
        return resposta_sem_permissao('Você não possui permissão para excluir clientes.')

    # Validação de schema #####################################################
    validator = SchemaValidator(schema[nomeForm])
    if not validator.validate(campos):
        erros = [
            f"{campo} - {', '.join(msgs)}"
            for campo, msgs in validator.get_errors().items()
        ]
        return JsonResponse(build_error_payload(erros), status=400)
    ###########################################################################

    id_cliente    = campos.get("id")
    codigo        = campos.get("codigo", "")
    grupo_id      = campos.get("grupo")
    nome          = campos.get("nome")
    rsocial       = campos.get("rsocial")
    logradouro    = campos.get("logradouro", "")
    endereco      = campos.get("endereco", "")
    numero        = campos.get("numero", "")
    complemento   = campos.get("complemento", "")
    bairro        = campos.get("bairro", "")
    pais_id       = campos.get("pais")
    regiao_id     = campos.get("regiao")
    cidade_id     = campos.get("cidade")
    codpostal     = campos.get("codpostal", "")
    identificador = campos.get("identificador", "")
    observacao    = campos.get("observacao", "")

    match estado:
        case "novo":
            cliente = Cliente(
                codigo        = codigo,
                grupo_id      = grupo_id,
                nome          = nome,
                rsocial       = rsocial,
                logradouro    = logradouro,
                endereco      = endereco,
                numero        = numero,
                complemento   = complemento,
                bairro        = bairro,
                pais_id       = pais_id,
                regiao_id     = regiao_id,
                cidade_id     = cidade_id,
                codpostal     = codpostal,
                identificador = identificador,
                observacao    = observacao,
                created_by    = request.user,
                updated_by    = request.user,
            )
            cliente.save()
            registrar_auditoria(
                actor=request.user,
                action=AuditEvent.ACTION_CREATE,
                instance=cliente,
                changed_fields=diff_snapshots({}, snapshot_instance(cliente)),
            )

        case "editar":
            try:
                cliente = Cliente.objects.get(pk=id_cliente)
            except Cliente.DoesNotExist:
                return JsonResponse(build_error_payload("Registro não encontrado."), status=404)

            before = snapshot_instance(cliente)

            cliente.grupo_id      = grupo_id
            cliente.codigo        = codigo
            cliente.nome          = nome
            cliente.rsocial       = rsocial
            cliente.logradouro    = logradouro
            cliente.endereco      = endereco
            cliente.numero        = numero
            cliente.complemento   = complemento
            cliente.bairro        = bairro
            cliente.pais_id       = pais_id
            cliente.regiao_id     = regiao_id
            cliente.cidade_id     = cidade_id
            cliente.codpostal     = codpostal
            cliente.identificador = identificador
            cliente.observacao    = observacao
            cliente.updated_by    = request.user
            cliente.save()
            changed_fields = diff_snapshots(before, snapshot_instance(cliente))
            if changed_fields:
                registrar_auditoria(
                    actor=request.user,
                    action=AuditEvent.ACTION_UPDATE,
                    instance=cliente,
                    changed_fields=changed_fields,
                )

        case "excluir":
            try:
                cliente = Cliente.objects.get(pk=id_cliente)
            except Cliente.DoesNotExist:
                return JsonResponse(build_error_payload("Registro não encontrado."), status=404)

            before = snapshot_instance(cliente)
            cliente.soft_delete(request.user, "Exclusão via cadastro de cliente")
            cliente.save()
            registrar_auditoria(
                actor=request.user,
                action=AuditEvent.ACTION_SOFT_DELETE,
                instance=cliente,
                changed_fields=diff_snapshots(before, snapshot_instance(cliente)),
                extra_data={"reason": cliente.delete_reason},
            )

            return JsonResponse(build_form_response(
                form_id=nomeForm,
                estado="novo",
                update=None,
                campos={
                    "id": None, "codigo": "", "grupo": None, "nome": "", "rsocial": "",
                    "logradouro": "", "endereco": "", "numero": "",
                    "complemento": "", "bairro": "", "pais": None,
                    "regiao": None, "cidade": None,
                    "codpostal": "", "identificador": "", "observacao": "",
                },
                mensagem_sucesso="Registro excluído com sucesso!",
            ))

        case _:
            return JsonResponse(build_error_payload(f"Estado inválido: '{estado}'"), status=400)

    # ===== RESPOSTA JSON =====
    return JsonResponse(build_form_response(
        form_id=nomeForm,
        estado="visualizar",
        update=cliente.atualizacao,
        campos={
            "id": cliente.id,
            "codigo": cliente.codigo,
            "grupo": cliente.grupo_id,
            "nome": cliente.nome,
            "rsocial": cliente.rsocial,
            "logradouro": cliente.logradouro,
            "endereco": cliente.endereco,
            "numero": cliente.numero,
            "complemento": cliente.complemento,
            "bairro": cliente.bairro,
            "pais": cliente.pais_id,
            "regiao": cliente.regiao_id,
            "cidade": cliente.cidade_id,
            "codpostal": cliente.codpostal,
            "identificador": cliente.identificador,
            "observacao": cliente.observacao,
        },
        mensagem_sucesso="Registro salvo com sucesso!",
    ))


@permission_required(PERMISSOES_CLIENTE["consultar"], raise_exception=True)
def cad_cliente_cons_view(request):
    """
    View de consulta de clientes.
    POST /app/cad/cliente/cons/

    Comportamento:
    - Se `id_selecionado` estiver preenchido: carrega o registro e retorna estado 'visualizar'.
    - Caso contrário: filtra por nome e retorna lista de registros para a tabela.
    """
    nomeForm     = 'cadCliente'
    nomeFormCons = 'consCliente'

    if request.method != 'POST':
        return JsonResponse(build_error_payload("Método não permitido."), status=405)

    dataFront   = request.sisvar_front
    form_cons   = dataFront.get("form", {}).get(nomeFormCons, {})
    campos      = form_cons.get("campos", {})

    id_selecionado = campos.get("id_selecionado")

    # ── Carregar registro individual ──────────────────────────────────────────
    if id_selecionado:
        try:
            cli = Cliente.objects.get(pk=id_selecionado)
        except Cliente.DoesNotExist:
            return JsonResponse(build_error_payload("Registro não encontrado."), status=404)

        return JsonResponse(build_form_response(
            form_id=nomeForm,
            estado="visualizar",
            update=cli.atualizacao,
            campos={
                "id": cli.id,
                "codigo": cli.codigo,
                "grupo": cli.grupo_id,
                "nome": cli.nome,
                "rsocial": cli.rsocial,
                "logradouro": cli.logradouro,
                "endereco": cli.endereco,
                "numero": cli.numero,
                "complemento": cli.complemento,
                "bairro": cli.bairro,
                "pais": cli.pais_id,
                "regiao": cli.regiao_id,
                "cidade": cli.cidade_id,
                "codpostal": cli.codpostal,
                "identificador": cli.identificador,
                "observacao": cli.observacao,
            },
        ))

    # ── Pesquisa por filtro ───────────────────────────────────────────────────
    codigo_cons = campos.get("codigo_cons", "").strip()
    nome_cons = campos.get("nome_cons", "").strip()
    qs = Cliente.objects.select_related('grupo', 'pais', 'regiao', 'cidade')

    if codigo_cons:
        qs = qs.filter(codigo__icontains=codigo_cons)

    if nome_cons:
        qs = qs.filter(nome__icontains=nome_cons)

    registros = [
        {
            "id":          c.id,
            "codigo":      c.codigo,
            "nome":        c.nome,
            "rsocial":     c.rsocial,
            "grupo":       c.grupo.descricao if c.grupo else "",
            "pais":        c.pais.nome       if c.pais   else "",
            "regiao":      c.regiao.sigla    if c.regiao else "",
            "cidade":      c.cidade.nome     if c.cidade else "",
            "identificador": c.identificador,
        }
        for c in qs.order_by('nome')[:200]
    ]

    return JsonResponse(build_records_response(registros))
