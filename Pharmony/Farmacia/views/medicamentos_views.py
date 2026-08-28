"""
Farmacia/views/medicamentos_views.py

Vistas relacionadas con el CRUD de medicamentos y el dashboard de
inventario (panel de staff/admin).
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from firebase_admin import firestore
from ..models import Medicamento
from ..serializers import MedicamentoSerializer
from .common import get_firestore_db, _redirect_por_rol


class MedicamentoViewSet(viewsets.ModelViewSet):
    queryset = Medicamento.objects.all().order_by("nombre_comercial")
    serializer_class = MedicamentoSerializer
    permission_classes = [IsAuthenticated]
    FIRESTORE_COLLECTION = "medicamentos"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            instance = serializer.save()
            self._guardar_en_firestore(instance, serializer.data)
            return Response(
                {
                    "mensaje": "Medicamento registrado correctamente",
                    "data": serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if serializer.is_valid():
            instance = serializer.save()
            self._guardar_en_firestore(instance, serializer.data)
            return Response(
                {
                    "mensaje": "Medicamento actualizado correctamente",
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        medicamento_id = instance.id
        self.perform_destroy(instance)
        self._eliminar_de_firestore(medicamento_id)
        return Response(
            {"mensaje": "Medicamento eliminado correctamente"},
            status=status.HTTP_200_OK
        )

    def _guardar_en_firestore(self, instance, data):
        db = get_firestore_db()
        if db is None:
            return
        try:
            db.collection(self.FIRESTORE_COLLECTION).document(str(instance.id)).set(dict(data))
        except Exception:
            pass

    def _eliminar_de_firestore(self, medicamento_id):
        db = get_firestore_db()
        if db is None:
            return
        try:
            db.collection(self.FIRESTORE_COLLECTION).document(str(medicamento_id)).delete()
        except Exception:
            pass

def dashboard_inventario(request):
    if request.user.rol in ('cliente', 'eps'):
        return redirect(_redirect_por_rol(request.user))

    db = get_firestore_db()
    if db is not None:
        try:
            docs = db.collection('medicamentos').stream()
            firestore_ids = set()
            for doc in docs:
                data = doc.to_dict()
                med_id = data.get('id') or (int(doc.id) if doc.id.isdigit() else None)
                if med_id is None:
                    continue
                firestore_ids.add(med_id)
                codigo_cum = data.get('codigo_cum') or doc.id
                Medicamento.objects.update_or_create(
                    id=med_id,
                    defaults={
                        'codigo_cum': str(codigo_cum),
                        'nombre_generico': data.get('nombre_generico', ''),
                        'nombre_comercial': data.get('nombre_comercial', ''),
                        'laboratorio': data.get('laboratorio', ''),
                        'concentracion': data.get('concentracion', ''),
                        'forma_farmaceutica': data.get('forma_farmaceutica', ''),
                        'descripcion': data.get('descripcion', ''),
                        'uso_indicado': data.get('uso_indicado', ''),
                        'efectos_secundarios': data.get('efectos_secundarios', ''),
                        'requiere_formula': bool(data.get('requiere_formula', False)),
                    }
                )
            if firestore_ids:
                Medicamento.objects.exclude(id__in=firestore_ids).delete()
        except Exception:
            pass

    medicamentos = Medicamento.objects.all().order_by("nombre_comercial")
    total_medicamentos = medicamentos.count()
    medicamentos_formula = medicamentos.filter(requiere_formula=True).count()
    medicamentos_libres = medicamentos.filter(requiere_formula=False).count()
    laboratorios = medicamentos.values('laboratorio').distinct().count()

    context = {
        'medicamentos': medicamentos,
        'total_medicamentos': total_medicamentos,
        'medicamentos_formula': medicamentos_formula,
        'medicamentos_libres': medicamentos_libres,
        'laboratorios': laboratorios
    }
    return render(request, 'inventario/DashboardInventario.html', context)

@never_cache
@login_required
def crear_medicamento(request):
    if request.method == 'POST':
        codigo_cum = request.POST.get('codigo_cum', '').strip().upper()
        if not codigo_cum:
            messages.error(request, 'Debes ingresar el código CUM original del producto.')
            return redirect('dashboard_inventario')
        if Medicamento.objects.filter(codigo_cum__iexact=codigo_cum).exists():
            messages.error(request, f'El código CUM {codigo_cum} ya está registrado. El medicamento no fue creado.')
            return redirect('dashboard_inventario')
        nombre_generico = request.POST.get('nombre_generico')
        nombre_comercial = request.POST.get('nombre_comercial')
        laboratorio = request.POST.get('laboratorio')
        concentracion = request.POST.get('concentracion')
        forma_farmaceutica = request.POST.get('forma_farmaceutica')
        descripcion = request.POST.get('descripcion')
        uso_indicated = request.POST.get('uso_indicado')
        efectos_secundarios = request.POST.get('efectos_secundarios')
        requiere_formula = request.POST.get('requiere_formula') == 'on'

        medicamento = Medicamento.objects.create(
            codigo_cum=codigo_cum,
            nombre_generico=nombre_generico,
            nombre_comercial=nombre_comercial,
            laboratorio=laboratorio,
            concentracion=concentracion,
            forma_farmaceutica=forma_farmaceutica,
            descripcion=descripcion,
            uso_indicado=uso_indicated,
            efectos_secundarios=efectos_secundarios,
            requiere_formula=requiere_formula
        )

        try:
            db = firestore.client()
            medicamento_data = {
                "id": medicamento.id,
                "codigo_cum": codigo_cum,
                "nombre_generico": nombre_generico,
                "nombre_comercial": nombre_comercial,
                "laboratorio": laboratorio,
                "concentracion": concentracion,
                "forma_farmaceutica": forma_farmaceutica,
                "descripcion": descripcion,
                "uso_indicado": uso_indicated,
                "efectos_secundarios": efectos_secundarios,
                "requiere_formula": requiere_formula
            }
            db.collection('medicamentos').document(str(medicamento.id)).set(medicamento_data)
        except Exception:
            pass

        return redirect('dashboard_inventario')
    
    return HttpResponseNotAllowed(['POST'])

@never_cache
@login_required
def editar_medicamento(request, pk):
    medicamento = get_object_or_404(Medicamento, pk=pk)

    if request.method == 'POST':
        codigo_cum = request.POST.get('edit_codigo_cum', '').strip().upper()
        if not codigo_cum:
            messages.error(request, 'Debes ingresar el código CUM original del producto.')
            return redirect('dashboard_inventario')
        if Medicamento.objects.filter(codigo_cum__iexact=codigo_cum).exclude(pk=medicamento.pk).exists():
            messages.error(request, f'El código CUM {codigo_cum} ya está registrado en otro medicamento. No se guardaron los cambios.')
            return redirect('dashboard_inventario')
        medicamento.codigo_cum = codigo_cum
        medicamento.nombre_generico = request.POST.get('edit_nombre_generico')
        medicamento.nombre_comercial = request.POST.get('edit_nombre_comercial')
        medicamento.laboratorio = request.POST.get('edit_laboratorio')
        medicamento.concentracion = request.POST.get('edit_concentracion')
        medicamento.forma_farmaceutica = request.POST.get('edit_forma_farmaceutica')
        medicamento.descripcion = request.POST.get('edit_descripcion')
        medicamento.uso_indicado = request.POST.get('edit_uso_indicado')
        medicamento.efectos_secundarios = request.POST.get('edit_efectos_secundarios')
        medicamento.requiere_formula = request.POST.get('requiere_formula') == 'on'
        medicamento.save()
        
        try:
            db = firestore.client()
            medicamento_data = {
                "id": medicamento.id,
                "codigo_cum": medicamento.codigo_cum,
                "nombre_generico": medicamento.nombre_generico,
                "nombre_comercial": medicamento.nombre_comercial,
                "laboratorio": medicamento.laboratorio,
                "concentracion": medicamento.concentracion,
                "forma_farmaceutica": medicamento.forma_farmaceutica,
                "descripcion": medicamento.descripcion,
                "uso_indicado": medicamento.uso_indicado,
                "efectos_secundarios": medicamento.efectos_secundarios,
                "requiere_formula": medicamento.requiere_formula
            }
            db.collection('medicamentos').document(str(medicamento.id)).update(medicamento_data)
        except Exception:
            pass

        return redirect('dashboard_inventario')
    
    return HttpResponseNotAllowed(['POST'])

@never_cache
@login_required
def eliminar_medicamento(request, pk):
    medicamento = get_object_or_404(Medicamento, pk=pk)
    if request.method == 'POST':
        id_a_eliminar = str(medicamento.id)
        medicamento.delete()
        try:
            db = firestore.client()
            db.collection('medicamentos').document(id_a_eliminar).delete()
        except Exception:
            pass
        return redirect('dashboard_inventario')
    return HttpResponseNotAllowed(['POST'])
