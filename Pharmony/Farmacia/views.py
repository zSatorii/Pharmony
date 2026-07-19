from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status
import datetime
import jwt
import os
from django.conf import settings
from rest_framework.permissions import IsAuthenticated

from .models import Medicamento
from .serializers import MedicamentoSerializer
import requests
import json
from django.urls import reverse
from django.http import JsonResponse
from django.contrib.auth import get_user_model, authenticate
import re
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth import get_user_model, authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.urls import reverse

# Tus dependencias solicitadas de Firebase Admin
from firebase_admin import auth as firebase_auth, firestore

from rest_framework import viewsets, status
from rest_framework.response import Response
from .models import Medicamento
from .serializers import MedicamentoSerializer

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotAllowed
from firebase_admin import firestore
from .models import Medicamento
from django.views.decorators.cache import never_cache

from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from firebase_admin import auth as firebase_auth
from firebase_admin import firestore
from IA.face_rec import get_embedding_from_base64, check_match


def get_firestore_db():
    try:
        return firestore.client()
    except Exception as e:
        print(f"Firestore no disponible: {e}")
        return None
    
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

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
    
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
 
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
 
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
        except Exception as e:
            print(f"Error al guardar el medicamento {instance.id} en Firestore: {e}")
 
    def _eliminar_de_firestore(self, medicamento_id):
        db = get_firestore_db()
        if db is None:
            return
        try:
            db.collection(self.FIRESTORE_COLLECTION).document(str(medicamento_id)).delete()
        except Exception as e:
            print(f"Error al eliminar el medicamento {medicamento_id} de Firestore: {e}")


# ==========================
# Dashboard Inventario
# ==========================
@never_cache
@login_required
@never_cache
def dashboard_inventario(request):
    if request.user.rol in ('cliente', 'eps'):
        return redirect(_redirect_por_rol(request.user))

    # Sincronizar desde Firestore a la base de datos local SQLite
    db = get_firestore_db()
    if db is not None:
        try:
            docs = db.collection('medicamentos').stream()
            firestore_ids = set()
            for doc in docs:
                data = doc.to_dict()
                try:
                    med_id = int(doc.id)
                except ValueError:
                    continue
                firestore_ids.add(med_id)
                Medicamento.objects.update_or_create(
                    id=med_id,
                    defaults={
                        'codigo_cum': data.get('codigo_cum', ''),
                        'nombre_generico': data.get('nombre_generico', ''),
                        'nombre_comercial': data.get('nombre_comercial', ''),
                        'laboratorio': data.get('laboratorio', ''),
                        'concentracion': data.get('concentracion', ''),
                        'forma_farmaceutica': data.get('forma_farmaceutica', ''),
                        'descripcion': data.get('descripcion', ''),
                        'uso_indicado': data.get('uso_indicado', ''),
                        'efectos_secundarios': data.get('efectos_secundarios', ''),
                        'requiere_formula': data.get('requiere_formula', False),
                    }
                )
            # Eliminar medicamentos locales que ya no existen en Firestore
            Medicamento.objects.exclude(id__in=firestore_ids).delete()
        except Exception as e:
            print(f"Error al sincronizar desde Firestore: {e}")

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
        # 1. Capturar absolutamente todos los datos del formulario HTML
        codigo_cum = request.POST.get('codigo_cum')
        nombre_generico = request.POST.get('nombre_generico')
        nombre_comercial = request.POST.get('nombre_comercial')
        laboratorio = request.POST.get('laboratorio')
        concentracion = request.POST.get('concentracion')
        forma_farmaceutica = request.POST.get('forma_farmaceutica')
        descripcion = request.POST.get('descripcion')
        uso_indicated = request.POST.get('uso_indicado')
        efectos_secundarios = request.POST.get('efectos_secundarios')
        requiere_formula = request.POST.get('requiere_formula') == 'on'
  
        # 2. Registrar localmente en la base de datos de Django (SQLite)
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

        # 3. Sincronizar la estructura completa en Firebase Firestore
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
        except Exception as e:
            print(f"⚠️ Error al sincronizar creación en Firebase: {e}")

        return redirect('dashboard_inventario')
    
    return HttpResponseNotAllowed(['POST'])


@never_cache
@login_required
def editar_medicamento(request, pk):
    medicamento = get_object_or_404(Medicamento, pk=pk)

    if request.method == 'POST':
        # 1. Actualizar las propiedades del objeto recuperado
        medicamento.codigo_cum = request.POST.get('edit_codigo_cum') # Ajustado con prefijo edit_ por orden en modales
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
        
        # 2. Replicar los cambios exactos de vuelta a Firestore
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
        except Exception as e:
            print(f"⚠️ Error al sincronizar edición en Firebase: {e}")

        return redirect('dashboard_inventario')
    
    return HttpResponseNotAllowed(['POST'])


