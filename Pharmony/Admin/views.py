from django.shortcuts import render, redirect
import re
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from firebase_admin import auth as firebase_auth
from google.cloud import firestore
import json
from Farmacia.models import Usuario, Medicamento
from .decorators import admin_required

@admin_required
def dashboard_admin_view(request):
    # Obtenemos algunas métricas rápidas para hacer el Dashboard interesante
    total_clientes = Usuario.objects.filter(rol='cliente').count()
    total_farmaceuticos = Usuario.objects.filter(rol='farmaceutico').count()
    total_medicamentos = Medicamento.objects.count()
    
    contexto = {
        'total_clientes': total_clientes,
        'total_farmaceuticos': total_farmaceuticos,
        'total_medicamentos': total_medicamentos,
    }
    return render(request, 'Farmacia/dashboard_admin.html', contexto)

@admin_required
@csrf_exempt
def crear_farmaceutico_view(request):
    # Nota: Aquí asumimos que ya pasó por el decorador de seguridad de administrador
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            nombre = data.get('nombre', '').strip()
            apellido = data.get('apellido', '').strip()
            email = data.get('email', '').strip().lower()
            password = data.get('password', '')
            telefono = data.get('telefono', '').strip()

            # Validaciones de seguridad para la contraseña
            patron_password = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$'
            if not re.match(patron_password, password):
                return JsonResponse({'success': False, 'error': 'La contraseña no cumple con los requisitos mínimos de seguridad.'}, status=400)

            if Usuario.objects.filter(email=email).exists():
                return JsonResponse({'success': False, 'error': 'Este correo ya está registrado en el sistema.'}, status=400)

            # 1. Registrar en Firebase Auth
            fb_uid = None
            try:
                # Limpieza rápida de teléfono para el formato requerido por Firebase (+57)
                cleaned_tel = ''.join(c for c in telefono if c.isdigit() or c == '+') if telefono else None
                if cleaned_tel and not cleaned_tel.startswith('+'):
                    cleaned_tel = '+57' + cleaned_tel if not cleaned_tel.startswith('57') else '+' + cleaned_tel

                fb_user = firebase_auth.create_user(
                    email=email,
                    password=password,
                    display_name=f"{nombre} {apellido}",
                    phone_number=cleaned_tel if cleaned_tel else None
                )
                fb_uid = fb_user.uid
            except Exception as e:
                return JsonResponse({'success': False, 'error': f'Error al crear cuenta en Firebase Auth: {str(e)}'}, status=400)

            # 2. Registrar en la Base de Datos de Django (Forzando el rol 'farmaceutico')
            try:
                user = Usuario.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                    first_name=nombre,
                    last_name=apellido,
                    telefono=telefono,
                    firebase_uid=fb_uid,
                    rol='farmaceutico'  # <- AQUÍ ASIGNAS EL ROL DIRECTAMENTE
                )
            except Exception as e:
                if fb_uid:
                    firebase_auth.delete_user(fb_uid)  # Revertir Firebase si Django falla
                return JsonResponse({'success': False, 'error': f'Error en Base de Datos local: {str(e)}'}, status=500)

            # 3. Registrar en Firestore de Firebase (Marcando el rol 'farmaceutico')
            try:
                db = firestore.client()
                db.collection('usuarios').document(fb_uid).set({
                    'nombre': nombre,
                    'apellido': apellido,
                    'email': email,
                    'telefono': telefono,
                    'rol': 'farmaceutico',  # <- CONSISTENCIA TOTAL EN FIRESTORE
                    'created_at': firestore.SERVER_TIMESTAMP,
                    'face_registered': False
                })
            except Exception as firestore_err:
                # Reversión en cascada completa si falla Firestore
                user.delete()
                if fb_uid:
                    firebase_auth.delete_user(fb_uid)
                return JsonResponse({'success': False, 'error': f'Error en Firestore: {str(firestore_err)}'}, status=500)

            return JsonResponse({'success': True, 'message': 'Farmacéutico registrado exitosamente en todos los servicios.'})

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Formato de datos inválido.'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Error interno: {str(e)}'}, status=500)

    return redirect('dashboard_admin')