"""
Farmacia/views/cliente_views.py

Vistas orientadas al usuario final (rol 'cliente'): dashboard con
búsqueda/disponibilidad de medicamentos, generación del PDF de derecho
de petición, y el endpoint para que EPS/farmacéutico marque la entrega.
"""

import datetime
import io
import json
import uuid

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from epsinventario.models import Eps, InventarioSede, Sede
from ..models import Medicamento, MedicamentoUsuario, DerechoPeticion
from ..firestore_sync import (
    sync_medicamento_usuario_firestore,
    eliminar_medicamento_usuario_firestore,
    sync_derecho_peticion_firestore,
)
from .common import _redirect_por_rol


def dashboard_cliente(request):
    if request.user.rol in ('admin', 'eps'):
        return redirect(_redirect_por_rol(request.user))

    medicamentos = list(Medicamento.objects.all().order_by("nombre_comercial"))
    total_medicamentos = len(medicamentos)
    medicamentos_formula = sum(1 for m in medicamentos if m.requiere_formula)
    medicamentos_libres = total_medicamentos - medicamentos_formula
    laboratorios = len(set(m.laboratorio for m in medicamentos))

    inventarios_qs = InventarioSede.objects.select_related('sede', 'medicamento')
    disponibilidad_por_medicamento = {}
    for inv in inventarios_qs:
        med_id = inv.medicamento_id
        if med_id not in disponibilidad_por_medicamento:
            disponibilidad_por_medicamento[med_id] = {
                'cantidad_total': 0,
                'sedes_count': 0,
                'estado': 'agotado',
            }
        info = disponibilidad_por_medicamento[med_id]
        info['cantidad_total'] += inv.cantidad_disponible
        if inv.cantidad_disponible > 0:
            info['sedes_count'] += 1
        if inv.estado_stock == 'disponible':
            info['estado'] = 'disponible'
        elif inv.estado_stock == 'stock_bajo' and info['estado'] != 'disponible':
            info['estado'] = 'stock_bajo'

    # Medicamentos asignados al paciente
    mis_asignaciones = list(MedicamentoUsuario.objects.filter(usuario=request.user, activo=True).select_related('medicamento'))
    mis_meds_dict = {a.medicamento_id: a for a in mis_asignaciones}

    # Derechos de petición activos del paciente (radicado o en trámite)
    peticiones_activas = {
        p.medicamento_id: p
        for p in DerechoPeticion.objects.filter(usuario=request.user, estado__in=['radicado', 'en_tramite']).select_related('medicamento')
    }

    for med in medicamentos:
        med.disponibilidad = disponibilidad_por_medicamento.get(med.id, {
            'cantidad_total': 0, 'sedes_count': 0, 'estado': 'agotado'
        })
        med.tiene_peticion_activa = med.id in peticiones_activas
        med.peticion_activa = peticiones_activas.get(med.id)
        med.asignacion_usuario = mis_meds_dict.get(med.id)
        med.es_mi_medicamento = med.id in mis_meds_dict

    medicamentos_agotados = [m for m in medicamentos if m.disponibilidad['cantidad_total'] == 0]
    mis_medicamentos = [m for m in medicamentos if m.id in mis_meds_dict]
    mis_medicamentos_agotados = [m for m in mis_medicamentos if m.disponibilidad['cantidad_total'] == 0]

    sedes_reales = Sede.objects.filter(estado=True).select_related('eps')

    if not sedes_reales.exists():
        epss = list(Eps.objects.filter(estado=True))
        if epss:
            sedes_def = [
                {'eps': epss[0], 'nombre': 'Sede Principal Chapinero', 'ciudad': 'Bogotá', 'direccion': 'Cra. 13 # 53-45'},
                {'eps': epss[0], 'nombre': 'Sede Norte Unicentro', 'ciudad': 'Bogotá', 'direccion': 'Av. 15 # 124-30'},
                {'eps': epss[min(1, len(epss)-1)], 'nombre': 'Sede El Poblado', 'ciudad': 'Medellín', 'direccion': 'Calle 10 # 43A-21'},
                {'eps': epss[min(2, len(epss)-1)], 'nombre': 'Sede Chipichape', 'ciudad': 'Cali', 'direccion': 'Av. 6N # 35N-10'},
                {'eps': epss[min(3, len(epss)-1)], 'nombre': 'Sede Alto Prado', 'ciudad': 'Barranquilla', 'direccion': 'Calle 76 # 54-11'},
                {'eps': epss[min(4, len(epss)-1)], 'nombre': 'Sede Cabecera', 'ciudad': 'Bucaramanga', 'direccion': 'Cra. 33 # 48-15'}
            ]
            for s_data in sedes_def:
                s = Sede.objects.create(**s_data)
                for m in medicamentos:
                    cant = 25 if m.id % 2 == 0 else 5
                    InventarioSede.objects.create(sede=s, medicamento=m, cantidad_disponible=cant, cantidad_minima=10)
            sedes_reales = Sede.objects.filter(estado=True).select_related('eps')

    sedes_map_data = []
    for sede in sedes_reales:
        if sede.hora_apertura and sede.hora_cierre:
            horario_texto = f"{sede.hora_apertura.strftime('%H:%M')} - {sede.hora_cierre.strftime('%H:%M')}"
        else:
            horario_texto = 'Horario no configurado'

        sedes_map_data.append({
            'id': sede.id,
            'lat': sede.latitud,
            'lng': sede.longitud,
            'nombre': f"{sede.eps.nombre} — {sede.nombre}",
            'ciudad': sede.ciudad,
            'addr': sede.direccion or sede.ciudad,
            'abierta': sede.esta_abierta_ahora,
            'horario': horario_texto,
        })

    context = {
        'medicamentos': medicamentos,
        'mis_medicamentos': mis_medicamentos,
        'mis_medicamentos_agotados': mis_medicamentos_agotados,
        'total_medicamentos': total_medicamentos,
        'mis_medicamentos_total': len(mis_medicamentos),
        'peticiones_activas_total': len(peticiones_activas),
        'medicamentos_formula': medicamentos_formula,
        'medicamentos_libres': medicamentos_libres,
        'laboratorios': laboratorios,
        'medicamentos_agotados': medicamentos_agotados,
        'sedes_map_json': json.dumps(sedes_map_data),
        'user_name': f"{request.user.first_name} {request.user.last_name}" if request.user.first_name else request.user.username,
        'user_initials': (request.user.first_name[0] + request.user.last_name[0]).upper() if request.user.first_name and request.user.last_name else request.user.email[:2].upper()
    }
    return render(request, 'inventario/DashboardCliente.html', context)

