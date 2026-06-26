from django.db import models
from Farmacia.models import Medicamento


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