from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from turnos.models import Turno, MensajeTurno
from epsinventario.models import Sede


class CrearTurnoView(APIView):
    """POST /api/v1/turnos/crear/ -> Solicitar un nuevo turno presencial/domicilio"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        sede_id = request.data.get('sede_id')
        tipo_atencion = request.data.get('tipo_atencion', 'presencial') # presencial o domicilio
        ciudad_envio = request.data.get('ciudad_envio', '')

        try:
            sede = Sede.objects.get(id=sede_id)
        except Sede.DoesNotExist:
            return Response({'detail': 'Sede no encontrada.'}, status=status.HTTP_400_BAD_REQUEST)

        # Generar código correlativo de turno
        count_hoy = Turno.objects.filter(sede=sede).count() + 1
        codigo_turno = f"T-{count_hoy:03d}"

        turno = Turno.objects.create(
            paciente=request.user,
            sede=sede,
            codigo=codigo_turno,
            tipo_atencion=tipo_atencion,
            ciudad_envio=ciudad_envio,
            estado='espera'
        )

        return Response({
            'id': turno.id,
            'codigo': turno.codigo,
            'estado': turno.estado,
            'sede': sede.nombre,
            'fecha_creacion': turno.fecha_creacion
        }, status=status.HTTP_201_CREATED)


class MisTurnosView(APIView):
    """GET /api/v1/turnos/mis-turnos/ -> Historial y turnos activos del paciente"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        turnos = Turno.objects.filter(paciente=request.user).order_by('-fecha_creacion').select_related('sede')
        data = [{
            'id': t.id,
            'codigo': t.codigo,
            'sede': t.sede.nombre if t.sede else 'Sin sede',
            'estado': t.estado,
            'tipo_atencion': getattr(t, 'tipo_atencion', 'presencial'),
            'fecha': t.fecha_creacion.strftime('%Y-%m-%d %H:%M')
        } for t in turnos]
        return Response(data)


class DetalleTurnoView(APIView):
    """GET /api/v1/turnos/<int:pk>/ -> Ver estado del turno en tiempo real"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            t = Turno.objects.get(pk=pk, paciente=request.user)
            mensajes = MensajeTurno.objects.filter(turno=t).order_by('fecha_envio')
            
            return Response({
                'id': t.id,
                'codigo': t.codigo,
                'estado': t.estado,
                'sede': t.sede.nombre if t.sede else '',
                'mensajes': [{
                    'remitente': m.remitente.username,
                    'contenido': m.contenido,
                    'fecha': m.fecha_envio.strftime('%H:%M')
                } for m in mensajes]
            })
        except Turno.DoesNotExist:
            return Response({'detail': 'Turno no encontrado.'}, status=status.HTTP_404_NOT_FOUND)