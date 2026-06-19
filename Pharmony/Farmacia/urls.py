from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    MedicamentoViewSet,
    dashboard_inventario
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

]

urlpatterns += router.urls