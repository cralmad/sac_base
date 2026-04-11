from django.contrib.auth.decorators import permission_required
from django.db import models as db_models
from django.http import JsonResponse
from django.shortcuts import render

from pages.auditoria.models import AuditEvent
from pages.auditoria.utils import diff_snapshots, registrar_auditoria, snapshot_instance
from sac_base.form_validador import SchemaValidator
from sac_base.sisvar_builders import build_error_payload, build_form_response, build_form_state, build_records_response, build_sisvar_payload, build_success_payload
from .models import GrupoCli


PERMISSOES_GRUPO_CLI = {
    'acessar': 'cad_grupo_cli.view_grupocli',
    'consultar': 'cad_grupo_cli.view_grupocli',
    'incluir': 'cad_grupo_cli.add_grupocli',
    'editar': 'cad_grupo_cli.change_grupocli',
    'excluir': 'cad_grupo_cli.delete_grupocli',
}


def obter_acoes_permitidas_grupo_cli(usuario):
    if not usuario or not getattr(usuario, 'is_authenticated', False):
        return {acao: False for acao in PERMISSOES_GRUPO_CLI}

    return {
        acao: usuario.has_perm(codename)
        for acao, codename in PERMISSOES_GRUPO_CLI.items()
    }


def resposta_sem_permissao(mensagem, status=403):
    return JsonResponse(build_error_payload(mensagem), status=status)


@permission_required(PERMISSOES_GRUPO_CLI['acessar'], raise_exception=True)
def cad_grupo_cli_view(request):
    template     = 'cadgrupocli.html'
    nomeForm     = 'cadGrupoCli'
    nomeFormCons = 'consGrupoCli'
    acoes_permitidas = obter_acoes_permitidas_grupo_cli(getattr(request, 'user', None))

    schema = {
        nomeForm: {
            'descricao': {'type': 'string', 'maxlength': 30, 'minlength': 3, 'required': True, 'value': ''},
        },
        nomeFormCons: {
            'descricao': {'type': 'string', 'maxlength': 30, 'value': ''},
        }
    }

    # GET
    if request.method == 'GET':
        request.sisvar_extra = build_sisvar_payload(
            schema=schema,
            forms={
                nomeForm: build_form_state(
                    estado='novo' if acoes_permitidas['incluir'] else 'visualizar',
                    campos={
                        'id': None,
                        'descricao': '',
                    },
                ),
                nomeFormCons: build_form_state(
                    campos={
                        'descricao': '',
                        'id_selecionado': None,
                    },
                ),
            },
            permissions={
                'cad_grupo_cli': acoes_permitidas,
            },
        )
        return render(request, template)

    # POST
    dataFront = request.sisvar_front
    form      = dataFront.get('form', {}).get(nomeForm, {})
    campos    = form.get('campos', {})
    estado    = form.get('estado', '')

    if estado == 'novo' and not acoes_permitidas['incluir']:
        return resposta_sem_permissao('Você não possui permissão para incluir grupos de cliente.')

    if estado == 'editar' and not acoes_permitidas['editar']:
        return resposta_sem_permissao('Você não possui permissão para editar grupos de cliente.')

    validator = SchemaValidator(schema[nomeForm])
    if not validator.validate(campos):
        erros = [f"{c} - {', '.join(e)}" for c, e in validator.get_errors().items()]
        return JsonResponse(build_error_payload(erros), status=400)

    descricao = campos.get('descricao', '').strip().upper()

    match estado:
        case 'novo':
            if GrupoCli.objects.filter(descricao=descricao).exists():
                return JsonResponse(build_error_payload('Descrição já cadastrada.'), status=422)
            grupo = GrupoCli.objects.create(
                descricao=descricao,
                created_by=request.user,
                updated_by=request.user,
            )
            registrar_auditoria(
                actor=request.user,
                action=AuditEvent.ACTION_CREATE,
                instance=grupo,
                changed_fields=diff_snapshots({}, snapshot_instance(grupo)),
            )

        case 'editar':
            id_registro = campos.get('id')
            try:
                grupo = GrupoCli.objects.get(id=id_registro)
            except GrupoCli.DoesNotExist:
                return JsonResponse(build_error_payload('Registro não encontrado.'), status=404)
            before = snapshot_instance(grupo)
            if GrupoCli.objects.filter(descricao=descricao).exclude(id=id_registro).exists():
                return JsonResponse(build_error_payload('Descrição já cadastrada.'), status=422)
            grupo.descricao = descricao
            grupo.updated_by = request.user
            grupo.save()
            changed_fields = diff_snapshots(before, snapshot_instance(grupo))
            if changed_fields:
                registrar_auditoria(
                    actor=request.user,
                    action=AuditEvent.ACTION_UPDATE,
                    instance=grupo,
                    changed_fields=changed_fields,
                )

        case _:
            return JsonResponse(build_error_payload(f"Estado inválido: '{estado}'"), status=400)

    return JsonResponse(build_form_response(
        form_id=nomeForm,
        estado='visualizar',
        update=grupo.atualizacao.isoformat(),
        campos={
            'id': grupo.id,
            'descricao': grupo.descricao,
        },
        mensagem_sucesso='Grupo de cliente salvo com sucesso!',
    ))


