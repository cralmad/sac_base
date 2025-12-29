from django.urls import path
from . import views

urlpatterns = [
    path('grupocli/', views.CadGrupoCli, name='cadgrupocli'),
]
