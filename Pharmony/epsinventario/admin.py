from django.contrib import admin
from .models import Eps, Sede, InventarioSede
from .views import (
    _sync_eps_firestore,
    _sync_sede_firestore,
    _sync_inventario_firestore,
    _eliminar_doc_firestore,
)


@admin.register(Eps)
class EpsAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'nit', 'ciudad', 'estado')
    search_fields = ('nombre', 'nit')
    list_filter = ('estado', 'ciudad')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        _sync_eps_firestore(obj)

    def delete_model(self, request, obj):
        eps_id = obj.id
        super().delete_model(request, obj)
        _eliminar_doc_firestore("eps", eps_id)


@admin.register(Sede)
class SedeAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'eps', 'ciudad', 'estado')
    list_filter = ('eps', 'ciudad', 'estado')
    search_fields = ('nombre', 'ciudad')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        _sync_sede_firestore(obj)

    def delete_model(self, request, obj):
        sede_id = obj.id
        super().delete_model(request, obj)
        _eliminar_doc_firestore("sedes", sede_id)


@admin.register(InventarioSede)
class InventarioSedeAdmin(admin.ModelAdmin):
    list_display = ('medicamento', 'sede', 'cantidad_disponible', 'estado_stock')
    list_filter = ('sede',)
    search_fields = ('medicamento__nombre_comercial', 'lote')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        _sync_inventario_firestore(obj)

    def delete_model(self, request, obj):
        inv_id = obj.id
        super().delete_model(request, obj)
        _eliminar_doc_firestore("inventario_sedes", inv_id)