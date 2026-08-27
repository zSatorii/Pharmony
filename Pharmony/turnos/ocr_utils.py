import re
import io

import pytesseract
from PIL import Image

# Si Tesseract no quedó en el PATH, descomenta y ajusta esta línea:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

try:
    from pdf2image import convert_from_bytes
except ImportError:
    convert_from_bytes = None

# Si poppler no quedó en el PATH, pásale poppler_path a convert_from_bytes abajo,
# ej: convert_from_bytes(contenido, poppler_path=r'C:\poppler\Library\bin')


def _extraer_texto_de_imagen(imagen_bytes):
    imagen = Image.open(io.BytesIO(imagen_bytes))
    return pytesseract.image_to_string(imagen, lang='spa')


def extraer_texto_documento(archivo_field):
    """
    Recibe el FieldFile de formula_medica y devuelve el texto detectado
    por OCR. Soporta imágenes directas y PDF (primera página). Los .docx
    no se procesan aquí (ya se revisan en el visor con mammoth.js).
    """
    if not archivo_field:
        return ''
    try:
        archivo_field.open('rb')
        contenido = archivo_field.read()
        archivo_field.close()
    except Exception:
        return ''

    nombre = archivo_field.name.lower()

    if nombre.endswith('.pdf'):
        if convert_from_bytes is None:
            return ''
        try:
            paginas = convert_from_bytes(contenido, first_page=1, last_page=1)
            if not paginas:
                return ''
            buffer = io.BytesIO()
            paginas[0].save(buffer, format='PNG')
            return _extraer_texto_de_imagen(buffer.getvalue())
        except Exception:
            return ''

    if nombre.endswith(('.jpg', '.jpeg', '.png', '.webp')):
        try:
            return _extraer_texto_de_imagen(contenido)
        except Exception:
            return ''

    return ''


def extraer_cedula(texto):
    match = re.search(r'(?:C\.?C\.?|C[eé]dula)[^\d]{0,15}(\d{6,12})', texto, re.IGNORECASE)
    return match.group(1) if match else None


def extraer_codigo_formula(texto):
    match = re.search(r'No\.?\s*([\d]{3,6}-[\d]{5,10})', texto)
    return match.group(1) if match else None