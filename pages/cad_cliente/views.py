from django.shortcuts import render
from django.http import JsonResponse
from sac_base.form_validador import SchemaValidator
from pages.cad_grupo_cli.models import GrupoCli
from pages.core.models import Pais, Regiao, Cidade
from .models import Cliente

def cad_cliente_view(request):
    template     = 'cadcliente.html'
    nomeForm     = 'cadCliente'
    nomeFormCons = 'consCliente'

    schema = {
        nomeForm: {
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
        },
        nomeFormCons: {
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

        request.sisvar_extra = {
            "schema": schema,
            "form": {
                nomeForm: {
                    "estado": "novo",
                    "update": None,
                    "campos": {
                        "id":            None,
                        "grupo":         None,
                        "nome":          "",
                        "rsocial":       "",
                        "logradouro":    "",
                        "endereco":      "",
                        "numero":        "",
                        "complemento":   "",
                        "bairro":        "",
                        "pais":          None,
                        "regiao":        None,
                        "cidade":        None,
                        "codpostal":     "",
                        "identificador": "",
                    }
                },
                nomeFormCons: {
                    "estado": "novo",
                    "campos": {
                        "nome_cons":      "",
                        "id_selecionado": None,
                    }
                }
            },
            "opcoes": {
                "grupos":  grupos,
                "paises":  paises,
                "regioes": regioes,
                "cidades": cidades,
            }
        }
        return render(request, template)

    # ---------- POST ----------
    dataFront = request.sisvar_front
    form      = dataFront.get("form", {}).get(nomeForm, {})
    campos    = form.get("campos", {})
    estado    = form.get("estado", "")

    # Validação de schema #####################################################
    validator = SchemaValidator(schema[nomeForm])
    if not validator.validate(campos):
        erros = [
            f"{campo} - {', '.join(msgs)}"
            for campo, msgs in validator.get_errors().items()
        ]
        return JsonResponse({
            "mensagens": {"erro": {"conteudo": erros, "ignorar": False}}
        }, status=400)
    ###########################################################################

    id_cliente    = campos.get("id")
    grupo_id      = campos.get("grupo")
    nome          = campos.get("nome")
    rsocial       = campos.get("rsocial")
    logradouro    = campos.get("logradouro") or ""
    endereco      = campos.get("endereco") or ""
    numero        = campos.get("numero") or ""
    complemento   = campos.get("complemento") or ""
    bairro        = campos.get("bairro") or ""
    pais_id       = campos.get("pais")
    regiao_id     = campos.get("regiao") or None
    cidade_id     = campos.get("cidade") or None
    codpostal     = campos.get("codpostal") or ""
    identificador = campos.get("identificador") or ""
    cliente       = None

    # Carrega o registro existente quando há ID (editar) ######################
    if id_cliente:
        try:
            cliente = Cliente.objects.get(id=id_cliente)
        except Cliente.DoesNotExist:
            return JsonResponse({
                "mensagens": {"erro": {"conteudo": ["Registro não encontrado"], "ignorar": False}}
            }, status=404)
    ###########################################################################

    # Validações de negócio ###################################################
    try:
        grupo_obj = GrupoCli.objects.get(id=grupo_id)
    except GrupoCli.DoesNotExist:
        return JsonResponse({
            "mensagens": {"erro": {"conteudo": ["Grupo não encontrado"], "ignorar": False}}
        }, status=422)

    try:
        pais_obj = Pais.objects.get(id=pais_id)
    except Pais.DoesNotExist:
        return JsonResponse({
            "mensagens": {"erro": {"conteudo": ["País não encontrado"], "ignorar": False}}
        }, status=422)

    regiao_obj = None
    if regiao_id:
        try:
            regiao_obj = Regiao.objects.get(id=regiao_id, pais=pais_obj)
        except Regiao.DoesNotExist:
            return JsonResponse({
                "mensagens": {"erro": {"conteudo": ["UF/Região não encontrada para o País informado"], "ignorar": False}}
            }, status=422)

    cidade_obj = None
    if cidade_id:
        try:
            cidade_obj = Cidade.objects.get(id=cidade_id, regiao=regiao_obj)
        except Cidade.DoesNotExist:
            return JsonResponse({
                "mensagens": {"erro": {"conteudo": ["Cidade não encontrada para a UF informada"], "ignorar": False}}
            }, status=422)
    ###########################################################################

    match estado:

        case 'novo':
            cliente = Cliente.objects.create(
                grupo=grupo_obj,
                nome=nome,
                rsocial=rsocial,
                logradouro=logradouro,
                endereco=endereco,
                numero=numero,
                complemento=complemento,
                bairro=bairro,
                pais=pais_obj,
                regiao=regiao_obj,
                cidade=cidade_obj,
                codpostal=codpostal,
                identificador=identificador,
            )

        case 'editar':
            cliente.grupo       = grupo_obj
            cliente.nome        = nome
            cliente.rsocial     = rsocial
            cliente.logradouro  = logradouro
            cliente.endereco    = endereco
            cliente.numero      = numero
            cliente.complemento = complemento
            cliente.bairro      = bairro
            cliente.pais        = pais_obj
            cliente.regiao      = regiao_obj
            cliente.cidade      = cidade_obj
            cliente.codpostal   = codpostal
            cliente.identificador = identificador
            cliente.save()

        case 'excluir':
            if not cliente:
                return JsonResponse({
                    "mensagens": {"erro": {"conteudo": ["Registro não encontrado para exclusão"], "ignorar": False}}
                }, status=404)
            cliente.delete()
            return JsonResponse({
                "success": True,
                "form": {
                    nomeForm: {
                        "estado": "novo",
                        "update": None,
                        "campos": {
                            "id": None, "grupo": None, "nome": "", "rsocial": "",
                            "logradouro": "", "endereco": "", "numero": "",
                            "complemento": "", "bairro": "", "pais": None,
                            "regiao": None, "cidade": None,
                            "codpostal": "", "identificador": "",
                        }
                    }
                },
                "mensagens": {
                    "sucesso": {"ignorar": True, "conteudo": ["Registro excluído com sucesso!"]}
                }
            })

        case _:
            return JsonResponse({
                "mensagens": {"erro": {"conteudo": [f"Estado inválido: '{estado}'"], "ignorar": False}}
            }, status=400)

    # ===== RESPOSTA JSON =====
    return JsonResponse({
        "success": True,
        "form": {
            nomeForm: {
                "estado": "visualizar",
                "update": cliente.atualizacao,
                "campos": {
                    "id":            cliente.id,
                    "grupo":         cliente.grupo_id,
                    "nome":          cliente.nome,
                    "rsocial":       cliente.rsocial,
                    "logradouro":    cliente.logradouro,
                    "endereco":      cliente.endereco,
                    "numero":        cliente.numero,
                    "complemento":   cliente.complemento,
                    "bairro":        cliente.bairro,
                    "pais":          cliente.pais_id,
                    "regiao":        cliente.regiao_id,
                    "cidade":        cliente.cidade_id,
                    "codpostal":     cliente.codpostal,
                    "identificador": cliente.identificador,
                }
            }
        },
        "mensagens": {
            "sucesso": {
                "ignorar": True,
                "conteudo": ["Operação realizada com sucesso!"]
            }
        }
    })

def cad_cliente_cons_view(request):
    nomeForm     = "cadCliente"
    nomeFormCons = "consCliente"

    if request.method == "POST":
        dataFront = request.sisvar_front
        form      = dataFront.get("form", {}).get(nomeFormCons, {})
        campos    = form.get("campos", {})

        id_selecionado = int(campos.get('id_selecionado') or 0)

        if id_selecionado:
            try:
                cliente = Cliente.objects.get(id=id_selecionado)
                return JsonResponse({
                    "form": {
                        nomeForm: {
                            "estado": "visualizar",
                            "update": cliente.atualizacao,
                            "campos": {
                                "id":            cliente.id,
                                "grupo":         cliente.grupo_id,
                                "nome":          cliente.nome,
                                "rsocial":       cliente.rsocial,
                                "logradouro":    cliente.logradouro,
                                "endereco":      cliente.endereco,
                                "numero":        cliente.numero,
                                "complemento":   cliente.complemento,
                                "bairro":        cliente.bairro,
                                "pais":          cliente.pais_id,
                                "regiao":        cliente.regiao_id,
                                "cidade":        cliente.cidade_id,
                                "codpostal":     cliente.codpostal,
                                "identificador": cliente.identificador,
                            }
                        }
                    }
                })
            except Cliente.DoesNotExist:
                return JsonResponse({
                    "mensagens": {"erro": {"conteudo": ["Registro não encontrado"], "ignorar": False}}
                }, status=404)

        nome_cons = campos.get('nome_cons', '').strip()
        filtros = {}
        if nome_cons:
            filtros['nome__icontains'] = nome_cons

        clientes = Cliente.objects.filter(**filtros).select_related('grupo', 'pais', 'regiao', 'cidade').values(
            'id', 'nome', 'rsocial', 'grupo_id', 'grupo__descricao',
            'pais_id', 'pais__nome', 'regiao_id', 'regiao__sigla',
            'cidade_id', 'cidade__nome', 'identificador'
        ).order_by('nome')

        return JsonResponse({"registros": list(clientes)})

    return JsonResponse({
        "mensagens": {"erro": {"conteudo": ["Método não permitido"], "ignorar": False}}
    }, status=405)