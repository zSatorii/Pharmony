import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponseForbidden, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from Farmacia.models import Medicamento
from Farmacia.views import get_firestore_db
from .models import Eps, InventarioSede, Sede, SolicitudMedicamento
from .serializers import EpsSerializer, InventarioSedeSerializer, SedeSerializer

def es_personal(user):
    return user.is_authenticated and user.rol in ('admin', 'eps')

def es_admin(user):
    return user.is_authenticated and user.rol == 'admin'

def puede_ver_sede(user, sede):
    if user.rol == 'admin':
        return True
    return user.eps_id is not None and sede.eps_id == user.eps_id

def _sync_eps_firestore(instance):
    db = get_firestore_db()
    if db is None:
        return
    try:
        data = {
            "id": instance.id,
            "nombre": instance.nombre,
            "nit": instance.nit,
            "direccion": instance.direccion,
            "ciudad": instance.ciudad,
            "telefono": instance.telefono,
            "email": instance.email,
            "estado": instance.estado,
        }
        db.collection("eps").document(str(instance.id)).set(data)
    except Exception:
        pass

def _sync_sede_firestore(instance):
    db = get_firestore_db()
    if db is None:
        return
    try:
        data = {
            "id": instance.id,
            "eps_id": instance.eps_id,
            "eps_nombre": instance.eps.nombre,
            "nombre": instance.nombre,
            "direccion": instance.direccion,
            "ciudad": instance.ciudad,
            "telefono": instance.telefono,
            "email": instance.email,
            "estado": instance.estado,
        }
        db.collection("sedes").document(str(instance.id)).set(data)
    except Exception:
        pass

def _sync_medicamento_firestore(instance):
    db = get_firestore_db()
    if db is None:
        return
    try:
        data = {
            "id": instance.id,
            "codigo_cum": instance.codigo_cum,
            "nombre_generico": instance.nombre_generico,
            "nombre_comercial": instance.nombre_comercial,
            "laboratorio": instance.laboratorio,
            "concentracion": instance.concentracion,
            "forma_farmaceutica": instance.forma_farmaceutica,
            "descripcion": instance.descripcion,
            "uso_indicado": instance.uso_indicado,
            "efectos_secundarios": instance.efectos_secundarios,
            "requiere_formula": instance.requiere_formula,
        }
        db.collection("medicamentos").document(instance.codigo_cum or str(instance.id)).set(data)
    except Exception:
        pass

def _sync_inventario_firestore(instance):
    db = get_firestore_db()
    if db is None:
        return
    try:
        data = {
            "id": instance.id,
            "sede_id": instance.sede_id,
            "sede_nombre": instance.sede.nombre,
            "eps_id": instance.sede.eps_id,
            "eps_nombre": instance.sede.eps.nombre,
            "ciudad": instance.sede.ciudad,
            "medicamento_id": instance.medicamento_id,
            "medicamento_nombre": instance.medicamento.nombre_comercial,
            "cantidad_disponible": instance.cantidad_disponible,
            "cantidad_minima": instance.cantidad_minima,
            "lote": instance.lote,
            "fecha_vencimiento": str(instance.fecha_vencimiento) if instance.fecha_vencimiento else None,
            "estado_stock": instance.estado_stock,
        }
        db.collection("inventario_sedes").document(str(instance.id)).set(data)
    except Exception:
        pass

def _eliminar_doc_firestore(coleccion, doc_id):
    db = get_firestore_db()
    if db is None:
        return
    try:
        db.collection(coleccion).document(str(doc_id)).delete()
    except Exception:
        pass

class EpsViewSet(viewsets.ModelViewSet):
    serializer_class = EpsSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.rol == 'admin':
            return Eps.objects.all().order_by('nombre')
        if user.eps_id:
            return Eps.objects.filter(id=user.eps_id)
        return Eps.objects.none()

