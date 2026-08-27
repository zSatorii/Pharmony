from django.urls import path

from .views import CrearUsuarioEpsView

urlpatterns = [
    path('usuarios-eps/', CrearUsuarioEpsView.as_view(), name='crear_usuario_eps'),
]