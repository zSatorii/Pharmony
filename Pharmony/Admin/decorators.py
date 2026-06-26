from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from Farmacia.views import get_user_from_jwt  # Asumiendo que get_user_from_jwt está en un archivo utils o tus vistas

def admin_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        # 1. Intentamos recuperar el usuario desde la cookie JWT o sesión de Django
        user = get_user_from_jwt(request)
        if not user and request.user.is_authenticated:
            user = request.user
            
        # 2. Si no hay usuario o su rol no es exactamente 'admin', denegar acceso
        if user and user.rol == 'admin':
            return view_func(request, *args, **kwargs)
        else:
            return HttpResponseForbidden("Acceso Denegado: Esta zona es exclusiva para Administradores.")
    return _wrapped_view