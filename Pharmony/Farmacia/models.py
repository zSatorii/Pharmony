from django.db import models


class Medicamento(models.Model):
    codigo_cum = models.CharField(max_length=50, unique=True)
    nombre_generico = models.CharField(max_length=200)
    nombre_comercial = models.CharField(max_length=200)
    laboratorio = models.CharField(max_length=200)

    concentracion = models.CharField(max_length=100)
    forma_farmaceutica = models.CharField(max_length=100)

    descripcion = models.TextField()
    uso_indicado = models.TextField()
    efectos_secundarios = models.TextField()

    requiere_formula = models.BooleanField(default=False)

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "medicamentos"
        verbose_name = "Medicamento"
        verbose_name_plural = "Medicamentos"

    def __str__(self):
        return f"{self.nombre_comercial} ({self.nombre_generico})"