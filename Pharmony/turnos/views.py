import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.http import HttpResponseForbidden
from django.http import JsonResponse, FileResponse


from epsinventario.views import es_admin
from epsinventario.models import Sede, InventarioSede, SolicitudMedicamento
from Farmacia.models import Medicamento
from .models import Turno, AuxiliarSede, Caja, MensajeTurno, validar_extension_documento
from .forms import SolicitarTurnoForm
from .firestore_sync import sync_turno_a_firestore, sync_mensaje_a_firestore, sync_auxiliar_sede_a_firestore
from .decorators import eps_required
from firebase_admin import auth as firebase_auth


Usuario = get_user_model()

def _generar_firebase_token(user):
    if not user.firebase_uid:
        return None
    try:
        token_bytes = firebase_auth.create_custom_token(user.firebase_uid)
        return token_bytes.decode('utf-8') if isinstance(token_bytes, bytes) else token_bytes
    except Exception:
        return None

@login_required
def gestionar_auxiliares(request, sede_id):
    sede = get_object_or_404(Sede, id=sede_id)
    if not es_admin(request.user, sede):
        return HttpResponseForbidden("Solo un administrador puede gestionar los auxiliares de una sede.")

    candidatos = Usuario.objects.filter(rol='eps', eps_id=sede.eps_id).order_by('username') if sede.eps_id else Usuario.objects.none()
    habilitados_ids = set(AuxiliarSede.objects.filter(sede=sede, activo=True).values_list('usuario_id', flat=True))

    if request.method == 'POST':
        usuario = get_object_or_404(candidatos, id=request.POST.get('usuario_id'))
        accion = request.POST.get('accion')
        if accion == 'habilitar':
            aux, _ = AuxiliarSede.objects.update_or_create(usuario=usuario, sede=sede, defaults={'activo': True})
        elif accion == 'deshabilitar':
            aux, _ = AuxiliarSede.objects.update_or_create(usuario=usuario, sede=sede, defaults={'activo': False})
        else:
            aux = None
        if aux:
            sync_auxiliar_sede_a_firestore(aux)
        return redirect('turnos:gestionar_auxiliares', sede_id=sede.id)

    return render(request, 'turnos/gestionar_auxiliares.html', {
        'sede': sede, 'candidatos': candidatos, 'habilitados_ids': habilitados_ids,
    })


from epsinventario.geo import ciudades_cercanas

@login_required
def solicitar_turno(request, sede_id, medicamento_id):
    sede = get_object_or_404(Sede, id=sede_id, estado=True)
    medicamento = get_object_or_404(Medicamento, id=medicamento_id)

    inventario = InventarioSede.objects.filter(
        sede=sede, medicamento=medicamento, cantidad_disponible__gt=0
    ).first()
    if not inventario:
        messages.error(request, 'Este medicamento ya no está disponible en la sede seleccionada.')
        return redirect('dashboard_cliente')

    turno_activo = Turno.objects.filter(
        usuario=request.user
    ).exclude(
        estado__in=['correcto', 'rechazado', 'finalizado', 'cancelado']
    ).first()
    if turno_activo:
        messages.warning(request, 'Ya tienes un turno en proceso. No puedes solicitar otro hasta que finalice.')
        return redirect('turnos:ver_ticket', codigo=turno_activo.codigo_ticket)

    ciudades_permitidas = ciudades_cercanas(sede.ciudad, radio_km=40)

    if request.method == 'POST':
        form = SolicitarTurnoForm(request.POST, request.FILES, ciudades_permitidas=ciudades_permitidas)
        if form.is_valid():
            solicitud = SolicitudMedicamento.objects.create(
                usuario=request.user, medicamento=medicamento, sede=sede, estado='pendiente'
            )
            turno = form.save(commit=False)
            turno.usuario = request.user
            turno.sede = sede
            turno.medicamento = medicamento
            turno.solicitud = solicitud
            turno.posicion_cola = Turno.objects.filter(
                sede=sede, estado__in=['pendiente', 'en_atencion']
            ).count() + 1
            turno.save()

            sync_turno_a_firestore(turno)

            messages.success(request, f'Turno generado: {turno.codigo_ticket}')
            return redirect('turnos:ver_ticket', codigo=turno.codigo_ticket)
    else:
        form = SolicitarTurnoForm(initial={'ciudad_envio': sede.ciudad}, ciudades_permitidas=ciudades_permitidas)

    return render(request, 'turnos/solicitar_turno.html', {
        'form': form, 'sede': sede, 'medicamento': medicamento, 'inventario': inventario,
    })

