from django.urls import path
from rest_framework.routers import DefaultRouter
from . import views

urlpatterns = [

    path('logout/', views.cerrar_sesion, name='cerrar_sesion'),
    path('inventario/', views.dashboard_inventario, name='dashboard_inventario'),
    path('inventario/crear/', views.crear_medicamento, name='crear_medicamento'),
    path('inventario/editar/<int:pk>/', views.editar_medicamento, name='editar_medicamento'),
    path('inventario/eliminar/<int:pk>/', views.eliminar_medicamento, name='eliminar_medicamento'),
    
]

from .views import (
    MedicamentoViewSet,
    dashboard_inventario,
    dashboard_cliente
)

router = DefaultRouter()

router.register(
    r'medicamentos',
    MedicamentoViewSet,
    basename='medicamentos'
)

urlpatterns = [

    path(
        'dashboard-inventario/',
        dashboard_inventario,
        name='dashboard_inventario'
    ),

    path(
        'dashboard-cliente/',
        dashboard_cliente,
        name='dashboard_cliente'
    ),

]

urlpatterns += router.urls
