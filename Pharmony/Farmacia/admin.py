from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, Medicamento
from .services import crear_usuario_eps


class UsuarioAdmin(UserAdmin):
    model = Usuario
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('telefono', 'firebase_uid', 'face_encoding', 'rol', 'eps')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ('email', 'telefono', 'firebase_uid', 'face_encoding', 'rol', 'eps')}),
    )
    list_display = ['email', 'username', 'first_name', 'last_name', 'rol', 'is_staff']
    list_filter = ['rol', 'is_staff', 'is_superuser', 'is_active']
    search_fields = ['email', 'username', 'first_name', 'last_name']
    ordering = ['email']

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        if change:
            # Edición de un usuario existente: no se intenta crear de nuevo
            # en Firebase (eso mantiene el comportamiento original).
            return

        password = form.cleaned_data.get('password1')
        resultado = crear_usuario_eps(obj, password_plano=password)

        if not resultado["firebase_ok"]:
            self.message_user(request, resultado["mensaje"], level='warning')


admin.site.register(Usuario, UsuarioAdmin)
admin.site.register(Medicamento)