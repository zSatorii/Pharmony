from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from Farmacia.models import Medicamento

class DerechoPeticionTestCase(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username='testuser',
            password='testpassword',
            first_name='Juan',
            last_name='Perez',
            email='juan.perez@example.com',
            telefono='3001234567'
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

    def test_generar_derecho_peticion_pdf(self):
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