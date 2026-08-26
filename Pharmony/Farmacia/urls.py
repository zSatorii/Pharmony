from django.urls import path
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(
    r'medicamentos',
    views.MedicamentoViewSet,
    basename='medicamentos'
)

urlpatterns = [
    path('dashboard-inventario/', views.dashboard_inventario, name='dashboard_inventario'),
    path('dashboard-cliente/', views.dashboard_cliente, name='dashboard_cliente'),
    path('inventario/crear/', views.crear_medicamento, name='crear_medicamento'),
    path('inventario/editar/<int:pk>/', views.editar_medicamento, name='editar_medicamento'),
    path('inventario/eliminar/<int:pk>/', views.eliminar_medicamento, name='eliminar_medicamento'),
    path('medicamentos/derecho-peticion/', views.generar_derecho_peticion, name='generar_derecho_peticion'),
    path('medicamentos/derecho-peticion/<int:peticion_id>/entregar/', views.entregar_derecho_peticion_api, name='entregar_derecho_peticion_api'),
    path('mi-cuenta/', views.mi_cuenta, name='mi_cuenta'),
]

urlpatterns += router.urls