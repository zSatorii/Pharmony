from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import Pedido
from turnos.models import Turno, ItemEntregaTurno
from turnos.decorators import eps_required


@login_required
def mis_pedidos(request):
    """Listado de pedidos del usuario autenticado."""
    pedidos = Pedido.objects.filter(turno__usuario=request.user).select_related(
        'turno', 'turno__sede', 'turno__medicamento'
    ).prefetch_related('turno__items_entregados__medicamento').order_by('-fecha_creacion')
    
    return render(request, 'pedidos/mis_pedidos.html', {
        'pedidos': pedidos,
        'user_name': request.user.nombre_para_mostrar(),
        'user_initials': (request.user.first_name[:1] + request.user.last_name[:1]).upper() if request.user.first_name and request.user.last_name else request.user.username[:2].upper()
    })


def seguimiento_pedido(request, codigo=None):
    """
    Rastreo en tiempo real de un pedido mediante su código de ticket (TRN-XXXXXXXX).
    Accesible con o sin sesión (útil para consultas rápidas con el código de factura).
    """
    codigo_busqueda = codigo or request.GET.get('codigo', '').strip().upper()
    pedido = None
    turno = None
    items_entregados = []
    error_msg = None

    if codigo_busqueda:
        turno = Turno.objects.filter(codigo_ticket__iexact=codigo_busqueda).first()
        if turno:
            # Si el turno está aprobado/finalizado y aún no tiene pedido creado, crearlo
            if turno.estado in ('correcto', 'finalizado'):
                pedido, _ = Pedido.objects.get_or_create(turno=turno, defaults={'estado': 'preparando'})
            else:
                pedido = getattr(turno, 'pedido', None)

            items_entregados = list(turno.items_entregados.select_related('medicamento').all())
        else:
            error_msg = f"No se encontró ningún pedido o turno con el código '{codigo_busqueda}'."

    # Determinar paso activo para la línea de tiempo
    paso_progreso = 1
    porcentaje = 33
    if pedido:
        if pedido.estado == 'preparando':
            paso_progreso = 1
            porcentaje = 33
        elif pedido.estado == 'en_camino':
            paso_progreso = 2
            porcentaje = 66
        elif pedido.estado == 'entregado':
            paso_progreso = 3
            porcentaje = 100

    return render(request, 'pedidos/seguimiento.html', {
        'codigo_busqueda': codigo_busqueda,
        'pedido': pedido,
        'turno': turno,
        'items_entregados': items_entregados,
        'paso_progreso': paso_progreso,
        'porcentaje': porcentaje,
        'error_msg': error_msg,
    })


@eps_required
def actualizar_estado_pedido(request, pedido_id):
    """Permite al personal de EPS o Administrador cambiar el estado del pedido."""
    pedido = get_object_or_404(Pedido, id=pedido_id)
    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        notas = request.POST.get('notas', '').strip()
        if nuevo_estado in dict(Pedido.ESTADOS):
            pedido.estado = nuevo_estado
            if notas:
                pedido.notas = notas
            if nuevo_estado == 'entregado' and not pedido.fecha_entrega:
                pedido.fecha_entrega = timezone.now()
            pedido.save()
            messages.success(request, f"Estado del pedido {pedido.turno.codigo_ticket} actualizado a '{pedido.get_estado_display()}'.")
    return redirect('pedidos:seguimiento_con_codigo', codigo=pedido.turno.codigo_ticket)
