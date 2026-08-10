from django.contrib import admin
from django.utils.html import format_html
from .models import Eps, Sede, InventarioSede
from .views import (
    _sync_eps_firestore,
    _sync_sede_firestore,
    _sync_inventario_firestore,
    _eliminar_doc_firestore,
)

@admin.register(Eps)
class EpsAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'nit', 'ciudad', 'estado_badge')
    search_fields = ('nombre', 'nit')
    list_filter = ('estado', 'ciudad')

    @admin.display(description='Estado')
    def estado_badge(self, obj):
        if str(obj.estado).lower() in ['activo', 'true', '1']:
            return format_html('<span class="badge-admin badge-success">{}</span>', 'Activo')
        return format_html('<span class="badge-admin badge-danger">{}</span>', 'Inactivo')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        _sync_eps_firestore(obj)

    def delete_model(self, request, obj):
        eps_id = obj.id
        super().delete_model(request, obj)
        _eliminar_doc_firestore("eps", eps_id)


@admin.register(Sede)
class SedeAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'eps', 'ciudad', 'estado_badge')
    list_filter = ('eps', 'ciudad', 'estado')
    search_fields = ('nombre', 'ciudad')

    @admin.display(description='Estado')
    def estado_badge(self, obj):
        if str(obj.estado).lower() in ['activo', 'true', '1']:
            return format_html('<span class="badge-admin badge-success">{}</span>', 'Activo')
        return format_html('<span class="badge-admin badge-danger">{}</span>', 'Inactivo')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        _sync_sede_firestore(obj)

    def delete_model(self, request, obj):
        sede_id = obj.id
        super().delete_model(request, obj)
        _eliminar_doc_firestore("sedes", sede_id)


@admin.register(InventarioSede)
class InventarioSedeAdmin(admin.ModelAdmin):
    list_display = ('medicamento', 'sede', 'cantidad_disponible', 'estado_stock_badge')
    list_filter = ('sede',)
    search_fields = ('medicamento__nombre_comercial', 'lote')

    @admin.display(description='Estado Stock')
    def estado_stock_badge(self, obj):
        estado = str(obj.estado_stock).lower()
        if 'dispon' in estado:
            return format_html('<span class="badge-admin badge-success">{}</span>', obj.estado_stock)
        elif 'bajo' in estado:
            return format_html('<span class="badge-admin badge-warning">{}</span>', obj.estado_stock)
        return format_html('<span class="badge-admin badge-danger">{}</span>', obj.estado_stock)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        _sync_inventario_firestore(obj)

    def delete_model(self, request, obj):
        inv_id = obj.id
        super().delete_model(request, obj)
        _eliminar_doc_firestore("inventario_sedes", inv_id)