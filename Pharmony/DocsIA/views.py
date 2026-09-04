import json
import re
import uuid
import unicodedata
import threading
import logging
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from Farmacia.models import Medicamento, MedicamentoUsuario
from Farmacia.firestore_sync import sync_medicamento_usuario_firestore
from .services.gemini_scanner import escanear_documento_medico

logger = logging.getLogger(__name__)


def normalizar_texto(texto):
    if not texto:
        return ""
    texto = unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('utf-8')
    return texto.lower().strip()


def buscar_coincidencia_medicamento(nombre_med):
    norm_query = normalizar_texto(nombre_med)
    if not norm_query:
        return None, []

    coincidencias_exactas = list(Medicamento.objects.filter(
        Q(nombre_comercial__iexact=nombre_med) | Q(nombre_generico__iexact=nombre_med)
    )[:5])
    if coincidencias_exactas:
        return coincidencias_exactas[0], coincidencias_exactas

    coincidencias_cont = list(Medicamento.objects.filter(
        Q(nombre_comercial__icontains=norm_query) | Q(nombre_generico__icontains=norm_query)
    )[:5])
    if coincidencias_cont:
        return coincidencias_cont[0], coincidencias_cont

    tokens = [t for t in re.split(r'[\s,.-]+', norm_query) if len(t) >= 3 and not t.isdigit()]
    if tokens:
        query_tokens = Q()
        for token in tokens[:4]:
            query_tokens |= Q(nombre_comercial__icontains=token) | Q(nombre_generico__icontains=token)
        
        coincidencias_tok = list(Medicamento.objects.filter(query_tokens)[:5])
        if coincidencias_tok:
            return coincidencias_tok[0], coincidencias_tok

    return None, []


def escaner_ui_view(request):
    return render(request, 'DocsIA/escaner.html')


