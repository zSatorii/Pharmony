import random
import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from Farmacia.models import Medicamento
from epsinventario.models import Eps, Sede, InventarioSede
from Farmacia.views import get_firestore_db


class Command(BaseCommand):
    help = "Puebla la base de datos de Pharmony con medicamentos completos, EPS, sedes geolocalizadas e inventario realista, sincronizando con Firestore."

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-firestore',
            action='store_true',
            help='Omitir la sincronización con Firestore.',
        )

    def handle(self, *args, **options):
        sync_firestore = not options.get('no_firestore', False)
        self.stdout.write(self.style.NOTICE("=== Iniciando población de datos para Pharmony ==="))

        with transaction.atomic():
            epss = self._poblar_eps()
            sedes = self._poblar_sedes(epss)
            medicamentos = self._poblar_medicamentos()
            inventarios = self._poblar_inventarios(sedes, medicamentos)

        self.stdout.write(self.style.SUCCESS(
            f"\n[OK en Base de Datos Local]:\n"
            f" - EPS activas: {len(epss)}\n"
            f" - Sedes registradas: {len(sedes)}\n"
            f" - Medicamentos completos: {len(medicamentos)}\n"
            f" - Registros de inventario: {len(inventarios)}"
        ))

        if sync_firestore:
            self.stdout.write(self.style.NOTICE("\nSincronizando con Firebase Firestore..."))
            self._sincronizar_firestore(epss, sedes, medicamentos, inventarios)
        else:
            self.stdout.write(self.style.WARNING("Sincronización con Firestore omitida por parámetro --no-firestore."))

        self.stdout.write(self.style.SUCCESS("\n=== Proceso completado exitosamente ==="))

    def _poblar_eps(self):
        self.stdout.write("1. Configurando EPS...")
        # Lista de EPS maestras (se actualizan o crean manteniendo compatibilidad)
        datos_eps = [
            {
                "id": 1,
                "nombre": "EPS Sanitas",
                "nit": "800251440-6",
                "direccion": "Calle 100 # 11B-27",
                "ciudad": "Bogotá",
                "telefono": "(601) 3759000",
                "email": "atencion@epssanitas.com",
                "estado": True,
            },
            {
                "id": 6,
                "nombre": "Famisanar EPS",
                "nit": "830003564-7",
                "direccion": "Calle 78 # 13A-07",
                "ciudad": "Bogotá",
                "telefono": "(601) 3078069",
                "email": "servicioalcliente@famisanar.com.co",
                "estado": True,
            },
            {
                "id": 7,
                "nombre": "Compensar EPS",
                "nit": "860066942-7",
                "direccion": "Av. Calle 26 # 66-15",
                "ciudad": "Bogotá",
                "telefono": "(601) 4441234",
                "email": "servicioeps@compensar.com",
                "estado": True,
            },
            {
                "id": 8,
                "nombre": "Nueva EPS",
                "nit": "900156264-2",
                "direccion": "Carrera 85K # 46A-65",
                "ciudad": "Bogotá",
                "telefono": "(601) 3077022",
                "email": "contacto@nuevaeps.com.co",
                "estado": True,
            },
            {
                "nombre": "EPS Sura",
                "nit": "800088702-2",
                "direccion": "Carrera 64B # 49A-30",
                "ciudad": "Medellín",
                "telefono": "(604) 4486115",
                "email": "contactenos@epssura.com.co",
                "estado": True,
            },
            {
                "nombre": "Salud Total EPS",
                "nit": "800130907-4",
                "direccion": "Carrera 45 # 104-76",
                "ciudad": "Bogotá",
                "telefono": "(601) 4854555",
                "email": "lineanacional@saludtotal.com.co",
                "estado": True,
            },
            # Mantener custom dev EPS de ser necesario
            {
                "id": 4,
                "nombre": "PabloSanar EPS",
                "nit": "900987111-1",
                "direccion": "Carrera 3 # 2-45",
                "ciudad": "Mosquera",
                "telefono": "(601) 8295000",
                "email": "contacto@pablosanar.com",
                "estado": True,
            },
            {
                "id": 5,
                "nombre": "JohanSanitas EPS",
                "nit": "900987222-2",
                "direccion": "Calle 7 # 4-20",
                "ciudad": "Madrid",
                "telefono": "(601) 8251234",
                "email": "contacto@johansanitas.com",
                "estado": True,
            },
        ]

        eps_map = {}
        for d in datos_eps:
            eps_id = d.get('id')
            if eps_id and Eps.objects.filter(id=eps_id).exists():
                eps_obj = Eps.objects.get(id=eps_id)
                eps_obj.nombre = d["nombre"]
                eps_obj.nit = d["nit"]
                eps_obj.direccion = d["direccion"]
                eps_obj.ciudad = d["ciudad"]
                eps_obj.telefono = d["telefono"]
                eps_obj.email = d["email"]
                eps_obj.estado = d["estado"]
                eps_obj.save()
            else:
                eps_obj, _ = Eps.objects.update_or_create(
                    nit=d["nit"],
                    defaults={
                        "nombre": d["nombre"],
                        "direccion": d["direccion"],
                        "ciudad": d["ciudad"],
                        "telefono": d["telefono"],
                        "email": d["email"],
                        "estado": d["estado"],
                    }
                )
            eps_map[d["nombre"]] = eps_obj

        # Vincular alias comunes para asociar sedes fácilmente
        eps_map["sanitas"] = eps_map.get("EPS Sanitas")
        eps_map["Compensar"] = eps_map.get("Compensar EPS")
        eps_map["Famisanar"] = eps_map.get("Famisanar EPS")
        eps_map["PabloSanar"] = eps_map.get("PabloSanar EPS")
        eps_map["JohanSanitas"] = eps_map.get("JohanSanitas EPS")

        return list(Eps.objects.all())

    def _poblar_sedes(self, epss):
        self.stdout.write("2. Configurando Red Nacional de Sedes...")
        eps_dict = {e.nombre: e for e in epss}

        def get_eps(nombre):
            return eps_dict.get(nombre) or eps_dict.get(f"{nombre} EPS") or epss[0]

        sanitas = get_eps("EPS Sanitas")
        compensar = get_eps("Compensar EPS")
        famisanar = get_eps("Famisanar EPS")
        sura = get_eps("EPS Sura")
        nueva = get_eps("Nueva EPS")
        salud_total = get_eps("Salud Total EPS")
        pablo = get_eps("PabloSanar EPS")
        johan = get_eps("JohanSanitas EPS")

        # Sedes con georreferenciación exacta y horarios realistas
        sedes_data = [
            # Sedes originales preservando IDs 1-7
            {
                "id": 1,
                "eps": sanitas,
                "nombre": "Sede Principal Chapinero",
                "ciudad": "Bogotá",
                "direccion": "Cra. 13 # 53-45",
                "telefono": "(601) 3759001",
                "email": "sede.chapinero@epssanitas.com",
                "latitud": 4.6432,
                "longitud": -74.0634,
                "hora_apertura": datetime.time(6, 0),
                "hora_cierre": datetime.time(20, 0),
                "atiende_fines_semana": True,
            },
            {
                "id": 2,
                "eps": sanitas,
                "nombre": "Sede Norte Unicentro",
                "ciudad": "Bogotá",
                "direccion": "Av. 15 # 124-30",
                "telefono": "(601) 3759002",
                "email": "sede.unicentro@epssanitas.com",
                "latitud": 4.7042,
                "longitud": -74.0321,
                "hora_apertura": datetime.time(7, 0),
                "hora_cierre": datetime.time(19, 0),
                "atiende_fines_semana": True,
            },
            {
                "id": 3,
                "eps": sura,
                "nombre": "Sede El Poblado",
                "ciudad": "Medellín",
                "direccion": "Calle 10 # 43A-21",
                "telefono": "(604) 4486116",
                "email": "sede.poblado@epssura.com.co",
                "latitud": 6.2089,
                "longitud": -75.5684,
                "hora_apertura": datetime.time(6, 30),
                "hora_cierre": datetime.time(19, 30),
                "atiende_fines_semana": True,
            },
            {
                "id": 4,
                "eps": sanitas,
                "nombre": "Sede Chipichape",
                "ciudad": "Cali",
                "direccion": "Av. 6N # 35N-10",
                "telefono": "(602) 4895001",
                "email": "sede.chipichape@epssanitas.com",
                "latitud": 3.4682,
                "longitud": -76.5298,
                "hora_apertura": datetime.time(7, 0),
                "hora_cierre": datetime.time(19, 0),
                "atiende_fines_semana": False,
            },
            {
                "id": 5,
                "eps": famisanar,
                "nombre": "Sede Alto Prado",
                "ciudad": "Barranquilla",
                "direccion": "Calle 76 # 54-11",
                "telefono": "(605) 3852001",
                "email": "sede.altoprado@famisanar.com.co",
                "latitud": 11.0039,
                "longitud": -74.8115,
                "hora_apertura": datetime.time(7, 0),
                "hora_cierre": datetime.time(19, 0),
                "atiende_fines_semana": False,
            },
            {
                "id": 6,
                "eps": compensar,
                "nombre": "Sede Cabecera del Llano",
                "ciudad": "Bucaramanga",
                "direccion": "Cra. 33 # 48-15",
                "telefono": "(607) 6971001",
                "email": "sede.cabecera@compensarsalud.com",
                "latitud": 7.1182,
                "longitud": -73.1098,
                "hora_apertura": datetime.time(6, 30),
                "hora_cierre": datetime.time(18, 30),
                "atiende_fines_semana": True,
            },
            {
                "id": 7,
                "eps": nueva,
                "nombre": "Sede Puente Aranda",
                "ciudad": "Bogotá",
                "direccion": "Cra. 56 # 11-30",
                "telefono": "(601) 3077025",
                "email": "sede.puentearanda@nuevaeps.com.co",
                "latitud": 4.6291,
                "longitud": -74.1165,
                "hora_apertura": datetime.time(6, 0),
                "hora_cierre": datetime.time(19, 0),
                "atiende_fines_semana": False,
            },
            # Sedes adicionales en Bogotá
            {
                "eps": compensar,
                "nombre": "Sede Salitre Calle 26",
                "ciudad": "Bogotá",
                "direccion": "Av. Calle 26 # 66-15",
                "telefono": "(601) 4441235",
                "email": "sede.salitre@compensarsalud.com",
                "latitud": 4.6565,
                "longitud": -74.1086,
                "hora_apertura": datetime.time(6, 0),
                "hora_cierre": datetime.time(20, 0),
                "atiende_fines_semana": True,
            },
            {
                "eps": compensar,
                "nombre": "Sede Suba Imperial",
                "ciudad": "Bogotá",
                "direccion": "Av. Ciudad de Cali # 139-07",
                "telefono": "(601) 4441236",
                "email": "sede.suba@compensarsalud.com",
                "latitud": 4.7431,
                "longitud": -74.0841,
                "hora_apertura": datetime.time(7, 0),
                "hora_cierre": datetime.time(19, 0),
                "atiende_fines_semana": True,
            },
            {
                "eps": famisanar,
                "nombre": "Sede Kennedy Central",
                "ciudad": "Bogotá",
                "direccion": "Transversal 78H # 38C-25 Sur",
                "telefono": "(601) 3078070",
                "email": "sede.kennedy@famisanar.com.co",
                "latitud": 4.6280,
                "longitud": -74.1534,
                "hora_apertura": datetime.time(6, 0),
                "hora_cierre": datetime.time(19, 0),
                "atiende_fines_semana": True,
            },
            {
                "eps": famisanar,
                "nombre": "Sede Restrepo Sur",
                "ciudad": "Bogotá",
                "direccion": "Cra. 19 # 17-40 Sur",
                "telefono": "(601) 3078071",
                "email": "sede.restrepo@famisanar.com.co",
                "latitud": 4.5823,
                "longitud": -74.0991,
                "hora_apertura": datetime.time(7, 0),
                "hora_cierre": datetime.time(18, 0),
                "atiende_fines_semana": False,
            },
            {
                "eps": salud_total,
                "nombre": "Sede Cedritos Usaquén",
                "ciudad": "Bogotá",
                "direccion": "Calle 140 # 11-45",
                "telefono": "(601) 4854556",
                "email": "sede.cedritos@saludtotal.com.co",
                "latitud": 4.7214,
                "longitud": -74.0345,
                "hora_apertura": datetime.time(7, 0),
                "hora_cierre": datetime.time(19, 0),
                "atiende_fines_semana": True,
            },
            # Cundinamarca (Municipios Sabana)
            {
                "eps": sanitas,
                "nombre": "Sede Chía Centro",
                "ciudad": "Chía",
                "direccion": "Cra. 9 # 11-40",
                "telefono": "(601) 8613400",
                "email": "sede.chia@epssanitas.com",
                "latitud": 4.8584,
                "longitud": -74.0567,
                "hora_apertura": datetime.time(7, 0),
                "hora_cierre": datetime.time(18, 0),
                "atiende_fines_semana": True,
            },
            {
                "eps": compensar,
                "nombre": "Sede Soacha San Mateo",
                "ciudad": "Soacha",
                "direccion": "Autopista Sur # 30-15",
                "telefono": "(601) 4441237",
                "email": "sede.soacha@compensarsalud.com",
                "latitud": 4.5881,
                "longitud": -74.2185,
                "hora_apertura": datetime.time(6, 0),
                "hora_cierre": datetime.time(19, 0),
                "atiende_fines_semana": True,
            },
            {
                "eps": pablo,
                "nombre": "Sede Mosquera Central",
                "ciudad": "Mosquera",
                "direccion": "Cra. 3 # 2-45",
                "telefono": "(601) 8295001",
                "email": "sede.mosquera@pablosanar.com",
                "latitud": 4.7061,
                "longitud": -74.2312,
                "hora_apertura": datetime.time(7, 0),
                "hora_cierre": datetime.time(18, 0),
                "atiende_fines_semana": False,
            },
            {
                "eps": johan,
                "nombre": "Sede Madrid Principal",
                "ciudad": "Madrid",
                "direccion": "Calle 7 # 4-20",
                "telefono": "(601) 8251235",
                "email": "sede.madrid@johansanitas.com",
                "latitud": 4.7335,
                "longitud": -74.2678,
                "hora_apertura": datetime.time(7, 0),
                "hora_cierre": datetime.time(18, 0),
                "atiende_fines_semana": False,
            },
            {
                "eps": famisanar,
                "nombre": "Sede Funza Parque",
                "ciudad": "Funza",
                "direccion": "Cra. 9 # 13-18",
                "telefono": "(601) 8261122",
                "email": "sede.funza@famisanar.com.co",
                "latitud": 4.7182,
                "longitud": -74.2105,
                "hora_apertura": datetime.time(7, 0),
                "hora_cierre": datetime.time(18, 0),
                "atiende_fines_semana": False,
            },
            # Medellín y Valle de Aburrá
            {
                "eps": sura,
                "nombre": "Sede Laureles Nutibara",
                "ciudad": "Medellín",
                "direccion": "Transversal 39B # 74-25",
                "telefono": "(604) 4486117",
                "email": "sede.laureles@epssura.com.co",
                "latitud": 6.2428,
                "longitud": -75.5947,
                "hora_apertura": datetime.time(6, 30),
                "hora_cierre": datetime.time(19, 0),
                "atiende_fines_semana": True,
            },
            {
                "eps": sanitas,
                "nombre": "Sede Medellín Centro Oriental",
                "ciudad": "Medellín",
                "direccion": "Cra. 46 # 54-14",
                "telefono": "(604) 5143322",
                "email": "sede.centro@epssanitas.com",
                "latitud": 6.2512,
                "longitud": -75.5683,
                "hora_apertura": datetime.time(7, 0),
                "hora_cierre": datetime.time(18, 30),
                "atiende_fines_semana": False,
            },
            {
                "eps": sura,
                "nombre": "Sede Envigado Las Vegas",
                "ciudad": "Envigado",
                "direccion": "Cra. 48 # 25 Sur-18",
                "telefono": "(604) 4486118",
                "email": "sede.envigado@epssura.com.co",
                "latitud": 6.1759,
                "longitud": -75.5917,
                "hora_apertura": datetime.time(7, 0),
                "hora_cierre": datetime.time(19, 0),
                "atiende_fines_semana": True,
            },
            # Cali y Valle del Cauca
            {
                "eps": sura,
                "nombre": "Sede Tequendama Salud",
                "ciudad": "Cali",
                "direccion": "Cra. 42 # 5B-34",
                "telefono": "(602) 5543200",
                "email": "sede.tequendama@epssura.com.co",
                "latitud": 3.4241,
                "longitud": -76.5413,
                "hora_apertura": datetime.time(6, 30),
                "hora_cierre": datetime.time(19, 30),
                "atiende_fines_semana": True,
            },
            {
                "eps": compensar,
                "nombre": "Sede Valle del Lili Sur",
                "ciudad": "Cali",
                "direccion": "Cra. 98 # 18-49",
                "telefono": "(602) 3319000",
                "email": "sede.valledellili@compensarsalud.com",
                "latitud": 3.3751,
                "longitud": -76.5268,
                "hora_apertura": datetime.time(7, 0),
                "hora_cierre": datetime.time(19, 0),
                "atiende_fines_semana": True,
            },
            {
                "eps": famisanar,
                "nombre": "Sede Palmira Centro",
                "ciudad": "Palmira",
                "direccion": "Calle 31 # 28-15",
                "telefono": "(602) 2854000",
                "email": "sede.palmira@famisanar.com.co",
                "latitud": 3.5394,
                "longitud": -76.3036,
                "hora_apertura": datetime.time(7, 0),
                "hora_cierre": datetime.time(18, 0),
                "atiende_fines_semana": False,
            },
            # Costa Caribe
            {
                "eps": nueva,
                "nombre": "Sede Murillo Centro",
                "ciudad": "Barranquilla",
                "direccion": "Calle 45 (Murillo) # 23-40",
                "telefono": "(605) 3718000",
                "email": "sede.murillo@nuevaeps.com.co",
                "latitud": 10.9632,
                "longitud": -74.7961,
                "hora_apertura": datetime.time(6, 30),
                "hora_cierre": datetime.time(18, 30),
                "atiende_fines_semana": True,
            },
            {
                "eps": sura,
                "nombre": "Sede Bocagrande Bahía",
                "ciudad": "Cartagena",
                "direccion": "Av. San Martín # 6-35",
                "telefono": "(605) 6652000",
                "email": "sede.bocagrande@epssura.com.co",
                "latitud": 10.4045,
                "longitud": -75.5562,
                "hora_apertura": datetime.time(7, 0),
                "hora_cierre": datetime.time(19, 0),
                "atiende_fines_semana": True,
            },
            {
                "eps": salud_total,
                "nombre": "Sede Rodadero",
                "ciudad": "Santa Marta",
                "direccion": "Cra. 4 # 11-20",
                "telefono": "(605) 4221100",
                "email": "sede.rodadero@saludtotal.com.co",
                "latitud": 11.2415,
                "longitud": -74.2052,
                "hora_apertura": datetime.time(7, 0),
                "hora_cierre": datetime.time(18, 0),
                "atiende_fines_semana": False,
            },
            # Eje Cafetero
            {
                "eps": sanitas,
                "nombre": "Sede Circunvalar Pinares",
                "ciudad": "Pereira",
                "direccion": "Av. Circunvalar # 12-40",
                "telefono": "(606) 3241000",
                "email": "sede.pereira@epssanitas.com",
                "latitud": 4.8112,
                "longitud": -75.6883,
                "hora_apertura": datetime.time(6, 30),
                "hora_cierre": datetime.time(19, 0),
                "atiende_fines_semana": True,
            },
            {
                "eps": sura,
                "nombre": "Sede El Cable",
                "ciudad": "Manizales",
                "direccion": "Cra. 23 # 65-10",
                "telefono": "(606) 8864000",
                "email": "sede.manizales@epssura.com.co",
                "latitud": 5.0562,
                "longitud": -75.4891,
                "hora_apertura": datetime.time(7, 0),
                "hora_cierre": datetime.time(18, 30),
                "atiende_fines_semana": False,
            },
            {
                "eps": nueva,
                "nombre": "Sede Armenia Castellana",
                "ciudad": "Armenia",
                "direccion": "Av. Bolívar # 14N-55",
                "telefono": "(606) 7453000",
                "email": "sede.armenia@nuevaeps.com.co",
                "latitud": 4.5452,
                "longitud": -75.6698,
                "hora_apertura": datetime.time(7, 0),
                "hora_cierre": datetime.time(18, 0),
                "atiende_fines_semana": False,
            },
            # Santander y Oriente
            {
                "eps": sanitas,
                "nombre": "Sede Cañaveral",
                "ciudad": "Floridablanca",
                "direccion": "Calle 30 # 25-18",
                "telefono": "(607) 6384000",
                "email": "sede.canaveral@epssanitas.com",
                "latitud": 7.0673,
                "longitud": -73.1065,
                "hora_apertura": datetime.time(7, 0),
                "hora_cierre": datetime.time(19, 0),
                "atiende_fines_semana": True,
            },
            {
                "eps": nueva,
                "nombre": "Sede Cúcuta Los Caobos",
                "ciudad": "Cúcuta",
                "direccion": "Av. 1E # 14-30",
                "telefono": "(607) 5712000",
                "email": "sede.cucuta@nuevaeps.com.co",
                "latitud": 7.8939,
                "longitud": -72.5078,
                "hora_apertura": datetime.time(6, 30),
                "hora_cierre": datetime.time(18, 30),
                "atiende_fines_semana": True,
            },
            {
                "eps": salud_total,
                "nombre": "Sede Villavicencio El Barzal",
                "ciudad": "Villavicencio",
                "direccion": "Cra. 40 # 33-15",
                "telefono": "(608) 6625000",
                "email": "sede.villavicencio@saludtotal.com.co",
                "latitud": 4.1420,
                "longitud": -73.6266,
                "hora_apertura": datetime.time(7, 0),
                "hora_cierre": datetime.time(18, 0),
                "atiende_fines_semana": False,
            },
            {
                "eps": famisanar,
                "nombre": "Sede Ibagué La Pola",
                "ciudad": "Ibagué",
                "direccion": "Cra. 3 # 7-42",
                "telefono": "(608) 2614000",
                "email": "sede.ibague@famisanar.com.co",
                "latitud": 4.4421,
                "longitud": -75.2412,
                "hora_apertura": datetime.time(7, 0),
                "hora_cierre": datetime.time(18, 0),
                "atiende_fines_semana": False,
            },
            {
                "eps": sura,
                "nombre": "Sede Pasto Maridíaz",
                "ciudad": "Pasto",
                "direccion": "Calle 18 # 31-15",
                "telefono": "(602) 7234000",
                "email": "sede.pasto@epssura.com.co",
                "latitud": 1.2162,
                "longitud": -77.2834,
                "hora_apertura": datetime.time(7, 0),
                "hora_cierre": datetime.time(18, 0),
                "atiende_fines_semana": False,
            },
            {
                "eps": salud_total,
                "nombre": "Sede Neiva Quirinal",
                "ciudad": "Neiva",
                "direccion": "Cra. 6 # 16-20",
                "telefono": "(608) 8713000",
                "email": "sede.neiva@saludtotal.com.co",
                "latitud": 2.9312,
                "longitud": -75.2891,
                "hora_apertura": datetime.time(7, 0),
                "hora_cierre": datetime.time(18, 0),
                "atiende_fines_semana": False,
            }
        ]

        sedes_creadas = []
        for s in sedes_data:
            sede_id = s.get('id')
            defaults = {
                "eps": s["eps"],
                "nombre": s["nombre"],
                "ciudad": s["ciudad"],
                "direccion": s["direccion"],
                "telefono": s["telefono"],
                "email": s["email"],
                "latitud": s["latitud"],
                "longitud": s["longitud"],
                "hora_apertura": s["hora_apertura"],
                "hora_cierre": s["hora_cierre"],
                "atiende_fines_semana": s["atiende_fines_semana"],
                "estado": True,
            }
            if sede_id and Sede.objects.filter(id=sede_id).exists():
                sede_obj = Sede.objects.get(id=sede_id)
                for k, v in defaults.items():
                    setattr(sede_obj, k, v)
                sede_obj.save()
            else:
                sede_obj, _ = Sede.objects.update_or_create(
                    eps=s["eps"],
                    nombre=s["nombre"],
                    ciudad=s["ciudad"],
                    defaults=defaults
                )
            sedes_creadas.append(sede_obj)

        return list(Sede.objects.filter(estado=True))

    def _poblar_medicamentos(self):
        self.stdout.write("3. Registrando Catálogo Completo de Medicamentos...")

        # Lista completa de 55 medicamentos de alta fidelidad clínica
        medicamentos_data = [
            # Preservar y enriquecer los medicamentos existentes (IDs 11 al 18)
            {
                "id": 11,
                "codigo_cum": "19934521-01",
                "nombre_generico": "Acetaminofén",
                "nombre_comercial": "Dolex Forte",
                "laboratorio": "GlaxoSmithKline Colombia S.A.",
                "concentracion": "500 mg",
                "forma_farmaceutica": "Tableta recubierta",
                "descripcion": "Analgésico y antipirético de primera línea que actúa inhibiendo la síntesis de prostaglandinas en el sistema nervioso central. Alivia dolores leves a moderados sin causar irritación en la mucosa gástrica.",
                "uso_indicado": "Cefalea tensional, dolores musculares, odontalgia, dolor articular leve, malestar general asociado a resfriados y control de fiebre.",
                "efectos_secundarios": "Raramente reacciones de hipersensibilidad o exantema cutáneo. Dosis acumuladas elevadas pueden generar toxicidad hepática.",
                "requiere_formula": False,
            },
            {
                "id": 12,
                "codigo_cum": "19912040-01",
                "nombre_generico": "Ácido Acetilsalicílico",
                "nombre_comercial": "Aspirina 100 Protect",
                "laboratorio": "Bayer S.A.",
                "concentracion": "100 mg",
                "forma_farmaceutica": "Tableta con cubierta entérica",
                "descripcion": "Antiagregante plaquetario que inhibe irreversiblemente la enzima ciclooxigenasa-1 (COX-1), reduciendo la síntesis de tromboxano A2. Diseñado con recubrimiento entérico que resiste el ácido estomacal.",
                "uso_indicado": "Prevención secundaria de infarto agudo de miocardio, accidente cerebrovascular isquémico no hemorrágico y trombosis arterial postoperatoria.",
                "efectos_secundarios": "Dispepsia leve, pirosis, microhemorragias digestivas en tratamientos crónicos, hipotrombocitemia.",
                "requiere_formula": False,
            },
            {
                "id": 13,
                "codigo_cum": "20015432-01",
                "nombre_generico": "Zopiclona (Somnolamida)",
                "nombre_comercial": "Solfaxin",
                "laboratorio": "BioPharma Latam S.A.",
                "concentracion": "7.5 mg",
                "forma_farmaceutica": "Tableta recubierta",
                "descripcion": "Agente hipnótico no benzodiacepínico del grupo ciclopirrolona. Actúa como modulador alostérico positivo de los complejos receptores GABA-A induciendo rápidamente el sueño de arquitectura fisiológica.",
                "uso_indicado": "Tratamiento a corto plazo del insomnio transitorio, situacional o crónico en adultos.",
                "efectos_secundarios": "Sabor amargo o metálico residual matutino, somnolencia diurna residual, sequedad de boca, cefalea y mareos leves.",
                "requiere_formula": True,
            },
            {
                "id": 14,
                "codigo_cum": "19945112-02",
                "nombre_generico": "Ibuprofeno",
                "nombre_comercial": "Advil Max",
                "laboratorio": "Pfizer Colombia S.A.S.",
                "concentracion": "400 mg",
                "forma_farmaceutica": "Cápsula blanda de gelatina",
                "descripcion": "Antiinflamatorio no esteroideo (AINE) derivado del ácido propiónico con rápida absorción y efecto analgésico, antiinflamatorio y antipirético gracias al bloqueo de las ciclooxigenasas COX-1 y COX-2.",
                "uso_indicado": "Dolor inflamatorio moderado, cefalea migrañosa, dismenorrea primaria, traumatismos musculares y dolor posquirúrgico odontológico.",
                "efectos_secundarios": "Epigastralgia, náuseas, pirosis, mareo transitorio. Usar con precaución en hipertensos y personas con antecedentes ulcerosos.",
                "requiere_formula": False,
            },
            {
                "id": 15,
                "codigo_cum": "19985612-01",
                "nombre_generico": "Levetiracetam",
                "nombre_comercial": "Keppra",
                "laboratorio": "UCB Pharma S.A.",
                "concentracion": "500 mg",
                "forma_farmaceutica": "Tableta recubierta",
                "descripcion": "Antiepiléptico de amplio espectro. Se une selectivamente a la proteína vesicular sináptica SV2A, inhibiendo la liberación presináptica de vesículas de glutamato e impidiendo la propagación de descargas epileptiformes.",
                "uso_indicado": "Monoterapia y tratamiento coadyuvante en crisis de inicio parcial, crisis mioclónicas juveniles y convulsiones tónico-clónicas primarias generalizadas.",
                "efectos_secundarios": "Somnolencia, astenia, mareo, cefalea, cambios de temperamento, labilidad emocional o irritabilidad.",
                "requiere_formula": True,
            },
            {
                "id": 16,
                "codigo_cum": "20023411-01",
                "nombre_generico": "Lacosamida",
                "nombre_comercial": "Vimpat",
                "laboratorio": "UCB Pharma S.A.",
                "concentracion": "100 mg",
                "forma_farmaceutica": "Tableta recubierta",
                "descripcion": "Antiepiléptico de tercera generación con un mecanismo de acción innovador que potencia selectivamente la inactivación lenta de los canales de sodio dependientes de voltaje, previniendo la hiperexcitabilidad patológica.",
                "uso_indicado": "Tratamiento coadyuvante y monoterapia de crisis convulsivas de inicio parcial con o sin generalización en pacientes con epilepsia refractaria.",
                "efectos_secundarios": "Mareos, ataxia, diplopía, náuseas, visión borrosa, fatiga y temblor leve.",
                "requiere_formula": True,
            },
            {
                "id": 17,
                "codigo_cum": "19954321-01",
                "nombre_generico": "Sertralina Clorhidrato",
                "nombre_comercial": "Zoloft",
                "laboratorio": "Pfizer Colombia S.A.S.",
                "concentracion": "50 mg",
                "forma_farmaceutica": "Tableta recubierta",
                "descripcion": "Inhibidor selectivo de la recaptación de serotonina (ISRS). Aumenta los niveles extracelulares de serotonina en las hendiduras sinápticas neuronales mejorando los circuitos moduladores del afecto y el estado anímico.",
                "uso_indicado": "Trastorno depresivo mayor, trastorno de pánico, trastorno obsesivo compulsivo (TOC), fobia social y trastorno por estrés postraumático.",
                "efectos_secundarios": "Náuseas transitorias iniciales, diarrea o heces blandas, temblor fino, insomnio, cefalea y disfunción sexual leve.",
                "requiere_formula": True,
            },
            {
                "id": 18,
                "codigo_cum": "19934521-02",
                "nombre_generico": "Paracetamol",
                "nombre_comercial": "Paracetamol MK",
                "laboratorio": "Tecnoquímicas S.A.",
                "concentracion": "1 g",
                "forma_farmaceutica": "Tableta recubierta",
                "descripcion": "Analgésico y antipirético formulado a concentración máxima para dolores moderados e intensos y fiebre severa persistente.",
                "uso_indicado": "Dolor agudo postquirúrgico, lumbalgia, artrosis de rodilla o cadera y cuadros febriles refractarios.",
                "efectos_secundarios": "Bien tolerado. Náuseas leves. No superar 4 gramos al día para prevenir toxicidad hepática.",
                "requiere_formula": False,
            },
            # Cardiovasculares y Antihipertensivos
            {
                "codigo_cum": "19943210-01",
                "nombre_generico": "Losartán Potásico",
                "nombre_comercial": "Cozaar",
                "laboratorio": "Merck Sharp & Dohme (MSD)",
                "concentracion": "50 mg",
                "forma_farmaceutica": "Tableta recubierta",
                "descripcion": "Antagonista de los receptores de angiotensina II (ARA-II) selectivo tipo AT1. Bloquea la vasoconstricción y la síntesis de aldosterona, promoviendo el control hemodinámico y la nefroprotección.",
                "uso_indicado": "Hipertensión arterial esencial, reducción del riesgo de ictus en hipertensos con hipertrofia ventricular izquierda y nefropatía en diabetes tipo 2.",
                "efectos_secundarios": "Hipotensión ortostática, mareo, fatiga, hiperpotasemia ligera y congestión nasal.",
                "requiere_formula": True,
            },
            {
                "codigo_cum": "19904321-01",
                "nombre_generico": "Enalapril Maleato",
                "nombre_comercial": "Renitec",
                "laboratorio": "Genfar S.A.",
                "concentracion": "20 mg",
                "forma_farmaceutica": "Tableta ranurada",
                "descripcion": "Inhibidor de la enzima convertidora de angiotensina (IECA). Reduce la resistencia periférica total y la presión arterial de forma sostenida sin aumentar la frecuencia cardíaca reflejo.",
                "uso_indicado": "Hipertensión arterial en todas sus etapas, insuficiencia cardíaca congestiva sintomática y disfunción ventricular izquierda asintomática.",
                "efectos_secundarios": "Tos seca irritativa no productiva, mareos posturales, cefalea, hipotensión.",
                "requiere_formula": True,
            },
            {
                "codigo_cum": "19921098-01",
                "nombre_generico": "Amlodipino Besilato",
                "nombre_comercial": "Norvasc",
                "laboratorio": "Pfizer Colombia S.A.S.",
                "concentracion": "5 mg",
                "forma_farmaceutica": "Tableta",
                "descripcion": "Calcioantagonista dihidropiridínico de acción prolongada. Relaja el músculo liso arterial reduciendo la poscarga cardíaca e incrementando el flujo miocárdico coronario.",
                "uso_indicado": "Hipertensión arterial esencial, angina de pecho vasoespástica (Prinzmetal) y cardiopatía isquémica estable.",
                "efectos_secundarios": "Edema maleolar bilateral periférico, rubor facial, mareos, palpitaciones transitorias.",
                "requiere_formula": True,
            },
            {
                "codigo_cum": "19910543-01",
                "nombre_generico": "Metoprolol Tartrato",
                "nombre_comercial": "Betaloc",
                "laboratorio": "AstraZeneca Colombia S.A.S.",
                "concentracion": "50 mg",
                "forma_farmaceutica": "Tableta ranurada",
                "descripcion": "Betabloqueador selectivo de receptores adrenérgicos beta-1 miocárdicos. Disminuye la frecuencia cardíaca, la contractilidad miocárdica y el consumo cardíaco de oxígeno.",
                "uso_indicado": "Hipertensión arterial, taquiarritmias supraventriculares, angina de pecho y profilaxis posinfarto.",
                "efectos_secundarios": "Bradicardia sinusal, frialdad en extremidades, astenia, mareos, insomnio.",
                "requiere_formula": True,
            },
            {
                "codigo_cum": "19901234-01",
                "nombre_generico": "Hidroclorotiazida",
                "nombre_comercial": "Hidroclorotiazida MK",
                "laboratorio": "Tecnoquímicas S.A.",
                "concentracion": "25 mg",
                "forma_farmaceutica": "Tableta",
                "descripcion": "Diurético tiazídico que inhibe la reabsorción de cloruro de sodio en la porción proximal del túbulo contorneado distal, incrementando la eliminación renal de agua y sodio.",
                "uso_indicado": "Hipertensión arterial como monoterapia o terapia combinada, y retención de líquidos por insuficiencia cardíaca.",
                "efectos_secundarios": "Hipopotasemia, hiponatremia, elevación leve de ácido úrico y mareos por ortostatismo.",
                "requiere_formula": True,
            },
            {
                "codigo_cum": "19965432-01",
                "nombre_generico": "Atorvastatina Cálcica",
                "nombre_comercial": "Lipitor",
                "laboratorio": "Pfizer Colombia S.A.S.",
                "concentracion": "20 mg",
                "forma_farmaceutica": "Tableta recubierta",
                "descripcion": "Inhibidor de la HMG-CoA reductasa. Promueve la disminución potente del colesterol LDL, apolipoproteína B y triglicéridos con aumento del colesterol HDL y estabilización de la placa ateromatosa.",
                "uso_indicado": "Hipercolesterolemia primaria, dislipidemia aterogénica y prevención secundaria de síndromes coronarios agudos.",
                "efectos_secundarios": "Mialgias leves, espasmos musculares, elevación de transaminasas, molestias gastrointestinales.",
                "requiere_formula": True,
            },
            {
                "codigo_cum": "20004321-01",
                "nombre_generico": "Rosuvastatina Cálcica",
                "nombre_comercial": "Crestor",
                "laboratorio": "AstraZeneca Colombia S.A.S.",
                "concentracion": "10 mg",
                "forma_farmaceutica": "Tableta recubierta",
                "descripcion": "Estatina hidrofílica de última generación con extraordinaria potencia reductora del colesterol de baja densidad (c-LDL) y perfil favorable de tolerancia muscular.",
                "uso_indicado": "Hipercolesterolemia severa familiar o mixta, aterosclerosis subclínica acelerada y prevención cardiovascular en pacientes de muy alto riesgo.",
                "efectos_secundarios": "Cefalea, mialgia ocasional, astenia, estreñimiento, dolor abdominal.",
                "requiere_formula": True,
            },
            # Antibióticos y Antiparasitarios
            {
                "codigo_cum": "19924567-01",
                "nombre_generico": "Amoxicilina",
                "nombre_comercial": "Amoxil",
                "laboratorio": "Genfar S.A.",
                "concentracion": "500 mg",
                "forma_farmaceutica": "Cápsula",
                "descripcion": "Antibiótico bactericida de amplio espectro perteneciente al grupo de las aminopenicilinas. Bloquea la síntesis del peptidoglicano de la pared celular bacteriana.",
                "uso_indicado": "Infecciones respiratorias agudas (faringoamigdalitis, bronquitis, otitis media), abscesos odontológicos e infecciones urológicas no complicadas.",
                "efectos_secundarios": "Diarrea bacteriana asociada a disbiosis, náuseas, vómito y erupción maculopapular cutánea.",
                "requiere_formula": True,
            },
            {
                "codigo_cum": "19943298-01",
                "nombre_generico": "Amoxicilina + Ácido Clavulánico",
                "nombre_comercial": "Clavulin 875/125",
                "laboratorio": "GlaxoSmithKline Colombia S.A.",
                "concentracion": "875 mg / 125 mg",
                "forma_farmaceutica": "Tableta recubierta",
                "descripcion": "Combinación antibiótica potenciada donde el ácido clavulánico inhibe irreversiblemente las enzimas betalactamasas microbianas, restituyendo la acción bactericida de la amoxicilina frente a cepas resistentes.",
                "uso_indicado": "Sinusitis bacteriana aguda, otitis media recurrente, neumonía adquirida en la comunidad, exacerbación de EPOC e infecciones de piel y tejidos blandos.",
                "efectos_secundarios": "Diarrea osmótica, malestar gástrico, sobrecrecimiento de Candida y náuseas.",
                "requiere_formula": True,
            },
            {
                "codigo_cum": "19954312-01",
                "nombre_generico": "Azitromicina",
                "nombre_comercial": "Zitromax",
                "laboratorio": "Pfizer Colombia S.A.S.",
                "concentracion": "500 mg",
                "forma_farmaceutica": "Tableta recubierta",
                "descripcion": "Antibiótico macrólido de la familia de los azálidos. Inhibe la biosíntesis de proteínas bacterianas al fijarse a la subunidad ribosomal 50S bacteriana, con alta penetración tisular y prolongada semivida intracelular.",
                "uso_indicado": "Neumonía atípica, bronquitis aguda, faringoamigdalitis estreptocócica en pacientes alérgicos a betalactámicos, uretritis y cervicitis por Chlamydia.",
                "efectos_secundarios": "Dolor y cólicos abdominales, diarrea, náuseas, flatulencia y cefalea.",
                "requiere_formula": True,
            },
            {
                "codigo_cum": "19918765-01",
                "nombre_generico": "Ciprofloxacino Clorhidrato",
                "nombre_comercial": "Cipro",
                "laboratorio": "Bayer S.A.",
                "concentracion": "500 mg",
                "forma_farmaceutica": "Tableta recubierta",
                "descripcion": "Fluoroquinolona bactericida de amplio espectro. Bloquea selectivamente la topoisomerasa II (ADN girasa) y la topoisomerasa IV bacterianas, deteniendo la replicación del ADN bacteriano.",
                "uso_indicado": "Infecciones urinarias complicadas, pielonefritis, prostatitis bacteriana aguda y crónica, y gastroenteritis bacteriana infecciosa severa.",
                "efectos_secundarios": "Náuseas, diarrea, mareo, cefalea, fotosensibilidad cutánea y tendinitis aquilea ocasional.",
                "requiere_formula": True,
            },
            {
                "codigo_cum": "19907654-01",
                "nombre_generico": "Cefalexina Monohidrato",
                "nombre_comercial": "Keflex",
                "laboratorio": "Genfar S.A.",
                "concentracion": "500 mg",
                "forma_farmaceutica": "Cápsula",
                "descripcion": "Cefalosporina oral de primera generación con actividad bactericida frente a Staphylococcus aureus y Streptococcus del grupo A. Inhibe la última etapa de síntesis de la pared bacteriana.",
                "uso_indicado": "Infecciones de piel y tejidos blandos (celulitis, foliculitis, forúnculos, impétigo), faringitis estreptocócica y cistitis aguda.",
                "efectos_secundarios": "Diarrea leve, dolor estomacal, náuseas, prurito genital y urticaria alérgica.",
                "requiere_formula": True,
            },
            {
                "codigo_cum": "19902345-01",
                "nombre_generico": "Metronidazol",
                "nombre_comercial": "Flagyl",
                "laboratorio": "Sanofi-Aventis de Colombia S.A.",
                "concentracion": "500 mg",
                "forma_farmaceutica": "Tableta recubierta",
                "descripcion": "Antiprotozoario y antibacteriano del grupo de los nitroimidazoles. Su metabolito reducido desestabiliza y fragmenta la estructura helicoidal del ADN de bacterias anaerobias y protozoarios.",
                "uso_indicado": "Amebiasis intestinal y hepática, giardiasis, tricomoniasis urogenital, vaginosis bacteriana e infecciones intraabdominales por anaerobios.",
                "efectos_secundarios": "Sabor metálico intenso en la boca, cefalea, náuseas y efecto antabús severo si se ingiere con bebidas alcohólicas.",
                "requiere_formula": True,
            },
            {
                "codigo_cum": "19945566-01",
                "nombre_generico": "Albendazol",
                "nombre_comercial": "Zentel",
                "laboratorio": "GlaxoSmithKline Colombia S.A.",
                "concentracion": "400 mg",
                "forma_farmaceutica": "Tableta masticable",
                "descripcion": "Antiparasitario benzimidazólico de amplio espectro. Inhibe la polimerización de la tubulina en los parásitos helmintos, bloqueando la captación de glucosa y agotando sus reservas energéticas.",
                "uso_indicado": "Parasitosis intestinales simples o mixtas producidas por Ascaris lumbricoides, Trichuris trichiura, Enterobius vermicularis, Uncinarias y Giardia lamblia.",
                "efectos_secundarios": "Molestias gastrointestinales transitorias, dolor epigástrico, náuseas, cefalea pasajera.",
                "requiere_formula": False,
            },
            {
                "codigo_cum": "19934455-01",
                "nombre_generico": "Trimetoprima + Sulfametoxazol",
                "nombre_comercial": "Bactrim F",
                "laboratorio": "Roche Farma de Colombia S.A.",
                "concentracion": "160 mg / 800 mg",
                "forma_farmaceutica": "Tableta",
                "descripcion": "Asociación sinérgica de una sulfonamida y una diaminopirimidina que inhibe secuencialmente dos enzimas vitales para la síntesis bacteriana del ácido tetrahidrofólico.",
                "uso_indicado": "Infecciones de vías urinarias no complicadas, exacerbaciones agudas de bronquitis crónica, shigelosis y profilaxis de neumonía por Pneumocystis jirovecii.",
                "efectos_secundarios": "Erupción cutánea eritematosa, prurito, náuseas, vómito y anorexia.",
                "requiere_formula": True,
            },
            # Gastrointestinales y Digestivos
            {
                "codigo_cum": "19932145-01",
                "nombre_generico": "Omeprazol",
                "nombre_comercial": "Losec",
                "laboratorio": "Tecnoquímicas S.A. (MK)",
                "concentracion": "20 mg",
                "forma_farmaceutica": "Cápsula con microgránulos entéricos",
                "descripcion": "Inhibidor de la bomba de protones (IBP) gástrica H+/K+-ATPasa. Suprime intensamente la secreción ácida tanto basal como estimulada protegiendo la mucosa gastroesofágica.",
                "uso_indicado": "Reflujo gastroesofágico sintomático, esofagitis por reflujo, úlcera péptica duodenal y gástrica, y protección mucosa durante el uso de AINEs.",
                "efectos_secundarios": "Cefalea, diarrea o estreñimiento, dolor abdominal difuso, flatulencia y náuseas leves.",
                "requiere_formula": False,
            },
            {
                "codigo_cum": "20018765-01",
                "nombre_generico": "Esomeprazol Magnésico",
                "nombre_comercial": "Nexium",
                "laboratorio": "AstraZeneca Colombia S.A.S.",
                "concentracion": "40 mg",
                "forma_farmaceutica": "Tableta con recubrimiento entérico",
                "descripcion": "Isómero S de omeprazol con mayor biodisponibilidad sistémica y menor variabilidad interindividual. Brinda una inhibición ácida gástrica superior durante las 24 horas del día.",
                "uso_indicado": "Esofagitis erosiva moderada a severa, cicatrización y prevención de úlceras asociadas a AINEs y síndrome de hipersecreción ácida.",
                "efectos_secundarios": "Dolor de cabeza, diarrea transitoria, sequedad bucal, meteorismo y mareo leve.",
                "requiere_formula": True,
            },
            {
                "codigo_cum": "19941098-01",
                "nombre_generico": "Trimebutina Maleato",
                "nombre_comercial": "Debridat",
                "laboratorio": "Pfizer Colombia S.A.S.",
                "concentracion": "200 mg",
                "forma_farmaceutica": "Tableta recubierta",
                "descripcion": "Antiespasmódico y neuromodulador de la motilidad digestiva. Actúa como agonista sobre receptores encefalinérgicos entéricos regulando el peristaltismo intestinal fisiológico.",
                "uso_indicado": "Síndrome de intestino irritable (colon irritable), dispepsia funcional, cólicos digestivos espasmódicos, meteorismo y flatulencia dolorosa.",
                "efectos_secundarios": "Somnolencia leve, mareos, boca seca, cefalea y náuseas transitorias.",
                "requiere_formula": False,
            },
            {
                "codigo_cum": "19905432-01",
                "nombre_generico": "Metoclopramida Clorhidrato",
                "nombre_comercial": "Plasil",
                "laboratorio": "Sanofi-Aventis de Colombia S.A.",
                "concentracion": "10 mg",
                "forma_farmaceutica": "Tableta",
                "descripcion": "Procinético y antiemético que antagoniza receptores dopaminérgicos D2 en la zona quimiorreceptora gatillo y aumenta la respuesta colinérgica del tracto digestivo superior.",
                "uso_indicado": "Prevención y tratamiento de náuseas y vómitos, alivio de la gastroparesia diabética y reflujo esofágico.",
                "efectos_secundarios": "Somnolencia, fatiga, inquietud psicomotora y rara vez síntomas extrapiramidales reversibles.",
                "requiere_formula": True,
            },
            {
                "codigo_cum": "19956677-01",
                "nombre_generico": "Hidróxido de Aluminio y Magnesio + Simeticona",
                "nombre_comercial": "Mylanta Plus",
                "laboratorio": "Johnson & Johnson de Colombia S.A.",
                "concentracion": "400 mg / 400 mg / 30 mg por 10 ml",
                "forma_farmaceutica": "Suspensión oral 360 ml",
                "descripcion": "Antiácido balanceado y antiflatulento que neutraliza el ácido estomacal en minutos sin producir rebote ácido ni alteraciones notorias en el hábito intestinal.",
                "uso_indicado": "Alivio rápido de la acidez estomacal, ardor epigástrico, indigestión ácida y sensación de pesadez o distensión por gases.",
                "efectos_secundarios": "Excelente tolerabilidad. Heces blandas o constipación leve según predisposición individual.",
                "requiere_formula": False,
            },
            # Antidiabéticos y Endocrinología
            {
                "codigo_cum": "19928765-01",
                "nombre_generico": "Metformina Clorhidrato",
                "nombre_comercial": "Glucophage",
                "laboratorio": "Merck S.A.",
                "concentracion": "850 mg",
                "forma_farmaceutica": "Tableta recubierta",
                "descripcion": "Biguanida antidiabética de primera elección. Reduce la gluconeogénesis hepática y aumenta la sensibilidad periférica a la insulina sin estimular la secreción pancreática ni causar hipoglucemia.",
                "uso_indicado": "Diabetes mellitus tipo 2 como monoterapia o combinada, estados prediabéticos y síndrome de ovario poliquístico.",
                "efectos_secundarios": "Diarrea transitoria, meteorismo, náuseas y sensación de plenitud. Se minimizan tomándolo con los alimentos principales.",
                "requiere_formula": True,
            },
            {
                "codigo_cum": "19909876-01",
                "nombre_generico": "Glibenclamida",
                "nombre_comercial": "Daonil",
                "laboratorio": "Sanofi-Aventis de Colombia S.A.",
                "concentracion": "5 mg",
                "forma_farmaceutica": "Tableta ranurada",
                "descripcion": "Sulfonilurea hipoglucemiante oral. Estimula la liberación de insulina fisiológica por parte de las células beta de los islotes de Langerhans pancreáticos.",
                "uso_indicado": "Control glucémico en adultos con diabetes mellitus tipo 2 que no logran metas metabólicas únicamente con dieta y ejercicio.",
                "efectos_secundarios": "Episodios de hipoglucemia (sudor frío, temblor, mareos), incremento leve de peso y molestias gástricas.",
                "requiere_formula": True,
            },
            {
                "codigo_cum": "20011234-01",
                "nombre_generico": "Insulina Glargina",
                "nombre_comercial": "Lantus SoloStar",
                "laboratorio": "Sanofi-Aventis de Colombia S.A.",
                "concentracion": "100 UI / ml",
                "forma_farmaceutica": "Solución inyectable en pluma precargada 3 ml",
                "descripcion": "Análogo de insulina humana de acción ultralarga. Proporciona una concentración plasmática basal constante sin picos pronunciados durante un intervalo de 24 horas continuas.",
                "uso_indicado": "Diabetes mellitus tipo 1 y diabetes mellitus tipo 2 con requerimiento de soporte insulínico basal en adultos y niños mayores de 2 años.",
                "efectos_secundarios": "Hipoglucemia sintomática, lipodistrofia en el sitio de inyección y ganancia de peso.",
                "requiere_formula": True,
            },
            {
                "codigo_cum": "20087654-01",
                "nombre_generico": "Empagliflozina",
                "nombre_comercial": "Jardiance",
                "laboratorio": "Boehringer Ingelheim S.A.",
                "concentracion": "10 mg",
                "forma_farmaceutica": "Tableta recubierta",
                "descripcion": "Inhibidor selectivo del cotransportador renal de sodio-glucosa tipo 2 (SGLT2). Disminuye la reabsorción tubular de glucosa promoviendo su excreción urinaria, favoreciendo el control metabólico y reduciendo la sobrecarga cardiovascular.",
                "uso_indicado": "Diabetes mellitus tipo 2, insuficiencia cardíaca con cualquier rango de fracción de eyección y enfermedad renal crónica para retardar su progresión.",
                "efectos_secundarios": "Infecciones micóticas genitales, infecciones urinarias bajas, aumento de la diuresis e hipotensión leve.",
                "requiere_formula": True,
            },
            {
                "codigo_cum": "19915678-01",
                "nombre_generico": "Levotiroxina Sódica",
                "nombre_comercial": "Synthroid 50",
                "laboratorio": "Abbott Laboratories de Colombia S.A.S.",
                "concentracion": "50 mcg",
                "forma_farmaceutica": "Tableta",
                "descripcion": "Hormona tiroidea sintética de alta pureza química. Tras su absorción se transforma en liotironina celular activa, restaurando el balance endocrino y metabólico corporal.",
                "uso_indicado": "Terapia de sustitución en hipotiroidismo primario subclínico o clínico, bocio no tóxico y tiroiditis crónica autoinmune.",
                "efectos_secundarios": "Prácticamente nulos a dosis terapéuticas óptimas. Síntomas de hipertiroidismo si la dosis está sobredimensionada.",
                "requiere_formula": True,
            },
            {
                "codigo_cum": "19915678-02",
                "nombre_generico": "Levotiroxina Sódica",
                "nombre_comercial": "Euthyrox 100",
                "laboratorio": "Merck S.A.",
                "concentracion": "100 mcg",
                "forma_farmaceutica": "Tableta ranurada",
                "descripcion": "Hormona tiroidea sintética para reposición terapéutica en hipotiroidismo manifiesto grave o tras ablación glandular quirúrgica o radioactiva.",
                "uso_indicado": "Hipotiroidismo primario de cualquier etiología, tiroidectomía total y supresión de TSH en cáncer de tiroides diferenciado.",
                "efectos_secundarios": "Palpitaciones, insomnio, pérdida de peso, temblor o diarrea si hay sobredosificación.",
                "requiere_formula": True,
            },
            # Respiratorios y Alergias
            {
                "codigo_cum": "19927890-01",
                "nombre_generico": "Salbutamol Sulfato",
                "nombre_comercial": "Ventilast Inhalador",
                "laboratorio": "GlaxoSmithKline Colombia S.A.",
                "concentracion": "100 mcg / dosis",
                "forma_farmaceutica": "Aerosol para inhalación (200 dosis)",
                "descripcion": "Broncodilatador agonista selectivo beta-2 adrenérgico de acción rápida. Relaja en menos de 5 minutos la musculatura lisa bronquial frente al espasmo asmático.",
                "uso_indicado": "Tratamiento de rescate del broncoespasmo agudo en asma bronquial, bronquitis espástica y prevención del broncoespasmo inducido por ejercicio.",
                "efectos_secundarios": "Temblor muscular distal en dedos, taquicardia sinusal, palpitaciones y cefalea transitoria.",
                "requiere_formula": True,
            },
            {
                "codigo_cum": "19938901-01",
                "nombre_generico": "Beclometasona Dipropionato",
                "nombre_comercial": "Becotide Inhalador",
                "laboratorio": "GlaxoSmithKline Colombia S.A.",
                "concentracion": "250 mcg / dosis",
                "forma_farmaceutica": "Aerosol para inhalación (200 dosis)",
                "descripcion": "Glucocorticoide inhalado de acción local directa sobre el epitelio respiratorio. Reduce el edema, la hipersecreción mucosa y la hiperreactividad bronquial.",
                "uso_indicado": "Terapia preventiva y control antiinflamatorio continuo del asma persistente en niños y adultos.",
                "efectos_secundarios": "Candidiasis orofaríngea (se previene enjuagando la boca con agua tras su uso), ronquera y carraspera.",
                "requiere_formula": True,
            },
            {
                "codigo_cum": "19946789-01",
                "nombre_generico": "Loratadina",
                "nombre_comercial": "Clarityne",
                "laboratorio": "Bayer S.A.",
                "concentracion": "10 mg",
                "forma_farmaceutica": "Tableta",
                "descripcion": "Antihistamínico selectivo de receptores H1 periféricos de segunda generación. Alivia los síntomas alérgicos de manera prolongada sin causar sedación apreciable.",
                "uso_indicado": "Rinitis alérgica estacional y perenne, estornudos en salva, congestión alérgica, lagrimeo y urticaria idiopática crónica.",
                "efectos_secundarios": "Cefalea leve, sequedad de boca, fatiga transitoria. Rara somnolencia.",
                "requiere_formula": False,
            },
            {
                "codigo_cum": "19957890-01",
                "nombre_generico": "Cetirizina Clorhidrato",
                "nombre_comercial": "Zyrtec",
                "laboratorio": "UCB Pharma S.A.",
                "concentracion": "10 mg",
                "forma_farmaceutica": "Tableta recubierta",
                "descripcion": "Potente antihistamínico de segunda generación que bloquea selectivamente receptores H1 e inhibe la migración tardía de eosinófilos en los tejidos expuestos a alérgenos.",
                "uso_indicado": "Rinitis y conjuntivitis alérgica, dermatitis atópica pruriginosa, eccemas alérgicos y prurito generalizado.",
                "efectos_secundarios": "Somnolencia leve en pacientes susceptibles, sequedad bucal, faringitis y mareo.",
                "requiere_formula": False,
            },
            {
                "codigo_cum": "19998765-01",
                "nombre_generico": "Montelukast Sódico",
                "nombre_comercial": "Singulair",
                "laboratorio": "Organon Colombia S.A.S.",
                "concentracion": "10 mg",
                "forma_farmaceutica": "Tableta recubierta",
                "descripcion": "Antagonista selectivo de los receptores de leucotrienos cisteinílicos (CysLT1). Bloquea la inflamación bronquial y la hiperreactividad mediada por leucotrienos.",
                "uso_indicado": "Profilaxis y tratamiento crónico del asma bronquial, asma inducida por aspirina y control de síntomas de rinitis alérgica persistente.",
                "efectos_secundarios": "Cefalea, dolor abdominal, sed, ocasionalmente alteraciones del sueño o pesadillas.",
                "requiere_formula": True,
            },
            # Dolor, Analgésicos y AINEs
            {
                "codigo_cum": "19903456-01",
                "nombre_generico": "Dipirona Sódica (Metamizol)",
                "nombre_comercial": "Nolotil / Dipirona Genfar",
                "laboratorio": "Genfar S.A.",
                "concentracion": "500 mg",
                "forma_farmaceutica": "Tableta",
                "descripcion": "Derivado pirazolónico con intensa acción analgésica periférica y central y notable eficacia antipirética y espasmolítica sobre la musculatura visceral.",
                "uso_indicado": "Dolor agudo moderado a severo por traumatismos, cirugías, cólicos renales o biliares, y fiebre alta refractaria.",
                "efectos_secundarios": "Hipotensión transitoria, erupción cutánea alérgica. Reacciones hematológicas sumamente infrecuentes.",
                "requiere_formula": False,
            },
            {
                "codigo_cum": "19914567-01",
                "nombre_generico": "Diclofenaco Sódico",
                "nombre_comercial": "Voltaren",
                "laboratorio": "Novartis de Colombia S.A.",
                "concentracion": "50 mg",
                "forma_farmaceutica": "Tableta con cubierta entérica",
                "descripcion": "Antiinflamatorio no esteroideo con potente poder analgésico y antirreumático derivado del ácido fenilacético. Reduce prostaglandinas implicadas en la inflamación sinovial.",
                "uso_indicado": "Artrosis, artritis reumatoide, espondilitis anquilosante, dolor lumbar agudo, bursitis y ataques agudos de gota.",
                "efectos_secundarios": "Dolor epigástrico, náuseas, pirosis, diarrea, riesgo de úlcera gástrica con uso crónico continuado.",
                "requiere_formula": True,
            },
            {
                "codigo_cum": "19925678-01",
                "nombre_generico": "Naproxeno Sódico",
                "nombre_comercial": "Flanax",
                "laboratorio": "Bayer S.A.",
                "concentracion": "275 mg",
                "forma_farmaceutica": "Tableta recubierta",
                "descripcion": "AINE de vida media prolongada (12 a 15 horas). Brinda alivio continuado y sostenido con dosis espaciadas dos veces al día.",
                "uso_indicado": "Traumatismos musculares, esguinces, dolores articulares, cefaleas intensas y dismenorrea severa.",
                "efectos_secundarios": "Malestar estomacal, somnolencia leve, mareos, acidez gástrica.",
                "requiere_formula": False,
            },
            {
                "codigo_cum": "19936789-01",
                "nombre_generico": "Tramadol Clorhidrato",
                "nombre_comercial": "Tramal",
                "laboratorio": "Grünenthal Colombiana S.A.",
                "concentracion": "50 mg",
                "forma_farmaceutica": "Cápsula",
                "descripcion": "Analgésico de acción central con mecanismo dual: unión a receptores opioides mu e inhibición de la recaptación de serotonina y noradrenalina espinal.",
                "uso_indicado": "Dolor agudo o crónico de moderado a intenso (postoperatorio, oncológico, dolor neuropático severo y fracturas).",
                "efectos_secundarios": "Náuseas, mareos, vértigo, somnolencia diurna, sudoración y estreñimiento.",
                "requiere_formula": True,
            },
            {
                "codigo_cum": "19967890-01",
                "nombre_generico": "Meloxicam",
                "nombre_comercial": "Mobic",
                "laboratorio": "Boehringer Ingelheim S.A.",
                "concentracion": "15 mg",
                "forma_farmaceutica": "Tableta",
                "descripcion": "AINE oxicam con selectividad preferencial por la COX-2 frente a la COX-1. Asegura alto poder antiinflamatorio con mayor protección gástrica.",
                "uso_indicado": "Osteoartritis degenerativa, artritis reumatoide crónica y espondilitis en esquema de dosis única diaria.",
                "efectos_secundarios": "Dispepsia, náuseas, flatulencia, cefalea y ligero edema periférico.",
                "requiere_formula": True,
            },
            # Sistema Nervioso Central y Salud Mental
            {
                "codigo_cum": "19908901-01",
                "nombre_generico": "Fluoxetina Clorhidrato",
                "nombre_comercial": "Prozac",
                "laboratorio": "Eli Lilly Interamerica Inc.",
                "concentracion": "20 mg",
                "forma_farmaceutica": "Cápsula",
                "descripcion": "Antidepresivo inhibidor selectivo de la recaptación de serotonina con vida media prolongada. Estimula la energía, el ánimo y disminuye la ideación obsesiva.",
                "uso_indicado": "Trastorno depresivo mayor, trastorno obsesivo compulsivo y bulimia nerviosa.",
                "efectos_secundarios": "Insomnio, disminución temporal del apetito, náuseas, temblor fino y astenia.",
                "requiere_formula": True,
            },
            {
                "codigo_cum": "19919012-01",
                "nombre_generico": "Clonazepam",
                "nombre_comercial": "Rivotril",
                "laboratorio": "Roche Farma de Colombia S.A.",
                "concentracion": "2 mg",
                "forma_farmaceutica": "Tableta ranurada",
                "descripcion": "Benzodiacepina potente que refuerza la inhibición gabaérgica central produciendo sedación, miorrelajación, efecto anticonvulsivo y control del pánico.",
                "uso_indicado": "Trastorno de pánico con o sin agorafobia, crisis mioclónicas, ausencias epilépticas y fobias refractarias.",
                "efectos_secundarios": "Sedación, somnolencia, ataxia motora, cansancio matutino; riesgo de dependencia en uso desmedido.",
                "requiere_formula": True,
            },
            {
                "codigo_cum": "19920123-01",
                "nombre_generico": "Alprazolam",
                "nombre_comercial": "Xanax",
                "laboratorio": "Pfizer Colombia S.A.S.",
                "concentracion": "0.5 mg",
                "forma_farmaceutica": "Tableta ranurada",
                "descripcion": "Triazolobenzodiacepina de inicio ultra rápido especialmente formulada para neutralizar crisis súbitas de pánico y ansiedad extrema.",
                "uso_indicado": "Crisis agudas de pánico, ansiedad generalizada y tensión psíquica incapacitante.",
                "efectos_secundarios": "Sedación, mareo, fatiga diurna, disminución de reflejos psicomotores.",
                "requiere_formula": True,
            },
            {
                "codigo_cum": "20045678-01",
                "nombre_generico": "Pregabalina",
                "nombre_comercial": "Lyrica",
                "laboratorio": "Pfizer Colombia S.A.S.",
                "concentracion": "75 mg",
                "forma_farmaceutica": "Cápsula dura",
                "descripcion": "Ligando de la subunidad alfa-2-delta de los canales de calcio neuronales. Reduce la entrada de calcio y frena la liberación de neurotransmisores del dolor neuropático.",
                "uso_indicado": "Dolor neuropático periférico (neuropatía diabética, neuralgia postherpética), fibromialgia y trastorno de ansiedad generalizada.",
                "efectos_secundarios": "Mareos, somnolencia pronunciada, visión borrosa, incremento ponderal y edema periférico.",
                "requiere_formula": True,
            },
            # Anticoagulantes y Hematológicos
            {
                "codigo_cum": "19989012-01",
                "nombre_generico": "Clopidogrel Bisulfato",
                "nombre_comercial": "Plavix",
                "laboratorio": "Sanofi-Aventis de Colombia S.A.",
                "concentracion": "75 mg",
                "forma_farmaceutica": "Tableta recubierta",
                "descripcion": "Inhibidor irreversible del receptor plaquetario P2Y12 de difosfato de adenosina (ADP). Previene la activación del complejo GPIIb/IIIa y la agregación de las plaquetas.",
                "uso_indicado": "Prevención de eventos aterotrombóticos en infarto agudo de miocardio reciente, ictus isquémico o tras colocación de stent coronario.",
                "efectos_secundarios": "Hematomas espontáneos, epistaxis, sangrado gastrointestinal, diarrea y dispepsia.",
                "requiere_formula": True,
            },
            {
                "codigo_cum": "19901122-01",
                "nombre_generico": "Warfarina Sódica",
                "nombre_comercial": "Coumadin",
                "laboratorio": "Bristol-Myers Squibb de Colombia S.A.",
                "concentracion": "5 mg",
                "forma_farmaceutica": "Tableta ranurada",
                "descripcion": "Anticoagulante oral cumarínico que antagoniza la vitamina K bloqueando la gamma-carboxilación de los factores II, VII, IX y X.",
                "uso_indicado": "Profilaxis y tratamiento de trombosis venosa profunda, tromboembolismo pulmonar y prevención de embolias sistémicas en fibrilación auricular o válvulas cardíacas mecánicas.",
                "efectos_secundarios": "Hemorragias mayores y menores. Requiere monitorización analítica estricta del INR.",
                "requiere_formula": True,
            },
            # Corticosteroides
            {
                "codigo_cum": "19912233-01",
                "nombre_generico": "Prednisolona",
                "nombre_comercial": "Prednisolona MK",
                "laboratorio": "Tecnoquímicas S.A.",
                "concentracion": "5 mg",
                "forma_farmaceutica": "Tableta",
                "descripcion": "Glucocorticoide sintético con potente actividad antiinflamatoria e inmunosupresora. Reduce la producción de citocinas inflamatorias y la migración celular.",
                "uso_indicado": "Enfermedades autoinmunes reumáticas (lupus eritematoso sistémico, artritis reumatoide), crisis asmáticas agudas y glomerulonefritis.",
                "efectos_secundarios": "Aumento del apetito, retención hidrosalina, insomnio, irritación gástrica, hipertensión en uso prolongado.",
                "requiere_formula": True,
            },
            {
                "codigo_cum": "19923344-01",
                "nombre_generico": "Dexametasona Fosfato Disódico",
                "nombre_comercial": "Decadron Inyectable",
                "laboratorio": "Genfar S.A.",
                "concentracion": "4 mg / ml",
                "forma_farmaceutica": "Solución inyectable en ampolla 2 ml",
                "descripcion": "Corticosteroide sintético fluorado de máxima potencia antiinflamatoria y prolongada duración de acción sin retención mineralocorticoide de sodio.",
                "uso_indicado": "Shock anafiláctico, edema cerebral vasogénico agudo, laringotraqueítis aguda obstructiva y estados hiperinflamatorios severos.",
                "efectos_secundarios": "Hiperglucemia aguda, rubor facial, taquicardia transitoria, hipertensión arterial.",
                "requiere_formula": True,
            },
            # Suplementos y Vitaminas
            {
                "codigo_cum": "19967788-01",
                "nombre_generico": "Ácido Fólico (Vitamina B9)",
                "nombre_comercial": "Ácido Fólico MK",
                "laboratorio": "Tecnoquímicas S.A.",
                "concentracion": "1 mg",
                "forma_farmaceutica": "Tableta",
                "descripcion": "Vitamina del complejo B esencial para la síntesis de purinas y pirimidinas y la eritropoyesis medular normal.",
                "uso_indicado": "Prevención de defectos del tubo neural durante la gestación y tratamiento de anemias megaloblásticas.",
                "efectos_secundarios": "Excelente tolerabilidad fisiológica. Muy rara vez náuseas o distensión abdominal.",
                "requiere_formula": False,
            },
            {
                "codigo_cum": "19978899-01",
                "nombre_generico": "Tiamina + Piridoxina + Cianocobalamina",
                "nombre_comercial": "Neurobión",
                "laboratorio": "Procter & Gamble Health Colombia S.A.S.",
                "concentracion": "100 mg / 100 mg / 1000 mcg",
                "forma_farmaceutica": "Tableta recubierta",
                "descripcion": "Complejo multivitamínico neurotropo que promueve la regeneración axonal, el metabolismo de mielina y el alivio del dolor neurítico periférico.",
                "uso_indicado": "Tratamiento coadyuvante de neuritis, lumbociática, neuralgia facial o intercostal y neuropatías carenciales.",
                "efectos_secundarios": "Coloración amarillenta intensa de la orina (por vitaminas B), sudoración o náuseas leves.",
                "requiere_formula": False,
            }
        ]

        meds_creados = []
        for m in medicamentos_data:
            med_id = m.get('id')
            codigo_cum = m['codigo_cum'].strip().upper()
            defaults = {
                "codigo_cum": codigo_cum,
                "nombre_generico": m["nombre_generico"],
                "nombre_comercial": m["nombre_comercial"],
                "laboratorio": m["laboratorio"],
                "concentracion": m["concentracion"],
                "forma_farmaceutica": m["forma_farmaceutica"],
                "descripcion": m["descripcion"],
                "uso_indicado": m["uso_indicado"],
                "efectos_secundarios": m["efectos_secundarios"],
                "requiere_formula": m["requiere_formula"],
            }

            if med_id and Medicamento.objects.filter(id=med_id).exists():
                med_obj = Medicamento.objects.get(id=med_id)
                for k, v in defaults.items():
                    setattr(med_obj, k, v)
                med_obj.save()
            else:
                med_obj, _ = Medicamento.objects.update_or_create(
                    codigo_cum=codigo_cum,
                    defaults=defaults
                )
            meds_creados.append(med_obj)

        return list(Medicamento.objects.all())

    def _poblar_inventarios(self, sedes, medicamentos):
        self.stdout.write("4. Generando Inventarios y Stock por Sede...")
        random.seed(42)  # Semilla determinista para inventarios coherentes

        inventarios_creados = []
        lotes_base = ["LT-2025-A101", "LT-2025-B202", "LT-2025-C303", "LT-2025-D404", "LT-2025-E505"]
        fecha_actual = timezone.now().date()

        for s in sedes:
            for m in medicamentos:
                # Determinación de stock:
                # 72% Disponible (15 a 90 unidades)
                # 18% Stock Bajo (2 a 8 unidades)
                # 10% Agotado (0 unidades) para permitir probar flujos de agotado y Derecho de Petición
                roll = random.random()
                if roll < 0.10:
                    cant = 0
                elif roll < 0.28:
                    cant = random.randint(2, 8)
                else:
                    cant = random.randint(15, 95)

                lote_elegido = f"{random.choice(lotes_base)}-{s.id % 10}"
                # Vencimiento entre 6 meses y 30 meses en el futuro
                dias_vence = random.randint(180, 900)
                vencimiento = fecha_actual + datetime.timedelta(days=dias_vence)

                inv_obj, _ = InventarioSede.objects.update_or_create(
                    sede=s,
                    medicamento=m,
                    lote=lote_elegido,
                    defaults={
                        "cantidad_disponible": cant,
                        "cantidad_minima": 10,
                        "fecha_vencimiento": vencimiento,
                    }
                )
                inventarios_creados.append(inv_obj)

        return inventarios_creados

    def _sincronizar_firestore(self, epss, sedes, medicamentos, inventarios):
        db = get_firestore_db()
        if db is None:
            self.stdout.write(self.style.ERROR("No se pudo conectar a Firestore (revisa ServiceAccountKey.json). Omitiendo sync remoto."))
            return

        BATCH_SIZE = 400

        # Sincronizar EPS
        self.stdout.write(f" -> Sincronizando {len(epss)} EPS...")
        batch = db.batch()
        count = 0
        for e in epss:
            doc_ref = db.collection("eps").document(str(e.id))
            data = {
                "id": e.id,
                "nombre": e.nombre,
                "nit": e.nit,
                "direccion": e.direccion,
                "ciudad": e.ciudad,
                "telefono": e.telefono,
                "email": e.email,
                "estado": e.estado,
            }
            batch.set(doc_ref, data)
            count += 1
            if count >= BATCH_SIZE:
                batch.commit()
                batch = db.batch()
                count = 0
        if count > 0:
            batch.commit()

        # Sincronizar Sedes
        self.stdout.write(f" -> Sincronizando {len(sedes)} Sedes...")
        batch = db.batch()
        count = 0
        for s in sedes:
            doc_ref = db.collection("sedes").document(str(s.id))
            data = {
                "id": s.id,
                "eps_id": s.eps_id,
                "eps_nombre": s.eps.nombre,
                "nombre": s.nombre,
                "direccion": s.direccion,
                "ciudad": s.ciudad,
                "telefono": s.telefono,
                "email": s.email,
                "estado": s.estado,
                "latitud": s.latitud,
                "longitud": s.longitud,
                "hora_apertura": s.hora_apertura.strftime("%H:%M:%S") if s.hora_apertura else "07:00:00",
                "hora_cierre": s.hora_cierre.strftime("%H:%M:%S") if s.hora_cierre else "19:00:00",
                "atiende_fines_semana": s.atiende_fines_semana,
            }
            batch.set(doc_ref, data)
            count += 1
            if count >= BATCH_SIZE:
                batch.commit()
                batch = db.batch()
                count = 0
        if count > 0:
            batch.commit()

        # Sincronizar Medicamentos
        self.stdout.write(f" -> Sincronizando {len(medicamentos)} Medicamentos...")
        batch = db.batch()
        count = 0
        for m in medicamentos:
            # En Firestore se usa codigo_cum como document id o id numérico
            doc_id = m.codigo_cum or str(m.id)
            doc_ref = db.collection("medicamentos").document(doc_id)
            data = {
                "id": m.id,
                "codigo_cum": m.codigo_cum,
                "nombre_generico": m.nombre_generico,
                "nombre_comercial": m.nombre_comercial,
                "laboratorio": m.laboratorio,
                "concentracion": m.concentracion,
                "forma_farmaceutica": m.forma_farmaceutica,
                "descripcion": m.descripcion,
                "uso_indicado": m.uso_indicado,
                "efectos_secundarios": m.efectos_secundarios,
                "requiere_formula": m.requiere_formula,
            }
            batch.set(doc_ref, data)
            count += 1
            if count >= BATCH_SIZE:
                batch.commit()
                batch = db.batch()
                count = 0
        if count > 0:
            batch.commit()

        # Sincronizar Inventario de Sedes
        self.stdout.write(f" -> Sincronizando {len(inventarios)} registros de Inventario...")
        batch = db.batch()
        count = 0
        for inv in inventarios:
            doc_ref = db.collection("inventario_sedes").document(str(inv.id))
            data = {
                "id": inv.id,
                "sede_id": inv.sede_id,
                "sede_nombre": inv.sede.nombre,
                "eps_id": inv.sede.eps_id,
                "eps_nombre": inv.sede.eps.nombre,
                "ciudad": inv.sede.ciudad,
                "medicamento_id": inv.medicamento_id,
                "medicamento_nombre": inv.medicamento.nombre_comercial,
                "cantidad_disponible": inv.cantidad_disponible,
                "cantidad_minima": inv.cantidad_minima,
                "lote": inv.lote,
                "fecha_vencimiento": str(inv.fecha_vencimiento) if inv.fecha_vencimiento else None,
                "estado_stock": inv.estado_stock,
            }
            batch.set(doc_ref, data)
            count += 1
            if count >= BATCH_SIZE:
                batch.commit()
                batch = db.batch()
                count = 0
        if count > 0:
            batch.commit()

        self.stdout.write(self.style.SUCCESS("[OK]: Sincronización completa en Firestore realizada con éxito."))