class SedeViewSet(viewsets.ModelViewSet):
    serializer_class = SedeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Sede.objects.all().order_by('ciudad', 'nombre')
        if user.rol != 'admin':
            qs = qs.filter(eps_id=user.eps_id) if user.eps_id else Sede.objects.none()
        ciudad = self.request.query_params.get('ciudad')
        eps_id = self.request.query_params.get('eps')
        if ciudad:
            qs = qs.filter(ciudad__iexact=ciudad)
        if eps_id:
            qs = qs.filter(eps_id=eps_id)
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        if user.rol != 'admin':
            serializer.save(eps=user.eps)
        else:
            serializer.save()
        _sync_sede_firestore(serializer.instance)

    def perform_update(self, serializer):
        instance = serializer.save()
        _sync_sede_firestore(instance)

class InventarioSedeViewSet(viewsets.ModelViewSet):
    serializer_class = InventarioSedeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = InventarioSede.objects.select_related('sede', 'medicamento').all()
        if user.rol != 'admin':
            qs = qs.filter(sede__eps_id=user.eps_id) if user.eps_id else InventarioSede.objects.none()
        sede_id = self.request.query_params.get('sede')
        ciudad = self.request.query_params.get('ciudad')
        if sede_id:
            qs = qs.filter(sede_id=sede_id)
        if ciudad:
            qs = qs.filter(sede__ciudad__iexact=ciudad)
        return qs

    def perform_create(self, serializer):
        instance = serializer.save()
        _sync_inventario_firestore(instance)

    def perform_update(self, serializer):
        instance = serializer.save()
        _sync_inventario_firestore(instance)

    def perform_destroy(self, instance):
        inv_id = instance.id
        instance.delete()
        _eliminar_doc_firestore("inventario_sedes", inv_id)

@never_cache
@login_required
@user_passes_test(es_personal, login_url='login')
def dashboard_eps(request):
    user = request.user
    is_admin = user.rol == 'admin'

    if is_admin:
        eps_list = Eps.objects.all().order_by('nombre')
        sedes = Sede.objects.select_related('eps').all().order_by('ciudad', 'nombre')
    else:
        if not user.eps_id:
            return render(request, 'epsinventario/DashboardEps.html', {
                'is_admin': False, 'sin_eps': True,
                'eps_list': [], 'sedes': [], 'ciudades': [], 'mi_eps': None,
            })
        eps_list = Eps.objects.filter(id=user.eps_id)
        sedes = Sede.objects.select_related('eps').filter(eps_id=user.eps_id).order_by('ciudad', 'nombre')

    ciudades = sedes.values_list('ciudad', flat=True).distinct().order_by('ciudad')

    context = {
        'is_admin': is_admin,
        'sin_eps': False,
        'eps_list': eps_list,
        'sedes': sedes,
        'ciudades': ciudades,
        'mi_eps': None if is_admin else eps_list.first(),
    }
    return render(request, 'epsinventario/DashboardEps.html', context)

@never_cache
@login_required
@user_passes_test(es_personal, login_url='login')
def inventario_por_sede(request, sede_id):
    sede = get_object_or_404(Sede, pk=sede_id)
    if not puede_ver_sede(request.user, sede):
        return HttpResponseForbidden("No tienes permiso para ver el inventario de esta sede.")

    inventarios = InventarioSede.objects.select_related('medicamento').filter(sede=sede).order_by('medicamento__nombre_comercial')
    medicamentos_disponibles = Medicamento.objects.all().order_by('nombre_comercial')

    context = {
        'sede': sede,
        'inventarios': inventarios,
        'medicamentos_disponibles': medicamentos_disponibles,
    }
    return render(request, 'epsinventario/InventarioSede.html', context)

@never_cache
@login_required
def medicamentos_por_ciudad(request, ciudad):
    sedes = Sede.objects.filter(ciudad__iexact=ciudad)
    inventarios = InventarioSede.objects.select_related('medicamento', 'sede').filter(
        sede__ciudad__iexact=ciudad,
    ).order_by('medicamento__nombre_comercial')

    context = {'ciudad': ciudad, 'sedes': sedes, 'inventarios': inventarios}
    return render(request, 'epsinventario/MedicamentosPorCiudad.html', context)

