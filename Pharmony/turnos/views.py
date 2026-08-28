import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.http import HttpResponseForbidden
from django.http import JsonResponse, FileResponse


from .ocr_utils import extraer_texto_documento, extraer_cedula, extraer_codigo_formula
from DocsIA.services.gemini_scanner import analizar_formula_turno
from epsinventario.views import es_admin, _sync_inventario_firestore
from pedidos.models import Pedido
from epsinventario.models import Sede, InventarioSede, SolicitudMedicamento
from Farmacia.models import Medicamento
from .models import Turno, AuxiliarSede, Caja, MensajeTurno, ItemEntregaTurno, validar_extension_documento
from .forms import SolicitarTurnoForm
from .firestore_sync import sync_turno_a_firestore, sync_mensaje_a_firestore, sync_auxiliar_sede_a_firestore
from .decorators import eps_required
from firebase_admin import auth as firebase_auth

from datetime import timedelta

DIAS_COOLDOWN_RECLAMO = 30

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

    # Cooldown de 30 días: solo aplica si el medicamento fue efectivamente entregado y aprobado
    from turnos.cooldown import verificar_cooldown_medicamento
    en_cooldown, cooldown_fecha = verificar_cooldown_medicamento(request.user, medicamento)
    if en_cooldown:
        messages.error(
            request,
            f"Ya realizaste una solicitud para {medicamento.nombre_comercial} que fue aprobada y despachada. "
            f"Puedes revisar el estado en la sección de Mis Pedidos (Disponible nuevamente el {cooldown_fecha})."
        )
        return redirect('dashboard_cliente')

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
    turno = get_object_or_404(Turno, codigo_ticket=codigo, usuario=request.user)
    if turno.estado not in ('correcto', 'rechazado', 'finalizado', 'cancelado'):
        return redirect('turnos:ver_ticket', codigo=turno.codigo_ticket)
    items_entregados = turno.items_entregados.select_related('medicamento').all()
    return render(request, 'turnos/factura.html', {'turno': turno, 'items_entregados': items_entregados})


@login_required
def volver_dashboard(request, codigo):
    turno = get_object_or_404(Turno, codigo_ticket=codigo, usuario=request.user)
    if turno.estado in ('correcto', 'rechazado'):
        turno.estado = 'finalizado'
        if not turno.fecha_finalizacion:
            turno.fecha_finalizacion = timezone.now()
        turno.save()
        sync_turno_a_firestore(turno)
    return redirect('dashboard_cliente')


#  administrador/auxiliar abrir caja

