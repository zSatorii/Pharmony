from django.db import models
from django.conf import settings
from Farmacia.models import Medicamento
from .geo import coords_para_ciudad
from django.utils import timezone

class Eps(models.Model):
    nombre = models.CharField(max_length=150)
    nit = models.CharField(max_length=20, unique=True)
    direccion = models.CharField(max_length=200, blank=True)
    ciudad = models.CharField(max_length=100, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    estado = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

class Sede(models.Model):
    eps = models.ForeignKey(Eps, on_delete=models.CASCADE, related_name='sedes')
    nombre = models.CharField(max_length=150)
    direccion = models.CharField(max_length=200, blank=True)
    ciudad = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    estado = models.BooleanField(default=True)

    latitud = models.FloatField(null=True, blank=True)
    longitud = models.FloatField(null=True, blank=True)

    hora_apertura = models.TimeField(null=True, blank=True)
    hora_cierre = models.TimeField(null=True, blank=True)
    atiende_fines_semana = models.BooleanField(default=False)

    @property
    def esta_abierta_ahora(self):
        if not self.hora_apertura or not self.hora_cierre:
            return None
        ahora = timezone.localtime()
        if ahora.weekday() >= 5 and not self.atiende_fines_semana:
            return False
        return self.hora_apertura <= ahora.time() <= self.hora_cierre

    def save(self, *args, **kwargs):
        if self.latitud is None or self.longitud is None:
            lat, lng = coords_para_ciudad(self.ciudad)
            self.latitud = self.latitud if self.latitud is not None else lat
            self.longitud = self.longitud if self.longitud is not None else lng
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombre} ({self.ciudad})"

class InventarioSede(models.Model):
    sede = models.ForeignKey(Sede, on_delete=models.CASCADE, related_name='inventarios')
    medicamento = models.ForeignKey(Medicamento, on_delete=models.CASCADE, related_name='inventarios')
    cantidad_disponible = models.PositiveIntegerField(default=0)
    cantidad_minima = models.PositiveIntegerField(default=10)
    lote = models.CharField(max_length=50, blank=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    ultima_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('sede', 'medicamento', 'lote')

    @property
    def estado_stock(self):
        if self.cantidad_disponible == 0:
            return 'agotado'
        elif self.cantidad_disponible <= self.cantidad_minima:
            return 'stock_bajo'
        return 'disponible'

    def __str__(self):
        return f"{self.medicamento.nombre_comercial} - {self.sede.nombre}"

class SolicitudMedicamento(models.Model):
    """Cuando un cliente pide un medicamento desde el dashboard, queda registrado aquí."""
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('atendida', 'Atendida'),
        ('rechazada', 'Rechazada'),
    ]

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='solicitudes_medicamento')
    medicamento = models.ForeignKey(Medicamento, on_delete=models.CASCADE, related_name='solicitudes')
    sede = models.ForeignKey(Sede, on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitudes')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    fecha_solicitud = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.usuario} solicitó {self.medicamento.nombre_comercial} ({self.estado})"