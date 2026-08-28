import os
import io
import json
import base64
import logging
import zipfile
import xml.etree.ElementTree as ET
from PIL import Image, ImageOps
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class MedicamentoExtraido(BaseModel):
    nombre_medicamento: str = Field(default="", description="Nombre del medicamento (genérico o comercial)")
    concentracion: str = Field(default="", description="Concentración ej: 500mg")
    forma_farmaceutica: str = Field(default="", description="Forma farmacéutica ej: Tabletas, Cápsulas")
    cantidad: str = Field(default="", description="Cantidad prescrita ej: 30 tabletas")
    posologia_indicaciones: str = Field(default="", description="Instrucciones o posología")


class ResultadoEscaneo(BaseModel):
    medicamentos: List[MedicamentoExtraido] = Field(default_factory=list, description="Lista de medicamentos encontrados en el documento")
    paciente_nombre: str = Field(default="", description="Nombre del paciente si aparece en el documento")
    paciente_cedula: str = Field(default="", description="Cédula o documento de identidad del paciente si aparece")
    codigo_formula: str = Field(default="", description="Código de autorización, folio o número de fórmula médica si aparece")
    medico_nombre: str = Field(default="", description="Nombre del médico, clínica o IPS que emite la fórmula")
    observaciones: str = Field(default="", description="Diagnóstico, notas o indicaciones generales")


def _extraer_texto_docx(file_bytes: bytes) -> str:
    """Extrae texto plano de un archivo .docx usando zipfile y XML estándar."""
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as doc:
            tree = ET.fromstring(doc.read('word/document.xml'))
            ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            texts = [node.text for node in tree.iterfind('.//w:t', ns) if node.text]
            return ' '.join(texts)
    except Exception:
        return ""


def optimizar_imagen_bytes(file_bytes: bytes, mime_type: str) -> Tuple[bytes, str]:
    if mime_type.startswith("image/"):
        try:
            img = Image.open(io.BytesIO(file_bytes))
            img = ImageOps.exif_transpose(img)
            
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            max_dimension = 1600
            w, h = img.size
            if w > max_dimension or h > max_dimension:
                img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85, optimize=True)
            return buffer.getvalue(), "image/jpeg"
        except Exception:
            return file_bytes, mime_type
    return file_bytes, mime_type


def escanear_documento_medico(file_bytes: bytes, mime_type: str, nombre_archivo: str = "") -> ResultadoEscaneo:
    """
    Envía una imagen, PDF o texto de DOCX a Google AI Studio (Gemini) y retorna los datos médicos extraídos estructuradamente.
    """
    api_key = os.getenv("ESCANER_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("No se configuró la API Key de Gemini. Agrega ESCANER_GEMINI_API_KEY o GEMINI_API_KEY en tu archivo .env")

    timeout_ms = int(os.getenv("ESCANER_GEMINI_TIMEOUT_MS", "60000"))
    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=timeout_ms))

    prompt = (
        "Examina detalladamente este documento médico (fórmula médica, receta, orden o documento clínico). "
        "Extrae cuidadosamente:\n"
        "1. Todos los medicamentos prescritos o mencionados, con su nombre (comercial o genérico), "
        "concentración (ej: 500 mg), forma farmacéutica (ej: Tabletas), cantidad prescrita (ej: 30) e indicaciones/posología.\n"
        "2. Nombre del paciente y número de cédula/documento de identidad si figuran.\n"
        "3. Número o folio de fórmula/receta médica si figura.\n"
        "4. Nombre del médico o institución prestadora de salud.\n"
        "5. Observaciones, diagnóstico o indicaciones adicionales."
    )

    # Preparar el contenido según el tipo de archivo
    es_docx = nombre_archivo.lower().endswith('.docx') or 'wordprocessingml' in mime_type
    if es_docx:
        texto_extraido = _extraer_texto_docx(file_bytes)
        if not texto_extraido:
            texto_extraido = "(Documento Word sin texto extraíble)"
        contents = [
            {"type": "text", "text": f"DOCUMENTO MÉDICO ADJUNTO (Texto extraído del archivo DOCX):\n\n{texto_extraido}\n\nINSTRUCCIÓN:\n{prompt}"}
        ]
    else:
        if mime_type.startswith("image/"):
            file_bytes, mime_type = optimizar_imagen_bytes(file_bytes, mime_type)
        tipo_entrada = "document" if mime_type == "application/pdf" else "image"
        contents = [
            {"type": tipo_entrada, "data": base64.b64encode(file_bytes).decode("utf-8"), "mime_type": mime_type},
            {"type": "text", "text": prompt}
        ]

    interaction = client.interactions.create(
        model="gemini-3.6-flash",
        input=contents,
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": ResultadoEscaneo.model_json_schema(),
        },
        store=False,
    )
    if not interaction.output_text:
        raise ValueError("No se obtuvo una respuesta válida de la IA.")
    return ResultadoEscaneo.model_validate_json(interaction.output_text)