@csrf_exempt
def escanear_documento_api(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido. Usa POST.'}, status=405)

    if 'documento' not in request.FILES:
        return JsonResponse({'success': False, 'error': 'Debes adjuntar un archivo en el campo "documento".'}, status=400)

    archivo = request.FILES['documento']
    mime_type = archivo.content_type or 'application/octet-stream'

    if mime_type == 'application/octet-stream':
        nombre_lower = archivo.name.lower()
        if nombre_lower.endswith('.pdf'):
            mime_type = 'application/pdf'
        elif nombre_lower.endswith(('.jpg', '.jpeg')):
            mime_type = 'image/jpeg'
        elif nombre_lower.endswith('.png'):
            mime_type = 'image/png'
        elif nombre_lower.endswith('.webp'):
            mime_type = 'image/webp'

    try:
        file_bytes = archivo.read()
        resultado_ia = escanear_documento_medico(file_bytes, mime_type)

        medicamentos_procesados = []
        asignados_automaticamente = []

        for item in resultado_ia.medicamentos:
            nombre_med = item.nombre_medicamento.strip()
            if not nombre_med:
                continue

            coincidencia_principal, coincidencias_qs = buscar_coincidencia_medicamento(nombre_med)
            
            if not coincidencia_principal:
                codigo_cum_auto = f"IA-{uuid.uuid4().hex[:6].upper()}"
                coincidencia_principal = Medicamento.objects.create(
                    codigo_cum=codigo_cum_auto,
                    nombre_generico=nombre_med,
                    nombre_comercial=nombre_med,
                    laboratorio="Fórmula Médica (IA)",
                    concentracion=(item.concentracion or 'Estándar').strip(),
                    forma_farmaceutica=(item.forma_farmaceutica or 'Tableta').strip(),
                    descripcion=f"Prescrito en fórmula médica. Indicaciones: {item.posologia_indicaciones or 'Según indicación médica'}",
                    uso_indicado=(item.posologia_indicaciones or 'Tratamiento prescrito').strip(),
                    efectos_secundarios="Consulte a su médico o farmacéutico.",
                    requiere_formula=True
                )
                coincidencias_qs = [coincidencia_principal]

            fue_asignado = False
            if request.user.is_authenticated and coincidencia_principal:
                dosis_val = (item.posologia_indicaciones or '')[:150]
                cant_val = (item.cantidad or '')[:100]
                med_user, created = MedicamentoUsuario.objects.update_or_create(
                    usuario=request.user,
                    medicamento=coincidencia_principal,
                    defaults={
                        'dosis': dosis_val,
                        'cantidad_prescrita': cant_val,
                        'fuente_asignacion': 'ia_formula',
                        'activo': True
                    }
                )
                threading.Thread(target=sync_medicamento_usuario_firestore, args=(med_user,), daemon=True).start()
                fue_asignado = True
                asignados_automaticamente.append({
                    'id': coincidencia_principal.id,
                    'nombre': coincidencia_principal.nombre_comercial,
                    'dosis': dosis_val,
                    'created': created
                })
            
            coincidencias_lista = [
                {
                    'id': med.id,
                    'codigo_cum': med.codigo_cum,
                    'nombre_comercial': med.nombre_comercial,
                    'nombre_generico': med.nombre_generico,
                    'laboratorio': med.laboratorio,
                    'concentracion': med.concentracion,
                    'forma_farmaceutica': med.forma_farmaceutica,
                    'requiere_formula': med.requiere_formula,
                }
                for med in coincidencias_qs
            ]

            medicamentos_procesados.append({
                'detectado_ia': {
                    'nombre': item.nombre_medicamento,
                    'concentracion': item.concentracion,
                    'forma_farmaceutica': item.forma_farmaceutica,
                    'cantidad': item.cantidad,
                    'posologia_indicaciones': item.posologia_indicaciones,
                },
                'encontrado_en_inventario': True,
                'asignado_a_perfil': fue_asignado,
                'coincidencias': coincidencias_lista
            })

        return JsonResponse({
            'success': True,
            'paciente_nombre': resultado_ia.paciente_nombre,
            'medico_nombre': resultado_ia.medico_nombre,
            'observaciones': resultado_ia.observaciones,
            'medicamentos': medicamentos_procesados,
            'asignados_automaticamente': asignados_automaticamente,
            'total_detectados': len(medicamentos_procesados),
            'usuario_autenticado': request.user.is_authenticated
        })

    except Exception as e:
        logger.exception("Error al procesar escaneo con IA en DocsIA: %s", e)
        error_msg = str(e)
        if "API Key" in error_msg:
            user_msg = "Error de configuración: Clave de Gemini no válida o ausente."
        elif "saturado" in error_msg or "429" in error_msg or "quota" in error_msg.lower():
            user_msg = "El servicio de IA alcanzó temporalmente el límite de consultas por minuto. Por favor reintenta en unos segundos."
        elif "vacío" in error_msg.lower():
            user_msg = "El archivo adjunto está vacío o dañado."
        else:
            user_msg = f"No se pudo extraer la información del documento: {error_msg}"

        return JsonResponse({
            'success': False,
            'error': user_msg
        }, status=500)


@csrf_exempt
def asignar_medicamento_usuario_api(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido.'}, status=405)

    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Debes iniciar sesión para asignar medicamentos.'}, status=401)

    try:
        data = json.loads(request.body) if request.body else request.POST
        medicamento_id = data.get('medicamento_id')
        dosis = data.get('dosis', '')
        cantidad = data.get('cantidad', '')

        if not medicamento_id:
            return JsonResponse({'success': False, 'error': 'medicamento_id es requerido.'}, status=400)

        medicamento = Medicamento.objects.get(id=medicamento_id)
        med_user, created = MedicamentoUsuario.objects.update_or_create(
            usuario=request.user,
            medicamento=medicamento,
            defaults={
                'dosis': str(dosis)[:150],
                'cantidad_prescrita': str(cantidad)[:100],
                'fuente_asignacion': 'ia_formula',
                'activo': True
            }
        )
        threading.Thread(target=sync_medicamento_usuario_firestore, args=(med_user,), daemon=True).start()

        return JsonResponse({
            'success': True,
            'mensaje': f'Medicamento {medicamento.nombre_comercial} asignado exitosamente a tu tratamiento.',
            'medicamento_id': medicamento.id,
            'asignacion_id': med_user.id
        })
    except Medicamento.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Medicamento no encontrado.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
