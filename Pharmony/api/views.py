from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from Farmacia.services import CrearUsuarioEpsError, crear_usuario_eps_completo

from .permissions import PuedeCrearUsuarioEps
from .serializers import CrearUsuarioEpsSerializer, UsuarioEpsResponseSerializer


class CrearUsuarioEpsView(APIView):
    """
    POST /api/v1/usuarios-eps/

    Crea un usuario EPS (Django + Firebase Auth + Firestore) reutilizando
    la misma lógica que usa el admin de Django (Farmacia/services.py).

    Reglas de permisos:
    - rol 'admin': puede crear en cualquier EPS (debe mandar eps_id).
    - rol 'eps': el eps_id que mande en el body se IGNORA; se fuerza a la
      EPS del propio usuario autenticado (self.request.user.eps_id), para
      que no pueda crear gente en una EPS que no es la suya.
    """
    permission_classes = [IsAuthenticated, PuedeCrearUsuarioEps]

    def post(self, request):
        serializer = CrearUsuarioEpsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = dict(serializer.validated_data)
        password = datos.pop('password')

        rol_solicitante = request.user.rol

        if rol_solicitante == 'eps':
            if not request.user.eps_id:
                return Response(
                    {"detail": "Tu usuario no tiene una EPS asignada."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            datos['eps_id'] = request.user.eps_id
        elif rol_solicitante == 'admin':
            if not datos.get('eps_id'):
                return Response(
                    {"detail": "Debes indicar eps_id para crear el usuario."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        # Cualquier otro rol ya fue bloqueado por PuedeCrearUsuarioEps.

        eps_id = datos.pop('eps_id')
        datos['eps_id'] = eps_id
        datos['rol'] = 'eps'  # este endpoint solo crea trabajadores de EPS

        try:
            usuario = crear_usuario_eps_completo(datos, password_plano=password)
        except CrearUsuarioEpsError as e:
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        response_serializer = UsuarioEpsResponseSerializer(usuario)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)