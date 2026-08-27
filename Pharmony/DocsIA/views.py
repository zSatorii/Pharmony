from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from Farmacia.models import Medicamento
from .services.gemini_scanner import escanear_documento_medico


def escaner_ui_view(request):
    """
    Renderiza la vista principal para subir y escanear documentos médicos.
    """
    return render(request, 'DocsIA/escaner.html')


@csrf_exempt
def escanear_documento_api(request):
    """
    API Endpoint para procesar el documento subido, enviar a Google AI Studio y buscar en el inventario.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido. Usa POST.'}, status=405)

    if 'documento' not in request.FILES:
        return JsonResponse({'success': False, 'error': 'Debes adjuntar un archivo en el campo "documento".'}, status=400)

    archivo = request.FILES['documento']
    mime_type = archivo.content_type or 'application/octet-stream'

    # Autodetectar tipo MIME si es genérico
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

        for item in resultado_ia.medicamentos:
            nombre_med = item.nombre_medicamento.strip()
            
            # Buscar coincidencias en la base de datos de Pharmony
            coincidencias_qs = Medicamento.objects.filter(
                Q(nombre_generico__icontains=nombre_med) |
                Q(nombre_comercial__icontains=nombre_med)
            )[:5] # Limitar a las 5 mejores coincidencias

            encontrado = coincidencias_qs.exists()
            
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
                'encontrado_en_inventario': encontrado,
                'coincidencias': coincidencias_lista
            })

        return JsonResponse({
            'success': True,
            'paciente_nombre': resultado_ia.paciente_nombre,
            'medico_nombre': resultado_ia.medico_nombre,
            'observaciones': resultado_ia.observaciones,
            'medicamentos': medicamentos_procesados,
            'total_detectados': len(medicamentos_procesados)
        })

    except Exception:
        return JsonResponse({
            'success': False,
            'error': 'No fue posible analizar el documento. Verifica la fórmula manualmente.'
        }, status=500)
