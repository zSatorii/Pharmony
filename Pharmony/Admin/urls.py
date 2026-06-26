from django.urls import path
from .views import dashboard_admin_view, crear_farmaceutico_view
# O si moviste las vistas a Admin/views.py, impórtalas desde ahí:
# from . import views

urlpatterns = [
    # Al entrar a las URLs de esta app, la raíz será el panel principal
    path('', dashboard_admin_view, name='dashboard_admin'),
    
    # Subruta para el registro de empleados
    path('crear-farmaceutico/', crear_farmaceutico_view, name='crear_farmaceutico'),
]