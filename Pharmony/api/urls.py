from django.urls import path
from .views import (
    HomeDataView, CrearUsuarioEpsView, LoginApiView, PerfilUsuarioView,
    ListarMedicamentosView, DetalleMedicamentoView, MisMedicamentosPacienteView,
    CrearTurnoView, MisTurnosView, DetalleTurnoView,
    CrearPedidoView, MisPedidosView, TrackingPedidoView,
    EscanearFormulaApiView, ListarSedesView
)

urlpatterns = [
    # Inicio y Sedes
    path('home/', HomeDataView.as_view(), name='api_home'),
    path('sedes/', ListarSedesView.as_view(), name='api_sedes'),

    # Autenticación y Perfil
    path('auth/login/', LoginApiView.as_view(), name='api_login'),
    path('usuario/perfil/', PerfilUsuarioView.as_view(), name='api_perfil'),
    path('usuarios-eps/', CrearUsuarioEpsView.as_view(), name='crear_usuario_eps'),

    # Medicamentos
    path('medicamentos/', ListarMedicamentosView.as_view(), name='api_medicamentos_list'),
    path('medicamentos/<int:pk>/', DetalleMedicamentoView.as_view(), name='api_medicamentos_detail'),
    path('mis-medicamentos/', MisMedicamentosPacienteView.as_view(), name='api_mis_medicamentos'),

    # Turnos
    path('turnos/crear/', CrearTurnoView.as_view(), name='api_turnos_crear'),
    path('turnos/mis-turnos/', MisTurnosView.as_view(), name='api_mis_turnos'),
    path('turnos/<int:pk>/', DetalleTurnoView.as_view(), name='api_turnos_detail'),

    # Pedidos
    path('pedidos/crear/', CrearPedidoView.as_view(), name='api_pedidos_crear'),
    path('pedidos/mis-pedidos/', MisPedidosView.as_view(), name='api_mis_pedidos'),
    path('pedidos/<int:pk>/seguimiento/', TrackingPedidoView.as_view(), name='api_pedidos_tracking'),

    # IA Scanner
    path('docs-ia/escanear/', EscanearFormulaApiView.as_view(), name='api_escanear_formula'),
]
