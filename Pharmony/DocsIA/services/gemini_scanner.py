import os
import io
import json
from PIL import Image, ImageOps
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Tuple


class MedicamentoExtraido(BaseModel):
    nombre_medicamento: str = Field(default="")
    concentracion: str = Field(default="")
    forma_farmaceutica: str = Field(default="")
    cantidad: str = Field(default="")
    posologia_indicaciones: str = Field(default="")


class ResultadoEscaneo(BaseModel):
    medicamentos: List[MedicamentoExtraido] = Field(default_factory=list)
    paciente_nombre: str = Field(default="")
    medico_nombre: str = Field(default="")
    observaciones: str = Field(default="")


_client_instance = None


def get_gemini_client() -> genai.Client:
    global _client_instance
    if _client_instance is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("No se configuró la API Key de Gemini. Agrega GEMINI_API_KEY en tu archivo .env")
        _client_instance = genai.Client(api_key=api_key)
    return _client_instance


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


def escanear_documento_medico(file_bytes: bytes, mime_type: str) -> ResultadoEscaneo:
    client = get_gemini_client()
    file_bytes_opt, mime_type_opt = optimizar_imagen_bytes(file_bytes, mime_type)

    prompt = """Examina esta fórmula o receta médica.
Extrae todos los medicamentos mencionados.
Responde ÚNICAMENTE un JSON válido con esta estructura exacta:
{
  "medicamentos": [
    {
      "nombre_medicamento": "Nombre del medicamento (genérico o comercial)",
      "concentracion": "Ej: 500mg, 10mg/ml (o cadena vacía si no aparece)",
      "forma_farmaceutica": "Ej: Tabletas, Jarabe, Cápsulas (o cadena vacía)",
      "cantidad": "Ej: 30 tabletas, 2 frascos (o cadena vacía)",
      "posologia_indicaciones": "Instrucciones de uso prescritas por el médico"
    }
  ],
  "paciente_nombre": "Nombre del paciente si aparece o cadena vacía",
  "medico_nombre": "Nombre del médico o clínica si aparece o cadena vacía",
  "observaciones": "Observaciones o notas adicionales"
}"""

    config_json = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.0
    )

    modelos = ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-flash-latest"]
    response = None
    ultimo_error = None

    for model_name in modelos:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    types.Part.from_bytes(data=file_bytes_opt, mime_type=mime_type_opt),
                    prompt
                ],
                config=config_json
            )
            if response and response.text:
                break
        except Exception as err:
            ultimo_error = err
            continue

    if not response and ultimo_error:
        raise ultimo_error

    if not response or not response.text:
        raise ValueError("No se obtuvo una respuesta válida de la IA.")

    raw_text = response.text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as je:
        raise ValueError(f"Error al decodificar respuesta JSON de la IA: {str(je)}")

    meds_list = []
    for item in data.get("medicamentos", []):
        if isinstance(item, dict):
            meds_list.append(MedicamentoExtraido(
                nombre_medicamento=str(item.get("nombre_medicamento") or "").strip(),
                concentracion=str(item.get("concentracion") or "").strip(),
                forma_farmaceutica=str(item.get("forma_farmaceutica") or "").strip(),
                cantidad=str(item.get("cantidad") or "").strip(),
                posologia_indicaciones=str(item.get("posologia_indicaciones") or "").strip()
            ))

    return ResultadoEscaneo(
        medicamentos=meds_list,
        paciente_nombre=str(data.get("paciente_nombre") or "").strip(),
        medico_nombre=str(data.get("medico_nombre") or "").strip(),
        observaciones=str(data.get("observaciones") or "").strip()
    )
