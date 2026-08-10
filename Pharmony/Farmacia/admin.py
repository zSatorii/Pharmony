from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from firebase_admin import auth as firebase_auth, firestore
from .models import Usuario, Medicamento

class UsuarioAdmin(UserAdmin):
    model = Usuario
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('telefono', 'firebase_uid', 'face_encoding', 'rol', 'eps')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ('telefono', 'firebase_uid', 'face_encoding', 'rol', 'eps')}),
    )
    list_display = ['email', 'username', 'first_name', 'last_name', 'rol', 'is_staff']
    list_filter = ['rol', 'is_staff', 'is_superuser', 'is_active']
    search_fields = ['email', 'username', 'first_name', 'last_name']
    ordering = ['email']

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change and not obj.firebase_uid and obj.email:
            password = form.cleaned_data.get('password1')
            if not password:
                self.message_user(
                    request,
                    f"Usuario {obj.email} creado solo en Django: no se pudo crear en "
                    f"Firebase porque no se recibió la contraseña en texto plano.",
                    level='warning'
                )
                return
            try:
                fb_user = firebase_auth.create_user(
                    email=obj.email,
                    password=password,
                    display_name=f"{obj.first_name} {obj.last_name}".strip() or obj.username,
                )
                obj.firebase_uid = fb_user.uid
                obj.save(update_fields=['firebase_uid'])

                db = firestore.client()
                db.collection('usuarios').document(fb_user.uid).set({
                    'nombre': obj.first_name,
                    'apellido': obj.last_name,
                    'email': obj.email,
                    'telefono': obj.telefono or "",
                    'rol': obj.rol,
                    'eps_id': obj.eps.id if obj.eps else None,
                    'face_registered': False,
                }, merge=True)
            except Exception as e:
                self.message_user(
                    request,
                    f"Usuario {obj.email} creado en Django, pero falló la sincronización "
                    f"con Firebase: {e}",
                    level='warning'
                )

admin.site.register(Usuario, UsuarioAdmin)
admin.site.register(Medicamento)