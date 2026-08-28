from django.contrib import admin
from django.urls import include, path

from Farmacia.views import cerrar_sesion, iniciar_sesion, login_face, login_face_select, registrar_usuario, validar_rostro

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('home.urls')),
    path('registro/', registrar_usuario, name='registro'),
    path('login/', iniciar_sesion, name='login'),
    path('logout/', cerrar_sesion, name='logout'),
    path('api/validar-rostro/', validar_rostro, name='validar_rostro'),
    path('api/login-face/', login_face, name='login_face'),
    path('api/login-face-select/', login_face_select, name='login_face_select'),
    path('api/', include('Farmacia.urls')),
    path('', include('epsinventario.urls')),
    path('docs-ia/', include('DocsIA.urls')),
    path('turnos/', include('turnos.urls')),
]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)