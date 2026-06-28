from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .models import Medicamento
from .serializers import MedicamentoSerializer

import json
import re
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth import get_user_model, authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.urls import reverse
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
def dashboard_inventario(request):
    if request.user.rol == 'cliente':
        return redirect('dashboard_cliente')

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

    medicamentos_formula = medicamentos.filter(
        requiere_formula=True
    ).count()

    medicamentos_libres = medicamentos.filter(
        requiere_formula=False
    ).count()

    laboratorios = medicamentos.values(
        'laboratorio'
    ).distinct().count()

    context = {
        'medicamentos': medicamentos,
        'total_medicamentos': total_medicamentos,
        'medicamentos_formula': medicamentos_formula,
        'medicamentos_libres': medicamentos_libres,
        'laboratorios': laboratorios
    }

    return render(
        request,
        'inventario/DashboardInventario.html',
        context
    )

@never_cache
@login_required
def dashboard_cliente(request):
    if request.user.rol in ['farmaceutico', 'admin']:
        return redirect('dashboard_inventario')

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
        'laboratorios': laboratorios,
        'user_name': f"{request.user.first_name} {request.user.last_name}" if request.user.first_name else request.user.username,
        'user_initials': (request.user.first_name[0] + request.user.last_name[0]).upper() if request.user.first_name and request.user.last_name else request.user.email[:2].upper()
    }

    return render(
        request,
        'inventario/DashboardCliente.html',
        context
    )

Usuario = get_user_model()

@never_cache
def registrar_usuario(request):
    if request.method == 'GET' and request.user.is_authenticated:
        if request.user.rol == 'cliente':
            return redirect('dashboard_cliente')
        else:
            return redirect('dashboard_inventario')

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
            redirect_url = reverse('dashboard_cliente') if matching_user.rol == 'cliente' else reverse('dashboard_inventario')
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
        if request.user.rol == 'cliente':
            return redirect('dashboard_cliente')
        else:
            return redirect('dashboard_inventario')
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email', '').strip().lower()
            password = data.get('password', '')

            if not email or not password:
                return JsonResponse({'success': False, 'error': 'El correo y la contraseña son requeridos.'}, status=400)

            print(f"DEBUG LOGIN: Intentando autenticar email='{email}', largo password={len(password)}")
            user = authenticate(request, username=email, password=password)
            print(f"DEBUG LOGIN: authenticate retorno {user}")
            if user is not None:
                login(request, user)
                redirect_url = reverse('dashboard_cliente') if user.rol == 'cliente' else reverse('dashboard_inventario')
                return JsonResponse({
                        'success': True,
                        'message': 'Inicio de sesión exitoso.',
                        'redirect_url': redirect_url
                    })
            else:
                return JsonResponse({'success': False, 'error': 'Credenciales inválidas.'}, status=401)

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Formato de datos inválido.'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Error interno: {str(e)}'}, status=500)

    # Si es GET, se renderiza la plantilla HTML
    return render(request, 'Farmacia/PharmonyLogin.html')

@never_cache
@require_GET
def cerrar_sesion(request):
    logout(request)
    return redirect('login')