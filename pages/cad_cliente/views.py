from django.shortcuts import render
from django.http import JsonResponse
from sac_base.form_validador import SchemaValidator
from pages.cad_grupo_cli.models import GrupoCli
from .models import Cliente


def cad_cliente_view(request):
    template     = 'cadcliente.html'
    nomeForm     = 'cadCliente'
    nomeFormCons = 'consCliente'

    schema = {
        nomeForm: {
            "grupo":       {'type': 'integer', 'required': True},
            "nome":        {'type': 'string',  'maxlength': 100, 'minlength': 3, 'required': True,  'value': ''},
            "rsocial":      {'type': 'string',  'maxlength': 100, 'minlength': 3, 'required': True,  'value': ''},
            "logradouro":  {'type': 'string',  'maxlength': 20,  'required': False, 'value': ''},
            "endereco":    {'type': 'string',  'maxlength': 150, 'required': False, 'value': ''},
            "numero":      {'type': 'string',  'maxlength': 10,  'required': False, 'value': ''},
            "complemento": {'type': 'string',  'maxlength': 50,  'required': False, 'value': ''},
            "bairro":      {'type': 'string',  'maxlength': 60,  'required': False, 'value': ''},
            "pais":        {'type': 'string',  'maxlength': 20,  'required': True,  'value': ''},
            "uf":          {'type': 'string',  'maxlength': 20,  'required': True,  'value': ''},
            "cidade":      {'type': 'string',  'maxlength': 50,  'required': True,  'value': ''},
            "codpostal":   {'type': 'string',  'maxlength': 10,   'required': False, 'value': ''},
            "identificador": {'type': 'string', 'maxlength': 20, 'required': False, 'value': ''},
        },
        nomeFormCons: {
            "nome_cons":      {'type': 'string',  'maxlength': 100},
            "id_selecionado": {'type': 'integer'},
        }
    }

    # ---------- GET ----------
    if request.method == 'GET':
        request.sisvar_extra = {
            "schema": schema,
            "form": {
                nomeForm: {
                    "estado": "novo",
                    "update": None,
                    "campos": {
                        "id":          None,
                        "grupo":       None,
                        "nome":        "",
                        "rsocial":     "",
                        "logradouro":  "",
                        "endereco":    "",
                        "numero":      "",
                        "complemento": "",
                        "bairro":      "",
                        "pais":        "",
                        "uf":          "",
                        "cidade":      "",
                        "codpostal":   "",
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

    id_cliente  = campos.get("id")
    grupo_id    = campos.get("grupo")
    nome        = campos.get("nome")
    rsocial     = campos.get("rsocial")
    logradouro  = campos.get("logradouro") or ""
    endereco    = campos.get("endereco") or ""
    numero      = campos.get("numero") or ""
    complemento = campos.get("complemento") or ""
    bairro      = campos.get("bairro") or ""
    pais        = campos.get("pais")
    uf          = campos.get("uf")
    cidade      = campos.get("cidade")
    codpostal   = campos.get("codpostal") or ""
    identificador = campos.get("identificador") or ""
    cliente     = None

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
    grupo_obj = None
    if grupo_id:
        try:
            grupo_obj = GrupoCli.objects.get(id=grupo_id)
        except GrupoCli.DoesNotExist:
            return JsonResponse({
                "mensagens": {"erro": {"conteudo": ["Grupo não encontrado"], "ignorar": False}}
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
                pais=pais,
                uf=uf,
                cidade=cidade,
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
            cliente.pais        = pais
            cliente.uf          = uf
            cliente.cidade      = cidade
            cliente.codpostal   = codpostal
            cliente.identificador = identificador
            cliente.save()

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
                    "id":          cliente.id,
                    "grupo":       cliente.grupo_id,
                    "nome":        cliente.nome,
                    "rsocial":     cliente.rsocial,
                    "logradouro":  cliente.logradouro,
                    "endereco":    cliente.endereco,
                    "numero":      cliente.numero,
                    "complemento": cliente.complemento,
                    "bairro":      cliente.bairro,
                    "pais":        cliente.pais,
                    "uf":          cliente.uf,
                    "cidade":      cliente.cidade,
                    "codpostal":   cliente.codpostal,
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
                                "id":          cliente.id,
                                "grupo":       cliente.grupo_id,
                                "nome":        cliente.nome,
                                "rsocial":     cliente.rsocial,
                                "logradouro":  cliente.logradouro,
                                "endereco":    cliente.endereco,
                                "numero":      cliente.numero,
                                "complemento": cliente.complemento,
                                "bairro":      cliente.bairro,
                                "pais":        cliente.pais,
                                "uf":          cliente.uf,
                                "cidade":      cliente.cidade,
                                "codpostal":   cliente.codpostal,
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

        clientes = Cliente.objects.filter(**filtros).values(
            'id', 'nome', 'rsocial', 'pais', 'uf', 'cidade', 'grupo_id', 'identificador'
        )

        return JsonResponse({"registros": list(clientes)})

    return JsonResponse({
        "mensagens": {"erro": {"conteudo": ["Método não permitido"], "ignorar": False}}
    }, status=405)