@eps_required
def seleccion_panel(request):
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

    # El análisis se solicita por AJAX para que la pantalla y los documentos abran sin esperar a Gemini.
    analisis_ia = None
    if turno.resultado_ia:
        analisis_ia = analizar_formula_turno(turno)

    cedula_detectada = turno.cedula_detectada_ia or ''
    codigo_formula_detectado = (analisis_ia or {}).get('codigo_formula', '')
    paciente_detectado = turno.paciente_detectado_ia or ''
    medico_detectado = turno.medico_detectado_ia or ''

    cedula_usuario = (turno.usuario.cedula or '').strip().replace('.', '').replace('-', '')
    cedula_detectada_clean = (cedula_detectada or '').strip().replace('.', '').replace('-', '')

    cedula_coincide = None
    if cedula_usuario and cedula_detectada_clean:
        cedula_coincide = (cedula_detectada_clean == cedula_usuario) or (cedula_usuario in cedula_detectada_clean) or (cedula_detectada_clean in cedula_usuario)

    # --- Stock actual del medicamento principal en esta sede ---
    inventario_actual = InventarioSede.objects.filter(sede=turno.sede, medicamento=turno.medicamento).first()

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

            if estado_final == 'correcto':
                # Procesar entrega de medicamentos (Múltiples medicamentos detectados y seleccionados)
                med_ids_seleccionados = request.POST.getlist('med_ids_entregar')
                
                # Si no se enviaron checkboxes específicos, tomar el medicamento principal
                if not med_ids_seleccionados:
                    med_ids_seleccionados = [str(turno.medicamento.id)]

                items_a_entregar = []
                errores_stock = []

                for med_id_str in med_ids_seleccionados:
                    try:
                        med_id = int(med_id_str)
                    except ValueError:
                        continue

                    med = Medicamento.objects.filter(id=med_id).first()
                    if not med:
                        continue

                    # Cantidad a entregar para este medicamento específico
                    campo_cant = f'cantidad_entregada_{med_id}'
                    cantidad_str = request.POST.get(campo_cant, '').strip()
                    if not cantidad_str:
                        # Fallback a cantidad_entregada general si es el principal
                        if med.id == turno.medicamento.id:
                            cantidad_str = request.POST.get('cantidad_entregada', '1').strip()
                        else:
                            cantidad_str = '1'

                    if not cantidad_str.isdigit() or int(cantidad_str) <= 0:
                        errores_stock.append(f"Indica una cantidad válida para {med.nombre_comercial}.")
                        continue

                    cantidad = int(cantidad_str)
                    inv = InventarioSede.objects.filter(sede=turno.sede, medicamento=med).first()
                    if not inv or inv.cantidad_disponible < cantidad:
                        disponibles = inv.cantidad_disponible if inv else 0
                        errores_stock.append(f"Stock insuficiente para {med.nombre_comercial} ({disponibles} disponibles, solicitaste {cantidad}).")
                        continue

                    # Obtener indicaciones para este medicamento
                    indicaciones = request.POST.get(f'indicaciones_{med_id}', '').strip()

                    items_a_entregar.append({
                        'medicamento': med,
                        'inventario': inv,
                        'cantidad': cantidad,
                        'indicaciones': indicaciones
                    })

                if errores_stock:
                    for err in errores_stock:
                        messages.error(request, err)
                    return redirect('turnos:atender_turno', codigo=codigo)

                if not items_a_entregar:
                    messages.error(request, 'Debes seleccionar al menos un medicamento disponible para entregar.')
                    return redirect('turnos:atender_turno', codigo=codigo)

                # Descontar stock y registrar entregas
                cantidad_principal = 0
                for item in items_a_entregar:
                    inv = item['inventario']
                    med = item['medicamento']
                    cant = item['cantidad']

                    inv.cantidad_disponible -= cant
                    inv.save()
                    _sync_inventario_firestore(inv)

                    ItemEntregaTurno.objects.create(
                        turno=turno,
                        medicamento=med,
                        cantidad=cant,
                        indicaciones=item['indicaciones']
                    )

                    if med.id == turno.medicamento.id:
                        cantidad_principal = cant

                # Si el principal no estuvo entre los ítems (caso raro), asignar cantidad del primer ítem
                if cantidad_principal == 0 and items_a_entregar:
                    cantidad_principal = items_a_entregar[0]['cantidad']

                turno.cantidad_entregada = cantidad_principal
                turno.estado = 'correcto'
                turno.motivo_estado = motivo or 'Dispensación aprobada y procesada correctamente.'
                turno.fecha_finalizacion = timezone.now()
                turno.save()

                Pedido.objects.get_or_create(turno=turno, defaults={'estado': 'preparando'})

                if turno.solicitud:
                    turno.solicitud.estado = 'atendida'
                    turno.solicitud.save()
                sync_turno_a_firestore(turno)

                total_items = sum(it['cantidad'] for it in items_a_entregar)
                messages.success(request, f'Turno {turno.codigo_ticket} aprobado con éxito. Se entregaron {len(items_a_entregar)} tipo(s) de medicamentos ({total_items} unidades en total).')
                return redirect('turnos:cola_turnos', sede_id=turno.sede.id)

            elif estado_final == 'rechazado':
                turno.estado = 'rechazado'
                turno.motivo_estado = motivo or 'Fórmula médica o requisitos no válidos.'
                turno.fecha_finalizacion = timezone.now()
                turno.save()
                if turno.solicitud:
                    turno.solicitud.estado = 'rechazada'
                    turno.solicitud.save()
                sync_turno_a_firestore(turno)
                messages.success(request, f'Turno {turno.codigo_ticket} marcado como rechazado.')
                return redirect('turnos:cola_turnos', sede_id=turno.sede.id)

        return redirect('turnos:atender_turno', codigo=codigo)

    return render(request, 'turnos/atender_turno.html', {
        'turno': turno,
        'mensajes': turno.mensajes.all(),
        'firebase_token': _generar_firebase_token(request.user),
        'analisis_ia': analisis_ia,
        'cedula_detectada': cedula_detectada,
        'codigo_formula_detectado': codigo_formula_detectado,
        'paciente_detectado': paciente_detectado,
        'medico_detectado': medico_detectado,
        'cedula_coincide': cedula_coincide,
        'usuario_tiene_cedula': bool(cedula_usuario),
        'inventario_actual': inventario_actual,
        'usuario_info': {
            'nombre_completo': turno.usuario.nombre_para_mostrar(),
            'username': turno.usuario.username,
            'cedula': turno.usuario.cedula or 'No registrada',
            'email': turno.usuario.email or 'No registrado',
            'telefono': turno.usuario.telefono or 'No registrado',
            'eps': turno.usuario.eps.nombre if turno.usuario.eps else 'Particular / Sin EPS',
            'direccion_registrada': turno.usuario.direccion or 'No registrada',
            'direccion_envio': f"{turno.direccion_envio}, {turno.ciudad_envio}",
            'fecha_registro': turno.usuario.date_joined.strftime('%d/%m/%Y') if turno.usuario.date_joined else '—',
        }
    })

