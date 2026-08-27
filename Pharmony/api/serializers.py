from rest_framework import serializers

from Farmacia.models import Usuario
from epsinventario.models import Eps


class CrearUsuarioEpsSerializer(serializers.Serializer):
    """
    Serializer de ENTRADA para crear un usuario EPS desde Flutter.

    No es un ModelSerializer porque necesitamos un campo extra (password)
    que no vive tal cual en el modelo, y porque el campo eps_id se
    valida/fuerza distinto según el rol de quien hace la petición
    (ver CrearUsuarioEpsView en views.py).
    """
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    telefono = serializers.CharField(max_length=20, required=False, allow_blank=True)
    cedula = serializers.CharField(max_length=20, required=False, allow_blank=True)
    eps_id = serializers.IntegerField(required=False)

    def validate_username(self, value):
        if Usuario.objects.filter(username=value).exists():
            raise serializers.ValidationError("Ese nombre de usuario ya está en uso.")
        return value

    def validate_email(self, value):
        if Usuario.objects.filter(email=value).exists():
            raise serializers.ValidationError("Ese correo ya está registrado.")
        return value

    def validate_eps_id(self, value):
        if not Eps.objects.filter(id=value).exists():
            raise serializers.ValidationError("La EPS indicada no existe.")
        return value


class UsuarioEpsResponseSerializer(serializers.ModelSerializer):
    """Serializer de SALIDA: lo que se devuelve tras crear el usuario."""

    class Meta:
        model = Usuario
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'telefono', 'rol', 'eps']
        read_only_fields = fields