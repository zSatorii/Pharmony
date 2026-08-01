from rest_framework import serializers
from .models import Eps, Sede, InventarioSede
from Farmacia.serializers import MedicamentoSerializer

class EpsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Eps
        fields = '__all__'

class SedeSerializer(serializers.ModelSerializer):
    eps_nombre = serializers.CharField(source='eps.nombre', read_only=True)

    class Meta:
        model = Sede
        fields = '__all__'

class InventarioSedeSerializer(serializers.ModelSerializer):
    medicamento_data = MedicamentoSerializer(source='medicamento', read_only=True)
    sede_nombre = serializers.CharField(source='sede.nombre', read_only=True)
    ciudad = serializers.CharField(source='sede.ciudad', read_only=True)
    estado_stock = serializers.CharField(read_only=True)

    class Meta:
        model = InventarioSede
        fields = '__all__'