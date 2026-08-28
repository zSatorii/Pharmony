"""
Farmacia/views/common.py

Funciones auxiliares compartidas entre los distintos módulos de vistas
(auth_views, medicamentos_views, cliente_views, cuenta_views).
"""

from django.urls import reverse
from firebase_admin import firestore


def get_firestore_db():
    try:
        return firestore.client()
    except Exception:
        return None

def _redirect_por_rol(user):
    if user.rol == 'cliente':
        return reverse('dashboard_cliente')
    if user.rol == 'eps':
        return reverse('turnos:seleccion_panel')
    return reverse('dashboard_inventario')
