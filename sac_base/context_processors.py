def sisvar_global(request):
    base = {
        "usuario": {
            "autenticado": request.user.is_authenticated,
            "id": request.user.id if request.user.is_authenticated else None,
            "nome": request.user.username if request.user.is_authenticated else None,
        },
        "schema": {},
        "form": {}, # formId: {estado:{novo|visualizar|editar|excluir}, update: data|null, campos: {campo1: valor1, campo2: valor2...}}
        "mensagens": {}, # sucesso|erro|aviso:{ignorar: true|false, conteudo: ["mensagem", ...]}
        "others": {},
    }

    # Se a view já tiver colocado algo em request.sisvar, mescla
    if hasattr(request, "sisvar_extra"):
        for key, value in request.sisvar_extra.items():
            base[key] = value

    return {"sisVar": base}

'''Adicionar conteúdo em sisVar na view
    def home(request):
        request.sisvar_extra = {
            "others": {"pagina": "home"}
        }

        return render(request, "home.html")
'''