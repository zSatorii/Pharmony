from django.contrib import admin
from django.urls import include, path

from Farmacia.views import cerrar_sesion, iniciar_sesion, login_face, registrar_usuario, validar_rostro

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('home.urls')),
    path('registro/', registrar_usuario, name='registro'),
    path('login/', iniciar_sesion, name='login'),
    path('logout/', cerrar_sesion, name='logout'),
    path('api/validar-rostro/', validar_rostro, name='validar_rostro'),
    path('api/login-face/', login_face, name='login_face'),
    path('api/', include('Farmacia.urls')),
    path('', include('epsinventario.urls')),
    path('docs-ia/', include('DocsIA.urls')),
]