@never_cache
@login_required
def eliminar_medicamento(request, pk):
    medicamento = get_object_or_404(Medicamento, pk=pk)
    
    if request.method == 'POST':
        id_a_eliminar = str(medicamento.id)
        
        # Eliminar localmente primero
        medicamento.delete()

        # Desvincular y limpiar el registro en la nube de Firestore
        try:
            db = firestore.client()
            db.collection('medicamentos').document(id_a_eliminar).delete()
        except Exception as e:
            print(f"⚠️ Error al sincronizar eliminación en Firebase: {e}")

        return redirect('dashboard_inventario')
        
    return HttpResponseNotAllowed(['POST'])

@never_cache
@login_required
def dashboard_cliente(request):
    if request.user.rol in ('admin', 'eps'):
        return redirect(_redirect_por_rol(request.user))

    from epsinventario.models import Sede, InventarioSede
    import json as json_lib

    medicamentos = Medicamento.objects.all().order_by("nombre_comercial")
    total_medicamentos = medicamentos.count()
    medicamentos_formula = medicamentos.filter(requiere_formula=True).count()
    medicamentos_libres = medicamentos.filter(requiere_formula=False).count()
    laboratorios = medicamentos.values('laboratorio').distinct().count()

    # Disponibilidad real: agregamos cantidades por medicamento sumando TODAS sus sedes
    inventarios_qs = InventarioSede.objects.select_related('sede', 'medicamento')
    disponibilidad_por_medicamento = {}
    for inv in inventarios_qs:
        med_id = inv.medicamento_id
        if med_id not in disponibilidad_por_medicamento:
            disponibilidad_por_medicamento[med_id] = {
                'cantidad_total': 0,
                'sedes_count': 0,
                'estado': 'agotado',
            }
        info = disponibilidad_por_medicamento[med_id]
        info['cantidad_total'] += inv.cantidad_disponible
        if inv.cantidad_disponible > 0:
            info['sedes_count'] += 1
        if inv.estado_stock == 'disponible':
            info['estado'] = 'disponible'
        elif inv.estado_stock == 'stock_bajo' and info['estado'] != 'disponible':
            info['estado'] = 'stock_bajo'

    for med in medicamentos:
        med.disponibilidad = disponibilidad_por_medicamento.get(med.id, {
            'cantidad_total': 0, 'sedes_count': 0, 'estado': 'agotado'
        })

    medicamentos_agotados = [m for m in medicamentos if m.disponibilidad['cantidad_total'] == 0]

    # Sedes reales con coordenadas reales, para el mapa (no más datos de ejemplo)
    sedes_reales = Sede.objects.filter(estado=True).select_related('eps')
    sedes_map_data = []
    for sede in sedes_reales:
        inv_sede = InventarioSede.objects.filter(sede=sede)
        total_meds = inv_sede.aggregate_count = inv_sede.count()
        unidades = sum(i.cantidad_disponible for i in inv_sede)
        if unidades == 0:
            stock_estado = 'out'
        elif any(i.estado_stock == 'stock_bajo' for i in inv_sede):
            stock_estado = 'low'
        else:
            stock_estado = 'ok'

        sedes_map_data.append({
            'lat': sede.latitud,
            'lng': sede.longitud,
            'nombre': f"{sede.eps.nombre} — {sede.nombre}",
            'addr': sede.direccion or sede.ciudad,
            'stock': stock_estado,
            'meds': unidades,
        })

    context = {
        'medicamentos': medicamentos,
        'total_medicamentos': total_medicamentos,
        'medicamentos_formula': medicamentos_formula,
        'medicamentos_libres': medicamentos_libres,
        'laboratorios': laboratorios,
        'medicamentos_agotados': medicamentos_agotados,
        'sedes_map_json': json_lib.dumps(sedes_map_data),
        'user_name': f"{request.user.first_name} {request.user.last_name}" if request.user.first_name else request.user.username,
        'user_initials': (request.user.first_name[0] + request.user.last_name[0]).upper() if request.user.first_name and request.user.last_name else request.user.email[:2].upper()
    }

    return render(
        request,
        'inventario/DashboardCliente.html',
        context
    )

Usuario = get_user_model()

def generate_jwt(user):
    payload = {
        'user_id': user.id,
        'email': user.email,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1),
        'iat': datetime.datetime.utcnow()
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

