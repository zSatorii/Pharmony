from django.urls import path
from . import views

app_name = 'turnos'

urlpatterns = [
    # Usuario
    path('solicitar/<int:sede_id>/<int:medicamento_id>/', views.solicitar_turno, name='solicitar_turno'),
    path('ticket/<str:codigo>/', views.ver_ticket, name='ver_ticket'),
    path('ticket/<str:codigo>/mensaje/', views.enviar_mensaje_usuario, name='enviar_mensaje_usuario'),
    path('ticket/<str:codigo>/estado.json', views.estado_turno_json, name='estado_turno_json'),
    path('factura/<str:codigo>/', views.factura_turno, name='factura_turno'),
    path('finalizar/<str:codigo>/', views.volver_dashboard, name='volver_dashboard'),

    # Admin / auxiliar
    path('panel/', views.seleccion_panel, name='seleccion_panel'),
    path('panel/marcar-tarjeta/', views.marcar_tarjeta, name='marcar_tarjeta'),
    path('panel/cola/<int:sede_id>/', views.cola_turnos, name='cola_turnos'),
    path('panel/siguiente/<int:sede_id>/', views.tomar_siguiente_turno, name='tomar_siguiente_turno'),
    path('panel/atender/<str:codigo>/', views.atender_turno, name='atender_turno'),
    path('panel/cerrar-caja/<int:sede_id>/', views.cerrar_caja, name='cerrar_caja'),
    path('sede/<int:sede_id>/auxiliares/', views.gestionar_auxiliares, name='gestionar_auxiliares'),
    path('mis-turnos/', views.mis_turnos, name='mis_turnos'),
    path('factura/<str:codigo>/pdf/', views.factura_pdf, name='factura_pdf'),
    path('ticket/<str:codigo>/cancelar/', views.cancelar_turno, name='cancelar_turno'),
]
