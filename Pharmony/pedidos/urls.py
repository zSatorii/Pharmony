from django.urls import path
from . import views

app_name = 'pedidos'

urlpatterns = [
    path('mis-pedidos/', views.mis_pedidos, name='mis_pedidos'),
    path('seguimiento/', views.seguimiento_pedido, name='seguimiento_publico'),
    path('seguimiento/<str:codigo>/', views.seguimiento_pedido, name='seguimiento_con_codigo'),
    path('actualizar/<int:pedido_id>/', views.actualizar_estado_pedido, name='actualizar_estado'),
]
