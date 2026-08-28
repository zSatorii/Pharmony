"""
Farmacia/views/__init__.py

Este paquete reemplaza al antiguo Farmacia/views.py monolítico (18
funciones/clases en un solo archivo). El código se dividió en módulos
por responsabilidad:

- auth_views.py        -> registro, login, login facial, logout, JWT
- medicamentos_views.py -> CRUD de medicamentos y dashboard de inventario
- cliente_views.py     -> dashboard del cliente, derecho de petición
                           (generar PDF + endpoint de entrega)
- cuenta_views.py      -> gestión del perfil propio ("Mi cuenta")
- common.py            -> helpers compartidos (Firestore, redirect por rol)

Los imports de abajo hacen que 'from . import views' y 'views.nombre_funcion'
sigan funcionando exactamente igual que antes en Farmacia/urls.py — no hace
falta tocar las URLs.
"""

from .auth_views import *
from .medicamentos_views import *
from .cliente_views import *
from .cuenta_views import *
