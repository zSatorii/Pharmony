from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from Farmacia.views import get_firestore_db
from Farmacia.models import Medicamento
from epsinventario.models import Eps, Sede, InventarioSede
import json

Usuario = get_user_model()

class Command(BaseCommand):
    help = "Trae EPS, Sedes, Medicamentos, Inventario y Usuarios con Biometria desde Firestore a SQLite."

    def handle(self, *args, **options):
        db = get_firestore_db()
        if db is None:
            self.stderr.write("No se pudo conectar a Firestore. Revisa tu ServiceAccountKey.json.")
            return

        # 1. EPS
        count_eps = 0
        for doc in db.collection('eps').stream():
            d = doc.to_dict()
            eps_id = d.get('id') or (int(doc.id) if doc.id.isdigit() else None)
            if eps_id is None:
                continue
            Eps.objects.update_or_create(
                id=eps_id,
                defaults={
                    'nombre': d.get('nombre', ''),
                    'nit': d.get('nit', ''),
                    'direccion': d.get('direccion', ''),
                    'ciudad': d.get('ciudad', ''),
                    'telefono': d.get('telefono', ''),
                    'email': d.get('email', ''),
                    'estado': d.get('estado', True),
                }
            )
            count_eps += 1
        self.stdout.write(f"[OK] {count_eps} EPS sincronizadas.")

        # 2. Sedes
        count_sedes = 0
        for doc in db.collection('sedes').stream():
            d = doc.to_dict()
            sede_id = d.get('id') or (int(doc.id) if doc.id.isdigit() else None)
            eps = Eps.objects.filter(id=d.get('eps_id')).first()
            if not eps or sede_id is None:
                continue
            Sede.objects.update_or_create(
                id=sede_id,
                defaults={
                    'eps': eps,
                    'nombre': d.get('nombre', ''),
                    'direccion': d.get('direccion', ''),
                    'ciudad': d.get('ciudad', ''),
                    'telefono': d.get('telefono', ''),
                    'email': d.get('email', ''),
                    'estado': d.get('estado', True),
                }
            )
            count_sedes += 1
        self.stdout.write(f"[OK] {count_sedes} sedes sincronizadas.")

        # 3. Medicamentos
        count_meds = 0
        for doc in db.collection('medicamentos').stream():
            d = doc.to_dict()
            med_id = d.get('id') or (int(doc.id) if doc.id.isdigit() else None)
            codigo_cum = d.get('codigo_cum') or doc.id
            if med_id is None:
                continue
            Medicamento.objects.update_or_create(
                id=med_id,
                defaults={
                    'codigo_cum': str(codigo_cum),
                    'nombre_generico': d.get('nombre_generico', ''),
                    'nombre_comercial': d.get('nombre_comercial', ''),
                    'laboratorio': d.get('laboratorio', ''),
                    'concentracion': d.get('concentracion', ''),
                    'forma_farmaceutica': d.get('forma_farmaceutica', ''),
                    'descripcion': d.get('descripcion', ''),
                    'uso_indicado': d.get('uso_indicado', ''),
                    'efectos_secundarios': d.get('efectos_secundarios', ''),
                    'requiere_formula': bool(d.get('requiere_formula', False)),
                }
            )
            count_meds += 1
        self.stdout.write(f"[OK] {count_meds} medicamentos sincronizados.")

        # 4. Inventario Sedes
        count_inv = 0
        for doc in db.collection('inventario_sedes').stream():
            d = doc.to_dict()
            inv_id = d.get('id') or (int(doc.id) if doc.id.isdigit() else None)
            sede = Sede.objects.filter(id=d.get('sede_id')).first()
            medicamento = Medicamento.objects.filter(id=d.get('medicamento_id')).first()
            if not sede or not medicamento or inv_id is None:
                continue
            
            cant_disp = d.get('cantidad_disponible', 0)
            try:
                cant_disp = int(cant_disp)
            except (ValueError, TypeError):
                cant_disp = 0

            cant_min = d.get('cantidad_minima', 10)
            try:
                cant_min = int(cant_min)
            except (ValueError, TypeError):
                cant_min = 10

            InventarioSede.objects.update_or_create(
                id=inv_id,
                defaults={
                    'sede': sede,
                    'medicamento': medicamento,
                    'cantidad_disponible': cant_disp,
                    'cantidad_minima': cant_min,
                    'lote': d.get('lote', ''),
                    'fecha_vencimiento': d.get('fecha_vencimiento') or None,
                }
            )
            count_inv += 1
        self.stdout.write(f"[OK] {count_inv} registros de inventario sincronizados.")

        # 5. Biometria map (UID -> embedding JSON)
        biometria_map = {}
        for doc in db.collection('usuarios_biometria').stream():
            bd = doc.to_dict()
            emb = bd.get('face_embedding')
            if emb:
                biometria_map[doc.id] = json.dumps(emb)

        # 6. Usuarios
        count_users = 0
        for doc in db.collection('usuarios').stream():
            ud = doc.to_dict()
            fb_uid = doc.id
            email = ud.get('email', '').strip().lower()
            if not email:
                email = f"{fb_uid}@pharmony.local"

            eps_obj = None
            eps_id = ud.get('eps_id')
            if eps_id:
                eps_obj = Eps.objects.filter(id=eps_id).first()

            face_enc = biometria_map.get(fb_uid)

            user = Usuario.objects.filter(firebase_uid=fb_uid).first()
            if not user:
                user = Usuario.objects.filter(email=email).first()

            if user:
                user.first_name = ud.get('nombre', user.first_name)
                user.last_name = ud.get('apellido', user.last_name)
                user.telefono = ud.get('telefono', user.telefono)
                user.cedula = ud.get('cedula', user.cedula)
                user.direccion = ud.get('direccion', user.direccion)
                user.rol = ud.get('rol', user.rol or 'cliente')
                user.firebase_uid = fb_uid
                if eps_obj:
                    user.eps = eps_obj
                if face_enc:
                    user.face_encoding = face_enc
                user.save()
            else:
                user = Usuario.objects.create_user(
                    username=email,
                    email=email,
                    first_name=ud.get('nombre', ''),
                    last_name=ud.get('apellido', ''),
                    telefono=ud.get('telefono', ''),
                    cedula=ud.get('cedula', ''),
                    direccion=ud.get('direccion', ''),
                    rol=ud.get('rol', 'cliente'),
                    firebase_uid=fb_uid,
                    eps=eps_obj,
                    face_encoding=face_enc
                )
            count_users += 1
        self.stdout.write(f"[OK] {count_users} usuarios sincronizados.")

        self.stdout.write(self.style.SUCCESS("Sincronizacion completa desde Firestore exitosa."))