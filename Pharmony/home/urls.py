from django.urls import path
from .views import home
from . import api

app_name = "home"

urlpatterns = [
    path("", home, name="home"),
    path("api/home/", api.api_home_data, name="api_home_data"),
]
