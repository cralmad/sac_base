from django.db import models as db_models
from django.http import JsonResponse
from django.shortcuts import render

from sac_base.form_validador import SchemaValidator
from .models import GrupoCli


def cad_grupo_cli_view(request):
    template     = 'cadgrupocli.html'
    nomeForm     = 'cadGrupoCli'
    nomeFormCons = 'consGrupoCli'

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
                    'estado': 'novo',
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
            }
        }
        return render(request, template)

    # POST
    dataFront = request.sisvar_front
    form      = dataFront.get('form', {}).get(nomeForm, {})
    campos    = form.get('campos', {})
    estado    = form.get('estado', '')

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


def cad_grupo_cli_cons_view(request):
    nomeFormCons = 'consGrupoCli'
    nomeForm     = 'cadGrupoCli'

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


def cad_grupo_cli_del_view(request):
    """
    Exclui um grupo de cliente pelo ID recebido no payload.
    Rota: POST /app/cad/grupocli/del
    """
    nomeForm = 'cadGrupoCli'

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
