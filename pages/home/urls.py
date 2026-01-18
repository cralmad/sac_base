# authapp/urls.py
from django.urls import path
from django.views.generic import RedirectView
from .views import home_view

urlpatterns = [
    path('', RedirectView.as_view(url='app/home/')),
    path("app/home/", home_view),
]
