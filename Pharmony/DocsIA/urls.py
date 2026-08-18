from django.urls import path
from . import views

app_name = 'DocsIA'

urlpatterns = [
    path('escaner/', views.escaner_ui_view, name='escaner_ui'),
    path('api/escanear/', views.escanear_documento_api, name='escanear_api'),
    path('api/asignar/', views.asignar_medicamento_usuario_api, name='asignar_api'),
]

