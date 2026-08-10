import os
import json
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List


class MedicamentoExtraido(BaseModel):
    nombre_medicamento: str = Field(description="Nombre genérico o comercial del medicamento")
    concentracion: str = Field(description="Concentración (ej. 500mg, 10mg/ml, etc.)", default="")
    forma_farmaceutica: str = Field(description="Forma farmacéutica (ej. Tabletas, Jarabe, Cápsulas)", default="")
    cantidad: str = Field(description="Cantidad prescrita o solicitada (ej. 30 tabletas, 2 frascos)", default="")
    posologia_indicaciones: str = Field(description="Modo de uso o indicaciones del médico", default="")


class ResultadoEscaneo(BaseModel):
    medicamentos: List[MedicamentoExtraido] = Field(default_factory=list, description="Lista de medicamentos encontrados en el documento")
    paciente_nombre: str = Field(default="", description="Nombre del paciente si aparece en el documento")
    medico_nombre: str = Field(default="", description="Nombre del médico o clínica si aparece")
    observaciones: str = Field(default="", description="Observaciones o notas adicionales")


def escanear_documento_medico(file_bytes: bytes, mime_type: str) -> ResultadoEscaneo:
    """
    Envía una imagen o PDF a Google AI Studio (Gemini 2.5 Flash) y retorna los medicamentos extraídos en formato estructurado.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("No se configuró la API Key de Gemini. Agrega GEMINI_API_KEY en tu archivo .env")

    client = genai.Client(api_key=api_key)

    prompt = (
        "Examina detenidamente esta imagen o documento médico (fórmula médica, receta o factura). "
        "Extrae todos los medicamentos mencionados con sus nombres (genérico o comercial), concentraciones, "
        "forma farmacéutica, cantidad prescrita e indicaciones."
    )

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=ResultadoEscaneo,
        temperature=0.1
    )


    modelos = ["gemini-flash-latest", "gemini-3-flash-preview", "gemini-2.0-flash"]
    response = None
    ultimo_error = None

    for model_name in modelos:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
                    prompt
                ],
                config=config
            )
            if response:
                break
        except Exception as err:
            ultimo_error = err
            continue

    if not response and ultimo_error:
        raise ultimo_error

    if response.parsed:
        return response.parsed
    elif response.text:
        data = json.loads(response.text)
        return ResultadoEscaneo(**data)
    else:
        raise ValueError("No se obtuvo una respuesta válida de la IA.")
