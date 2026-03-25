from django.urls import path
from . import views

urlpatterns = [
    path('', views.cad_cliente_view, name='cadcliente'),
    path('cons/', views.cad_cliente_cons_view, name='cadcliente_cons'),
]
