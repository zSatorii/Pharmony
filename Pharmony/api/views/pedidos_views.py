from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from pedidos.models import Pedido


class CrearPedidoView(APIView):
    """POST /api/v1/pedidos/crear/ -> Generar un pedido de medicamentos"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        direccion = request.data.get('direccion_entrega', request.user.direccion)
        if not direccion:
            return Response({'detail': 'Debes especificar una dirección de entrega.'}, status=status.HTTP_400_BAD_REQUEST)

        pedido = Pedido.objects.create(
            usuario=request.user,
            direccion_entrega=direccion,
            estado='pendiente'
        )
        return Response({'id': pedido.id, 'estado': pedido.estado, 'detail': 'Pedido creado con éxito.'}, status=status.HTTP_201_CREATED)


class MisPedidosView(APIView):
    """GET /api/v1/pedidos/mis-pedidos/ -> Lista de pedidos del usuario"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pedidos = Pedido.objects.filter(usuario=request.user).order_by('-fecha_creacion')
        data = [{
            'id': p.id,
            'estado': p.estado,
            'direccion': p.direccion_entrega,
            'fecha': p.fecha_creacion.strftime('%Y-%m-%d %H:%M')
        } for p in pedidos]
        return Response(data)


class TrackingPedidoView(APIView):
    """GET /api/v1/pedidos/<int:pk>/seguimiento/ -> Estado en vivo del domicilio"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            p = Pedido.objects.get(pk=pk, usuario=request.user)
            return Response({
                'id': p.id,
                'estado': p.estado,
                'direccion': p.direccion_entrega,
                'ultima_actualizacion': getattr(p, 'fecha_actualizacion', p.fecha_creacion)
            })
        except Pedido.DoesNotExist:
            return Response({'detail': 'Pedido no encontrado.'}, status=status.HTTP_404_NOT_FOUND)