def analizar_formula_turno(turno, forzar_reanalisis: bool = False):
    """
    Analiza la fórmula médica de un turno usando Gemini AI.
    Guarda los resultados estructurados en el objeto turno y retorna un dict con:
    - datos_ia: ResultadoEscaneo serializado
    - medicamentos_enriquecidos: lista de medicamentos encontrados con su match en BD y stock en la sede del turno.
    """
    from Farmacia.models import Medicamento
    from epsinventario.models import InventarioSede
    from django.db.models import Q

    if not turno.formula_medica:
        return None

    resultado_dict = turno.resultado_ia

    if not resultado_dict or forzar_reanalisis:
        try:
            turno.formula_medica.open('rb')
            file_bytes = turno.formula_medica.read()
            turno.formula_medica.close()

            nombre = turno.formula_medica.name.lower()
            mime_type = 'application/octet-stream'
            if nombre.endswith('.pdf'):
                mime_type = 'application/pdf'
            elif nombre.endswith(('.jpg', '.jpeg')):
                mime_type = 'image/jpeg'
            elif nombre.endswith('.png'):
                mime_type = 'image/png'
            elif nombre.endswith('.webp'):
                mime_type = 'image/webp'
            elif nombre.endswith('.docx'):
                mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

            resultado_ia = escanear_documento_medico(file_bytes, mime_type, nombre_archivo=nombre)
            resultado_dict = resultado_ia.model_dump()

            turno.resultado_ia = resultado_dict
            turno.cedula_detectada_ia = resultado_dict.get('paciente_cedula') or ''
            turno.paciente_detectado_ia = resultado_dict.get('paciente_nombre') or ''
            turno.medico_detectado_ia = resultado_dict.get('medico_nombre') or ''
            turno.save(update_fields=['resultado_ia', 'cedula_detectada_ia', 'paciente_detectado_ia', 'medico_detectado_ia'])
        except Exception as error:
            if error.__class__.__name__ in {"APITimeoutError", "ReadTimeout"}:
                logger.warning("Tiempo de espera agotado al analizar la fórmula del turno %s", turno.codigo_ticket)
            else:
                logger.exception("Error analizando fórmula del turno %s", turno.codigo_ticket)
            # Si falla la IA (por ejemplo sin red), generamos una estructura vacía o de fallback
            resultado_dict = {
                'medicamentos': [
                    {
                        'nombre_medicamento': turno.medicamento.nombre_comercial,
                        'concentracion': turno.medicamento.concentracion,
                        'forma_farmaceutica': turno.medicamento.forma_farmaceutica,
                        'cantidad': '1',
                        'posologia_indicaciones': 'Medicamento principal solicitado'
                    }
                ],
                'paciente_nombre': turno.usuario.nombre_para_mostrar(),
                'paciente_cedula': turno.usuario.cedula or '',
                'codigo_formula': '',
                'medico_nombre': '',
                'observaciones': 'Análisis automático no disponible. Verifica la fórmula manualmente.'
            }

    # Enriquecer los medicamentos detectados con la base de datos y el stock de la sede
    medicamentos_enriquecidos = []
    med_principal = turno.medicamento
    inv_principal = InventarioSede.objects.filter(sede=turno.sede, medicamento=med_principal).first()

    # Aseguramos que el medicamento principal del turno esté siempre incluido
    incluido_principal = False

    for item in resultado_dict.get('medicamentos', []):
        nombre_detectado = (item.get('nombre_medicamento') or '').strip()
        if not nombre_detectado:
            continue

        # Buscar coincidencia exacta o por contención
        match_med = Medicamento.objects.filter(
            Q(nombre_comercial__icontains=nombre_detectado) |
            Q(nombre_generico__icontains=nombre_detectado)
        ).first()

        es_el_principal = False
        if match_med and match_med.id == med_principal.id:
            es_el_principal = True
            incluido_principal = True
        elif not match_med and (med_principal.nombre_comercial.lower() in nombre_detectado.lower() or nombre_detectado.lower() in med_principal.nombre_comercial.lower()):
            match_med = med_principal
            es_el_principal = True
            incluido_principal = True

        stock_sede = 0
        inv_sede = None
        if match_med:
            inv_sede = InventarioSede.objects.filter(sede=turno.sede, medicamento=match_med).first()
            if inv_sede:
                stock_sede = inv_sede.cantidad_disponible

        medicamentos_enriquecidos.append({
            'detectado': item,
            'medicamento_db': match_med,
            'nombre_mostrar': match_med.nombre_comercial if match_med else item.get('nombre_medicamento', ''),
            'nombre_generico': match_med.nombre_generico if match_med else '',
            'concentracion_mostrar': item.get('concentracion') or (match_med.concentracion if match_med else '—'),
            'forma_mostrar': item.get('forma_farmaceutica') or (match_med.forma_farmaceutica if match_med else '—'),
            'posologia_mostrar': item.get('posologia_indicaciones') or '',
            'inventario_sede': inv_sede,
            'stock_disponible': stock_sede,
            'es_principal': es_el_principal,
            'disponible': stock_sede > 0,
        })

    # Si por alguna razón el medicamento principal del turno no vino en la lista extraída, agregarlo de primero
    if not incluido_principal:
        medicamentos_enriquecidos.insert(0, {
            'detectado': {
                'nombre_medicamento': med_principal.nombre_comercial,
                'concentracion': med_principal.concentracion,
                'forma_farmaceutica': med_principal.forma_farmaceutica,
                'cantidad': '1',
                'posologia_indicaciones': 'Medicamento principal solicitado'
            },
            'medicamento_db': med_principal,
            'nombre_mostrar': med_principal.nombre_comercial,
            'nombre_generico': med_principal.nombre_generico,
            'concentracion_mostrar': med_principal.concentracion or '—',
            'forma_mostrar': med_principal.forma_farmaceutica or '—',
            'posologia_mostrar': 'Medicamento principal solicitado',
            'inventario_sede': inv_principal,
            'stock_disponible': inv_principal.cantidad_disponible if inv_principal else 0,
            'es_principal': True,
            'disponible': (inv_principal.cantidad_disponible > 0) if inv_principal else False,
        })

    return {
        'datos_ia': resultado_dict,
        'medicamentos': medicamentos_enriquecidos,
        'paciente_nombre': resultado_dict.get('paciente_nombre', ''),
        'paciente_cedula': resultado_dict.get('paciente_cedula', ''),
        'codigo_formula': resultado_dict.get('codigo_formula', ''),
        'medico_nombre': resultado_dict.get('medico_nombre', ''),
        'observaciones': resultado_dict.get('observaciones', ''),
    }
