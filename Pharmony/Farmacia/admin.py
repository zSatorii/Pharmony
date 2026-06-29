from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario


class UsuarioAdmin(UserAdmin):
    model = Usuario
    list_display = ('username', 'email', 'rol', 'eps', 'is_active', 'is_staff')
    list_filter = ('rol', 'eps', 'is_active', 'is_staff')

    fieldsets = UserAdmin.fieldsets + (
        ('Datos de Pharmony', {'fields': ('telefono', 'firebase_uid', 'rol', 'eps')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Datos de Pharmony', {'fields': ('telefono', 'rol', 'eps')}),
    )

    def save_model(self, request, obj, form, change):
        # Capturamos la contraseña en texto plano SOLO en el momento de creación,
        # antes de que Django la hashee, para poder crear la cuenta también en Firebase Auth.
        raw_password = form.cleaned_data.get('password1') if not change else None
        super().save_model(request, obj, form, change)
        self._sync_con_firebase(obj, raw_password, is_new=not change)

    def _sync_con_firebase(self, user, raw_password, is_new):
        try:
            from firebase_admin import auth as firebase_auth, firestore
        except ImportError:
            return
        try:
            if is_new and raw_password and not user.firebase_uid:
                fb_user = firebase_auth.create_user(
                    email=user.email or user.username,
                    password=raw_password,
                    display_name=f"{user.first_name} {user.last_name}".strip() or user.username,
                )
                user.firebase_uid = fb_user.uid
                user.save(update_fields=['firebase_uid'])

            if user.firebase_uid:
                db = firestore.client()
                db.collection('usuarios').document(user.firebase_uid).set({
                    'nombre': user.first_name,
                    'apellido': user.last_name,
                    'email': user.email,
                    'telefono': user.telefono or '',
                    'rol': user.rol,
                    'eps_id': user.eps_id,
                    'eps_nombre': user.eps.nombre if user.eps_id else None,
                    'created_at': firestore.SERVER_TIMESTAMP,
                }, merge=True)
        except Exception as e:
            print(f"Error al sincronizar usuario {user.username} con Firebase: {e}")


admin.site.register(Usuario, UsuarioAdmin)