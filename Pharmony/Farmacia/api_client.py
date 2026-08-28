import json
import uuid
import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login
from django.db.models import Q
from .models import Usuario, Medicamento, MedicamentoUsuario, DerechoPeticion
from .firestore_sync import sync_derecho_peticion_firestore
from epsinventario.models import Eps, Sede, InventarioSede


@csrf_exempt
def api_login(request):
    """
    Endpoint para autenticación de usuarios desde Flutter.
    Recibe JSON o Form POST con 'email' (o username) y 'password'.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido. Usa POST.'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        identifier = (data.get('email') or data.get('username') or '').strip()
        password = (data.get('password') or '').strip()

        if not identifier or not password:
            return JsonResponse({'success': False, 'error': 'Debes ingresar correo/usuario y contraseña.'}, status=400)

        # Buscar usuario por correo o username
        user_obj = Usuario.objects.filter(Q(email__iexact=identifier) | Q(username__iexact=identifier)).first()
        username_to_auth = user_obj.username if user_obj else identifier

        user = authenticate(request, username=username_to_auth, password=password)

        if user is None:
            return JsonResponse({'success': False, 'error': 'Credenciales inválidas. Revisa tu correo y contraseña.'}, status=401)

        if not user.is_active:
            return JsonResponse({'success': False, 'error': 'Esta cuenta ha sido desactivada.'}, status=403)

        login(request, user)

        eps_nombre = user.eps.nombre if hasattr(user, 'eps') and user.eps else 'Pharmony'

        return JsonResponse({
            'success': True,
            'mensaje': f'Bienvenido de nuevo, {user.get_full_name() or user.username}!',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'nombre_completo': user.get_full_name() or user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'cedula': user.cedula or '',
                'tipo_documento': user.tipo_documento or 'CC',
                'telefono': user.telefono or '',
                'direccion': user.direccion or '',
                'ciudad': user.ciudad or 'Bogotá',
                'rol': user.rol or 'cliente',
                'eps': eps_nombre,
                'eps_id': user.eps.id if hasattr(user, 'eps') and user.eps else None,
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
def api_register(request):
    """
    Endpoint para registro de nuevos pacientes desde Flutter.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido. Usa POST.'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST

        first_name = (data.get('first_name') or '').strip()
        last_name = (data.get('last_name') or '').strip()
        email = (data.get('email') or '').strip().lower()
        password = (data.get('password') or '').strip()
        cedula = (data.get('cedula') or '').strip()
        tipo_documento = (data.get('tipo_documento') or 'CC').strip()
        telefono = (data.get('telefono') or '').strip()
        direccion = (data.get('direccion') or '').strip()
        ciudad = (data.get('ciudad') or 'Bogotá').strip()
        eps_id = data.get('eps_id')

        if not email or not password or not first_name:
            return JsonResponse({'success': False, 'error': 'Nombre, correo electrónico y contraseña son obligatorios.'}, status=400)

        if Usuario.objects.filter(email__iexact=email).exists():
            return JsonResponse({'success': False, 'error': 'Ya existe una cuenta registrada con este correo electrónico.'}, status=400)

        # Generar un username único
        base_username = email.split('@')[0].replace('.', '_')
        username = base_username
        counter = 1
        while Usuario.objects.filter(username__iexact=username).exists():
            username = f"{base_username}_{counter}"
            counter += 1

        eps_obj = None
        if eps_id:
            eps_obj = Eps.objects.filter(id=eps_id, estado=True).first()
        if not eps_obj:
            eps_obj = Eps.objects.filter(estado=True).first()

        user = Usuario.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            cedula=cedula,
            tipo_documento=tipo_documento,
            telefono=telefono,
            direccion=direccion,
            ciudad=ciudad,
            rol='cliente',
            eps=eps_obj
        )

        return JsonResponse({
            'success': True,
            'mensaje': 'Cuenta creada exitosamente. Ya puedes iniciar sesión en Pharmony.',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'nombre_completo': user.get_full_name(),
                'cedula': user.cedula,
                'rol': user.rol,
                'eps': eps_obj.nombre if eps_obj else 'Pharmony',
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
def api_epss_list(request):
    """
    Lista de EPS activas para formularios de registro y selección.
    """
    epss = Eps.objects.filter(estado=True).values('id', 'nombre', 'nit', 'ciudad')
    return JsonResponse({'success': True, 'epss': list(epss)})


from .derecho_peticion_cooldown import (
    verificar_cooldown_derecho_peticion,
    verificar_limite_descargas,
    registrar_descarga,
    DIAS_COOLDOWN_DERECHO_PETICION
)


@csrf_exempt
def api_client_dashboard(request):
    """
    Suministra todos los datos en tiempo real del Dashboard del Paciente para Flutter:
    - Datos del paciente y métricas
    - Medicamentos asignados a su tratamiento con stock en tiempo real
    - Catálogo general de medicamentos y disponibilidad por sedes
    - Sedes de farmacia activas
    - Derechos de petición radicados y control de cooldown legal
    """
    req_user = getattr(request, 'user', None)
    user = req_user if (req_user and req_user.is_authenticated) else None
    
    # Si no está autenticado, usar el usuario de demostración o el primer cliente
    if not user:
        user = Usuario.objects.filter(rol='cliente').first() or Usuario.objects.first()

    # 1. Catálogo completo de medicamentos y disponibilidad
    medicamentos = list(Medicamento.objects.all().order_by("nombre_comercial"))
    inventarios_qs = InventarioSede.objects.select_related('sede', 'medicamento').all()

    disponibilidad_por_med = {}
    sedes_por_med = {}

    for inv in inventarios_qs:
        m_id = inv.medicamento_id
        if m_id not in disponibilidad_por_med:
            disponibilidad_por_med[m_id] = {
                'cantidad_total': 0,
                'sedes_count': 0,
                'estado': 'agotado',
            }
            sedes_por_med[m_id] = []

        disponibilidad_por_med[m_id]['cantidad_total'] += inv.cantidad_disponible
        if inv.cantidad_disponible > 0:
            disponibilidad_por_med[m_id]['sedes_count'] += 1
            disponibilidad_por_med[m_id]['estado'] = 'disponible'
        elif inv.estado_stock == 'stock_bajo' and disponibilidad_por_med[m_id]['estado'] != 'disponible':
            disponibilidad_por_med[m_id]['estado'] = 'stock_bajo'

        sedes_por_med[m_id].append({
            'sede_id': inv.sede.id,
            'sede_nombre': inv.sede.nombre,
            'ciudad': inv.sede.ciudad,
            'cantidad_disponible': inv.cantidad_disponible,
            'estado_stock': inv.estado_stock,
        })

    # 2. Medicamentos asignados al paciente
    mis_asignaciones = []
    peticiones_activas = {}

    if user:
        mis_asignaciones = list(MedicamentoUsuario.objects.filter(usuario=user, activo=True).select_related('medicamento'))
        peticiones_qs = DerechoPeticion.objects.filter(usuario=user).select_related('medicamento')
        for p in peticiones_qs:
            peticiones_activas[p.medicamento_id] = {
                'id': p.id,
                'numero_radicado': p.numero_radicado,
                'estado': p.get_estado_display(),
                'fecha_radicacion': p.fecha_radicacion.strftime('%d/%m/%Y %H:%M') if p.fecha_radicacion else '',
            }

    mis_meds_dict = {a.medicamento_id: a for a in mis_asignaciones}

    # Serializar medicamentos asignados
    mis_medicamentos_data = []
    for asig in mis_asignaciones:
        m = asig.medicamento
        disp = disponibilidad_por_med.get(m.id, {'cantidad_total': 0, 'sedes_count': 0, 'estado': 'agotado'})
        peticion = peticiones_activas.get(m.id)
        cd_info = verificar_cooldown_derecho_peticion(user, m)

        mis_medicamentos_data.append({
            'asignacion_id': asig.id,
            'medicamento_id': m.id,
            'nombre_comercial': m.nombre_comercial,
            'nombre_generico': m.nombre_generico,
            'laboratorio': m.laboratorio,
            'concentracion': m.concentracion,
            'forma_farmaceutica': m.forma_farmaceutica,
            'dosis': asig.dosis or 'Según prescripción médica',
            'cantidad_prescrita': asig.cantidad_prescrita or '30 tabletas',
            'requiere_formula': m.requiere_formula,
            'cantidad_disponible': disp['cantidad_total'],
            'sedes_con_stock': disp['sedes_count'],
            'estado_stock': disp['estado'],
            'disponible': disp['cantidad_total'] > 0,
            'tiene_peticion': bool(peticion),
            'peticion': peticion,
            'en_cooldown_dp': cd_info['en_cooldown'],
            'cooldown_dp_fecha': cd_info['fecha_disponible'],
            'cooldown_dp_dias_restantes': cd_info['dias_restantes'],
            'cooldown_dp_mensaje': cd_info['mensaje'],
            'sedes': sedes_por_med.get(m.id, []),
        })

    # Serializar catálogo completo
    catalogo_data = []
    for m in medicamentos:
        disp = disponibilidad_por_med.get(m.id, {'cantidad_total': 0, 'sedes_count': 0, 'estado': 'agotado'})
        peticion = peticiones_activas.get(m.id)
        es_mio = m.id in mis_meds_dict
        cd_info = verificar_cooldown_derecho_peticion(user, m)

        catalogo_data.append({
            'id': m.id,
            'nombre_comercial': m.nombre_comercial,
            'nombre_generico': m.nombre_generico,
            'laboratorio': m.laboratorio,
            'concentracion': m.concentracion,
            'forma_farmaceutica': m.forma_farmaceutica,
            'descripcion': m.descripcion,
            'uso_indicado': m.uso_indicado,
            'requiere_formula': m.requiere_formula,
            'cantidad_disponible': disp['cantidad_total'],
            'sedes_con_stock': disp['sedes_count'],
            'estado_stock': disp['estado'],
            'disponible': disp['cantidad_total'] > 0,
            'es_mi_medicamento': es_mio,
            'tiene_peticion': bool(peticion),
            'peticion': peticion,
            'en_cooldown_dp': cd_info['en_cooldown'],
            'cooldown_dp_fecha': cd_info['fecha_disponible'],
            'cooldown_dp_dias_restantes': cd_info['dias_restantes'],
            'cooldown_dp_mensaje': cd_info['mensaje'],
            'sedes': sedes_por_med.get(m.id, []),
        })

    # 3. Sedes activas
    sedes_qs = Sede.objects.filter(estado=True).select_related('eps')
    sedes_data = []
    for s in sedes_qs:
        horario = f"{s.hora_apertura.strftime('%H:%M')} - {s.hora_cierre.strftime('%H:%M')}" if s.hora_apertura and s.hora_cierre else "08:00 - 18:00"
        sedes_data.append({
            'id': s.id,
            'nombre': s.nombre,
            'eps_nombre': s.eps.nombre if s.eps else 'Pharmony',
            'ciudad': s.ciudad,
            'direccion': s.direccion,
            'telefono': s.telefono or '',
            'horario': horario,
            'lat': s.latitud or 4.6097,
            'lng': s.longitud or -74.0817,
        })

    # 4. Datos del paciente
    paciente_info = {
        'id': user.id if user else 0,
        'nombre_completo': user.get_full_name() or user.username if user else 'Paciente Invitado',
        'email': user.email if user else '',
        'cedula': user.cedula if user else '1020304050',
        'tipo_documento': getattr(user, 'tipo_documento', 'CC'),
        'telefono': getattr(user, 'telefono', ''),
        'eps': user.eps.nombre if user and hasattr(user, 'eps') and user.eps else 'Sanitas',
        'rol': user.rol if user else 'cliente',
    }

    # 5. Métricas para el paciente
    total_asignados = len(mis_asignaciones)
    disponibles_count = sum(1 for m in mis_medicamentos_data if m['disponible'])
    agotados_count = total_asignados - disponibles_count
    peticiones_count = len(peticiones_activas)

    return JsonResponse({
        'success': True,
        'paciente': paciente_info,
        'estadisticas': {
            'total_medicamentos_tratamiento': total_asignados,
            'disponibles': disponibles_count,
            'agotados': agotados_count,
            'peticiones_activas': peticiones_count,
            'total_catalogo': len(catalogo_data),
        },
        'mis_medicamentos': mis_medicamentos_data,
        'catalogo_medicamentos': catalogo_data,
        'sedes': sedes_data,
    })


@csrf_exempt
def api_crear_derecho_peticion(request):
    """
    Genera un radicado oficial de Derecho de Petición para un medicamento agotado
    con validación de cooldown legal de 15 días y límite de descargas.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido. Usa POST.'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        medicamento_id = data.get('medicamento_id')

        if not medicamento_id:
            return JsonResponse({'success': False, 'error': 'medicamento_id es requerido.'}, status=400)

        medicamento = Medicamento.objects.filter(id=medicamento_id).first()
        if not medicamento:
            return JsonResponse({'success': False, 'error': 'Medicamento no encontrado.'}, status=404)

        user = request.user if (getattr(request, 'user', None) and request.user.is_authenticated) else Usuario.objects.filter(rol='cliente').first()
        if not user:
            return JsonResponse({'success': False, 'error': 'Usuario no identificado.'}, status=401)

        # 1. Verificar límite diario de descargas/peticiones
        puede_descargar, msg_limite = verificar_limite_descargas(user.id, medicamento.id)
        if not puede_descargar:
            return JsonResponse({'success': False, 'error': msg_limite}, status=429)

        # 2. Verificar Cooldown Legal de 15 días (No duplicar si está en trámite)
        cooldown_info = verificar_cooldown_derecho_peticion(user, medicamento)
        if cooldown_info['en_cooldown']:
            registrar_descarga(user.id, medicamento.id)
            return JsonResponse({
                'success': True,
                'en_cooldown': True,
                'mensaje': cooldown_info['mensaje'],
                'radicado': cooldown_info['radicado'],
                'peticion_id': cooldown_info.get('peticion_id'),
                'estado': cooldown_info['estado'],
                'fecha_radicacion': cooldown_info['fecha_radicacion'],
                'fecha_disponible': cooldown_info['fecha_disponible'],
                'dias_restantes': cooldown_info['dias_restantes'],
                'medicamento': medicamento.nombre_comercial,
            })

        # Actualizar datos del usuario si fueron proporcionados en el formulario
        nombre_ingresado = (data.get('nombre_completo') or '').strip()
        cedula_ingresada = (data.get('cedula') or '').strip()
        telefono_ingresado = (data.get('telefono') or '').strip()
        direccion_ingresada = (data.get('direccion') or '').strip()

        if nombre_ingresado:
            partes = nombre_ingresado.split(' ', 1)
            user.first_name = partes[0]
            if len(partes) > 1:
                user.last_name = partes[1]
        if cedula_ingresada:
            user.cedula = cedula_ingresada
        if telefono_ingresado:
            user.telefono = telefono_ingresado
        if direccion_ingresada:
            user.direccion = direccion_ingresada
        user.save()

        # Generar número de radicado único
        ahora = datetime.datetime.now()
        numero_radicado = f"DP-{ahora.strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"

        peticion = DerechoPeticion.objects.create(
            usuario=user,
            medicamento=medicamento,
            numero_radicado=numero_radicado,
            estado='radicado'
        )

        try:
            sync_derecho_peticion_firestore(peticion)
        except Exception:
            pass

        registrar_descarga(user.id, medicamento.id)

        nueva_cooldown = verificar_cooldown_derecho_peticion(user, medicamento)

        return JsonResponse({
            'success': True,
            'en_cooldown': True,
            'mensaje': 'Derecho de Petición radicado exitosamente ante la EPS. Plazo legal de respuesta: 15 días hábiles.',
            'radicado': peticion.numero_radicado,
            'peticion_id': peticion.id,
            'estado': peticion.get_estado_display(),
            'fecha_radicacion': peticion.fecha_radicacion.strftime('%d/%m/%Y %H:%M'),
            'fecha_disponible': nueva_cooldown.get('fecha_disponible'),
            'dias_restantes': nueva_cooldown.get('dias_restantes', 15),
            'medicamento': medicamento.nombre_comercial,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
