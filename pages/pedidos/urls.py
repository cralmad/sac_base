
from django.urls import path, include

from .views import (
    pedido_dev_del_view,
    pedido_dev_foto_add_view,
    pedido_dev_foto_del_view,
    pedido_dev_list_view,
    pedido_dev_save_view,
    pedido_motoristas_view,
    pedido_mov_del_view,
    pedido_mov_list_view,
    pedido_mov_save_view,
    pedidos_cadastro_cons_view,
    pedidos_cadastro_del_view,
    pedidos_cadastro_view,
    pedidos_importacao_view,
    pedidos_importar_view,
    pedidos_relatorio_volumes_view,
)

urlpatterns = [
    path("logistica/pedidos/", pedidos_cadastro_view, name="pedidos"),
    path("logistica/pedidos/cons", pedidos_cadastro_cons_view, name="pedidos_cons"),
    path("logistica/pedidos/del", pedidos_cadastro_del_view, name="pedidos_del"),
    path("logistica/pedidos/mov/list", pedido_mov_list_view, name="pedidos_mov_list"),
    path("logistica/pedidos/motoristas", pedido_motoristas_view, name="pedidos_motoristas"),
    path("logistica/pedidos/mov/save", pedido_mov_save_view, name="pedidos_mov_save"),
    path("logistica/pedidos/mov/del", pedido_mov_del_view, name="pedidos_mov_del"),
    path("logistica/pedidos/dev/list", pedido_dev_list_view, name="pedidos_dev_list"),
    path("logistica/pedidos/dev/save", pedido_dev_save_view, name="pedidos_dev_save"),
    path("logistica/pedidos/dev/del", pedido_dev_del_view, name="pedidos_dev_del"),
    path("logistica/pedidos/dev/foto/add", pedido_dev_foto_add_view, name="pedidos_dev_foto_add"),
    path("logistica/pedidos/dev/foto/del", pedido_dev_foto_del_view, name="pedidos_dev_foto_del"),
    path("logistica/pedidos/importacao/", pedidos_importacao_view, name="pedidos_importacao"),
    path("logistica/pedidos/importar", pedidos_importar_view, name="pedidos_importar"),
    path("logistica/pedidos/relatorio-volumes/", pedidos_relatorio_volumes_view, name="pedidos_relatorio_volumes"),

    # Relatório de conferência de volumes
    path("logistica/", include("pages.pedidos.urls_relatorio")),

    # Mapa de conferência / rotas
    path("logistica/", include("pages.pedidos.urls_mapa")),
]
