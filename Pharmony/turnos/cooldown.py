from datetime import timedelta
from django.utils import timezone

DIAS_COOLDOWN_RECLAMO = 30

def verificar_cooldown_medicamento(usuario, medicamento):
    """
    Retorna una tupla (en_cooldown: bool, fecha_disponible_str: str or None).
    
    Regla estricta de negocio:
    - SOLO aplica cooldown de 30 días si el medicamento fue EFECTIVAMENTE ENTREGADO
      y aprobado (estado 'correcto' o 'finalizado') con cantidad > 0.
    - Si el turno fue RECHAZADO, CANCELADO, o si el medicamento no fue entregado
      por falta de stock u otra razón (no aparece en ItemEntregaTurno),
      NO HAY COOLDOWN y el usuario puede solicitar turno nuevamente de inmediato.
    """
    if not usuario or not getattr(usuario, 'is_authenticated', False):
        return False, None

    from turnos.models import Turno, ItemEntregaTurno

    # 1. Verificar en ItemEntregaTurno de turnos aprobados / finalizados
    ultimo_item = ItemEntregaTurno.objects.filter(
        turno__usuario=usuario,
        medicamento=medicamento,
        cantidad__gt=0,
        turno__estado__in=['correcto', 'finalizado']
    ).select_related('turno').order_by('-turno__fecha_finalizacion', '-fecha_creacion').first()

    # 2. Verificar turnos legacy donde la cantidad entregada confirma el despacho.
    ultimo_turno_legacy = Turno.objects.filter(
        usuario=usuario,
        medicamento=medicamento,
        estado__in=['correcto', 'finalizado'],
        cantidad_entregada__gt=0,
        items_entregados__isnull=True,
    ).order_by('-fecha_finalizacion', '-fecha_solicitud').first()

    fecha_base = None
    if ultimo_item:
        fecha_base = ultimo_item.turno.fecha_finalizacion or ultimo_item.fecha_creacion
    elif ultimo_turno_legacy:
        fecha_base = ultimo_turno_legacy.fecha_finalizacion or ultimo_turno_legacy.fecha_solicitud

    if fecha_base:
        disponible_desde = fecha_base + timedelta(days=DIAS_COOLDOWN_RECLAMO)
        if timezone.now() < disponible_desde:
            return True, disponible_desde.strftime('%d/%m/%Y')

    return False, None
