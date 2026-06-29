from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, Medicamento

class UsuarioAdmin(UserAdmin):
    model = Usuario
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('telefono', 'firebase_uid', 'face_encoding', 'rol')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ('telefono', 'firebase_uid', 'face_encoding', 'rol')}),
    )
    list_display = ['email', 'username', 'first_name', 'last_name', 'rol', 'is_staff']
    list_filter = ['rol', 'is_staff', 'is_superuser', 'is_active']
    search_fields = ['email', 'username', 'first_name', 'last_name']
    ordering = ['email']

admin.site.register(Usuario, UsuarioAdmin)
admin.site.register(Medicamento)

