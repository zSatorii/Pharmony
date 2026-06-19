from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status
import datetime
import jwt
import os
from django.conf import settings
from .models import Medicamento
from .serializers import MedicamentoSerializer
import requests
import json
from django.urls import reverse
from django.http import JsonResponse
from django.contrib.auth import get_user_model, authenticate
import re
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth import get_user_model, authenticate, login
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

@login_required
@never_cache
def dashboard_inventario(request):
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
    # Si ya tiene una sesión iniciada, redirigir al dashboard
    user = get_user_from_jwt(request)
    if user is not None:
        return redirect('dashboard_inventario')

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            nombre = data.get('nombre', '').strip()
            apellido = data.get('apellido', '').strip()
            email = data.get('email', '').strip()
            password = data.get('password', '')
            telefono = data.get('telefono', '').strip()

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
                user = Usuario.objects.create_user(
                    username=email, # Usamos el email como nombre de usuario
                    email=email,
                    password=password,
                    first_name=nombre,
                    last_name=apellido,
                    telefono=telefono,
                    firebase_uid=fb_uid
                )
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
def iniciar_sesion(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email', '').strip()
            password = data.get('password', '')

            if not email or not password:
                return JsonResponse({'success': False, 'error': 'El correo y la contraseña son requeridos.'}, status=400)

            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                return JsonResponse({
                        'success': True,
                        'message': 'Inicio de sesión exitoso.',
                        'redirect_url': reverse('dashboard_inventario')
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

                # 2. Buscar o sincronizar/crear el usuario localmente
                try:
                    user = Usuario.objects.get(firebase_uid=fb_uid)
                except Usuario.DoesNotExist:
                    try:
                        # Si existe en Firebase Auth pero no en Django local, obtener detalles y crear local
                        fb_user = firebase_auth.get_user(fb_uid)
                        display_name = fb_user.display_name or ""
                        parts = display_name.split(' ', 1)
                        first_name = parts[0] if len(parts) > 0 else ""
                        last_name = parts[1] if len(parts) > 1 else ""

                        user = Usuario.objects.create_user(
                            username=email,
                            email=email,
                            password=password,
                            first_name=first_name,
                            last_name=last_name,
                            telefono=fb_user.phone_number or "",
                            firebase_uid=fb_uid
                        )

                        # Asegurarse de que esté también en Firestore
                        try:
                            db = firestore.client()
                            user_doc = db.collection('usuarios').document(fb_uid).get()
                            if not user_doc.exists:
                                db.collection('usuarios').document(fb_uid).set({
                                    'nombre': first_name,
                                    'apellido': last_name,
                                    'email': email,
                                    'telefono': fb_user.phone_number or "",
                                    'rol': 'cliente',
                                    'created_at': firestore.SERVER_TIMESTAMP,
                                    'face_registered': False
                                })
                        except Exception as firestore_err:
                            print(f"Error al sincronizar Firestore en login: {firestore_err}")

                    except Exception as sync_err:
                        return JsonResponse({'success': False, 'error': f'Error al sincronizar usuario: {str(sync_err)}'}, status=500)
                    
                login(request, user)
                # 3. Generar token JWT local y establecer cookie
                token = generate_jwt(user)
                response = JsonResponse({'success': True, 'token': token, 'message': 'Inicio de sesión exitoso.'})
                response.set_cookie('jwt_token', token, max_age=86400, httponly=True, samesite='Lax')
                return response
            else:
                # Manejar errores de Firebase Auth REST API
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

    user = get_user_from_jwt(request)
    if user is not None:
        return redirect('dashboard_inventario')
    return render(request, 'Farmacia/PharmonyLogin.html')


@never_cache
def cerrar_sesion(request):
    response = redirect('login')
    response.delete_cookie('jwt_token')
    return response
