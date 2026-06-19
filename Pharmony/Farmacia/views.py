from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status

from .models import Medicamento
from .serializers import MedicamentoSerializer

import json
import os
import requests
from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import JsonResponse
from django.contrib.auth import get_user_model, authenticate
from django.conf import settings
from django.views.decorators.cache import never_cache

# Tus dependencias solicitadas de Firebase Admin
from firebase_admin import auth as firebase_auth, firestore

from rest_framework import viewsets, status
from rest_framework.response import Response
from .models import Medicamento
from .serializers import MedicamentoSerializer

class MedicamentoViewSet(viewsets.ModelViewSet):
    queryset = Medicamento.objects.all().order_by("nombre_comercial")
    serializer_class = MedicamentoSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # 1. Guardamos localmente en la base de datos de Django (SQLite/Postgres)
            instance = serializer.save() 

            # 2. Extraemos los datos validados listos para enviar en formato JSON a Firebase
            medicamento_data = serializer.data

            try:
                # 3. LLAMADA DIRECTA: Inicializamos el cliente usando la dependencia nativa 'firestore'
                db = firestore.client()

                # 4. Asignamos el ID único del documento (preferiblemente el código del medicamento o su nombre comercial)
                document_id = str(medicamento_data.get('id')) or medicamento_data.get('nombre_comercial')

                # 5. Enviamos a Firestore (Creará de forma automática la colección si no existe)
                db.collection('medicamentos').document(document_id).set(medicamento_data)
                
                return Response(
                    {
                        "mensaje": "Medicamento registrado correctamente en Django y Firebase",
                        "data": medicamento_data
                    },
                    status=status.HTTP_201_CREATED
                )
                
            except Exception as firebase_error:
                return Response(
                    {
                        "error": "El medicamento se validó, pero falló el envío a Firebase",
                        "detalle": str(firebase_error)
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

# ==========================
# Dashboard Inventario
# ==========================

def dashboard_inventario(request):

    medicamentos = Medicamento.objects.all()

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

Usuario = get_user_model()

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
                login(request, user)
                return JsonResponse({'success': True, 'message': 'Inicio de sesión exitoso.'})
            else:
                return JsonResponse({'success': False, 'error': 'Credenciales inválidas.'}, status=401)

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Formato de datos inválido.'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Error interno: {str(e)}'}, status=500)

    # Si es GET, se renderiza la plantilla HTML
    return render(request, 'Farmacia/PharmonyLogin.html')
