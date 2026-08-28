from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from epsinventario.models import Sede


class ListarSedesView(APIView):
    """GET /api/v1/sedes/ -> Lista completa de sedes para mapa/filtros en Flutter"""
    permission_classes = [AllowAny]

    def get(self, request):
        sedes = Sede.objects.filter(estado=True)
        data = [{
            'id': s.id,
            'nombre': s.nombre,
            'ciudad': s.ciudad,
            'direccion': s.direccion or 'Dirección no especificada',
            'telefono': s.telefono or '',
            'lat': float(s.latitud) if s.latitud else None,
            'lng': float(s.longitud) if s.longitud else None,
            'hora_apertura': str(getattr(s, 'hora_apertura', '')),
            'atiende_fines_semana': getattr(s, 'atiende_fines_semana', False)
        } for s in sedes]
        return Response(data)