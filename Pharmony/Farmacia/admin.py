from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from firebase_admin import auth as firebase_auth, firestore
from .models import Usuario, Medicamento
from .services import crear_usuario_eps


class UsuarioAdmin(UserAdmin):
    model = Usuario
    fieldsets = UserAdmin.fieldsets + (
        ('Información Pharmony', {'fields': ('telefono', 'firebase_uid', 'face_encoding', 'rol', 'eps')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información Inicial', {'fields': ('first_name', 'last_name', 'email', 'telefono', 'firebase_uid', 'face_encoding', 'rol', 'eps')}),
    )
    list_display = ['email', 'username', 'full_name', 'rol_badge', 'is_staff_badge']
    list_filter = ['rol', 'is_staff', 'is_superuser', 'is_active']
    search_fields = ['email', 'username', 'first_name', 'last_name']
    ordering = ['email']

    @admin.display(description='Nombre Completo')
    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or "—"

    @admin.display(description='Rol')
    def rol_badge(self, obj):
        return format_html('<span class="badge-admin badge-info">{}</span>', obj.rol or "Usuario")

    @admin.display(description='Staff')
    def is_staff_badge(self, obj):
        if obj.is_staff:
            return format_html('<span class="badge-admin badge-success">{}</span>', 'Si')
        return format_html('<span class="badge-admin badge-warning">{}</span>', 'No')

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

@admin.register(Medicamento)
class MedicamentoAdmin(admin.ModelAdmin):
    list_display = ('nombre_comercial', 'nombre_generico', 'laboratorio', 'requiere_formula_badge')
    search_fields = ('nombre_comercial', 'nombre_generico', 'laboratorio')

    @admin.display(description='Fórmula Médica')
    def requiere_formula_badge(self, obj):
        if getattr(obj, 'requiere_formula', False):
            return format_html('<span class="badge-admin badge-danger">{}</span>', 'Requerida')
        return format_html('<span class="badge-admin badge-success">{}</span>', 'Venta Libre')