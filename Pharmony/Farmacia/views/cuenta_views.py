"""
Farmacia/views/cuenta_views.py

Vista para que el usuario gestione su propio perfil (datos personales,
EPS asignada), con sincronización a Firestore/Firebase Auth.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from firebase_admin import auth as firebase_auth

from epsinventario.models import Eps
from .common import get_firestore_db


def mi_cuenta(request):
    db = get_firestore_db()
    if db:
        try:
            eps_ref = db.collection('eps').stream()
            for doc in eps_ref:
                data = doc.to_dict()
                eps_id = data.get('id')
                if eps_id is not None:
                    Eps.objects.update_or_create(
                        id=int(eps_id),
                        defaults={
                            'nombre': data.get('nombre', ''),
                            'nit': data.get('nit', ''),
                            'direccion': data.get('direccion', ''),
                            'ciudad': data.get('ciudad', ''),
                            'telefono': data.get('telefono', ''),
                            'email': data.get('email', ''),
                            'estado': data.get('estado', True)
                        }
                    )
        except Exception:
            pass
            
    mensaje_exito = None
    mensaje_error = None
    epss = Eps.objects.filter(estado=True)
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        apellido = request.POST.get('apellido', '').strip()
        cedula = request.POST.get('cedula', '').strip()
        direccion = request.POST.get('direccion', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        email = request.POST.get('email', '').strip()
        eps_id = request.POST.get('eps_id', '').strip()
        
        user = request.user
        
        if not nombre or not email:
            mensaje_error = "El nombre y el correo electrónico son requeridos."
        else:
            user.first_name = nombre
            user.last_name = apellido
            user.cedula = cedula
            user.direccion = direccion
            user.telefono = telefono
            user.email = email
            
            eps_obj = None
            if eps_id:
                try:
                    eps_obj = Eps.objects.get(id=eps_id)
                    user.eps = eps_obj
                except Eps.DoesNotExist:
                    user.eps = None
            else:
                user.eps = None
                
            user.save()
            
            fb_uid = user.firebase_uid
            if fb_uid:
                try:
                    db = get_firestore_db()
                    if db:
                        db.collection('usuarios').document(fb_uid).set({
                            'nombre': user.first_name,
                            'apellido': user.last_name,
                            'email': user.email,
                            'telefono': user.telefono or "",
                            'cedula': user.cedula or "",
                            'direccion': user.direccion or "",
                            'eps_id': eps_obj.id if eps_obj else None
                        }, merge=True)
                except Exception:
                    pass
                
                try:
                    firebase_auth.update_user(
                        fb_uid,
                        email=user.email
                    )
                except Exception:
                    pass
                    
            return redirect(reverse('mi_cuenta') + '?saved=1')
            
    if request.GET.get('saved') == '1':
        mensaje_exito = "¡Tu información de perfil se ha guardado y sincronizado con Firebase correctamente!"
        
    user_name = request.user.get_full_name() or request.user.username
    parts = user_name.split()
    user_initials = "".join([p[0].upper() for p in parts[:2]]) if parts else "?"
        
    return render(request, 'inventario/MiCuenta.html', {
        'mensaje_exito': mensaje_exito,
        'mensaje_error': mensaje_error,
        'epss': epss,
        'user_name': user_name,
        'user_initials': user_initials
    })


