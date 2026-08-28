from django.contrib import admin
from .models import Pedido


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('turno', 'estado', 'fecha_creacion', 'fecha_entrega')
    list_filter = ('estado',)
    search_fields = ('turno__codigo_ticket', 'turno__usuario__username')