@login_required
def ver_ticket(request, codigo):
    turno = get_object_or_404(Turno, codigo_ticket=codigo, usuario=request.user)
    if turno.estado in ('correcto', 'rechazado', 'finalizado', 'cancelado'):
        return redirect('turnos:factura_turno', codigo=turno.codigo_ticket)
    return render(request, 'turnos/ver_ticket.html', {
        'turno': turno, 'firebase_token': _generar_firebase_token(request.user),
    })

@login_required
def enviar_mensaje_usuario(request, codigo):
    turno = get_object_or_404(Turno, codigo_ticket=codigo, usuario=request.user)
    if request.method == 'POST' and turno.estado in ('pendiente', 'en_atencion'):
        contenido = request.POST.get('contenido', '').strip()
        archivo = request.FILES.get('archivo')
        if archivo:
            try:
                validar_extension_documento(archivo)
            except ValidationError as e:
                messages.error(request, e.message)
                archivo = None
        if contenido or archivo:
            msg = MensajeTurno.objects.create(turno=turno, remitente=request.user, contenido=contenido, archivo=archivo)
            sync_mensaje_a_firestore(turno, request.user, contenido, archivo_url=msg.archivo.url if msg.archivo else None)
    return redirect('turnos:ver_ticket', codigo=codigo)

@login_required
def estado_turno_json(request, codigo):
    """
    Polling temporal mientras conectamos el listener real de Firestore
    (Fase 5). Devuelve estado + mensajes para refrescar la pantalla de
    espera sin recargar la página completa.
    """
    turno = get_object_or_404(Turno, codigo_ticket=codigo, usuario=request.user)
    mensajes = [
        {'de': m.remitente.username, 'texto': m.contenido, 'fecha': m.fecha.strftime('%H:%M')}
        for m in turno.mensajes.all()
    ]
    return JsonResponse({
        'estado': turno.estado,
        'posicion_cola': turno.posicion_cola,
        'motivo_estado': turno.motivo_estado or '',
        'mensajes': mensajes,
    })


@login_required
def factura_turno(request, codigo):
    """
    Solo accesible si el turno ya está finalizado. Si el turno sigue
    activo, lo manda de vuelta al ticket (nunca deja 'reabrir' un
    turno ya cerrado desde otra pantalla intermedia).
    """
    turno = get_object_or_404(Turno, codigo_ticket=codigo, usuario=request.user)
    if turno.estado not in ('correcto', 'rechazado', 'finalizado', 'cancelado'):
        return redirect('turnos:ver_ticket', codigo=turno.codigo_ticket)
    return render(request, 'turnos/factura.html', {'turno': turno})


@login_required
def volver_dashboard(request, codigo):
    """
    Botón final de la factura. Cierra el turno como 'finalizado' de forma
    explícita y lo saca de la sala de espera para que no pueda volver
    a /turnos/ticket/<codigo>/ y generar conflicto con el auxiliar.
    """
    turno = get_object_or_404(Turno, codigo_ticket=codigo, usuario=request.user)
    if turno.estado in ('correcto', 'rechazado'):
        turno.estado = 'finalizado'
        turno.fecha_finalizacion = timezone.now()
        turno.save()
        sync_turno_a_firestore(turno)
    return redirect('dashboard_cliente')



#  administrador/auxiliar abrir caja

@eps_required
def seleccion_panel(request):
    """Pantalla de las 2 ventanas. Apunta aquí el redirect que hoy mandaba a rol='eps' directo al dashboard."""
    return render(request, 'turnos/seleccion_panel.html')


