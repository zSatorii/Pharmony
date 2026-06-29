from django.db import models
from django.contrib.auth.models import AbstractUser

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
    
class Usuario(AbstractUser):
    telefono = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono")
    firebase_uid = models.CharField(max_length=255, unique=True, blank=True, null=True, verbose_name="Firebase UID")
    
    # Ejemplo de un campo de roles
    ROLES = [
        ('admin', 'Administrador'),
        ('cliente', 'Cliente'),
        ('farmaceutico', 'Farmacéutico')
    ]
    rol = models.CharField(max_length=20, choices=ROLES, default='cliente')

    eps = models.ForeignKey(
        'epsinventario.Eps',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='personal',
        verbose_name="EPS asignada"
    )

    def __str__(self):
        return f"{self.username} - {self.get_rol_display()}"

