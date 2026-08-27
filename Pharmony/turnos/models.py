from django.db import models
from django.conf import settings
from epsinventario.models import Sede, Eps, SolicitudMedicamento
from Farmacia.models import Medicamento
from django.core.exceptions import ValidationError


EXTENSIONES_DOCUMENTO_PERMITIDAS = ('.pdf', '.docx', '.jpg', '.jpeg', '.png', '.webp')


def validar_extension_documento(archivo):
    nombre = archivo.name.lower()
    if not nombre.endswith(EXTENSIONES_DOCUMENTO_PERMITIDAS):
        raise ValidationError('Solo se permiten archivos PDF, DOCX o imágenes (JPG, PNG, WEBP).')


class AuxiliarSede(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sedes_habilitadas')
    sede = models.ForeignKey(Sede, on_delete=models.CASCADE, related_name='auxiliares')
    activo = models.BooleanField(default=True)
    fecha_asignacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('usuario', 'sede')

    def __str__(self):
        return f"{self.usuario.username} - {self.sede.nombre}"


class Caja(models.Model):
    auxiliar = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cajas')
    sede = models.ForeignKey(Sede, on_delete=models.CASCADE, related_name='cajas')
    abierta = models.BooleanField(default=True)
    fecha_apertura = models.DateTimeField(auto_now_add=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    firestore_id = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"Caja {self.id} - {self.auxiliar.username} - {self.sede.nombre}"


class Turno(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('en_atencion', 'En atención'),
        ('correcto', 'Aprobado'),
        ('rechazado', 'Rechazado'),
        ('finalizado', 'Finalizado'),
        ('cancelado', 'Cancelado'),
    ]

    codigo_ticket = models.CharField(max_length=20, unique=True, editable=False)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='turnos')
    sede = models.ForeignKey(Sede, on_delete=models.CASCADE, related_name='turnos')
    medicamento = models.ForeignKey(Medicamento, on_delete=models.CASCADE, related_name='turnos')
    solicitud = models.OneToOneField(
        SolicitudMedicamento, on_delete=models.CASCADE, related_name='turno', null=True, blank=True
    )
    auxiliar_asignado = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='turnos_atendidos'
    )
    caja = models.ForeignKey(Caja, on_delete=models.SET_NULL, null=True, blank=True, related_name='turnos')

    formula_medica = models.FileField(upload_to='turnos/formulas/', validators=[validar_extension_documento])
    cedula_ciudadania = models.FileField(upload_to='turnos/cedulas/', validators=[validar_extension_documento])
    ciudad_envio = models.CharField(max_length=100, blank=True)
    direccion_envio = models.CharField(max_length=255)
    
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='pendiente')
    motivo_estado = models.TextField(blank=True, null=True)
    cantidad_entregada = models.PositiveIntegerField(null=True, blank=True)

    posicion_cola = models.PositiveIntegerField(default=0)
    firestore_id = models.CharField(max_length=100, blank=True, null=True)

    resultado_ia = models.JSONField(null=True, blank=True)
    cedula_detectada_ia = models.CharField(max_length=30, blank=True, null=True)
    paciente_detectado_ia = models.CharField(max_length=150, blank=True, null=True)
    medico_detectado_ia = models.CharField(max_length=150, blank=True, null=True)

    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    fecha_inicio_atencion = models.DateTimeField(null=True, blank=True)
    fecha_finalizacion = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.codigo_ticket:
            import uuid
            self.codigo_ticket = f"TRN-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.codigo_ticket} - {self.usuario.username} ({self.estado})"


class ItemEntregaTurno(models.Model):
    turno = models.ForeignKey(Turno, on_delete=models.CASCADE, related_name='items_entregados')
    medicamento = models.ForeignKey(Medicamento, on_delete=models.CASCADE, related_name='entregas_turno')
    cantidad = models.PositiveIntegerField(default=1)
    indicaciones = models.CharField(max_length=255, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.cantidad}x {self.medicamento.nombre_comercial} (Turno {self.turno.codigo_ticket})"


class MensajeTurno(models.Model):
    turno = models.ForeignKey(Turno, on_delete=models.CASCADE, related_name='mensajes')
    remitente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    contenido = models.TextField(blank=True)
    archivo = models.FileField(upload_to='turnos/chat_adjuntos/', blank=True, null=True, validators=[validar_extension_documento])
    fecha = models.DateTimeField(auto_now_add=True)
    leido = models.BooleanField(default=False)

    class Meta:
        ordering = ['fecha']