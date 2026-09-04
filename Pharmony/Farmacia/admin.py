from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.utils import timezone
from firebase_admin import auth as firebase_auth, firestore
from .services import crear_usuario_eps
from .models import Usuario, Medicamento, MedicamentoUsuario, DerechoPeticion
from .firestore_sync import (
    sync_medicamento_usuario_firestore,
    eliminar_medicamento_usuario_firestore,
    sync_derecho_peticion_firestore
)

from .forms import UsuarioAdminCreationForm, UsuarioAdminChangeForm


class UsuarioAdmin(UserAdmin):
    model = Usuario
    add_form = UsuarioAdminCreationForm
    form = UsuarioAdminChangeForm

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Información Personal (Obligatoria)', {'fields': ('first_name', 'last_name', 'email', 'cedula', 'telefono', 'direccion')}),
        ('Asignación Institucional (Obligatoria)', {'fields': ('rol', 'eps')}),
        ('Biometría y Firebase (Opcional)', {
            'classes': ('collapse',),
            'fields': ('firebase_uid', 'face_encoding'),
        }),
        ('Permisos', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Fechas Importantes', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        ('Crear Nuevo Usuario — Datos Obligatorios', {
            'classes': ('wide',),
            'fields': (
                'username',
                'first_name',
                'last_name',
                'email',
                'cedula',
                'telefono',
                'direccion',
                'rol',
                'eps',
                'password1',
                'password2',
            ),
        }),
        ('Campos Opcionales', {
            'classes': ('collapse',),
            'fields': ('firebase_uid', 'face_encoding'),
        }),
    )

    list_display = ['email', 'username', 'full_name', 'cedula', 'telefono', 'rol_badge', 'eps', 'is_staff_badge']
    list_filter = ['rol', 'eps', 'is_staff', 'is_superuser', 'is_active']
    search_fields = ['email', 'username', 'first_name', 'last_name', 'cedula']
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
    list_display = ('nombre_comercial', 'nombre_generico', 'laboratorio', 'concentracion', 'requiere_formula_badge')
    search_fields = ('nombre_comercial', 'nombre_generico', 'laboratorio')

    @admin.display(description='Fórmula Médica')
    def requiere_formula_badge(self, obj):
        if getattr(obj, 'requiere_formula', False):
            return format_html('<span class="badge-admin badge-danger">{}</span>', 'Requerida')
        return format_html('<span class="badge-admin badge-success">{}</span>', 'Venta Libre')


@admin.register(MedicamentoUsuario)
class MedicamentoUsuarioAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'medicamento', 'dosis', 'cantidad_prescrita', 'fuente_badge', 'activo', 'fecha_asignacion')
    list_filter = ('fuente_asignacion', 'activo', 'fecha_asignacion')
    search_fields = ('usuario__username', 'usuario__first_name', 'usuario__last_name', 'usuario__cedula', 'medicamento__nombre_comercial', 'medicamento__nombre_generico')
    autocomplete_fields = ('usuario', 'medicamento')

    @admin.display(description='Fuente')
    def fuente_badge(self, obj):
        colores = {
            'ia_formula': 'badge-info',
            'eps_manual': 'badge-success',
            'admin': 'badge-warning',
        }
        cls = colores.get(obj.fuente_asignacion, 'badge-secondary')
        return format_html('<span class="badge-admin {}">{}</span>', cls, obj.get_fuente_asignacion_display())

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        sync_medicamento_usuario_firestore(obj)

    def delete_model(self, request, obj):
        eliminar_medicamento_usuario_firestore(obj.usuario_id, obj.medicamento_id, obj.usuario.firebase_uid)
        super().delete_model(request, obj)


@admin.register(DerechoPeticion)
class DerechoPeticionAdmin(admin.ModelAdmin):
    list_display = ('numero_radicado', 'usuario', 'medicamento', 'sede', 'estado_badge', 'fecha_radicacion', 'fecha_respuesta', 'atendido_por')
    list_filter = ('estado', 'fecha_radicacion', 'sede')
    search_fields = ('numero_radicado', 'usuario__username', 'usuario__first_name', 'usuario__last_name', 'usuario__cedula', 'medicamento__nombre_comercial')
    autocomplete_fields = ('usuario', 'medicamento', 'sede')
    actions = ['marcar_como_entregado', 'marcar_en_tramite']

    @admin.display(description='Estado')
    def estado_badge(self, obj):
        colores = {
            'radicado': 'badge-warning',
            'en_tramite': 'badge-info',
            'entregado': 'badge-success',
            'rechazado': 'badge-danger',
            'cancelado': 'badge-secondary',
        }
        cls = colores.get(obj.estado, 'badge-secondary')
        return format_html('<span class="badge-admin {}">{}</span>', cls, obj.get_estado_display())

    @admin.action(description='Marcar seleccionados como ENTREGADO (Resuelto por Farmacéutico/EPS)')
    def marcar_como_entregado(self, request, queryset):
        actualizados = 0
        for peticion in queryset:
            peticion.estado = 'entregado'
            peticion.fecha_respuesta = timezone.now()
            peticion.atendido_por = request.user
            peticion.save()
            sync_derecho_peticion_firestore(peticion)
            actualizados += 1
        self.message_user(request, f"{actualizados} derecho(s) de petición marcado(s) como ENTREGADOS. Se desbloqueó la opción para el paciente en futuras ocasiones.")

    @admin.action(description='Marcar seleccionados como EN TRÁMITE')
    def marcar_en_tramite(self, request, queryset):
        actualizados = 0
        for peticion in queryset:
            peticion.estado = 'en_tramite'
            peticion.atendido_por = request.user
            peticion.save()
            sync_derecho_peticion_firestore(peticion)
            actualizados += 1
        self.message_user(request, f"{actualizados} derecho(s) de petición marcado(s) EN TRÁMITE.")

    def save_model(self, request, obj, form, change):
        if not obj.atendido_por and request.user.is_authenticated:
            obj.atendido_por = request.user
        if obj.estado == 'entregado' and not obj.fecha_respuesta:
            obj.fecha_respuesta = timezone.now()
        super().save_model(request, obj, form, change)
        sync_derecho_peticion_firestore(obj)