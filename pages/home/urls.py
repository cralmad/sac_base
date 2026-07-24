# authapp/urls.py
from django.urls import path
from django.views.generic import RedirectView
from .views import home_view
from .views_iframe_teste import iframe_embed_probe_view, iframe_embed_teste_view

urlpatterns = [
    path('', RedirectView.as_view(url='app/home/')),
    path("app/home/", home_view),
    path("app/teste/iframe-embed/", iframe_embed_teste_view, name="iframe_embed_teste"),
    path("app/teste/iframe-embed/probe/", iframe_embed_probe_view, name="iframe_embed_probe"),
]