@never_cache
@login_required
def buscar_medicamentos(request):
    ciudades = Sede.objects.values_list('ciudad', flat=True).distinct().order_by('ciudad')
    return render(request, 'epsinventario/BuscarMedicamentos.html', {'ciudades': ciudades})

@never_cache
@login_required
@user_passes_test(es_admin, login_url='login')
def editar_eps(request, pk):
    eps = get_object_or_404(Eps, pk=pk)
    if request.method == 'POST':
        eps.nombre = request.POST.get('nombre', eps.nombre)
        eps.nit = request.POST.get('nit', eps.nit)
        eps.direccion = request.POST.get('direccion', eps.direccion)
        eps.ciudad = request.POST.get('ciudad', eps.ciudad)
        eps.telefono = request.POST.get('telefono', eps.telefono)
        eps.email = request.POST.get('email', eps.email)
        eps.estado = request.POST.get('estado') == 'on'
        eps.save()
        _sync_eps_firestore(eps)
        return redirect('dashboard_eps')
    return HttpResponseNotAllowed(['POST'])

@never_cache
@login_required
@user_passes_test(es_admin, login_url='login')
def eliminar_eps(request, pk):
    eps = get_object_or_404(Eps, pk=pk)
    if request.method == 'POST':
        eps_id = eps.id
        eps.delete()
        _eliminar_doc_firestore("eps", eps_id)
        return redirect('dashboard_eps')
    return HttpResponseNotAllowed(['POST'])

@never_cache
@login_required
@user_passes_test(es_personal, login_url='login')
def crear_sede(request):
    user = request.user
    if request.method == 'POST':
        if user.rol == 'admin':
            eps = get_object_or_404(Eps, pk=request.POST.get('eps_id'))
        else:
            if not user.eps_id:
                return HttpResponseForbidden("Tu cuenta no tiene una EPS asignada.")
            eps = user.eps

        sede = Sede.objects.create(
            eps=eps,
            nombre=request.POST.get('nombre'),
            direccion=request.POST.get('direccion'),
            ciudad=request.POST.get('ciudad'),
            telefono=request.POST.get('telefono'),
            email=request.POST.get('email'),
        )
        _sync_sede_firestore(sede)
        return redirect('dashboard_eps')
    return HttpResponseNotAllowed(['POST'])

@never_cache
@login_required
@user_passes_test(es_personal, login_url='login')
def editar_sede(request, pk):
    sede = get_object_or_404(Sede, pk=pk)
    if not puede_ver_sede(request.user, sede):
        return HttpResponseForbidden("No tienes permiso para editar esta sede.")
    if request.method == 'POST':
        sede.nombre = request.POST.get('nombre', sede.nombre)
        sede.direccion = request.POST.get('direccion', sede.direccion)
        sede.ciudad = request.POST.get('ciudad', sede.ciudad)
        sede.telefono = request.POST.get('telefono', sede.telefono)
        sede.email = request.POST.get('email', sede.email)
        sede.estado = request.POST.get('estado') == 'on'
        if request.user.rol == 'admin':
            eps_id = request.POST.get('eps_id')
            if eps_id:
                sede.eps = get_object_or_404(Eps, pk=eps_id)
        sede.save()
        _sync_sede_firestore(sede)
        return redirect('dashboard_eps')
    return HttpResponseNotAllowed(['POST'])

@never_cache
@login_required
@user_passes_test(es_personal, login_url='login')
def eliminar_sede(request, pk):
    sede = get_object_or_404(Sede, pk=pk)
    if not puede_ver_sede(request.user, sede):
        return HttpResponseForbidden("No tienes permiso para eliminar esta sede.")
    if request.method == 'POST':
        sede_id = sede.id
        sede.delete()
        _eliminar_doc_firestore("sedes", sede_id)
        return redirect('dashboard_eps')
    return HttpResponseNotAllowed(['POST'])

