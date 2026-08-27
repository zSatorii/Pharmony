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

    def save(self, *args, **kwargs):
        if self.codigo_cum:
            self.codigo_cum = self.codigo_cum.strip().upper()
        super().save(*args, **kwargs)    

    def __str__(self):
        return f"{self.nombre_comercial} ({self.nombre_generico})"
    
class Usuario(AbstractUser):
    telefono = models.CharField(max_length=20, blank=True, null=True, verbose_name="Teléfono")
    cedula = models.CharField(max_length=20, blank=True, null=True, verbose_name="Cédula/Documento")
    direccion = models.CharField(max_length=200, blank=True, null=True, verbose_name="Dirección")
    firebase_uid = models.CharField(max_length=255, unique=True, blank=True, null=True, verbose_name="Firebase UID")
    face_encoding = models.TextField(blank=True, null=True, verbose_name="Face Encoding")
    
    ROLES = [
        ('admin', 'Administrador'),
        ('cliente', 'Cliente'),
        ('eps', 'EPS')
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

    def nombre_para_mostrar(self):
        nombre_completo = f"{self.first_name} {self.last_name}".strip()
        return nombre_completo or self.username


class MedicamentoUsuario(models.Model):
    FUENTES = [
        ('ia_formula', 'Escaneo IA (Fórmula Médica)'),
        ('eps_manual', 'Asignación EPS / Farmacéutico'),
        ('admin', 'Administrador'),
    ]

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name='medicamentos_asignados',
        verbose_name="Paciente"
    )
    medicamento = models.ForeignKey(
        Medicamento,
        on_delete=models.CASCADE,
        related_name='usuarios_asignados',
        verbose_name="Medicamento"
    )
    dosis = models.CharField(max_length=150, blank=True, null=True, verbose_name="Dosis / Frecuencia")
    cantidad_prescrita = models.CharField(max_length=100, blank=True, null=True, verbose_name="Cantidad prescrita")
    fuente_asignacion = models.CharField(max_length=20, choices=FUENTES, default='ia_formula', verbose_name="Fuente de Asignación")
    activo = models.BooleanField(default=True, verbose_name="Tratamiento Activo")
    fecha_asignacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Asignación")
    firestore_id = models.CharField(max_length=100, blank=True, null=True, verbose_name="Firestore ID")

    class Meta:
        db_table = "medicamentos_usuario"
        verbose_name = "Medicamento Asignado a Paciente"
        verbose_name_plural = "Medicamentos Asignados a Pacientes"
        unique_together = ('usuario', 'medicamento')

    def __str__(self):
        return f"{self.usuario.get_full_name() or self.usuario.username} -> {self.medicamento.nombre_comercial}"


class DerechoPeticion(models.Model):
    ESTADOS = [
        ('radicado', 'Radicado'),
        ('en_tramite', 'En Trámite'),
        ('entregado', 'Entregado por EPS (Resuelto)'),
        ('rechazado', 'Rechazado'),
        ('cancelado', 'Cancelado'),
    ]

    numero_radicado = models.CharField(max_length=30, unique=True, verbose_name="Número de Radicado")
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name='derechos_peticion',
        verbose_name="Paciente"
    )
    medicamento = models.ForeignKey(
        Medicamento,
        on_delete=models.CASCADE,
        related_name='derechos_peticion',
        verbose_name="Medicamento Reclamado"
    )
    sede = models.ForeignKey(
        'epsinventario.Sede',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='derechos_peticion',
        verbose_name="Sede donde acudió"
    )
    estado = models.CharField(max_length=20, choices=ESTADOS, default='radicado', verbose_name="Estado de la Petición")
    fecha_radicacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Radicación")
    fecha_respuesta = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Respuesta/Entrega")
    observaciones_eps = models.TextField(blank=True, null=True, verbose_name="Observaciones de la EPS / Farmacéutico")
    atendido_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='peticiones_gestionadas',
        verbose_name="Farmacéutico / Personal que atendió"
    )
    firestore_id = models.CharField(max_length=100, blank=True, null=True, verbose_name="Firestore ID")

    class Meta:
        db_table = "derechos_peticion"
        verbose_name = "Derecho de Petición"
        verbose_name_plural = "Derechos de Petición"
        ordering = ['-fecha_radicacion']

    def __str__(self):
        return f"{self.numero_radicado} - {self.usuario.username} ({self.medicamento.nombre_comercial}) [{self.get_estado_display()}]"