@permission_required(PERMISSOES_GRUPO_CLI['consultar'], raise_exception=True)
def cad_grupo_cli_cons_view(request):
    nomeFormCons = 'consGrupoCli'
    nomeForm     = 'cadGrupoCli'

    if request.method != 'POST':
        return JsonResponse(build_error_payload('Método não permitido.'), status=405)

    dataFront = request.sisvar_front
    form      = dataFront.get('form', {}).get(nomeFormCons, {})
    campos    = form.get('campos', {})

    id_selecionado = campos.get('id_selecionado')

    if id_selecionado:
        try:
            grupo = GrupoCli.objects.get(id=id_selecionado)
        except GrupoCli.DoesNotExist:
            return JsonResponse(build_error_payload('Registro não encontrado.'), status=404)
        return JsonResponse(build_form_response(
            form_id=nomeForm,
            estado='visualizar',
            update=grupo.atualizacao.isoformat(),
            campos={
                'id': grupo.id,
                'descricao': grupo.descricao,
            },
        ))

    descricao_filtro = campos.get('descricao', '').strip().upper()
    qs = GrupoCli.objects.all().order_by('descricao')
    if descricao_filtro:
        qs = qs.filter(descricao__icontains=descricao_filtro)

    registros = [
        {'id': g.id, 'descricao': g.descricao}
        for g in qs
    ]

    return JsonResponse(build_records_response(registros))


@permission_required(PERMISSOES_GRUPO_CLI['acessar'], raise_exception=True)
def cad_grupo_cli_del_view(request):
    """
    Exclui um grupo de cliente pelo ID recebido no payload.
    Rota: POST /app/cad/grupocli/del
    """
    nomeForm = 'cadGrupoCli'
    usuario = getattr(request, 'user', None)

    if not usuario or not usuario.has_perm(PERMISSOES_GRUPO_CLI['excluir']):
        return resposta_sem_permissao('Você não possui permissão para excluir grupos de cliente.')

    dataFront = request.sisvar_front
    form      = dataFront.get('form', {}).get(nomeForm, {})
    campos    = form.get('campos', {})
    id_registro = campos.get('id')

    if not id_registro:
        return JsonResponse(build_error_payload('ID não informado.'), status=400)

    try:
        grupo = GrupoCli.objects.get(id=id_registro)
    except GrupoCli.DoesNotExist:
        return JsonResponse(build_error_payload('Registro não encontrado.'), status=404)

    if grupo.cliente_set.exists():
        return JsonResponse(build_error_payload('Este grupo não pode ser excluído pois está vinculado a um ou mais clientes.'), status=409)

    before = snapshot_instance(grupo)
    grupo.soft_delete(request.user, 'Exclusão via cadastro de grupo de cliente')
    grupo.save()
    registrar_auditoria(
        actor=request.user,
        action=AuditEvent.ACTION_SOFT_DELETE,
        instance=grupo,
        changed_fields=diff_snapshots(before, snapshot_instance(grupo)),
        extra_data={'reason': grupo.delete_reason},
    )

    return JsonResponse(build_success_payload('Grupo de cliente excluído com sucesso!'))