@eps_required
def analizar_formula_turno_ajax(request, codigo):
    if request.method != 'GET':
        return JsonResponse({'ok': False, 'error': 'Método no permitido.'}, status=405)

    turno = get_object_or_404(Turno, codigo_ticket=codigo, auxiliar_asignado=request.user, estado='en_atencion')
    try:
        analisis_ia = analizar_formula_turno(turno, forzar_reanalisis=request.GET.get('reanalizar') == '1')
        contexto = {
            'analisis_ia': analisis_ia,
            'cedula_detectada': analisis_ia.get('paciente_cedula', '') if analisis_ia else '',
            'codigo_formula_detectado': analisis_ia.get('codigo_formula', '') if analisis_ia else '',
            'paciente_detectado': analisis_ia.get('paciente_nombre', '') if analisis_ia else '',
            'medico_detectado': analisis_ia.get('medico_nombre', '') if analisis_ia else '',
        }
        return JsonResponse({'ok': True, 'html': render_to_string('turnos/_analisis_formula.html', contexto, request=request)})
    except Exception:
        return JsonResponse({'ok': False, 'error': 'No fue posible analizar la fórmula. Verifícala manualmente.'}, status=503)

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
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=45, leftMargin=45, topMargin=45, bottomMargin=45)
    styles = getSampleStyleSheet()

    style_title = ParagraphStyle('TituloFactura', parent=styles['Heading1'], fontName='Helvetica-Bold',
                                  fontSize=20, textColor=colors.HexColor('#052060'), alignment=1, spaceAfter=4)
    style_sub = ParagraphStyle('SubFactura', parent=styles['Normal'], fontName='Helvetica',
                                fontSize=11, textColor=colors.HexColor('#64748b'), alignment=1, spaceAfter=15)
    style_section = ParagraphStyle('SectionHeader', parent=styles['Normal'], fontName='Helvetica-Bold',
                                   fontSize=12, textColor=colors.HexColor('#0a3a8c'), spaceBefore=12, spaceAfter=6)
    style_label = ParagraphStyle('Label', parent=styles['Normal'], fontName='Helvetica-Bold',
                                  fontSize=9.5, textColor=colors.HexColor('#475569'))
    style_value = ParagraphStyle('Value', parent=styles['Normal'], fontName='Helvetica',
                                  fontSize=9.5, textColor=colors.HexColor('#1e293b'))

    data_info = [
        [Paragraph('Estado final', style_label), Paragraph(turno.get_estado_display(), style_value)],
        [Paragraph('Motivo / Observación', style_label), Paragraph(turno.motivo_estado or '—', style_value)],
        [Paragraph('Sede de despacho', style_label), Paragraph(f"{turno.sede.nombre} ({turno.sede.ciudad})", style_value)],
        [Paragraph('Paciente / Titular', style_label), Paragraph(f"{turno.usuario.nombre_para_mostrar()} (C.C. {turno.usuario.cedula or '—'})", style_value)],
        [Paragraph('Dirección de entrega', style_label), Paragraph(f"{turno.direccion_envio}, {turno.ciudad_envio}", style_value)],
        [Paragraph('Atendido por', style_label), Paragraph(turno.auxiliar_asignado.nombre_para_mostrar() if turno.auxiliar_asignado else '—', style_value)],
        [Paragraph('Fecha de solicitud', style_label), Paragraph(turno.fecha_solicitud.strftime('%d/%m/%Y %H:%M'), style_value)],
        [Paragraph('Fecha de atención', style_label), Paragraph(turno.fecha_finalizacion.strftime('%d/%m/%Y %H:%M') if turno.fecha_finalizacion else '—', style_value)],
    ]
    tabla_info = Table(data_info, colWidths=[150, 360])
    tabla_info.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))

    story = [
        Paragraph('PHARMONY', style_title),
        Paragraph(f'Comprobante de Entrega y Factura de Dispensación — {turno.codigo_ticket}', style_sub),
        tabla_info,
        Spacer(1, 15),
    ]

    # Lista de medicamentos entregados
    items = list(turno.items_entregados.select_related('medicamento').all())
    if items:
        story.append(Paragraph('Medicamentos Dispensados en esta Fórmula:', style_section))
        meds_data = [
            [Paragraph('Medicamento', style_label), Paragraph('Concentración / Forma', style_label), Paragraph('Cant. Entregada', style_label)]
        ]
        for it in items:
            meds_data.append([
                Paragraph(f"<b>{it.medicamento.nombre_comercial}</b><br/><font size=8 color='#64748b'>{it.medicamento.nombre_generico} · {it.medicamento.laboratorio}</font>", style_value),
                Paragraph(f"{it.medicamento.concentracion}<br/><font size=8 color='#64748b'>{it.medicamento.forma_farmaceutica}</font>", style_value),
                Paragraph(f"<b>{it.cantidad} unid.</b>", style_value),
            ])
        tabla_meds = Table(meds_data, colWidths=[240, 180, 90])
        tabla_meds.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(tabla_meds)
        story.append(Spacer(1, 15))
    else:
        # Fallback medicamento único
        story.append(Paragraph(f'Medicamento solicitado: <b>{turno.medicamento.nombre_comercial}</b> ({turno.cantidad_entregada or 1} unid.)', style_value))
        story.append(Spacer(1, 15))

    story.extend([
        Paragraph(f'Código de seguimiento de envío: <b>{turno.codigo_ticket}</b>', style_value),
        Paragraph('Puedes rastrear el estado de este pedido en tiempo real ingresando a la sección de Pedidos de Pharmony con este código.', style_sub),
    ])

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