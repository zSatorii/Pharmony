from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status

from .models import Medicamento
from .serializers import MedicamentoSerializer


class MedicamentoViewSet(viewsets.ModelViewSet):

    queryset = Medicamento.objects.all().order_by("nombre_comercial")
    serializer_class = MedicamentoSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            serializer.save()

            return Response(
                {
                    "mensaje": "Medicamento registrado correctamente",
                    "data": serializer.data
                },
                status=status.HTTP_201_CREATED
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )