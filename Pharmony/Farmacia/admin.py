from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from firebase_admin import auth as firebase_auth, firestore
from .models import Usuario, Medicamento

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

@admin.register(Medicamento)
class MedicamentoAdmin(admin.ModelAdmin):
    list_display = ('nombre_comercial', 'nombre_generico', 'laboratorio', 'requiere_formula_badge')
    search_fields = ('nombre_comercial', 'nombre_generico', 'laboratorio')

    @admin.display(description='Fórmula Médica')
    def requiere_formula_badge(self, obj):
        if getattr(obj, 'requiere_formula', False):
            return format_html('<span class="badge-admin badge-danger">{}</span>', 'Requerida')
        return format_html('<span class="badge-admin badge-success">{}</span>', 'Venta Libre')