@never_cache
@login_required
@user_passes_test(es_personal, login_url='login')
def crear_inventario(request, sede_id):
    sede = get_object_or_404(Sede, pk=sede_id)
    if not puede_ver_sede(request.user, sede):
        return HttpResponseForbidden("No tienes permiso para modificar el inventario de esta sede.")

    if request.method == 'POST':
        modo = request.POST.get('modo', 'existente')

        if modo == 'nuevo':
            codigo_cum = request.POST.get('codigo_cum', '').strip().upper()
            if not codigo_cum:
                messages.error(request, 'Debes ingresar el código CUM original del producto.')
                return redirect('inventario_por_sede', sede_id=sede.id)
            if Medicamento.objects.filter(codigo_cum__iexact=codigo_cum).exists():
                messages.error(
                    request, 
                    f"El medicamento con código CUM '{codigo_cum}' ya existe en el sistema global. "
                    f"Por favor, búscalo y selecciónalo desde la opción de 'Medicamento Existente'."
                )
                return redirect('inventario_por_sede', sede_id=sede.id)

            medicamento = Medicamento.objects.create(
                codigo_cum=codigo_cum,
                nombre_generico=request.POST.get('nombre_generico', ''),
                nombre_comercial=request.POST.get('nombre_comercial', ''),
                laboratorio=request.POST.get('laboratorio', ''),
                concentracion=request.POST.get('concentracion', ''),
                forma_farmaceutica=request.POST.get('forma_farmaceutica', ''),
                descripcion=request.POST.get('descripcion', ''),
                uso_indicado=request.POST.get('uso_indicado', ''),
                efectos_secundarios=request.POST.get('efectos_secundarios', ''),
                requiere_formula=request.POST.get('requiere_formula') == 'on',
            )
            _sync_medicamento_firestore(medicamento)
        else:
            medicamento = get_object_or_404(Medicamento, pk=request.POST.get('medicamento_id'))

        inv = InventarioSede.objects.create(
            sede=sede, 
            medicamento=medicamento,
            cantidad_disponible=request.POST.get('cantidad_disponible') or 0,
            lote=request.POST.get('lote', ''),
            fecha_vencimiento=request.POST.get('fecha_vencimiento') or None,
        )
        _sync_inventario_firestore(inv)
        
        messages.success(request, "Medicamento e inventario agregados correctamente.")
        return redirect('inventario_por_sede', sede_id=sede.id)
        
    return HttpResponseNotAllowed(['POST'])

@never_cache
@login_required
@user_passes_test(es_personal, login_url='login')
def editar_inventario(request, pk):
    inv = get_object_or_404(InventarioSede, pk=pk)
    if not puede_ver_sede(request.user, inv.sede):
        return HttpResponseForbidden("No tienes permiso para modificar este inventario.")
    if request.method == 'POST':
        inv.cantidad_disponible = request.POST.get('cantidad_disponible') or inv.cantidad_disponible
        inv.lote = request.POST.get('lote', inv.lote)
        inv.fecha_vencimiento = request.POST.get('fecha_vencimiento') or inv.fecha_vencimiento
        inv.save()
        _sync_inventario_firestore(inv)
        return redirect('inventario_por_sede', sede_id=inv.sede.id)
    return HttpResponseNotAllowed(['POST'])

@never_cache
@login_required
@user_passes_test(es_personal, login_url='login')
def eliminar_inventario(request, pk):
    inv = get_object_or_404(InventarioSede, pk=pk)
    if not puede_ver_sede(request.user, inv.sede):
        return HttpResponseForbidden("No tienes permiso para eliminar este inventario.")
    sede_id = inv.sede.id
    if request.method == 'POST':
        inv_id = inv.id
        inv.delete()
        _eliminar_doc_firestore("inventario_sedes", inv_id)
        return redirect('inventario_por_sede', sede_id=sede_id)
    return HttpResponseNotAllowed(['POST'])

