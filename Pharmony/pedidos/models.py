from django.db import models
from turnos.models import Turno


class Pedido(models.Model):
    ESTADOS = [
        ('preparando', 'Preparando'),
        ('en_camino', 'En camino'),
        ('entregado', 'Entregado'),
    ]
    turno = models.OneToOneField(Turno, on_delete=models.CASCADE, related_name='pedido')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='preparando')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    fecha_entrega = models.DateTimeField(null=True, blank=True)
    notas = models.TextField(blank=True)

    def __str__(self):
        return f"Pedido {self.turno.codigo_ticket} — {self.get_estado_display()}"