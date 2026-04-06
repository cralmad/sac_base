from django.contrib.auth.decorators import permission_required
from django.db import models as db_models
from django.http import JsonResponse
from django.shortcuts import render

from sac_base.form_validador import SchemaValidator
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
    return JsonResponse({
        'success': False,
        'mensagens': {'erro': {'conteudo': [mensagem], 'ignorar': False}}
    }, status=status)


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
        request.sisvar_extra = {
            'schema': schema,
            'form': {
                nomeForm: {
                    'estado': 'novo' if acoes_permitidas['incluir'] else 'visualizar',
                    'update': None,
                    'campos': {
                        'id':        None,
                        'descricao': '',
                    }
                },
                nomeFormCons: {
                    'estado': 'novo',
                    'update': None,
                    'campos': {
                        'descricao':      '',
                        'id_selecionado': None,
                    }
                }
            },
            'others': {
                'permissoes': {
                    'cad_grupo_cli': acoes_permitidas,
                }
            }
        }
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
        return JsonResponse({
            'mensagens': {'erro': {'conteudo': erros, 'ignorar': False}}
        }, status=400)

    descricao = campos.get('descricao', '').strip().upper()

    match estado:
        case 'novo':
            if GrupoCli.objects.filter(descricao=descricao).exists():
                return JsonResponse({
                    'mensagens': {'erro': {'conteudo': ['Descrição já cadastrada.'], 'ignorar': False}}
                }, status=422)
            grupo = GrupoCli.objects.create(descricao=descricao)

        case 'editar':
            id_registro = campos.get('id')
            try:
                grupo = GrupoCli.objects.get(id=id_registro)
            except GrupoCli.DoesNotExist:
                return JsonResponse({
                    'mensagens': {'erro': {'conteudo': ['Registro não encontrado.'], 'ignorar': False}}
                }, status=404)
            if GrupoCli.objects.filter(descricao=descricao).exclude(id=id_registro).exists():
                return JsonResponse({
                    'mensagens': {'erro': {'conteudo': ['Descrição já cadastrada.'], 'ignorar': False}}
                }, status=422)
            grupo.descricao = descricao
            grupo.save()

        case _:
            return JsonResponse({
                'mensagens': {'erro': {'conteudo': [f"Estado inválido: '{estado}'"], 'ignorar': False}}
            }, status=400)

    return JsonResponse({
        'success': True,
        'form': {
            nomeForm: {
                'estado': 'visualizar',
                'update': grupo.atualizacao.isoformat(),
                'campos': {
                    'id':        grupo.id,
                    'descricao': grupo.descricao,
                }
            }
        },
        'mensagens': {
            'sucesso': {'ignorar': True, 'conteudo': ['Grupo de cliente salvo com sucesso!']}
        }
    })


@permission_required(PERMISSOES_GRUPO_CLI['consultar'], raise_exception=True)
def cad_grupo_cli_cons_view(request):
    nomeFormCons = 'consGrupoCli'
    nomeForm     = 'cadGrupoCli'

    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'mensagens': {'erro': {'conteudo': ['Método não permitido.'], 'ignorar': False}}
        }, status=405)

    dataFront = request.sisvar_front
    form      = dataFront.get('form', {}).get(nomeFormCons, {})
    campos    = form.get('campos', {})

    id_selecionado = campos.get('id_selecionado')

    if id_selecionado:
        try:
            grupo = GrupoCli.objects.get(id=id_selecionado)
        except GrupoCli.DoesNotExist:
            return JsonResponse({
                'mensagens': {'erro': {'conteudo': ['Registro não encontrado.'], 'ignorar': False}}
            }, status=404)
        return JsonResponse({
            'success': True,
            'form': {
                nomeForm: {
                    'estado': 'visualizar',
                    'update': grupo.atualizacao.isoformat(),
                    'campos': {
                        'id':        grupo.id,
                        'descricao': grupo.descricao,
                    }
                }
            }
        })

    descricao_filtro = campos.get('descricao', '').strip().upper()
    qs = GrupoCli.objects.all().order_by('descricao')
    if descricao_filtro:
        qs = qs.filter(descricao__icontains=descricao_filtro)

    registros = [
        {'id': g.id, 'descricao': g.descricao}
        for g in qs
    ]

    return JsonResponse({
        'success':   True,
        'registros': registros,
    })


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
        return JsonResponse({
            'mensagens': {'erro': {'conteudo': ['ID não informado.'], 'ignorar': False}}
        }, status=400)

    try:
        grupo = GrupoCli.objects.get(id=id_registro)
    except GrupoCli.DoesNotExist:
        return JsonResponse({
            'mensagens': {'erro': {'conteudo': ['Registro não encontrado.'], 'ignorar': False}}
        }, status=404)

    try:
        grupo.delete()
    except db_models.ProtectedError:
        return JsonResponse({
            'mensagens': {'erro': {'conteudo': ['Este grupo não pode ser excluído pois está vinculado a um ou mais clientes.'], 'ignorar': False}}
        }, status=409)

    return JsonResponse({
        'success': True,
        'mensagens': {
            'sucesso': {'ignorar': True, 'conteudo': ['Grupo de cliente excluído com sucesso!']}
        }
    })
