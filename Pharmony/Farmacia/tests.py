from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from Farmacia.models import Medicamento, MedicamentoUsuario, DerechoPeticion

class DerechoPeticionTestCase(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username='testuser',
            password='testpassword',
            first_name='Juan',
            last_name='Perez',
            email='juan.perez@example.com',
            telefono='3001234567',
            rol='cliente'
        )
        self.eps_user = self.User.objects.create_user(
            username='epsuser',
            password='epspassword',
            first_name='Auxiliar',
            last_name='Farmacia',
            email='eps@pharmony.com',
            rol='eps'
        )
        self.medicamento = Medicamento.objects.create(
            codigo_cum='12345-1',
            nombre_generico='Acetaminofen',
            nombre_comercial='Dolex',
            laboratorio='GSK',
            concentracion='500mg',
            forma_farmaceutica='Tableta',
            descripcion='Para el dolor',
            uso_indicado='Tomar cada 6 horas',
            efectos_secundarios='Ninguno',
            requiere_formula=False
        )

    def test_generar_derecho_peticion_pdf_y_radicado(self):
        self.client.login(username='testuser', password='testpassword')
        
        url = reverse('generar_derecho_peticion')
        
        data = {
            'medicamento_id': self.medicamento.id,
            'nombre_usuario': 'Juan Perez',
            'tipo_documento': 'Cédula de Ciudadanía',
            'numero_documento': '10101010',
            'eps_nombre': 'SURA',
            'direccion': 'Calle 10 # 20-30',
            'telefono': '3001234567',
            'email': 'juan.perez@example.com',
            'ciudad': 'Bogotá'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Content-Type'], 'application/pdf')
        
        pdf_content = b"".join(response.streaming_content)
        self.assertTrue(pdf_content.startswith(b'%PDF'))

        self.user.refresh_from_db()
        self.assertEqual(self.user.cedula, '10101010')
        self.assertEqual(self.user.direccion, 'Calle 10 # 20-30')
        self.assertEqual(self.user.telefono, '3001234567')

        # Verificar que se creó el registro DerechoPeticion en base de datos
        peticion = DerechoPeticion.objects.filter(usuario=self.user, medicamento=self.medicamento).first()
        self.assertIsNotNone(peticion)
        self.assertEqual(peticion.estado, 'radicado')
        self.assertTrue(peticion.numero_radicado.startswith('DP-'))

    def test_bloqueo_duplicados_derecho_peticion(self):
        self.client.login(username='testuser', password='testpassword')
        url = reverse('generar_derecho_peticion')
        data = {
            'medicamento_id': self.medicamento.id,
            'nombre_usuario': 'Juan Perez',
            'numero_documento': '10101010',
            'direccion': 'Calle 10 # 20-30',
        }
        
        # Primera solicitud
        resp1 = self.client.post(url, data)
        self.assertEqual(resp1.status_code, 200)
        total_peticiones_1 = DerechoPeticion.objects.filter(usuario=self.user, medicamento=self.medicamento).count()
        self.assertEqual(total_peticiones_1, 1)
        peticion_original = DerechoPeticion.objects.get(usuario=self.user, medicamento=self.medicamento)

        # Segunda solicitud (debe reutilizar el mismo radicado sin duplicar)
        resp2 = self.client.post(url, data)
        self.assertEqual(resp2.status_code, 200)
        total_peticiones_2 = DerechoPeticion.objects.filter(usuario=self.user, medicamento=self.medicamento).count()
        self.assertEqual(total_peticiones_2, 1)

    def test_marcar_entrega_eps_y_desbloqueo(self):
        # Crear petición en estado radicado
        peticion = DerechoPeticion.objects.create(
            numero_radicado='DP-2026-TEST-001',
            usuario=self.user,
            medicamento=self.medicamento,
            estado='radicado'
        )

        # Farmacéutico marca como entregado
        self.client.login(username='epsuser', password='epspassword')
        url = reverse('entregar_derecho_peticion_api', kwargs={'peticion_id': peticion.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)

        peticion.refresh_from_db()
        self.assertEqual(peticion.estado, 'entregado')
        self.assertIsNotNone(peticion.fecha_respuesta)

        # Ahora el usuario podría radicar una nueva si vuelve a quedar sin medicamento
        self.client.login(username='testuser', password='testpassword')
        url_gen = reverse('generar_derecho_peticion')
        data = {'medicamento_id': self.medicamento.id}
        resp = self.client.post(url_gen, data)
        self.assertEqual(resp.status_code, 200)

        total_peticiones = DerechoPeticion.objects.filter(usuario=self.user, medicamento=self.medicamento).count()
        self.assertEqual(total_peticiones, 2)

    def test_asignacion_medicamento_usuario(self):
        med_user = MedicamentoUsuario.objects.create(
            usuario=self.user,
            medicamento=self.medicamento,
            dosis='1 tableta cada 8 horas',
            cantidad_prescrita='30 tabletas',
            fuente_asignacion='ia_formula'
        )
        self.assertEqual(self.user.medicamentos_asignados.count(), 1)
        self.assertEqual(self.user.medicamentos_asignados.first().medicamento, self.medicamento)

    def test_asignar_medicamento_api_docsia(self):
        self.client.login(username='testuser', password='testpassword')
        url = reverse('DocsIA:asignar_api')
        import json
        payload = {
            'medicamento_id': self.medicamento.id,
            'dosis': '500mg cada 12 horas',
            'cantidad': '20 tabletas'
        }
        response = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertEqual(MedicamentoUsuario.objects.filter(usuario=self.user, medicamento=self.medicamento).count(), 1)

    def test_mi_cuenta_get_and_post(self):
        self.client.login(username='testuser', password='testpassword')
        
        url = reverse('mi_cuenta')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        post_data = {
            'nombre': 'Carlos',
            'apellido': 'Gomez',
            'cedula': '999999',
            'direccion': 'Avenida Siempre Viva 123',
            'telefono': '3159998877',
            'email': 'carlos@example.com',
            'eps_id': ''
        }
        response = self.client.post(url, post_data)
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('?saved=1', response.url)
        
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Carlos')
        self.assertEqual(self.user.last_name, 'Gomez')
        self.assertEqual(self.user.cedula, '999999')
        self.assertEqual(self.user.direccion, 'Avenida Siempre Viva 123')
        self.assertEqual(self.user.telefono, '3159998877')
        self.assertEqual(self.user.email, 'carlos@example.com')