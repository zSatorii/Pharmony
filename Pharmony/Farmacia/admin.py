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


admin.site.register(Usuario, UsuarioAdmin)