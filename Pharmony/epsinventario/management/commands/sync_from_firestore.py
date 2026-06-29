from django.core.management.base import BaseCommand
from Farmacia.views import get_firestore_db
from Farmacia.models import Medicamento
from epsinventario.models import Eps, Sede, InventarioSede


class Command(BaseCommand):
    help = "Trae EPS, Sedes, Medicamentos e Inventario desde Firestore a la base de datos local (SQLite)."

    def handle(self, *args, **options):
        db = get_firestore_db()
        if db is None:
            self.stderr.write("No se pudo conectar a Firestore. Revisa tu ServiceAccountKey.json.")
            return

        # 1. EPS
        count = 0
        for doc in db.collection('eps').stream():
            d = doc.to_dict()
            Eps.objects.update_or_create(
                id=d.get('id'),
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
            count += 1
        self.stdout.write(f"✓ {count} EPS sincronizadas.")

        # 2. Medicamentos (catálogo)
        count = 0
        for doc in db.collection('medicamentos').stream():
            d = doc.to_dict()
            if not d.get('id'):
                continue
            Medicamento.objects.update_or_create(
                id=d.get('id'),
                defaults={
                    'codigo_cum': d.get('codigo_cum', ''),
                    'nombre_generico': d.get('nombre_generico', ''),
                    'nombre_comercial': d.get('nombre_comercial', ''),
                    'laboratorio': d.get('laboratorio', ''),
                    'concentracion': d.get('concentracion', ''),
                    'forma_farmaceutica': d.get('forma_farmaceutica', ''),
                    'descripcion': d.get('descripcion', ''),
                    'uso_indicado': d.get('uso_indicado', ''),
                    'efectos_secundarios': d.get('efectos_secundarios', ''),
                    'requiere_formula': d.get('requiere_formula', False),
                }
            )
            count += 1
        self.stdout.write(f"✓ {count} medicamentos sincronizados.")

        # 3. Sedes (dependen de que su EPS ya exista localmente)
        count = 0
        for doc in db.collection('sedes').stream():
            d = doc.to_dict()
            eps = Eps.objects.filter(id=d.get('eps_id')).first()
            if not eps:
                continue
            Sede.objects.update_or_create(
                id=d.get('id'),
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
            count += 1
        self.stdout.write(f"✓ {count} sedes sincronizadas.")

        # 4. Inventario (depende de Sede y Medicamento ya existentes localmente)
        count = 0
        for doc in db.collection('inventario_sedes').stream():
            d = doc.to_dict()
            sede = Sede.objects.filter(id=d.get('sede_id')).first()
            medicamento = Medicamento.objects.filter(id=d.get('medicamento_id')).first()
            if not sede or not medicamento:
                continue
            InventarioSede.objects.update_or_create(
                id=d.get('id'),
                defaults={
                    'sede': sede,
                    'medicamento': medicamento,
                    'cantidad_disponible': d.get('cantidad_disponible', 0),
                    'cantidad_minima': d.get('cantidad_minima', 10),
                    'lote': d.get('lote', ''),
                    'fecha_vencimiento': d.get('fecha_vencimiento') or None,
                }
            )
            count += 1
        self.stdout.write(f"✓ {count} registros de inventario sincronizados.")

        self.stdout.write(self.style.SUCCESS("Sincronización completa desde Firestore."))