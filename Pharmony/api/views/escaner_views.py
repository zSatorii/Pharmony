from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from DocsIA.views import escanear_documento_api


class EscanearFormulaApiView(APIView):
    """POST /api/v1/docs-ia/escanear/ -> Recibe imagen/PDF de fórmula y responde con JSON de la IA"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Delegamos la lógica al procesador central de DocsIA
        return escanear_documento_api(request)