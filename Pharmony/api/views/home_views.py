from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from epsinventario.models import Sede
from home.views import obtener_noticias_salud


class HomeDataView(APIView):
    """
    GET /api/v1/home/

    Datos públicos para la pantalla de inicio de la app Flutter:
    noticias de salud (con su propio fallback si el RSS falla) y sedes
    con coordenadas para el mapa.

    No requiere autenticación (AllowAny) porque es la misma información
    que hoy ve cualquier visitante en la landing page sin necesidad de
    iniciar sesión.

    Reutiliza obtener_noticias_salud() de home/views.py en vez de
    reescribir el scraping/parsing del RSS de El Tiempo, para no tener
    dos versiones de esa lógica que puedan desalinearse con el tiempo.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        noticias = obtener_noticias_salud()

        sedes_data = []
        try:
            sedes_qs = Sede.objects.filter(estado=True).select_related('eps')
            for s in sedes_qs:
                if s.latitud is not None and s.longitud is not None:
                    sedes_data.append({
                        'id': s.id,
                        'nombre': s.nombre,
                        'ciudad': s.ciudad,
                        'direccion': s.direccion or 'Dirección no especificada',
                        'telefono': s.telefono or '',
                        'eps': s.eps.nombre if s.eps else 'Pharmony',
                        'lat': float(s.latitud),
                        'lng': float(s.longitud),
                    })
        except Exception:
            # Igual que en home/views.py: si algo falla consultando
            # sedes, se devuelve una lista vacía en vez de tumbar todo
            # el endpoint (las noticias sí deben poder mostrarse igual).
            sedes_data = []

        return Response({
            'noticia_destacada': noticias[0] if noticias else None,
            'noticias_secundarias': noticias[1:] if len(noticias) > 1 else [],
            'sedes': sedes_data,
        })