def get_user_from_jwt(request):
    token = request.COOKIES.get('jwt_token')
    if not token:
        # Check Authorization header as fallback
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
    
    if not token:
        return None
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')
        return Usuario.objects.get(id=user_id)
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, Usuario.DoesNotExist):
        return None


@never_cache
def registrar_usuario(request):
    if request.method == 'GET' and request.user.is_authenticated:
        return redirect(_redirect_por_rol(request.user))

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            nombre = data.get('nombre', '').strip()
            apellido = data.get('apellido', '').strip()
            email = data.get('email', '').strip().lower()
            password = data.get('password', '')
            telefono = data.get('telefono', '').strip()
            face_image = data.get('face_image', '')
            face_registered = data.get('face_registered', False)

            # Validaciones básicas
            patron_password = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$'
            if not re.match(patron_password, password):
                return JsonResponse({
                    'success': False,
                    'error': 'La contraseña debe tener mínimo 8 caracteres e incluir mayúscula, minúscula, número y carácter especial.'
                }, status=400)
            if not nombre or not email or not password:
                return JsonResponse({'success': False, 'error': 'El nombre, email y contraseña son requeridos.'}, status=400)

            if Usuario.objects.filter(email=email).exists():
                return JsonResponse({'success': False, 'error': 'Este correo electrónico ya está registrado.'}, status=400)

            # 1. Registrar en Firebase Auth
            fb_uid = None
            try:
                # Limpiar teléfono para Firebase y agregar +57 si no lo tiene
                cleaned_tel = ''.join(c for c in telefono if c.isdigit() or c == '+') if telefono else None
                if cleaned_tel and not cleaned_tel.startswith('+'):
                    if cleaned_tel.startswith('57') and len(cleaned_tel) == 12:
                        cleaned_tel = '+' + cleaned_tel
                    else:
                        cleaned_tel = '+57' + cleaned_tel

                fb_user = firebase_auth.create_user(
                    email=email,
                    password=password,
                    display_name=f"{nombre} {apellido}",
                    phone_number=cleaned_tel if cleaned_tel else None
                )
                fb_uid = fb_user.uid
            except Exception as e:
                # Extraer mensaje de error legible de Firebase si es posible
                error_msg = str(e)
                if "EMAIL_EXISTS" in error_msg:
                    error_msg = "El correo electrónico ya está registrado en Firebase."
                elif "PHONE_NUMBER_EXISTS" in error_msg:
                    error_msg = "El número de teléfono ya está registrado en Firebase."
                elif "INVALID_PHONE_NUMBER" in error_msg:
                    error_msg = "El número de teléfono es inválido o muy corto. Asegúrate de incluir el código de país (ejemplo: +573000000000)."
                return JsonResponse({'success': False, 'error': f'Error en Firebase: {error_msg}'}, status=400)

            # 2. Registrar en la Base de Datos de Django
            try:
                face_encoding_json = None
                embedding_lista = None # Guardaremos la lista nativa de números para Firestore
                
                if face_registered and face_image:
                    try:
                        embedding = get_embedding_from_base64(face_image)
                        embedding_lista = embedding  # Lista de floats
                        face_encoding_json = json.dumps(embedding)
                    except Exception as e:
                        # Si falla la extracción de características faciales, eliminamos el usuario recién creado en Firebase
                        if fb_uid:
                            try:
                                firebase_auth.delete_user(fb_uid)
                            except Exception as delete_err:
                                print(f"Error al revertir registro en Firebase para {email}: {delete_err}")
                        return JsonResponse({'success': False, 'error': f'Error en procesamiento de rostro: {str(e)}'}, status=400)

                user = Usuario.objects.create_user(
                    username=email, # Usamos el email como nombre de usuario
                    email=email,
                    password=password,
                    first_name=nombre,
                    last_name=apellido,
                    telefono=telefono,
                    firebase_uid=fb_uid,
                    face_encoding=face_encoding_json
                )
                
                # 3. Guardar el perfil y el embedding biométrico en Firestore
                db = get_firestore_db()
                if db is not None:
                    try:
                        doc_ref = db.collection('usuarios_biometria').document(fb_uid)
                        doc_ref.set({
                            'django_id': user.id,
                            'nombre': nombre,
                            'apellido': apellido,
                            'email': email,
                            'telefono': telefono,
                            'face_embedding': embedding_lista,  # Lista directa aceptada por Firestore
                            'is_face_login_enabled': True if embedding_lista else False,
                            'created_at': firestore.SERVER_TIMESTAMP
                        })
                    except Exception as fs_err:
                        print(f"Error crítico al respaldar perfil en Firestore: {fs_err}")

            except Exception as e:
                # Si falla el registro en la base de datos de Django, borramos el usuario de Firebase para no dejar inconsistencias
                if fb_uid:
                    try:
                        firebase_auth.delete_user(fb_uid)
                    except Exception as delete_err:
                        print(f"Error al revertir registro en Firebase para {email}: {delete_err}")
                return JsonResponse({'success': False, 'error': f'Error en Base de Datos: {str(e)}'}, status=500)

            # 3. Registrar en Firestore de Firebase
            try:
                db = firestore.client()
                db.collection('usuarios').document(fb_uid).set({
                    'nombre': nombre,
                    'apellido': apellido,
                    'email': email,
                    'telefono': telefono,
                    'rol': 'cliente',
                    'created_at': firestore.SERVER_TIMESTAMP,
                    'face_registered': data.get('face_registered', False)
                })
            except Exception as firestore_err:
                print(f"Error al registrar en Firestore: {firestore_err}")
                # Revertir base de datos Django y Firebase Auth si falla Firestore para consistencia
                try:
                    user.delete()
                except Exception as db_delete_err:
                    print(f"Error al revertir registro local para {email}: {db_delete_err}")
                if fb_uid:
                    try:
                        firebase_auth.delete_user(fb_uid)
                    except Exception as delete_err:
                        print(f"Error al revertir registro en Firebase Auth para {email}: {delete_err}")
                return JsonResponse({'success': False, 'error': f'Error al guardar en base de datos Firebase: {str(firestore_err)}'}, status=500)

            return JsonResponse({'success': True, 'message': 'Usuario registrado con éxito.'})

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Formato de datos inválido.'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Error interno: {str(e)}'}, status=500)

    # Si es GET, se renderiza la plantilla HTML
    return render(request, 'Farmacia/PharmonyRegistro.html')

