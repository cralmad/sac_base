from django.shortcuts import render

def CadGrupoCli(request):
    
    template = 'cadgrupocli.html'

    return render(request, template)