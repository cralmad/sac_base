from django.urls import path

from .views import (
    cadastro_config_logistica_cons_view,
    cadastro_config_logistica_del_view,
    cadastro_config_logistica_view,
)

urlpatterns = [
    path("logistica/configuracao-logistica/", cadastro_config_logistica_view),
    path("logistica/configuracao-logistica/cons", cadastro_config_logistica_cons_view),
    path("logistica/configuracao-logistica/del", cadastro_config_logistica_del_view),
]
