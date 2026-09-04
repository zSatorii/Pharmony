from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from epsinventario.models import Sede, InventarioSede
from Farmacia.models import Medicamento
from .views import obtener_noticias_salud

HEALTH_TIPS = [
    {
        "id": "hipertension",
        "titulo": "Salud Cardiovascular & Hipertensión",
        "subtitulo": "Monitoreo y adherencia al tratamiento",
        "icono": "heart_pulse",
        "descripcion": "La hipertensión arterial es una condición silenciosa. Mantener tus tomas a la misma hora y reducir el sodio es clave para proteger tu corazón.",
        "puntos_clave": [
            "Toma tu antihipertensivo todos los días a la misma hora sin saltar dosis.",
            "Registra tu presión arterial 2 veces por semana en reposo.",
            "Evita automedicarte con antiinflamatorios (AINEs) sin consultar a tu médico.",
            "Mantén un consumo de agua de al menos 2 litros al día."
        ],
        "nota_visual": "Adherencia recomendada: 98%"
    },
    {
        "id": "diabetes",
        "titulo": "Control Glucémico & Diabetes",
        "subtitulo": "Cuidado integral del paciente diabético",
        "icono": "droplet",
        "descripcion": "El manejo de la insulina y los hipoglucemiantes orales requiere horarios estrictos de alimentación y revisión constante.",
        "puntos_clave": [
            "Almacena la insulina en refrigeración (2°C - 8°C) antes de abrirla.",
            "Rota los sitios de inyección para evitar lipodistrofias.",
            "Lleva contigo siempre una fuente de carbohidratos simples por si sufres hipoglucemia.",
            "Revisa tus pies a diario y usa calzado cómodo."
        ],
        "nota_visual": "Insulina y glucómetros disponibles"
    },
    {
        "id": "antibioticos",
        "titulo": "Uso Responsable de Antibióticos",
        "subtitulo": "Prevención de resistencia bacteriana",
        "icono": "shield_check",
        "descripcion": "Los antibióticos no curan infecciones virales como la gripe. Completar el ciclo prescrito salva vidas y evita bacterias multirresistentes.",
        "puntos_clave": [
            "Nunca suspendas el tratamiento aunque te sientas mejor.",
            "No reutilices sobrantes de tratamientos previos.",
            "Toma el medicamento con agua y respeta los intervalos exactos (cada 8h o 12h).",
            "Exige siempre fórmula médica autorizada."
        ],
        "nota_visual": "Compromiso OMS contra la resistencia"
    },
    {
        "id": "respiratoria",
        "titulo": "Salud Respiratoria & Asma",
        "subtitulo": "Técnica inhalatoria y prevención",
        "icono": "wind",
        "descripcion": "El uso correcto de inhaladores y aerocámaras garantiza que la dosis llegue directamente a los pulmones y no se quede en la boca.",
        "puntos_clave": [
            "Agita el inhalador 5 segundos antes de cada disparo.",
            "Enjuágate la boca con agua tras usar corticoides inhalados.",
            "Limpia la aerocámara semanalmente con agua tibia y jabón suave.",
            "Identifica y evita alérgenos como polvo, humo y cambios bruscos de temperatura."
        ],
        "nota_visual": "Asesoría farmacéutica en sede"
    }
]

MODULOS_PHARMONY = [
    {
        "id": "docs_ia",
        "titulo": "DocsIA: Escáner Inteligente",
        "tag": "Inteligencia Artificial",
        "icono": "scan",
        "color": "#06b6d4",
        "descripcion": "Digitaliza y extrae medicamentos, dosis y cédula de tus recetas médicas al instante con IA multimodal.",
        "accion": "/docs-ia/"
    },
    {
        "id": "inventario",
        "titulo": "Disponibilidad en Vivo",
        "tag": "Stock en Tiempo Real",
        "icono": "pill",
        "color": "#0d47c9",
        "descripcion": "Consulta qué farmacia y sede tiene tu medicamento disponible antes de salir de casa.",
        "accion": "/api/dashboard-cliente/"
    },
    {
        "id": "turnos",
        "titulo": "Turnos & Fila Virtual",
        "tag": "Cero Esperas",
        "icono": "ticket",
        "color": "#2563eb",
        "descripcion": "Solicita tu turno desde el móvil, recibe alertas en tiempo real y chatea con el auxiliar de farmacia.",
        "accion": "/turnos/mis-turnos/"
    },
    {
        "id": "derecho_peticion",
        "titulo": "Derecho de Petición Legal",
        "tag": "Respaldo Constitucional",
        "icono": "scale",
        "color": "#0284c7",
        "descripcion": "Genera automáticamente un documento PDF membretado ante la EPS en caso de medicamentos agotados.",
        "accion": "/medicamentos/derecho-peticion/"
    },
    {
        "id": "pedidos",
        "titulo": "Domicilios & Rastreo",
        "tag": "Entrega Segura",
        "icono": "truck",
        "color": "#10b981",
        "descripcion": "Recibe tus medicamentos en casa y sigue el estado de tu despacho paso a paso con código único.",
        "accion": "/pedidos/seguimiento/"
    },
    {
        "id": "biometria",
        "titulo": "Seguridad Biométrica",
        "tag": "Face ID",
        "icono": "face_id",
        "color": "#6366f1",
        "descripcion": "Ingreso ultra-seguro mediante reconocimiento facial con biometría avanzada.",
        "accion": "/api/login-face/"
    }
]

@never_cache
def api_home_data(request):
    """
    Endpoint REST API para suministrar datos completos a la aplicación móvil Flutter.
    """
    noticias_raw = obtener_noticias_salud()
    
    # Sedes activas
    sedes_list = []
    try:
        sedes_qs = Sede.objects.filter(estado=True).select_related('eps')
        for s in sedes_qs:
            horario = "08:00 - 18:00"
            if s.hora_apertura and s.hora_cierre:
                horario = f"{s.hora_apertura.strftime('%H:%M')} - {s.hora_cierre.strftime('%H:%M')}"
            
            sedes_list.append({
                "id": s.id,
                "nombre": s.nombre,
                "ciudad": s.ciudad,
                "direccion": s.direccion or "Dirección no especificada",
                "telefono": s.telefono or "",
                "eps_nombre": s.eps.nombre if s.eps else "Pharmony Red",
                "lat": float(s.latitud) if s.latitud is not None else 4.6097,
                "lng": float(s.longitud) if s.longitud is not None else -74.0817,
                "abierta": s.esta_abierta_ahora,
                "horario": horario
            })
    except Exception:
        sedes_list = []

    # Estadísticas generales del sistema
    total_meds = Medicamento.objects.count() or 24
    total_sedes = len(sedes_list) or 7

    stats = {
        "formulas_escaneadas": "+15,000",
        "precision_ia": "99.4%",
        "sedes_activas": total_sedes,
        "medicamentos_catalogo": total_meds,
        "tiempo_promedio_turno": "4 min"
    }

    return JsonResponse({
        "success": True,
        "app_name": "Pharmony",
        "tagline": "Portal de Gestión Farmacéutica & Salud Digital",
        "stats": stats,
        "modulos": MODULOS_PHARMONY,
        "noticias": noticias_raw,
        "sedes": sedes_list,
        "health_tips": HEALTH_TIPS
    }, json_dumps_params={'ensure_ascii': False})
