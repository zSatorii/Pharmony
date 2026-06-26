from django.urls import path
from rest_framework.routers import DefaultRouter
from . import views

urlpatterns = [
    path('login/', views.iniciar_sesion, name='login'),

    path('logout/', views.cerrar_sesion, name='cerrar_sesion'),
    path('inventario/', views.dashboard_inventario, name='dashboard_inventario'),
    path('inventario/crear/', views.crear_medicamento, name='crear_medicamento'),
    path('inventario/editar/<int:pk>/', views.editar_medicamento, name='editar_medicamento'),
    path('inventario/eliminar/<int:pk>/', views.eliminar_medicamento, name='eliminar_medicamento'),
    
]