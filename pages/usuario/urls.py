# authapp/urls.py
from django.urls import path
from .views import login_view, logout_view, cadastro_view

urlpatterns = [
    path("usuario/login/", login_view),
    path("usuario/logout/", logout_view),
    path("usuario/cadastro/", cadastro_view),
]
