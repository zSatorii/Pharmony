from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'eps', views.EpsViewSet, basename='eps-api')
router.register(r'sedes', views.SedeViewSet, basename='sede-api')
router.register(r'inventario', views.InventarioSedeViewSet, basename='inventario-api')

urlpatterns = [
    path('api/', include(router.urls)),

    path('eps/dashboard/', views.dashboard_eps, name='dashboard_eps'),
    path('eps/<int:pk>/editar/', views.editar_eps, name='editar_eps'),
    path('eps/<int:pk>/eliminar/', views.eliminar_eps, name='eliminar_eps'),

    path('sedes/crear/', views.crear_sede, name='crear_sede'),
    path('sedes/<int:pk>/editar/', views.editar_sede, name='editar_sede'),
    path('sedes/<int:pk>/eliminar/', views.eliminar_sede, name='eliminar_sede'),
    path('sedes/<int:sede_id>/inventario/', views.inventario_por_sede, name='inventario_por_sede'),
    path('sedes/<int:sede_id>/inventario/crear/', views.crear_inventario, name='crear_inventario'),

    path('inventario/<int:pk>/editar/', views.editar_inventario, name='editar_inventario'),
    path('inventario/<int:pk>/eliminar/', views.eliminar_inventario, name='eliminar_inventario'),
    path('ciudad/<str:ciudad>/medicamentos/', views.medicamentos_por_ciudad, name='medicamentos_por_ciudad'),
    path('medicamentos/buscar/', views.buscar_medicamentos, name='buscar_medicamentos'),
]