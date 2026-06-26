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


@never_cache
def home(request):
    """Vista principal de la página de inicio de Pharmony."""
    context = {
        "noticias": NOTICIAS,
        "noticia_destacada": NOTICIAS[0],
        "noticias_secundarias": NOTICIAS[1:],
    }
    return render(request, "home/index.html", context)
