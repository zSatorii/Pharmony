"""
api/authentication.py

Clase de autenticación para Django REST Framework que reutiliza la
lógica de JWT que ya existe en Farmacia/views/auth_views.py
(generate_jwt / get_user_from_jwt), en vez de reescribirla.

Sin esta clase, DRF no tiene forma de saber qué usuario está haciendo
la petición cuando Flutter manda el header:

    Authorization: Bearer <token>

y por lo tanto request.user siempre queda anónimo, sin importar que el
token sea válido — cualquier vista con IsAuthenticated rechazaría la
petición igual.
"""

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class JWTAuthentication(BaseAuthentication):
    """
    Autentica la petición usando el JWT casero del proyecto (el mismo
    que ya usa el login por navegador), leído desde:

    1. El header 'Authorization: Bearer <token>' (lo que manda Flutter).
    2. La cookie 'jwt_token' (lo que usa el navegador), como respaldo.

    Si no hay token o es inválido, devuelve None (no lanza excepción)
    para que DRF pueda seguir probando otras clases de autenticación o,
    si no hay ninguna, tratar la petición como anónima — dejando que sea
    el permission_class (ej. IsAuthenticated) quien decida si eso basta
    para rechazarla.
    """

    def authenticate(self, request):
        # Import diferido (no al inicio del archivo) a propósito: DRF
        # resuelve DEFAULT_AUTHENTICATION_CLASSES mientras 'rest_framework'
        # todavía se está terminando de cargar. Si este import estuviera
        # arriba del archivo, se dispararía en ese mismo instante y
        # terminaría reimportando rest_framework.viewsets a medio cargar
        # (a través de Farmacia.views -> medicamentos_views.py), causando
        # un import circular. Importándolo aquí, se resuelve solo cuando
        # llega una petición real, con todo ya cargado.
        from Farmacia.views import get_user_from_jwt

        usuario = get_user_from_jwt(request._request)

        if usuario is None:
            # No hay token, o es inválido/expirado. No es un error en sí
            # mismo — puede que la petición simplemente sea anónima.
            return None

        if not usuario.is_active:
            raise AuthenticationFailed('Esta cuenta está deshabilitada.')

        # (usuario, auth) — DRF espera esta tupla; 'auth' puede ir en
        # None ya que no usamos un objeto de token separado.
        return (usuario, None)