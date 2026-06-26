from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponseNotAllowed
from django.views.decorators.cache import never_cache

from .models import Eps, Sede, InventarioSede
from .serializers import EpsSerializer, SedeSerializer, InventarioSedeSerializer
from Farmacia.models import Medicamento
from Farmacia.views import get_firestore_db


def es_personal(user):
    return user.is_authenticated and user.rol in ('admin', 'farmaceutico')


# ==========================
# API (CRUD vía DRF)
# ==========================
class EpsViewSet(viewsets.ModelViewSet):
    queryset = Eps.objects.all().order_by('nombre')
    serializer_class = EpsSerializer
    permission_classes = [IsAuthenticated]


class SedeViewSet(viewsets.ModelViewSet):
    queryset = Sede.objects.all().order_by('ciudad', 'nombre')
    serializer_class = SedeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        ciudad = self.request.query_params.get('ciudad')
        eps_id = self.request.query_params.get('eps')
        if ciudad:
            qs = qs.filter(ciudad__iexact=ciudad)
        if eps_id:
            qs = qs.filter(eps_id=eps_id)
        return qs


class InventarioSedeViewSet(viewsets.ModelViewSet):
    queryset = InventarioSede.objects.select_related('sede', 'medicamento').all()
    serializer_class = InventarioSedeSerializer
    permission_classes = [IsAuthenticated]
    FIRESTORE_COLLECTION = "inventario_sedes"

    def get_queryset(self):
        qs = super().get_queryset()
        sede_id = self.request.query_params.get('sede')
        ciudad = self.request.query_params.get('ciudad')
        if sede_id:
            qs = qs.filter(sede_id=sede_id)
        if ciudad:
            qs = qs.filter(sede__ciudad__iexact=ciudad)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            instance = serializer.save()
            self._guardar_en_firestore(instance)
            return Response(
                {"mensaje": "Inventario registrado correctamente", "data": self.get_serializer(instance).data},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if serializer.is_valid():
            instance = serializer.save()
            self._guardar_en_firestore(instance)
            return Response(
                {"mensaje": "Inventario actualizado correctamente", "data": self.get_serializer(instance).data},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        inv_id = instance.id
        self.perform_destroy(instance)
        self._eliminar_de_firestore(inv_id)
        return Response({"mensaje": "Inventario eliminado correctamente"}, status=status.HTTP_200_OK)

    def _guardar_en_firestore(self, instance):
        db = get_firestore_db()
        if db is None:
            return
        try:
            data = {
                "id": instance.id,
                "sede_id": instance.sede_id,
                "sede_nombre": instance.sede.nombre,
                "ciudad": instance.sede.ciudad,
                "medicamento_id": instance.medicamento_id,
                "medicamento_nombre": instance.medicamento.nombre_comercial,
                "cantidad_disponible": instance.cantidad_disponible,
                "cantidad_minima": instance.cantidad_minima,
                "lote": instance.lote,
                "fecha_vencimiento": str(instance.fecha_vencimiento) if instance.fecha_vencimiento else None,
                "estado_stock": instance.estado_stock,
            }
            db.collection(self.FIRESTORE_COLLECTION).document(str(instance.id)).set(data)
        except Exception as e:
            print(f"Error al guardar inventario {instance.id} en Firestore: {e}")

    def _eliminar_de_firestore(self, inv_id):
        db = get_firestore_db()
        if db is None:
            return
        try:
            db.collection(self.FIRESTORE_COLLECTION).document(str(inv_id)).delete()
        except Exception as e:
            print(f"Error al eliminar inventario {inv_id} de Firestore: {e}")


# ==========================
# Vistas con templates
# ==========================
@never_cache
@login_required
@user_passes_test(es_personal, login_url='login')
def dashboard_eps(request):
    eps_list = Eps.objects.all().order_by('nombre')
    sedes = Sede.objects.select_related('eps').all().order_by('ciudad', 'nombre')
    ciudades = Sede.objects.values_list('ciudad', flat=True).distinct().order_by('ciudad')

    context = {
        'eps_list': eps_list,
        'sedes': sedes,
        'ciudades': ciudades,
    }
    return render(request, 'epsinventario/DashboardEps.html', context)


@login_required
@user_passes_test(es_personal, login_url='login')
def inventario_por_sede(request, sede_id):
    sede = get_object_or_404(Sede, pk=sede_id)
    inventarios = InventarioSede.objects.select_related('medicamento').filter(sede=sede).order_by('medicamento__nombre_comercial')
    medicamentos_disponibles = Medicamento.objects.all().order_by('nombre_comercial')

    context = {
        'sede': sede,
        'inventarios': inventarios,
        'medicamentos_disponibles': medicamentos_disponibles,
    }
    return render(request, 'epsinventario/InventarioSede.html', context)


@login_required
def medicamentos_por_ciudad(request, ciudad):
    sedes = Sede.objects.filter(ciudad__iexact=ciudad)
    inventarios = InventarioSede.objects.select_related('medicamento', 'sede').filter(
        sede__ciudad__iexact=ciudad,
        cantidad_disponible__gt=0
    ).order_by('medicamento__nombre_comercial')

    context = {
        'ciudad': ciudad,
        'sedes': sedes,
        'inventarios': inventarios,
    }
    return render(request, 'epsinventario/MedicamentosPorCiudad.html', context)


@login_required
@user_passes_test(es_personal, login_url='login')
def crear_eps(request):
    if request.method == 'POST':
        Eps.objects.create(
            nombre=request.POST.get('nombre'),
            nit=request.POST.get('nit'),
            direccion=request.POST.get('direccion'),
            ciudad=request.POST.get('ciudad'),
            telefono=request.POST.get('telefono'),
            email=request.POST.get('email'),
        )
        return redirect('dashboard_eps')
    return HttpResponseNotAllowed(['POST'])


@login_required
@user_passes_test(es_personal, login_url='login')
def crear_sede(request):
    if request.method == 'POST':
        eps = get_object_or_404(Eps, pk=request.POST.get('eps_id'))
        Sede.objects.create(
            eps=eps,
            nombre=request.POST.get('nombre'),
            direccion=request.POST.get('direccion'),
            ciudad=request.POST.get('ciudad'),
            telefono=request.POST.get('telefono'),
            email=request.POST.get('email'),
        )
        return redirect('dashboard_eps')
    return HttpResponseNotAllowed(['POST'])


@login_required
@user_passes_test(es_personal, login_url='login')
def crear_inventario(request, sede_id):
    sede = get_object_or_404(Sede, pk=sede_id)
    if request.method == 'POST':
        medicamento = get_object_or_404(Medicamento, pk=request.POST.get('medicamento_id'))
        InventarioSede.objects.create(
            sede=sede,
            medicamento=medicamento,
            cantidad_disponible=request.POST.get('cantidad_disponible') or 0,
            cantidad_minima=request.POST.get('cantidad_minima') or 10,
            lote=request.POST.get('lote', ''),
            fecha_vencimiento=request.POST.get('fecha_vencimiento') or None,
        )
        return redirect('inventario_por_sede', sede_id=sede.id)
    return HttpResponseNotAllowed(['POST'])


@login_required
@user_passes_test(es_personal, login_url='login')
def editar_inventario(request, pk):
    inv = get_object_or_404(InventarioSede, pk=pk)
    if request.method == 'POST':
        inv.cantidad_disponible = request.POST.get('cantidad_disponible') or inv.cantidad_disponible
        inv.cantidad_minima = request.POST.get('cantidad_minima') or inv.cantidad_minima
        inv.lote = request.POST.get('lote', inv.lote)
        inv.fecha_vencimiento = request.POST.get('fecha_vencimiento') or inv.fecha_vencimiento
        inv.save()
        return redirect('inventario_por_sede', sede_id=inv.sede.id)
    return HttpResponseNotAllowed(['POST'])


@login_required
@user_passes_test(es_personal, login_url='login')
def eliminar_inventario(request, pk):
    inv = get_object_or_404(InventarioSede, pk=pk)
    sede_id = inv.sede.id
    if request.method == 'POST':
        inv.delete()
        return redirect('inventario_por_sede', sede_id=sede_id)
    return HttpResponseNotAllowed(['POST'])