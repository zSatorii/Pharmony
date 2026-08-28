"""
Farmacia/views/auth_views.py

Vistas de autenticación: registro, login (con y sin reconocimiento
facial), logout, y utilidades de JWT.
"""

import datetime
import json
import os
import re

import jwt
import requests

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from firebase_admin import auth as firebase_auth
from firebase_admin import firestore
from IA.face_rec import check_match, get_embedding_from_base64
from epsinventario.models import Eps
from .common import _redirect_por_rol, get_firestore_db

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

            fb_uid = None
            try:
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
                error_msg = str(e)
                if "EMAIL_EXISTS" in error_msg:
                    error_msg = "El correo electrónico ya está registrado en Firebase."
                elif "PHONE_NUMBER_EXISTS" in error_msg:
                    error_msg = "El número de teléfono ya está registrado en Firebase."
                elif "INVALID_PHONE_NUMBER" in error_msg:
                    error_msg = "El número de teléfono es inválido o muy corto. Asegúrate de incluir el código de país (ejemplo: +573000000000)."
                return JsonResponse({'success': False, 'error': f'Error en Firebase: {error_msg}'}, status=400)

            try:
                face_encoding_json = None
                embedding_lista = None
                
                if face_registered and face_image:
                    try:
                        embedding = get_embedding_from_base64(face_image)
                        embedding_lista = embedding
                        face_encoding_json = json.dumps(embedding)
                    except Exception as e:
                        if fb_uid:
                            try:
                                firebase_auth.delete_user(fb_uid)
                            except Exception:
                                pass
                        return JsonResponse({'success': False, 'error': f'Error en procesamiento de rostro: {str(e)}'}, status=400)

                user = Usuario.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                    first_name=nombre,
                    last_name=apellido,
                    telefono=telefono,
                    firebase_uid=fb_uid,
                    face_encoding=face_encoding_json
                )
                
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
                            'face_embedding': embedding_lista,
                            'is_face_login_enabled': True if embedding_lista else False,
                            'created_at': firestore.SERVER_TIMESTAMP
                        })
                    except Exception:
                        pass

            except Exception as e:
                if fb_uid:
                    try:
                        firebase_auth.delete_user(fb_uid)
                    except Exception:
                        pass
                return JsonResponse({'success': False, 'error': f'Error en Base de Datos: {str(e)}'}, status=500)

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
                try:
                    user.delete()
                except Exception:
                    pass
                if fb_uid:
                    try:
                        firebase_auth.delete_user(fb_uid)
                    except Exception:
                        pass
                return JsonResponse({'success': False, 'error': f'Error al guardar en base de datos Firebase: {str(firestore_err)}'}, status=500)

            return JsonResponse({'success': True, 'message': 'Usuario registrado con éxito.'})

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Formato de datos inválido.'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Error interno: {str(e)}'}, status=500)

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
        get_embedding_from_base64(face_image)
        return JsonResponse({'success': True, 'message': 'Rostro verificado correctamente.'})
    except ValueError as ve:
        return JsonResponse({'success': False, 'error': str(ve)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error de validación facial: {str(e)}'}, status=500)

@never_cache
def login_face(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    try:
        data = json.loads(request.body)
        face_image = data.get('image', '')
        if not face_image:
            return JsonResponse({'success': False, 'error': 'No se proporcionó imagen de rostro.'}, status=400)
        
        try:
            query_embedding = get_embedding_from_base64(face_image)
        except ValueError as ve:
            return JsonResponse({'success': False, 'error': str(ve)}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Error de análisis de rostro: {str(e)}'}, status=400)
        
        matching_user = None
        best_score = -1.0
        UMBRAL_ESTRICTO = 0.43 
        
        users_with_face = Usuario.objects.filter(face_encoding__isnull=False).exclude(face_encoding='')
        
        for user in users_with_face:
            try:
                db_embedding = json.loads(user.face_encoding)
                is_match, score = check_match(query_embedding, db_embedding)
                if score >= UMBRAL_ESTRICTO and score > best_score:
                    best_score = score
                    matching_user = user
            except Exception:
                continue
        
        if matching_user is not None:
            login(request, matching_user)
            redirect_url = _redirect_por_rol(matching_user)
            return JsonResponse({
                'success': True,
                'message': 'Autenticación biométrica exitosa.',
                'redirect_url': redirect_url
            })
        else:
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
                token = generate_jwt(user)
                response = JsonResponse({
                    'success': True,
                    'token': token,
                    'message': 'Inicio de sesión exitoso.',
                    'redirect_url': redirect_url
                })
                response.set_cookie('jwt_token', token, max_age=86400, httponly=True, samesite='Lax')
                return response

            api_key = os.getenv('FIREBASE_WEB_API_KEY') or os.getenv('FIREBASE_API_KEY')
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
                                    eps_obj = Eps.objects.filter(id=eps_id).first()
                        except Exception:
                            pass

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
                        except Exception:
                            pass

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

    user = get_user_from_jwt(request)
    if user is not None:
        login(request, user)
        try:
            return redirect(_redirect_por_rol(user))
        except Exception:
            pass
    return render(request, 'Farmacia/PharmonyLogin.html')

@never_cache
@require_GET
def cerrar_sesion(request):
    logout(request)
    response = redirect('login')
    response.delete_cookie('jwt_token')
    return response