def generar_derecho_peticion(request):
    if request.method not in ['POST', 'GET']:
        return HttpResponse("Método no permitido", status=405)
    
    data = request.POST if request.method == 'POST' else request.GET
    med_id = data.get('medicamento_id')
    if not med_id:
        return HttpResponse("ID de medicamento requerido", status=400)
    
    medicamento = get_object_or_404(Medicamento, id=med_id)
    user = request.user
    datos_actualizados = False
    
    post_cedula = data.get('numero_documento')
    if post_cedula and post_cedula != user.cedula:
        user.cedula = post_cedula
        datos_actualizados = True
        
    post_direccion = data.get('direccion')
    if post_direccion and post_direccion != user.direccion:
        user.direccion = post_direccion
        datos_actualizados = True
        
    post_telefono = data.get('telefono')
    if post_telefono and post_telefono != user.telefono:
        user.telefono = post_telefono
        datos_actualizados = True

    post_full_name = data.get('nombre_usuario')
    if post_full_name and post_full_name != (user.get_full_name() or user.username):
        partes = post_full_name.split(' ', 1)
        if len(partes) > 1:
            user.first_name = partes[0]
            user.last_name = partes[1]
        else:
            user.first_name = post_full_name
            user.last_name = ''
        datos_actualizados = True
        
    if datos_actualizados:
        user.save()
        
    nombre_usuario = user.get_full_name() or user.username
    tipo_documento = data.get('tipo_documento') or 'Cédula de Ciudadanía'
    numero_documento = user.cedula or '_______________'
    
    eps_nombre = data.get('eps_nombre')
    if not eps_nombre and user.eps:
        eps_nombre = user.eps.nombre
    if not eps_nombre:
        eps_nombre = 'ENTIDAD PROMOTORA DE SALUD (EPS)'
        
    direccion = user.direccion or '_______________'
    telefono = user.telefono or '_______________'
    email = user.email or '_______________'
    ciudad = data.get('ciudad') or 'Bogotá D.C.'
    
    fecha_actual = datetime.datetime.now()
    meses = {
        1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
        7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
    }
    fecha_str = f"{ciudad}, {fecha_actual.day} de {meses[fecha_actual.month]} de {fecha_actual.year}"

    # Control de duplicidad: Verificar si ya tiene un derecho de petición activo
    peticion_existente = DerechoPeticion.objects.filter(
        usuario=user,
        medicamento=medicamento,
        estado__in=['radicado', 'en_tramite']
    ).first()

    if not peticion_existente:
        num_radicado = f"DP-{fecha_actual.strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
        peticion = DerechoPeticion.objects.create(
            numero_radicado=num_radicado,
            usuario=user,
            medicamento=medicamento,
            estado='radicado'
        )
        sync_derecho_peticion_firestore(peticion)
    else:
        peticion = peticion_existente
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    styles = getSampleStyleSheet()
    style_normal = ParagraphStyle(
        name='NormalJustify',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        alignment=TA_JUSTIFY,
        spaceAfter=10
    )
    style_heading = ParagraphStyle(
        name='HeadingCustom',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        alignment=TA_LEFT,
        spaceBefore=12,
        spaceAfter=6
    )
    
    story = [
        Paragraph(f"<b>RADICADO OFICIAL:</b> {peticion.numero_radicado}<br/><b>ESTADO DEL TRÁMITE:</b> {peticion.get_estado_display().upper()}<br/><b>FECHA DE EXPEDICIÓN:</b> {fecha_str}", style_normal),
        Spacer(1, 15),
        Paragraph(f"<b>Señores:</b><br/><b>{eps_nombre.upper()}</b><br/>Oficina de Atención al Usuario / Representante Legal<br/>E. S. D.", style_normal),
        Spacer(1, 15),
        Paragraph(f"<b>ASUNTO:</b> DERECHO DE PETICIÓN (Artículo 23 de la Constitución Política de Colombia, Ley 1755 de 2015 y Ley Estatutaria de Salud 1751 de 2015) para la entrega inmediata del medicamento <b>{medicamento.nombre_comercial} ({medicamento.nombre_generico})</b>.", style_normal),
        Spacer(1, 15),
        Paragraph(
            f"Yo, <b>{nombre_usuario}</b>, mayor de edad, identificado con <b>{tipo_documento}</b> número <b>{numero_documento}</b>, "
            f"afiliado a la entidad promotora de salud <b>{eps_nombre}</b>, domiciliado en la dirección <b>{direccion}</b>, "
            f"con número de teléfono <b>{telefono}</b> y correo electrónico <b>{email}</b>, actuando en nombre propio y en ejercicio del "
            f"derecho constitucional de petición consagrado en el artículo 23 de la Constitución Política de Colombia, en concordancia con "
            f"la Ley 1755 de 2015 (que regula el derecho de petición) y la Ley Estatutaria de Salud 1751 de 2015, me dirijo ante ustedes de manera "
            f"respetuosa con el fin de formular la presente solicitud, con fundamento en los siguientes:",
            style_normal
        ),
        Spacer(1, 10),
        Paragraph("HECHOS", style_heading),
        Paragraph(
            f"1. Se me encuentra prescrito el medicamento <b>{medicamento.nombre_comercial} ({medicamento.nombre_generico})</b>, "
            f"concentración <b>{medicamento.concentracion}</b> y forma farmacéutica <b>{medicamento.forma_farmaceutica}</b>, "
            f"producido por el laboratorio <b>{medicamento.laboratorio}</b>, para el tratamiento de mi estado de salud.",
            style_normal
        ),
        Paragraph(
            f"2. Al acudir a reclamar dicho medicamento en la red de farmacias Pharmony, se me informó que el medicamento se encuentra actualmente "
            f"<b>AGOTADO</b> en su totalidad de sedes, impidiendo que inicie o continúe con mi tratamiento en los términos indicados por el profesional de la salud.",
            style_normal
        ),
        Paragraph(
            "3. La no entrega oportuna de los medicamentos prescritos pone en riesgo mi salud y bienestar, constituyendo una vulneración directa "
            "al derecho fundamental a la salud consagrado en la legislación colombiana y ampliamente protegido por la jurisprudencia constitucional.",
            style_normal
        ),
        Spacer(1, 10),
        Paragraph("PETICIONES", style_heading),
        Paragraph(
            f"1. Solicito de manera inmediata que la EPS <b>{eps_nombre}</b> gestione, autorice y haga entrega efectiva del medicamento "
            f"<b>{medicamento.nombre_comercial} ({medicamento.nombre_generico})</b> en las dosis y cantidades formuladas, en un plazo máximo "
            f"de cuarenta y ocho (48) horas, conforme a los lineamientos vigentes del Ministerio de Salud y la Superintendencia Nacional de Salud.",
            style_normal
        ),
        Paragraph(
            "2. En caso de persistir la falta de stock del medicamento en el canal de dispensación habitual, se proceda a suministrar un sustituto "
            "terapéutico equivalente previa autorización médica, o bien, se gestione la entrega a domicilio del medicamento tan pronto se encuentre disponible "
            "sin que esto represente costos adicionales o cargas administrativas para mi persona.",
            style_normal
        ),
        Spacer(1, 10),
        Paragraph("FUNDAMENTOS DE DERECHO", style_heading),
        Paragraph(
            "Esta solicitud se fundamenta en el artículo 23 de la Constitución Política de Colombia; la Ley 1755 de 2015, por medio de la cual "
            "se regula el derecho fundamental de petición; la Ley 1751 de 2015 (Ley Estatutaria de Salud) que reconoce la salud como un derecho "
            "fundamental autónemo e irrenunciable, garantizando la entrega oportuna de tecnologías y medicamentos; y la jurisprudencia de la "
            "Corte Constitucional (Sentencia T-760 de 2008 y siguientes) que señala que el suministro incompleto o inoportuno de medicamentos "
            "vulnera el derecho a la salud y a la vida en condiciones dignas.",
            style_normal
        ),
        Spacer(1, 10),
        Paragraph("NOTIFICACIONES y DIRECCIÓN DE CONTACTO", style_heading),
        Paragraph(
            f"Recibiré respuesta a esta petición en los siguientes datos de contacto:<br/>"
            f"<b>Dirección física:</b> {direccion}<br/>"
            f"<b>Teléfono:</b> {telefono}<br/>"
            f"<b>Correo electrónico:</b> {email}",
            style_normal
        ),
        Spacer(1, 30),
        Paragraph(
            f"Atentamente,<br/><br/><br/>"
            f"__________________________________________<br/>"
            f"<b>{nombre_usuario}</b><br/>"
            f"<b>{tipo_documento}:</b> {numero_documento}<br/>"
            f"<b>Radicado:</b> {peticion.numero_radicado}",
            style_normal
        )
    ]
    
    doc.build(story)
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f"Derecho_Peticion_{peticion.numero_radicado}_{medicamento.nombre_comercial.replace(' ', '_')}.pdf")


@login_required
@csrf_exempt
def entregar_derecho_peticion_api(request, peticion_id):
    """
    Endpoint para que el farmacéutico o personal EPS marque la entrega efectiva del medicamento,
    resolviendo la petición y liberando el bloqueo de duplicidad.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido. Usa POST.'}, status=405)
    
    if request.user.rol not in ('admin', 'eps') and not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'No autorizado. Solo personal EPS o Farmacéuticos.'}, status=403)
        
    peticion = get_object_or_404(DerechoPeticion, id=peticion_id)
    peticion.estado = 'entregado'
    peticion.fecha_respuesta = timezone.now()
    peticion.atendido_por = request.user
    peticion.save()
    sync_derecho_peticion_firestore(peticion)
    
    return JsonResponse({
        'success': True,
        'mensaje': f'Derecho de petición {peticion.numero_radicado} resuelto y marcado como ENTREGADO.',
        'radicado': peticion.numero_radicado,
        'estado': peticion.estado,
        'fecha_respuesta': peticion.fecha_respuesta.isoformat()
    })
