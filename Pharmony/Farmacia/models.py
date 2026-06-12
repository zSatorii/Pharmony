from django.db import models
from django.contrib.auth.models import AbstractUser


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

    def __str__(self):
        return f"{self.username} - {self.get_rol_display()}"
