from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def eps_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if getattr(request.user, 'rol', None) != 'eps':
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper