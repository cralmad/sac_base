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

    # ── GET ──────────────────────────────────────────────────────────────────
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
                    'campos': {
                        'descricao':    '',
                        'id_selecionado': None,
                    }
                }
            }
        }
        return render(request, template)

    # ── POST ─────────────────────────────────────────────────────────────────
    dataFront = request.sisvar_front
    form      = dataFront.get('form', {}).get(nomeForm, {})
    campos    = form.get('campos', {})
    estado    = form.get('estado', '')

    # 1ª camada — validação de schema
    validator = SchemaValidator(schema[nomeForm])
    if not validator.validate(campos):
        erros = [f"{c} - {', '.join(e)}" for c, e in validator.get_errors().items()]
        return JsonResponse({
            'mensagens': {'erro': {'conteudo': erros, 'ignorar': False}}
        }, status=400)

    descricao = campos.get('descricao', '').strip().upper()

    # 2ª camada — validações de negócio
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

    schema_cons = {
        'descricao':      {'type': 'string', 'maxlength': 30, 'value': ''},
        'id_selecionado': {'type': 'integer', 'required': False, 'value': None},
    }

    dataFront = request.sisvar_front
    form      = dataFront.get('form', {}).get(nomeFormCons, {})
    campos    = form.get('campos', {})

    id_selecionado = campos.get('id_selecionado')

    # Seleção de um registro específico
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

    # Pesquisa com filtro
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