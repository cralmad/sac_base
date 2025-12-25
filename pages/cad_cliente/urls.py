from django.urls import path
from . import views

urlpatterns = [
    path('cliente/', views.CadCliente, name='cadcliente'),
]