@eps_required
def marcar_tarjeta(request):
    sedes_habilitadas = Sede.objects.filter(
        auxiliares__usuario=request.user, auxiliares__activo=True, estado=True
    ).distinct()

    caja_abierta = Caja.objects.filter(auxiliar=request.user, abierta=True).first()
    if caja_abierta:
        return redirect('turnos:cola_turnos', sede_id=caja_abierta.sede.id)

    if request.method == 'POST':
        sede = get_object_or_404(sedes_habilitadas, id=request.POST.get('sede_id'))
        Caja.objects.create(auxiliar=request.user, sede=sede)
        return redirect('turnos:cola_turnos', sede_id=sede.id)

    if not sedes_habilitadas.exists():
        messages.warning(request, 'No estás habilitado en ninguna sede todavía. Pide al administrador que te asigne una.')

    return render(request, 'turnos/marcar_tarjeta.html', {'sedes': sedes_habilitadas})


@eps_required
def cola_turnos(request, sede_id):
    caja = get_object_or_404(Caja, auxiliar=request.user, sede_id=sede_id, abierta=True)

    turno_en_atencion = Turno.objects.filter(
        sede_id=sede_id, auxiliar_asignado=request.user, estado='en_atencion'
    ).first()
    if turno_en_atencion:
        return redirect('turnos:atender_turno', codigo=turno_en_atencion.codigo_ticket)

    cola = Turno.objects.filter(sede_id=sede_id, estado='pendiente').order_by('posicion_cola', 'fecha_solicitud')
    return render(request, 'turnos/cola_turnos.html', {
        'cola': cola, 'caja': caja, 'firebase_token': _generar_firebase_token(request.user),
    })

@eps_required
def tomar_siguiente_turno(request, sede_id):
    caja = get_object_or_404(Caja, auxiliar=request.user, sede_id=sede_id, abierta=True)
    siguiente = Turno.objects.filter(
        sede_id=sede_id, estado='pendiente'
    ).order_by('posicion_cola', 'fecha_solicitud').first()

    if not siguiente:
        messages.info(request, 'No hay turnos pendientes en este momento.')
        return redirect('turnos:cola_turnos', sede_id=sede_id)

    siguiente.estado = 'en_atencion'
    siguiente.auxiliar_asignado = request.user
    siguiente.caja = caja
    siguiente.fecha_inicio_atencion = timezone.now()
    siguiente.save()
    sync_turno_a_firestore(siguiente)
    return redirect('turnos:atender_turno', codigo=siguiente.codigo_ticket)

@eps_required
def atender_turno(request, codigo):
    turno = get_object_or_404(Turno, codigo_ticket=codigo, auxiliar_asignado=request.user, estado='en_atencion')

    if request.method == 'POST':
        accion = request.POST.get('accion')

        if accion == 'mensaje':
            contenido = request.POST.get('contenido', '').strip()
            archivo = request.FILES.get('archivo')
            if archivo:
                try:
                    validar_extension_documento(archivo)
                except ValidationError as e:
                    messages.error(request, e.message)
                    archivo = None
            if contenido or archivo:
                msg = MensajeTurno.objects.create(turno=turno, remitente=request.user, contenido=contenido, archivo=archivo)
                sync_mensaje_a_firestore(turno, request.user, contenido, archivo_url=msg.archivo.url if msg.archivo else None)

        elif accion == 'finalizar':
            estado_final = request.POST.get('estado_final')
            motivo = request.POST.get('motivo', '').strip()
            if estado_final in ('correcto', 'rechazado'):
                turno.estado = estado_final
                turno.motivo_estado = motivo
                turno.save()
                if turno.solicitud:
                    turno.solicitud.estado = 'atendida' if estado_final == 'correcto' else 'rechazada'
                    turno.solicitud.save()
                sync_turno_a_firestore(turno)
                messages.success(request, f'Turno {turno.codigo_ticket} marcado como {estado_final}.')
                return redirect('turnos:cola_turnos', sede_id=turno.sede.id)

        return redirect('turnos:atender_turno', codigo=codigo)

    return render(request, 'turnos/atender_turno.html', {
        'turno': turno, 'mensajes': turno.mensajes.all(), 'firebase_token': _generar_firebase_token(request.user),
    })

