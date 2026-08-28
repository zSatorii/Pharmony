import datetime
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache

# Plazo legal de respuesta y entrega fijado por la Ley 1755 de 2015 (15 días hábiles / 21 días calendario)
DIAS_COOLDOWN_DERECHO_PETICION = 15
MAX_DESCARGAS_POR_DIA = 5


def calcular_fecha_limite_eps(fecha_radicacion, dias=DIAS_COOLDOWN_DERECHO_PETICION):
    """
    Calcula la fecha límite de vencimiento del término legal de la EPS.
    """
    if timezone.is_naive(fecha_radicacion):
        fecha_radicacion = timezone.make_aware(fecha_radicacion)
    return fecha_radicacion + timedelta(days=dias)


def verificar_cooldown_derecho_peticion(usuario, medicamento):
    """
    Verifica si el usuario tiene un límite activo (cooldown legal de 15 días)
    para radicar o solicitar un nuevo Derecho de Petición sobre el medicamento.

    Retorna un diccionario con:
    - en_cooldown: bool (True si no puede pedir otro todavía)
    - fecha_disponible: str ('DD/MM/YYYY')
    - dias_restantes: int
    - radicado: str
    - estado: str
    - fecha_radicacion: str
    - mensaje: str
    """
    if not usuario or not getattr(usuario, 'is_authenticated', False):
        return {
            'en_cooldown': False,
            'fecha_disponible': None,
            'dias_restantes': 0,
            'radicado': None,
            'estado': None,
            'fecha_radicacion': None,
            'mensaje': None,
        }

    from .models import DerechoPeticion

    # Buscar la última petición activa o radicada recientemente
    peticion = DerechoPeticion.objects.filter(
        usuario=usuario,
        medicamento=medicamento,
        estado__in=['radicado', 'en_tramite']
    ).order_by('-fecha_radicacion').first()

    if not peticion:
        return {
            'en_cooldown': False,
            'fecha_disponible': None,
            'dias_restantes': 0,
            'radicado': None,
            'estado': None,
            'fecha_radicacion': None,
            'mensaje': None,
        }

    fecha_rad = peticion.fecha_radicacion
    fecha_limite = calcular_fecha_limite_eps(fecha_rad)
    ahora = timezone.now()

    if ahora < fecha_limite:
        delta = fecha_limite - ahora
        dias_restantes = max(1, delta.days + (1 if delta.seconds > 0 else 0))
        fecha_disp_str = fecha_limite.strftime('%d/%m/%Y')
        fecha_rad_str = fecha_rad.strftime('%d/%m/%Y')

        mensaje = (
            f"Ya tienes un Derecho de Petición en trámite con radicado {peticion.numero_radicado} "
            f"(radicado el {fecha_rad_str}). El plazo legal de respuesta de la EPS es de "
            f"{DIAS_COOLDOWN_DERECHO_PETICION} días. Podrás solicitar uno nuevo a partir del {fecha_disp_str} "
            f"(faltan {dias_restantes} días)."
        )

        return {
            'en_cooldown': True,
            'fecha_disponible': fecha_disp_str,
            'dias_restantes': dias_restantes,
            'radicado': peticion.numero_radicado,
            'estado': peticion.get_estado_display(),
            'fecha_radicacion': fecha_rad_str,
            'peticion_id': peticion.id,
            'mensaje': mensaje,
        }

    return {
        'en_cooldown': False,
        'fecha_disponible': None,
        'dias_restantes': 0,
        'radicado': peticion.numero_radicado,
        'estado': peticion.get_estado_display(),
        'fecha_radicacion': fecha_rad.strftime('%d/%m/%Y'),
        'peticion_id': peticion.id,
        'mensaje': None,
    }


def verificar_limite_descargas(usuario_id, medicamento_id):
    """
    Control de tasa de descargas: Evita descargas infinitas o abusivas
    permitiendo hasta MAX_DESCARGAS_POR_DIA descargas diarias por usuario y medicamento.
    """
    key = f"dp_downloads_{usuario_id}_{medicamento_id}_{timezone.now().strftime('%Y%m%d')}"
    descargas = cache.get(key, 0)
    if descargas >= MAX_DESCARGAS_POR_DIA:
        return False, f"Has alcanzado el límite diario de {MAX_DESCARGAS_POR_DIA} descargas para este documento. Consulta el radicado con tu EPS."
    return True, None


def registrar_descarga(usuario_id, medicamento_id):
    """
    Registra una descarga exitosa incrementando el contador en caché con TTL de 24 horas.
    """
    key = f"dp_downloads_{usuario_id}_{medicamento_id}_{timezone.now().strftime('%Y%m%d')}"
    descargas = cache.get(key, 0)
    cache.set(key, descargas + 1, timeout=86400)
