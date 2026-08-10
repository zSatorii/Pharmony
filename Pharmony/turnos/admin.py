from django.contrib import admin
from django.utils.html import format_html
from .models import AuxiliarSede, Caja, Turno, MensajeTurno
from .firestore_sync import sync_auxiliar_sede_a_firestore, eliminar_auxiliar_sede_de_firestore


@admin.register(AuxiliarSede)
class AuxiliarSedeAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'sede', 'activo_badge', 'fecha_asignacion')
    list_filter = ('sede', 'activo')
    search_fields = ('usuario__username', 'usuario__email', 'sede__nombre')

    @admin.display(description='Estado')
    def activo_badge(self, obj):
        if obj.activo:
            return format_html('<span class="badge-admin badge-success">{}</span>', 'Activo')
        return format_html('<span class="badge-admin badge-danger">{}</span>', 'Inactivo')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        sync_auxiliar_sede_a_firestore(obj)

    def delete_model(self, request, obj):
        usuario_id, sede_id = obj.usuario_id, obj.sede_id
        super().delete_model(request, obj)
        eliminar_auxiliar_sede_de_firestore(usuario_id, sede_id)


@admin.register(Caja)
class CajaAdmin(admin.ModelAdmin):
    list_display = ('auxiliar', 'sede', 'estado_caja', 'fecha_apertura', 'fecha_cierre')
    list_filter = ('sede', 'abierta')
    search_fields = ('auxiliar__username',)

    @admin.display(description='Caja')
    def estado_caja(self, obj):
        if obj.abierta:
            return format_html('<span class="badge-admin badge-success">{}</span>', 'Abierta')
        return format_html('<span class="badge-admin badge-danger">{}</span>', 'Cerrada')


@admin.register(Turno)
class TurnoAdmin(admin.ModelAdmin):
    list_display = ('codigo_ticket', 'usuario', 'sede', 'medicamento', 'estado_badge', 'auxiliar_asignado', 'fecha_solicitud')
    list_filter = ('estado', 'sede')
    search_fields = ('codigo_ticket', 'usuario__username', 'usuario__email')
    readonly_fields = ('codigo_ticket', 'fecha_solicitud', 'fecha_inicio_atencion', 'fecha_finalizacion')

    @admin.display(description='Estado Turno')
    def estado_badge(self, obj):
        e = str(obj.estado).lower()
        if 'complet' in e or 'atendido' in e:
            return format_html('<span class="badge-admin badge-success">{}</span>', obj.estado)
        elif 'espera' in e or 'pendiente' in e:
            return format_html('<span class="badge-admin badge-warning">{}</span>', obj.estado)
        return format_html('<span class="badge-admin badge-info">{}</span>', obj.estado)


@admin.register(MensajeTurno)
class MensajeTurnoAdmin(admin.ModelAdmin):
    list_display = ('turno', 'remitente', 'fecha', 'leido_badge')
    search_fields = ('turno__codigo_ticket', 'remitente__username')

    @admin.display(description='Leído')
    def leido_badge(self, obj):
        if obj.leido:
            return format_html('<span class="badge-admin badge-success">{}</span>', 'Leído')
        return format_html('<span class="badge-admin badge-warning">{}</span>', 'Pendiente')