@eps_required
def cerrar_caja(request, sede_id):
    caja = get_object_or_404(Caja, auxiliar=request.user, sede_id=sede_id, abierta=True)
    if Turno.objects.filter(caja=caja, estado='en_atencion').exists():
        messages.error(request, 'Termina el turno en curso antes de cerrar caja.')
        return redirect('turnos:cola_turnos', sede_id=sede_id)
    caja.abierta = False
    caja.fecha_cierre = timezone.now()
    caja.save()
    return redirect('turnos:seleccion_panel')

@login_required
def mis_turnos(request):
    turnos = Turno.objects.filter(usuario=request.user).order_by('-fecha_solicitud')
    return render(request, 'turnos/mis_turnos.html', {'turnos': turnos})


@login_required
def factura_pdf(request, codigo):
    turno = get_object_or_404(Turno, codigo_ticket=codigo, usuario=request.user)
    if turno.estado not in ('correcto', 'rechazado', 'finalizado'):
        return redirect('turnos:ver_ticket', codigo=turno.codigo_ticket)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=60, leftMargin=60, topMargin=60, bottomMargin=60)
    styles = getSampleStyleSheet()

    style_title = ParagraphStyle('TituloFactura', parent=styles['Heading1'], fontName='Helvetica-Bold',
                                  fontSize=20, textColor=colors.HexColor('#052060'), alignment=1, spaceAfter=4)
    style_sub = ParagraphStyle('SubFactura', parent=styles['Normal'], fontName='Helvetica',
                                fontSize=11, textColor=colors.HexColor('#64748b'), alignment=1, spaceAfter=20)
    style_label = ParagraphStyle('Label', parent=styles['Normal'], fontName='Helvetica-Bold',
                                  fontSize=10, textColor=colors.HexColor('#475569'))
    style_value = ParagraphStyle('Value', parent=styles['Normal'], fontName='Helvetica',
                                  fontSize=10, textColor=colors.HexColor('#1e293b'))

    data = [
        [Paragraph('Estado final', style_label), Paragraph(turno.get_estado_display(), style_value)],
        [Paragraph('Motivo', style_label), Paragraph(turno.motivo_estado or '—', style_value)],
        [Paragraph('Sede', style_label), Paragraph(f"{turno.sede.nombre} ({turno.sede.ciudad})", style_value)],
        [Paragraph('Medicamento', style_label), Paragraph(turno.medicamento.nombre_comercial, style_value)],
        [Paragraph('Dirección de envío', style_label), Paragraph(f"{turno.direccion_envio}, {turno.ciudad_envio}", style_value)],
        [Paragraph('Atendido por', style_label), Paragraph(turno.auxiliar_asignado.nombre_para_mostrar() if turno.auxiliar_asignado else '—', style_value)],
        [Paragraph('Fecha de solicitud', style_label), Paragraph(turno.fecha_solicitud.strftime('%d/%m/%Y %H:%M'), style_value)],
        [Paragraph('Fecha de finalización', style_label), Paragraph(turno.fecha_finalizacion.strftime('%d/%m/%Y %H:%M') if turno.fecha_finalizacion else '—', style_value)],
    ]
    tabla = Table(data, colWidths=[150, 320])
    tabla.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))

    story = [
        Paragraph('PHARMONY', style_title),
        Paragraph(f'Factura de turno — {turno.codigo_ticket}', style_sub),
        tabla,
        Spacer(1, 30),
        Paragraph(f'Código de seguimiento: <b>{turno.codigo_ticket}</b>', style_value),
        Paragraph('Guarda este código para verificar el estado del envío más adelante.', style_sub),
    ]
    doc.build(story)
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f"Factura_{turno.codigo_ticket}.pdf")

@login_required
def cancelar_turno(request, codigo):
    turno = get_object_or_404(Turno, codigo_ticket=codigo, usuario=request.user)
    if request.method == 'POST' and turno.estado in ('pendiente', 'en_atencion'):
        turno.estado = 'cancelado'
        turno.motivo_estado = 'Cancelado por el usuario.'
        turno.fecha_finalizacion = timezone.now()
        turno.save()
        if turno.solicitud:
            turno.solicitud.estado = 'rechazada'
            turno.solicitud.save()
        sync_turno_a_firestore(turno)
        messages.success(request, 'Tu turno ha sido cancelado.')
    return redirect('turnos:factura_turno', codigo=turno.codigo_ticket)