@never_cache
def validar_rostro(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    try:
        data = json.loads(request.body)
        face_image = data.get('image', '')
        if not face_image:
            return JsonResponse({'success': False, 'error': 'No se proporcionó imagen de rostro.'}, status=400)
        
        # Test detection and embedding extraction
        get_embedding_from_base64(face_image)
        return JsonResponse({'success': True, 'message': 'Rostro verificado correctamente.'})
    except ValueError as ve:
        return JsonResponse({'success': False, 'error': str(ve)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error de validación facial: {str(e)}'}, status=500)

@never_cache
@never_cache
def login_face(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    try:
        data = json.loads(request.body)
        face_image = data.get('image', '')
        if not face_image:
            return JsonResponse({'success': False, 'error': 'No se proporcionó imagen de rostro.'}, status=400)
        
        # 1. Extraer el embedding de la cámara actual
        try:
            query_embedding = get_embedding_from_base64(face_image)
        except ValueError as ve:
            return JsonResponse({'success': False, 'error': str(ve)}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Error de análisis de rostro: {str(e)}'}, status=400)
        
        # Variables para rastrear al usuario con el puntaje más alto
        matching_user = None
        best_score = -1.0
        
        # IMPORTANTE: Subimos el umbral mínimo para el login global sin correo.
        # SFace por defecto usa 0.363, pero para búsquedas abiertas "1 a N" 
        # se recomienda subirlo a 0.42 o 0.45 para evitar CUALQUIER falso positivo.
        UMBRAL_ESTRICTO = 0.43 
        
        # 2. Recorrer todos los usuarios locales que tengan rostro registrado
        users_with_face = Usuario.objects.filter(face_encoding__isnull=False).exclude(face_encoding='')
        
        for user in users_with_face:
            try:
                db_embedding = json.loads(user.face_encoding)
                is_match, score = check_match(query_embedding, db_embedding)
                
                # Registramos en consola para que veas cuánto da tu rostro vs el de tu amigo
                print(f"DEBUG RECOGNITION: Evaluando {user.email} | Score: {score}")
                
                # No solo debe pasar el umbral estricto, sino ganarle al mejor puntaje guardado
                if score >= UMBRAL_ESTRICTO and score > best_score:
                    best_score = score
                    matching_user = user
            except Exception as e:
                print(f"Error al procesar coincidencia para {user.email}: {e}")
                continue
        
        # 3. Si encontramos un claro ganador que superó el umbral estricto
        if matching_user is not None:
            print(f"¡ Rostro Reconocido ! Ganador: {matching_user.email} con Score de: {best_score}")
            login(request, matching_user)
            redirect_url = _redirect_por_rol(matching_user)
            return JsonResponse({
                'success': True,
                'message': 'Autenticación biométrica exitosa.',
                'redirect_url': redirect_url
            })
        else:
            # Si nadie superó el UMBRAL_ESTRICTO (por ejemplo, tu amigo dando un score de 0.38)
            return JsonResponse({
                'success': False,
                'error': 'Rostro no reconocido en el sistema. Asegúrate de mirar fijamente la cámara.'
            }, status=401)
            
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Formato de datos inválido.'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error interno de autenticación: {str(e)}'}, status=500)

@never_cache
def iniciar_sesion(request):
    if request.method == 'GET' and request.user.is_authenticated:
        return redirect(_redirect_por_rol(request.user))
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email', '').strip().lower()
            password = data.get('password', '')

            if not email or not password:
                return JsonResponse({'success': False, 'error': 'El correo y la contraseña son requeridos.'}, status=400)

            usuario_local = Usuario.objects.filter(email__iexact=email).first()
            user = authenticate(request, username=usuario_local.username, password=password) if usuario_local else None
            if user is not None:
                login(request, user)
                redirect_url = _redirect_por_rol(user)
                return JsonResponse({
                        'success': True,
                        'message': 'Inicio de sesión exitoso.',
                        'redirect_url': redirect_url
                    })

            # 1. Autenticar con la API REST de Firebase Auth
            api_key = os.getenv('FIREBASE_WEB_API_KEY')
            if not api_key:
                return JsonResponse({'success': False, 'error': 'API key de Firebase no configurada.'}, status=500)

            url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
            payload = {
                "email": email,
                "password": password,
                "returnSecureToken": True
            }

            fb_response = requests.post(url, json=payload)
            fb_data = fb_response.json()

            if fb_response.status_code == 200:
                fb_uid = fb_data.get('localId')

                try:
                    user = Usuario.objects.get(firebase_uid=fb_uid)
                except Usuario.DoesNotExist:
                    try:
                        fb_user = firebase_auth.get_user(fb_uid)
                        display_name = fb_user.display_name or ""
                        parts = display_name.split(' ', 1)
                        first_name = parts[0] if len(parts) > 0 else ""
                        last_name = parts[1] if len(parts) > 1 else ""

                        # Buscamos en Firestore si esta cuenta ya tiene un rol/EPS asignado
                        # (por ejemplo, una cuenta EPS creada por un admin desde otra máquina)
                        rol_asignado = 'cliente'
                        eps_obj = None
                        try:
                            db = firestore.client()
                            user_doc = db.collection('usuarios').document(fb_uid).get()
                            if user_doc.exists:
                                doc_data = user_doc.to_dict()
                                rol_asignado = doc_data.get('rol', 'cliente')
                                eps_id = doc_data.get('eps_id')
                                if eps_id:
                                    from epsinventario.models import Eps
                                    eps_obj = Eps.objects.filter(id=eps_id).first()
                        except Exception as lookup_err:
                            print(f"Error al consultar rol en Firestore: {lookup_err}")

                        user = Usuario.objects.create_user(
                            username=email,
                            email=email,
                            password=password,
                            first_name=first_name,
                            last_name=last_name,
                            telefono=fb_user.phone_number or "",
                            firebase_uid=fb_uid,
                            rol=rol_asignado,
                            eps=eps_obj,
                        )

                        try:
                            db = firestore.client()
                            db.collection('usuarios').document(fb_uid).set({
                                'nombre': first_name,
                                'apellido': last_name,
                                'email': email,
                                'telefono': fb_user.phone_number or "",
                                'rol': rol_asignado,
                                'eps_id': eps_obj.id if eps_obj else None,
                                'face_registered': False
                            }, merge=True)
                        except Exception as firestore_err:
                            print(f"Error al sincronizar Firestore en login: {firestore_err}")

                    except Exception as sync_err:
                        return JsonResponse({'success': False, 'error': f'Error al sincronizar usuario: {str(sync_err)}'}, status=500)

                login(request, user)
                token = generate_jwt(user)
                response = JsonResponse({
                    'success': True,
                    'token': token,
                    'message': 'Inicio de sesión exitoso.',
                    'redirect_url': _redirect_por_rol(user)
                })
                response.set_cookie('jwt_token', token, max_age=86400, httponly=True, samesite='Lax')
                return response
            else:
                fb_error = fb_data.get('error', {})
                error_code = fb_error.get('message', '')
                if error_code in ['INVALID_LOGIN_CREDENTIALS', 'EMAIL_NOT_FOUND', 'INVALID_PASSWORD']:
                    error_msg = "Correo o contraseña incorrectos."
                elif error_code == 'USER_DISABLED':
                    error_msg = "Esta cuenta ha sido deshabilitada."
                else:
                    error_msg = f"Error al autenticar con Firebase: {error_code}"
                return JsonResponse({'success': False, 'error': error_msg}, status=401)

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Formato de datos inválido.'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Error interno: {str(e)}'}, status=500)

    # DESPUÉS
    user = get_user_from_jwt(request)
    if user is not None:
        login(request, user)
        try:
            return redirect(_redirect_por_rol(user))
        except Exception as e:
            print(f"Error al redirigir por rol: {e}")
    return render(request, 'Farmacia/PharmonyLogin.html')

# DESPUÉS
def _redirect_por_rol(user):
    """Centraliza a dónde va cada rol después de loguearse."""
    if user.rol == 'cliente':
        return reverse('dashboard_cliente')
    if user.rol == 'eps':
        return reverse('dashboard_eps')
    return reverse('dashboard_inventario')


@never_cache
@require_GET
def cerrar_sesion(request):
    logout(request)
    response = redirect('login')
    response.delete_cookie('jwt_token')
    return response


@login_required
def generar_derecho_peticion(request):
    import io
    from datetime import datetime
    from django.http import FileResponse, HttpResponse
    from django.shortcuts import get_object_or_404
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT

    if request.method not in ['POST', 'GET']:
        return HttpResponse("Método no permitido", status=405)
    
    # Obtener parámetros
    data = request.POST if request.method == 'POST' else request.GET
    
    med_id = data.get('medicamento_id')
    if not med_id:
        return HttpResponse("ID de medicamento requerido", status=400)
    
    medicamento = get_object_or_404(Medicamento, id=med_id)
    
    user = request.user
    datos_actualizados = False
    
    post_cedula = data.get('numero_documento')
    if post_cedula and post_cedula != user.cedula:
        user.cedula = post_cedula
        datos_actualizados = True
        
    post_direccion = data.get('direccion')
    if post_direccion and post_direccion != user.direccion:
        user.direccion = post_direccion
        datos_actualizados = True
        
    post_telefono = data.get('telefono')
    if post_telefono and post_telefono != user.telefono:
        user.telefono = post_telefono
        datos_actualizados = True

    post_full_name = data.get('nombre_usuario')
    if post_full_name and post_full_name != (user.get_full_name() or user.username):
        partes = post_full_name.split(' ', 1)
        if len(partes) > 1:
            user.first_name = partes[0]
            user.last_name = partes[1]
        else:
            user.first_name = post_full_name
            user.last_name = ''
        datos_actualizados = True
        
    if datos_actualizados:
        user.save()
        
    nombre_usuario = user.get_full_name() or user.username
    tipo_documento = data.get('tipo_documento') or 'Cédula de Ciudadanía'
    numero_documento = user.cedula or '_______________'
    
    eps_nombre = data.get('eps_nombre')
    if not eps_nombre and user.eps:
        eps_nombre = user.eps.nombre
    if not eps_nombre:
        eps_nombre = 'ENTIDAD PROMOTORA DE SALUD (EPS)'
        
    direccion = user.direccion or '_______________'
    telefono = user.telefono or '_______________'
    email = user.email or '_______________'
    ciudad = data.get('ciudad') or 'Bogotá D.C.'
    
    # Formatear la fecha en español
    fecha_actual = datetime.now()
    meses = {
        1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
        7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
    }
    fecha_str = f"{ciudad}, {fecha_actual.day} de {meses[fecha_actual.month]} de {fecha_actual.year}"
    
    # Crear buffer en memoria para el PDF
    buffer = io.BytesIO()
    
    # Configurar el documento PDF
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=72, # 1 pulgada
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    styles = getSampleStyleSheet()
    
    # Estilos personalizados
    style_normal = ParagraphStyle(
        name='NormalJustify',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        alignment=TA_JUSTIFY,
        spaceAfter=10
    )
    
    style_heading = ParagraphStyle(
        name='HeadingCustom',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        alignment=TA_LEFT,
        spaceBefore=12,
        spaceAfter=6
    )
    
    story = []
    
    # 1. Fecha y Lugar
    story.append(Paragraph(fecha_str, style_normal))
    story.append(Spacer(1, 15))
    
    # 2. Destinatario
    destinatario_text = f"<b>Señores:</b><br/><b>{eps_nombre.upper()}</b><br/>Oficina de Atención al Usuario / Representante Legal<br/>E. S. D."
    story.append(Paragraph(destinatario_text, style_normal))
    story.append(Spacer(1, 15))
    
    # 3. Asunto
    asunto_text = f"<b>ASUNTO:</b> DERECHO DE PETICIÓN (Artículo 23 de la Constitución Política de Colombia, Ley 1755 de 2015 y Ley Estatutaria de Salud 1751 de 2015) para la entrega inmediata del medicamento <b>{medicamento.nombre_comercial} ({medicamento.nombre_generico})</b>."
    story.append(Paragraph(asunto_text, style_normal))
    story.append(Spacer(1, 15))
    
    # 4. Presentación del peticionario
    presentacion_text = (
        f"Yo, <b>{nombre_usuario}</b>, mayor de edad, identificado con <b>{tipo_documento}</b> número <b>{numero_documento}</b>, "
        f"afiliado a la entidad promotora de salud <b>{eps_nombre}</b>, domiciliado en la dirección <b>{direccion}</b>, "
        f"con número de teléfono <b>{telefono}</b> y correo electrónico <b>{email}</b>, actuando en nombre propio y en ejercicio del "
        f"derecho constitucional de petición consagrado en el artículo 23 de la Constitución Política de Colombia, en concordancia con "
        f"la Ley 1755 de 2015 (que regula el derecho de petición) y la Ley Estatutaria de Salud 1751 de 2015, me dirijo ante ustedes de manera "
        f"respetuosa con el fin de formular la presente solicitud, con fundamento en los siguientes:"
    )
    story.append(Paragraph(presentacion_text, style_normal))
    story.append(Spacer(1, 10))
    
    # 5. Hechos
    story.append(Paragraph("HECHOS", style_heading))
    
    hecho1 = (
        f"1. Se me encuentra prescrito el medicamento <b>{medicamento.nombre_comercial} ({medicamento.nombre_generico})</b>, "
        f"concentración <b>{medicamento.concentracion}</b> y forma farmacéutica <b>{medicamento.forma_farmaceutica}</b>, "
        f"producido por el laboratorio <b>{medicamento.laboratorio}</b>, para el tratamiento de mi estado de salud."
    )
    story.append(Paragraph(hecho1, style_normal))
    
    hecho2 = (
        f"2. Al acudir a reclamar dicho medicamento en la red de farmacias Pharmony, se me informó que el medicamento se encuentra actualmente "
        f"<b>AGOTADO</b> en su totalidad de sedes, impidiendo que inicie o continúe con mi tratamiento en los términos indicados por el profesional de la salud."
    )
    story.append(Paragraph(hecho2, style_normal))
    
    hecho3 = (
        "3. La no entrega oportuna de los medicamentos prescritos pone en riesgo mi salud y bienestar, constituyendo una vulneración directa "
        "al derecho fundamental a la salud consagrado en la legislación colombiana y ampliamente protegido por la jurisprudencia constitucional."
    )
    story.append(Paragraph(hecho3, style_normal))
    story.append(Spacer(1, 10))
    
    # 6. Petición
    story.append(Paragraph("PETICIONES", style_heading))
    
    peticion1 = (
        f"1. Solicito de manera inmediata que la EPS <b>{eps_nombre}</b> gestione, autorice y haga entrega efectiva del medicamento "
        f"<b>{medicamento.nombre_comercial} ({medicamento.nombre_generico})</b> en las dosis y cantidades formuladas, en un plazo máximo "
        f"de cuarenta y ocho (48) horas, conforme a los lineamientos vigentes del Ministerio de Salud y la Superintendencia Nacional de Salud."
    )
    story.append(Paragraph(peticion1, style_normal))
    
    peticion2 = (
        "2. En caso de persistir la falta de stock del medicamento en el canal de dispensación habitual, se proceda a suministrar un sustituto "
        "terapéutico equivalente previa autorización médica, o bien, se gestione la entrega a domicilio del medicamento tan pronto se encuentre disponible "
        "sin que esto represente costos adicionales o cargas administrativas para mi persona."
    )
    story.append(Paragraph(peticion2, style_normal))
    story.append(Spacer(1, 10))
    
    # 7. Fundamentos de Derecho
    story.append(Paragraph("FUNDAMENTOS DE DERECHO", style_heading))
    fundamentos = (
        "Esta solicitud se fundamenta en el artículo 23 de la Constitución Política de Colombia; la Ley 1755 de 2015, por medio de la cual "
        "se regula el derecho fundamental de petición; la Ley 1751 de 2015 (Ley Estatutaria de Salud) que reconoce la salud como un derecho "
        "fundamental autónemo e irrenunciable, garantizando la entrega oportuna de tecnologías y medicamentos; y la jurisprudencia de la "
        "Corte Constitucional (Sentencia T-760 de 2008 y siguientes) que señala que el suministro incompleto o inoportuno de medicamentos "
        "vulnera el derecho a la salud y a la vida en condiciones dignas."
    )
    story.append(Paragraph(fundamentos, style_normal))
    story.append(Spacer(1, 10))
    
    # 8. Notificaciones
    story.append(Paragraph("NOTIFICACIONES y DIRECCIÓN DE CONTACTO", style_heading))
    notificaciones_text = (
        f"Recibiré respuesta a esta petición en los siguientes datos de contacto:<br/>"
        f"<b>Dirección física:</b> {direccion}<br/>"
        f"<b>Teléfono:</b> {telefono}<br/>"
        f"<b>Correo electrónico:</b> {email}"
    )
    story.append(Paragraph(notificaciones_text, style_normal))
    story.append(Spacer(1, 30))
    
    # 9. Firma
    firma_text = (
        f"Atentamente,<br/><br/><br/>"
        f"__________________________________________<br/>"
        f"<b>{nombre_usuario}</b><br/>"
        f"<b>{tipo_documento}:</b> {numero_documento}"
    )
    story.append(Paragraph(firma_text, style_normal))
    
    # Construir el PDF
    doc.build(story)
    
    # Volver al inicio del buffer
    buffer.seek(0)
    
    # Retornar como descarga de archivo
    response = FileResponse(buffer, as_attachment=True, filename=f"Derecho_Peticion_{medicamento.nombre_comercial.replace(' ', '_')}.pdf")
    return response


@login_required
@never_cache
def mi_cuenta(request):
    from epsinventario.models import Eps
    
    # Sincronizar EPS de Firebase Firestore a SQLite local
    db = get_firestore_db()
    if db:
        try:
            eps_ref = db.collection('eps').stream()
            for doc in eps_ref:
                data = doc.to_dict()
                eps_id = data.get('id')
                if eps_id is not None:
                    Eps.objects.update_or_create(
                        id=int(eps_id),
                        defaults={
                            'nombre': data.get('nombre', ''),
                            'nit': data.get('nit', ''),
                            'direccion': data.get('direccion', ''),
                            'ciudad': data.get('ciudad', ''),
                            'telefono': data.get('telefono', ''),
                            'email': data.get('email', ''),
                            'estado': data.get('estado', True)
                        }
                    )
        except Exception as sync_err:
            print(f"Error al sincronizar EPS desde Firestore: {sync_err}")
            
    mensaje_exito = None
    mensaje_error = None
    epss = Eps.objects.filter(estado=True)
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        apellido = request.POST.get('apellido', '').strip()
        cedula = request.POST.get('cedula', '').strip()
        direccion = request.POST.get('direccion', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        email = request.POST.get('email', '').strip()
        eps_id = request.POST.get('eps_id', '').strip()
        
        user = request.user
        
        if not nombre or not email:
            mensaje_error = "El nombre y el correo electrónico son requeridos."
        else:
            user.first_name = nombre
            user.last_name = apellido
            user.cedula = cedula
            user.direccion = direccion
            user.telefono = telefono
            user.email = email
            
            eps_obj = None
            if eps_id:
                try:
                    eps_obj = Eps.objects.get(id=eps_id)
                    user.eps = eps_obj
                except Eps.DoesNotExist:
                    user.eps = None
            else:
                user.eps = None
                
            user.save()
            
            # Sincronizar con Firebase (Firestore y Auth)
            fb_uid = user.firebase_uid
            if fb_uid:
                # Firestore
                try:
                    db = get_firestore_db()
                    if db:
                        db.collection('usuarios').document(fb_uid).set({
                            'nombre': user.first_name,
                            'apellido': user.last_name,
                            'email': user.email,
                            'telefono': user.telefono or "",
                            'cedula': user.cedula or "",
                            'direccion': user.direccion or "",
                            'eps_id': eps_obj.id if eps_obj else None
                        }, merge=True)
                except Exception as fs_err:
                    print(f"Error sincronizando perfil en Firestore: {fs_err}")
                
                # Firebase Auth
                try:
                    firebase_auth.update_user(
                        fb_uid,
                        email=user.email
                    )
                except Exception as auth_err:
                    print(f"Error actualizando Firebase Auth: {auth_err}")
                    
            return redirect(reverse('mi_cuenta') + '?saved=1')
            
    if request.GET.get('saved') == '1':
        mensaje_exito = "¡Tu información de perfil se ha guardado y sincronizado con Firebase correctamente!"
        
    # Calcular iniciales para el avatar
    user_name = request.user.get_full_name() or request.user.username
    parts = user_name.split()
    user_initials = "".join([p[0].upper() for p in parts[:2]]) if parts else "?"
        
    return render(request, 'inventario/MiCuenta.html', {
        'mensaje_exito': mensaje_exito,
        'mensaje_error': mensaje_error,
        'epss': epss,
        'user_name': user_name,
        'user_initials': user_initials
    })
