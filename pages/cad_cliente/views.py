from django.shortcuts import render

def CadCliente(request):
    
    template = 'cadcliente.html'

    return render(request, template)