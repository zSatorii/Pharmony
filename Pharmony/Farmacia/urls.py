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
    # Nota: login, registro, logout, validar_rostro y login_face
    # YA están definidos en el urls.py raíz del proyecto. No se repiten aquí.

    path('dashboard-inventario/', views.dashboard_inventario, name='dashboard_inventario'),
    path('dashboard-cliente/', views.dashboard_cliente, name='dashboard_cliente'),

    path('inventario/crear/', views.crear_medicamento, name='crear_medicamento'),
    path('inventario/editar/<int:pk>/', views.editar_medicamento, name='editar_medicamento'),
    path('inventario/eliminar/<int:pk>/', views.eliminar_medicamento, name='eliminar_medicamento'),
]

urlpatterns += router.urls