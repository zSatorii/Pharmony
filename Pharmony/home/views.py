from django.shortcuts import render
from django.views.decorators.cache import never_cache

# Noticias de ejemplo — puedes sustituirlas por datos reales de una BD o API
NOTICIAS = [
    {
        "id": 1,
        "categoria": "Salud pública",
        "titulo": "Colombia actualizará el listado de medicamentos esenciales en 2026",
        "resumen": "El Ministerio de Salud publicó el borrador del nuevo vademécum nacional con más de 600 principios activos incluidos, buscando ampliar el acceso a tratamientos de alta complejidad.",
        "fecha": "24 jun. 2026",
        "lectura": "3 min de lectura",
        "icono": "💊",
    },
    {
        "id": 2,
        "categoria": "Tecnología",
        "titulo": "Inteligencia artificial acelera el descubrimiento de nuevos antibióticos",
        "resumen": "Investigadores del MIT usaron modelos de lenguaje para identificar moléculas con potencial antibacteriano contra cepas resistentes, reduciendo el tiempo de búsqueda de años a semanas.",
        "fecha": "22 jun. 2026",
        "lectura": "5 min de lectura",
        "icono": "🧬",
    },
    {
        "id": 3,
        "categoria": "Regulación",
        "titulo": "INVIMA fortalece la vigilancia de medicamentos biológicos en Colombia",
        "resumen": "El instituto aprueba nuevas directrices para el registro y seguimiento post-mercado de biosimilares, garantizando mayor seguridad para los pacientes y transparencia en la cadena farmacéutica.",
        "fecha": "20 jun. 2026",
        "lectura": "4 min de lectura",
        "icono": "🔬",
    },
    {
        "id": 4,
        "categoria": "Farmacia",
        "titulo": "Digitalización de farmacias: el reto del sector en Latinoamérica",
        "resumen": "Un estudio regional revela que el 68% de las farmacias independientes aún no cuentan con sistemas de gestión de inventario digital, aumentando el riesgo de desabastecimiento y errores de dispensación.",
        "fecha": "18 jun. 2026",
        "lectura": "6 min de lectura",
        "icono": "🏥",
    },
    {
        "id": 5,
        "categoria": "Investigación",
        "titulo": "Nueva vacuna contra el dengue entra en fase III de ensayos clínicos",
        "resumen": "Un consorcio de laboratorios latinoamericanos inicia la última fase de pruebas de su candidata vacunal contra el dengue, con alta eficacia reportada en las fases anteriores y sin efectos adversos graves.",
        "fecha": "15 jun. 2026",
        "lectura": "4 min de lectura",
        "icono": "💉",
    },
    {
        "id": 6,
        "categoria": "Gestión",
        "titulo": "Control de cadena de frío: clave para preservar la calidad de los medicamentos",
        "resumen": "Expertos del sector destacan la importancia de los sistemas de monitoreo continuo de temperatura en el almacenamiento y transporte de productos farmacéuticos, especialmente biológicos y vacunas.",
        "fecha": "12 jun. 2026",
        "lectura": "3 min de lectura",
        "icono": "🌡️",
    },
]

import requests
import xml.etree.ElementTree as ET

def obtener_noticias_salud():
    url = "https://www.eltiempo.com/rss/salud.xml"
    noticias = []
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            channel = root.find("channel")
            if channel is not None:
                items = channel.findall("item")
                for i, item in enumerate(items):
                    title = item.find("title").text if item.find("title") is not None else ""
                    description = item.find("description").text if item.find("description") is not None else ""
                    link = item.find("link").text if item.find("link") is not None else "#"
                    pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
                    
                    fecha = pub_date
                    if pub_date:
                        try:
                            parts = pub_date.split()
                            if len(parts) >= 4:
                                day = parts[1]
                                month_str = parts[2][:3].lower()
                                year = parts[3]
                                meses_es = {
                                    "jan": "ene", "feb": "feb", "mar": "mar", "apr": "abr",
                                    "may": "may", "jun": "jun", "jul": "jul", "aug": "ago",
                                    "sep": "sep", "oct": "oct", "nov": "nov", "dec": "dic"
                                }
                                month_es = meses_es.get(month_str, month_str)
                                fecha = f"{day} {month_es}. {year}"
                        except Exception:
                            pass
                    
                    icono = "💊"
                    categoria = "Salud"
                    t_lower = title.lower()
                    if "vacuna" in t_lower or "vacunación" in t_lower:
                        icono = "💉"
                        categoria = "Prevención"
                    elif "tecnología" in t_lower or "ia" in t_lower or "inteligencia artificial" in t_lower:
                        icono = "🧬"
                        categoria = "Tecnología"
                    elif "investigación" in t_lower or "estudio" in t_lower or "descubren" in t_lower:
                        icono = "🔬"
                        categoria = "Investigación"
                    elif "invima" in t_lower or "ministerio" in t_lower or "gobierno" in t_lower or "minsalud" in t_lower:
                        icono = "🏥"
                        categoria = "Regulación"
                    
                    enclosure = item.find("enclosure")
                    image_url = enclosure.attrib.get("url") if enclosure is not None else None

                    words = len(description.split())
                    reading_time = max(2, words // 35)

                    noticias.append({
                        "id": i + 1,
                        "categoria": categoria,
                        "titulo": title,
                        "resumen": description,
                        "fecha": fecha,
                        "lectura": f"{reading_time} min de lectura",
                        "icono": icono,
                        "link": link,
                        "image_url": image_url
                    })
    except Exception as e:
        print(f"Error al obtener noticias RSS: {e}")
    
    if not noticias:
        return NOTICIAS
    return noticias

@never_cache
def home(request):
    """Vista principal de la página de inicio de Pharmony."""
    noticias = obtener_noticias_salud()
    context = {
        "noticias": noticias,
        "noticia_destacada": noticias[0] if noticias else None,
        "noticias_secundarias": noticias[1:] if len(noticias) > 1 else [],
    }
    return render(request, "home/index.html", context)
