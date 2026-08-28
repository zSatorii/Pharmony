from rest_framework.permissions import BasePermission


class PuedeCrearUsuarioEps(BasePermission):
    """
    Permite crear usuarios EPS solo a:
    - usuarios con rol 'admin' (pueden crear en cualquier EPS)
    - usuarios con rol 'eps' (solo pueden crear dentro de su propia EPS,
      eso se fuerza en la vista, no aquí)

    Cualquier otro rol (ej. 'cliente') o usuario no autenticado, queda fuera.
    """

    message = "No tienes permiso para crear usuarios de EPS."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and getattr(user, 'rol', None) in ('admin', 'eps')
        )