def _sync_solicitud_firestore(instance):
    db = get_firestore_db()
    if db is None:
        return
    try:
        data = {
            "id": instance.id,
            "usuario_id": instance.usuario_id,
            "usuario_email": instance.usuario.email,
            "medicamento_id": instance.medicamento_id,
            "medicamento_nombre": instance.medicamento.nombre_comercial,
            "sede_id": instance.sede_id,
            "sede_nombre": instance.sede.nombre if instance.sede else None,
            "estado": instance.estado,
            "fecha_solicitud": instance.fecha_solicitud.isoformat(),
        }
        db.collection("solicitudes_medicamento").document(str(instance.id)).set(data)
    except Exception:
        pass

@never_cache
@login_required
def api_medicamento_detalle(request, medicamento_id):
    from turnos.cooldown import verificar_cooldown_medicamento

    medicamento = get_object_or_404(Medicamento, pk=medicamento_id)
    ciudad = request.GET.get('ciudad')

    inventarios = InventarioSede.objects.select_related('sede').filter(medicamento=medicamento)
    if ciudad:
        inventarios = inventarios.filter(sede__ciudad__iexact=ciudad)

    sedes_data = [{
        "sede_id": inv.sede.id,
        "sede_nombre": inv.sede.nombre,
        "ciudad": inv.sede.ciudad,
        "cantidad_disponible": inv.cantidad_disponible,
        "estado_stock": inv.estado_stock,
    } for inv in inventarios]

    disponible = any(s["cantidad_disponible"] > 0 for s in sedes_data)

    # Verificar si el usuario ya reclamó este medicamento efectivamente en los últimos 30 días
    en_cooldown, cooldown_fecha = verificar_cooldown_medicamento(request.user, medicamento)

    from Farmacia.derecho_peticion_cooldown import verificar_cooldown_derecho_peticion
    cooldown_dp = verificar_cooldown_derecho_peticion(request.user, medicamento)

    from Farmacia.models import DerechoPeticion
    peticion = DerechoPeticion.objects.filter(
        usuario=request.user,
        medicamento=medicamento,
        estado__in=['radicado', 'en_tramite']
    ).first()

    return JsonResponse({
        "id": medicamento.id,
        "nombre_comercial": medicamento.nombre_comercial,
        "nombre_generico": medicamento.nombre_generico,
        "laboratorio": medicamento.laboratorio,
        "concentracion": medicamento.concentracion,
        "forma_farmaceutica": medicamento.forma_farmaceutica,
        "descripcion": medicamento.descripcion,
        "uso_indicado": medicamento.uso_indicado,
        "efectos_secundarios": medicamento.efectos_secundarios,
        "requiere_formula": medicamento.requiere_formula,
        "disponible": disponible,
        "sedes": sedes_data,
        "en_cooldown": en_cooldown,
        "cooldown_fecha": cooldown_fecha,
        "tiene_peticion": bool(peticion),
        "peticion_radicado": peticion.numero_radicado if peticion else "",
        "peticion_estado": peticion.get_estado_display() if peticion else "",
        "en_cooldown_dp": cooldown_dp['en_cooldown'],
        "cooldown_dp_fecha": cooldown_dp['fecha_disponible'],
        "cooldown_dp_dias_restantes": cooldown_dp['dias_restantes'],
        "cooldown_dp_mensaje": cooldown_dp['mensaje'],
    })

@never_cache
@login_required
def solicitar_medicamento(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    try:
        data = json.loads(request.body)
        medicamento_id = data.get('medicamento_id')
        sede_id = data.get('sede_id')
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"success": False, "error": "Datos inválidos."}, status=400)

    medicamento = get_object_or_404(Medicamento, pk=medicamento_id)
    sede = Sede.objects.filter(pk=sede_id).first() if sede_id else None

    solicitud = SolicitudMedicamento.objects.create(
        usuario=request.user,
        medicamento=medicamento,
        sede=sede,
        estado='pendiente',
    )
    _sync_solicitud_firestore(solicitud)

    return JsonResponse({
        "success": True,
        "message": f"Tu solicitud de {medicamento.nombre_comercial} fue registrada."
    })