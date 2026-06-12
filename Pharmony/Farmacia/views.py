import json
import datetime
import jwt
from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import JsonResponse
from django.contrib.auth import get_user_model, authenticate
from django.conf import settings
from firebase_admin import auth as firebase_auth

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

def registrar_usuario(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            nombre = data.get('nombre', '').strip()
            apellido = data.get('apellido', '').strip()
            email = data.get('email', '').strip()
            password = data.get('password', '')
            telefono = data.get('telefono', '').strip()

            # Validaciones básicas
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

            return JsonResponse({'success': True, 'message': 'Usuario registrado con éxito.'})

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Formato de datos inválido.'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Error interno: {str(e)}'}, status=500)

    # Si es GET, se renderiza la plantilla HTML
    return render(request, 'Farmacia/PharmonyRegistro.html')

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
                token = generate_jwt(user)
                response = JsonResponse({'success': True, 'token': token, 'message': 'Inicio de sesión exitoso.'})
                response.set_cookie('jwt_token', token, max_age=86400, httponly=True, samesite='Lax')
                return response
            else:
                return JsonResponse({'success': False, 'error': 'Credenciales inválidas.'}, status=401)

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Formato de datos inválido.'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Error interno: {str(e)}'}, status=500)

    user = get_user_from_jwt(request)
    if user is not None:
        return redirect('dashboard')
    return render(request, 'Farmacia/PharmonyLogin.html')

def dashboard(request):
    user = get_user_from_jwt(request)
    if not user:
        return redirect('login')
    return render(request, 'Farmacia/PharmonyDashboard.html', {'user': user})

def cerrar_sesion(request):
    response = redirect('login')
    response.delete_cookie('jwt_token')
    return response
