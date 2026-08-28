from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q

from Farmacia.models import Medicamento, MedicamentoUsuario


class ListarMedicamentosView(APIView):
    """GET /api/v1/medicamentos/ -> Buscador y lista general del catálogo"""
    permission_classes = [AllowAny]

    def get(self, request):
        query = request.query_params.get('q', '').strip()
        qs = Medicamento.objects.all()
        if query:
            qs = qs.filter(
                Q(nombre_comercial__icontains=query) |
                Q(nombre_generico__icontains=query) |
                Q(codigo_cum__icontains=query)
            )
        
        data = [{
            'id': m.id,
            'codigo_cum': m.codigo_cum,
            'nombre_comercial': m.nombre_comercial,
            'nombre_generico': m.nombre_generico,
            'laboratorio': m.laboratorio,
            'concentracion': m.concentracion,
            'forma_farmaceutica': m.forma_farmaceutica,
            'requiere_formula': m.requiere_formula
        } for m in qs[:50]] # Límite para rendimiento móvil
        
        return Response(data)


class DetalleMedicamentoView(APIView):
    """GET /api/v1/medicamentos/<int:pk>/ -> Información detallada"""
    permission_classes = [AllowAny]

    def get(self, request, pk):
        try:
            m = Medicamento.objects.get(pk=pk)
            return Response({
                'id': m.id,
                'codigo_cum': m.codigo_cum,
                'nombre_comercial': m.nombre_comercial,
                'nombre_generico': m.nombre_generico,
                'laboratorio': m.laboratorio,
                'concentracion': m.concentracion,
                'forma_farmaceutica': m.forma_farmaceutica,
                'descripcion': m.descripcion,
                'uso_indicado': m.uso_indicado,
                'efectos_secundarios': m.efectos_secundarios,
                'requiere_formula': m.requiere_formula,
            })
        except Medicamento.DoesNotExist:
            return Response({'detail': 'Medicamento no encontrado.'}, status=status.HTTP_404_NOT_FOUND)


class MisMedicamentosPacienteView(APIView):
    """GET /api/v1/mis-medicamentos/ -> Tratamientos/fórmulas asignadas al paciente"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        meds_user = MedicamentoUsuario.objects.filter(usuario=request.user, activo=True).select_related('medicamento')
        data = [{
            'id_asignacion': mu.id,
            'medicamento_id': mu.medicamento.id,
            'nombre': mu.medicamento.nombre_comercial,
            'dosis': mu.dosis,
            'cantidad_prescrita': mu.cantidad_prescrita,
            'fuente': mu.fuente_asignacion,
            'fecha_asignacion': mu.fecha_asignacion.strftime('%Y-%m-%d')
        } for mu in meds_user]
        return Response(data)