# Pharmony — Plataforma de Gestión Farmacéutica & Salud Digital con IA

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Django Version](https://img.shields.io/badge/django-6.0%2B-green.svg)](https://www.djangoproject.com/)
[![Flutter Version](https://img.shields.io/badge/flutter-3.x-blue.svg)](https://flutter.dev/)
[![Leaflet Maps](https://img.shields.io/badge/maps-Leaflet.js-green.svg)](https://leafletjs.com/)
[![Google Gemini AI](https://img.shields.io/badge/AI-Google%20Gemini%20Flash-purple.svg)](https://ai.google.dev/)
[![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)](LICENSE)

> **Pharmony** es una solución tecnológica integral de salud digital y dispensación farmacéutica para Colombia. Conecta en tiempo real a **Pacientes**, **EPS** y **Farmacias**, integrando lectura inteligente de fórmulas médicas mediante Visión Artificial con **Google Gemini**, turnos virtuales georreferenciados con tickets QR, autenticación biométrica facial y pantallas de sala de espera en alta definición.

---

## 📑 Tabla de Contenidos

- [Características Principales](#-características-principales)
- [Stack Tecnológico](#-stack-tecnológico)
- [Arquitectura del Sistema](#-arquitectura-del-sistema)
  - [Estructura del Proyecto](#estructura-del-proyecto)
  - [Módulos de la Aplicación](#módulos-de-la-aplicación)
  - [Flujo de Datos y Ciclo de Peticiones](#flujo-de-datos-y-ciclo-de-peticiones)
  - [Modelo de Base de Datos (Schema)](#modelo-de-base-de-datos-schema)
- [Arquitectura y Módulos del Frontend](#-arquitectura-y-módulos-del-frontend)
  - [1. Estructura y Estilos de la Interfaz](#1-estructura-y-estilos-de-la-interfaz)
  - [2. Desglose de Pantallas y Plantillas Web](#2-desglose-de-pantallas-y-plantillas-web)
  - [3. Librerías de Interacción en Cliente](#3-librerías-de-interacción-en-cliente)
- [Requisitos Previos](#-requisitos-previos)
- [Guía de Instalación y Ejecución Local](#-guía-de-instalación-y-ejecución-local)
  - [1. Clonar el Repositorio](#1-clonar-el-repositorio)
  - [2. Configurar el Entorno Virtual](#2-configurar-el-entorno-virtual)
  - [3. Instalar Dependencias](#3-instalar-dependencias)
  - [4. Configurar Variables de Entorno](#4-configurar-variables-de-entorno)
  - [5. Base de Datos y Migraciones](#5-base-de-datos-y-migraciones)
  - [6. Iniciar el Servidor de Desarrollo](#6-iniciar-el-servidor-de-desarrollo)
  - [7. Cliente Móvil y Desktop (Flutter)](#7-cliente-móvil-y-desktop-flutter)
- [Variables de Entorno](#-variables-de-entorno)
- [Comandos Disponibles](#-comandos-disponibles)
- [Rutas y Vistas Principales](#-rutas-y-vistas-principales)
- [Pruebas Automatizadas (Testing)](#-pruebas-automatizadas-testing)
- [Despliegue en Producción](#-despliegue-en-producción)
- [Solución de Problemas (Troubleshooting)](#-solución-de-problemas-troubleshooting)
- [Contribución](#-contribución)
- [Licencia](#-licencia)

---

## 🚀 Características Principales

1. **DocsIA: Digitalización de Recetas Médicas con IA**
   - Extracción estructurada de prescripciones manuscritas e impresas mediante visión multimodal con **Google Gemini Flash**.
   - Detección precisa de principio activo, concentración, forma farmacéutica, dosis, posología y datos del médico tratante.
   - Asignación automática del medicamento escaneado al historial del paciente.

2. **Sistema de Turnos Virtuales y Atención en Sala**
   - Generación de tickets digitales georreferenciados con código QR y seguimiento de estado en tiempo real.
   - Pantalla de llamados para sala de espera en farmacias con alertas visuales y sonoras.
   - Panel de auxiliar de farmacia para apertura/cierre de cajas y atención secuencial.

3. **Autenticación Biométrica Facial**
   - Registro y validación facial en tiempo real vía WebCam (OpenCV / Face Recognition) para inicio de sesión sin contraseñas.

4. **Georreferenciación y Red de Cobertura Nacional**
   - Mapa interactivo de Colombia en Leaflet.js con localización de farmacias aliadas, sedes por EPS y disponibilidad de inventario.
   - Sincronización en tiempo real con Google Cloud Firestore.

5. **Farmacovigilancia y Derechos de Petición Automáticos**
   - Control de lotes y fechas de vencimiento de medicamentos.
   - Asistente legal automatizado para la radicación formal de *Derecho de Petición* ante desabastecimiento de medicamentos esenciales.

6. **Noticias y Alertas Sanitarias en Tiempo Real**
   - Agregador de noticias del sector salud con lectura de feeds RSS (INVIMA / MinSalud / El Tiempo) y filtrado por categorías.

---

## 🛠️ Stack Tecnológico

| Capa | Tecnologías |
|---|---|
| **Backend** | Python 3.11+, Django 6.0+, Django REST Framework (DRF), SimpleJWT, Corsheaders |
| **Inteligencia Artificial** | Google GenAI SDK (`google-genai` / Gemini Flash Vision), OpenCV, Pydantic |
| **Bases de Datos & Realtime** | SQLite (Desarrollo local), PostgreSQL (Producción), Google Cloud Firestore |
| **Frontend Web** | Django Templates, HTML5 Semántico, CSS3 Moderno, Leaflet.js, Lucide Icons, Motion One, FormKit AutoAnimate |
| **Frontend Móvil / Desktop** | Flutter 3.x, Dart 3.11+, Material Design & Cupertino |
| **Autenticación** | Django Auth personalizado (`Usuario` con roles `cliente`, `eps`, `admin`), Biometría Facial |

---

## 🏛️ Arquitectura del Sistema

### Estructura del Proyecto

```
Pharmony/
├── Pharmony/                   # Directorio raíz del backend Django
│   ├── manage.py               # Script de gestión de Django
│   ├── db.sqlite3              # Base de datos SQLite local
│   ├── requirements.txt        # Dependencias Python
│   ├── ServiceAccountKey.json  # Credenciales de Google Firebase (opcional)
│   ├── PharmonyBase/           # Configuración del proyecto
│   │   ├── settings.py         # Configuración central, apps y base de datos
│   │   ├── urls.py             # Enrutador principal de URLs
│   │   ├── wsgi.py             # Entrada WSGI para servidores de producción
│   │   └── asgi.py             # Entrada ASGI
│   ├── Farmacia/               # Módulo de usuarios, medicamentos y dashboards
│   │   ├── models.py           # Modelos: Usuario, Medicamento, MedicamentoUsuario, DerechoPeticion
│   │   ├── views.py            # Lógica de negocio, autenticación y vistas
│   │   ├── urls.py             # Rutas del módulo
│   │   ├── templates/          # Vistas HTML (Registro, Login, DashboardCliente, etc.)
│   │   └── tests.py            # Pruebas unitarias
│   ├── DocsIA/                 # Módulo de escaneo de fórmulas con IA
│   │   ├── services/
│   │   │   └── gemini_scanner.py # Procesamiento multimodal con Gemini
│   │   ├── views.py            # Endpoints de digitalización y asignación
│   │   └── templates/DocsIA/   # Interfaz del escáner web
│   ├── IA/                     # Módulo de biometría y reconocimiento facial
│   │   ├── face_rec.py         # Procesamiento de vectores faciales
│   │   └── views.py            # Endpoints de validación y login facial
│   ├── epsinventario/          # Módulo de EPS, sedes e inventarios
│   │   ├── models.py           # Modelos: Eps, Sede, InventarioSede, SolicitudMedicamento
│   │   └── geo.py              # Geocodificación de ciudades en Colombia
│   ├── turnos/                 # Módulo de filas virtuales y salas de espera
│   │   ├── models.py           # Modelos: AuxiliarSede, Caja, Turno
│   │   ├── views.py            # Generación de tickets, visualizador de TV y cajas
│   │   └── templates/turnos/   # Plantillas para tickets, turnos en sala y facturas
│   ├── home/                   # Módulo de portal principal
│   │   ├── views.py            # Lector de noticias RSS y procesamiento de sedes
│   │   └── templates/home/     # Plantilla index.html principal
│   ├── static/                 # Archivos estáticos globales (CSS, JS, imágenes)
│   └── templates/              # Plantillas base compartidas
├── PharmonyFront/              # Aplicación multiplataforma en Flutter
│   └── pharmonyfront/
│       ├── lib/                # Código fuente Dart (pantallas, servicios, modelos)
│       ├── pubspec.yaml        # Dependencias de Flutter
│       └── android/ios/web/    # Configuraciones de compilación multiplataforma
├── .env                        # Variables de entorno secretas (API Keys)
├── requirements.txt            # Dependencias del entorno general
└── README.md                   # Documentación oficial del proyecto
```

---

### Módulos de la Aplicación

1. **`Farmacia`**:
   - Catálogo maestro de medicamentos con código CUM, laboratorio, principio activo, concentración, forma farmacéutica y alertas de fórmula médica.
   - Modelo `Usuario` con 3 roles: `cliente` (paciente), `eps` (auxiliar de farmacia) y `admin` (administrador).
   - Generación y seguimiento de *Derechos de Petición* legales ante medicamentos pendientes.

2. **`DocsIA`**:
   - Servicio de inteligencia artificial conectado a `gemini-2.5-flash` / `gemini-3.0-flash`.
   - Transforma capturas de recetas médicas manuscritas en modelos JSON validados con `Pydantic`.
   - Vincula automáticamente el tratamiento prescrito al perfil del usuario.

3. **`IA` (Biometría Facial)**:
   - Procesamiento de video WebCam con OpenCV para extraer descriptores faciales de 128 dimensiones.
   - Autenticación rápida por comparación de distancias euclidianas.

4. **`turnos`**:
   - Flujo integral de turnos para farmacias y salas de espera.
   - Emisión de tickets QR únicos, pantalla de llamado en TV para farmacias y panel de despacho para auxiliares.

5. **`epsinventario` & `home`**:
   - Geolocalización de sedes farmacéuticas en las principales ciudades de Colombia.
   - Lector de noticias RSS verificadas del sector salud.

---

### Flujo de Datos y Ciclo de Peticiones

```
[Paciente / Personal Farmacéutico]
              │
              ▼
    [Navegador Web / App Flutter]
              │
              ├── (Petición HTTP / JSON) ──► [Enrutador Django (PharmonyBase/urls.py)]
              │                                          │
              │                                          ├──► [Farmacia / Auth] ──► Base de Datos SQLite / PostgreSQL
              │                                          ├──► [DocsIA Scanner] ──► Google Gemini Vision API
              │                                          ├──► [Turnos Engine] ───► Cloud Firestore Realtime Sync
              │                                          └──► [Home & Noticias] ─► Leaflet Maps / Feeds RSS
              ▼
[Respuesta Renderizada / JSON de API]
```

---

### Modelo de Base de Datos (Schema)

```
┌─────────────────────────┐         ┌─────────────────────────┐
│         Usuario         │         │       Medicamento       │
├─────────────────────────┤         ├─────────────────────────┤
│ id (PK)                 │         │ id (PK)                 │
│ username / email        │         │ codigo_cum (Unique)     │
│ rol (cliente/eps/admin) │         │ nombre_generico         │
│ face_encoding           │         │ nombre_comercial        │
│ eps_id (FK -> Eps)      │         │ concentracion           │
│ cedula / telefono       │         │ requiere_formula        │
└────────────┬────────────┘         └────────────┬────────────┘
             │                                   │
             │         ┌─────────────────────────┤
             │         │                         │
             ▼         ▼                         ▼
┌─────────────────────────────┐     ┌─────────────────────────────┐
│     MedicamentoUsuario      │     │       InventarioSede        │
├─────────────────────────────┤     ├─────────────────────────────┤
│ id (PK)                     │     │ id (PK)                     │
│ usuario_id (FK -> Usuario)  │     │ sede_id (FK -> Sede)        │
│ medicamento_id (FK -> Med)  │     │ medicamento_id (FK -> Med)  │
│ dosis / posologia           │     │ cantidad_disponible         │
│ fuente_asignacion (ia/eps)  │     │ lote                        │
│ activo (boolean)            │     │ fecha_vencimiento           │
└─────────────────────────────┘     └─────────────────────────────┘
                                                 ▲
┌─────────────────────────┐         ┌────────────┴────────────┐
│           Eps           │         │          Sede           │
├─────────────────────────┤         ├─────────────────────────┤
│ id (PK)                 │◄────────┤ id (PK)                 │
│ nombre                  │         │ eps_id (FK -> Eps)      │
│ nit (Unique)            │         │ nombre                  │
│ ciudad / direccion      │         │ latitud / longitud      │
└─────────────────────────┘         └────────────┬────────────┘
                                                 │
                                                 ▼
                                    ┌─────────────────────────┐
                                    │          Turno          │
                                    ├─────────────────────────┤
                                    │ id (PK)                 │
                                    │ codigo_ticket (Unique)  │
                                    │ usuario_id (FK -> User) │
                                    │ sede_id (FK -> Sede)    │
                                    │ estado (pendiente/atend)│
                                    └─────────────────────────┘
```

---

## 🎨 Arquitectura y Módulos del Frontend

### 1. Estructura y Estilos de la Interfaz

La interfaz web de Pharmony está diseñada con una arquitectura modular y limpia, utilizando variables CSS globales:

- **Paleta Cromática Balanceada**:
  - Superficies y fondos principales: Canvas oscuro / claro con contrastes óptimos.
  - Tipografías: **Plus Jakarta Sans** para textos descriptivos y de lectura clínica, y **Outfit** para titulares y elementos de navegación.
  - Acentos visuales: Azul médico (`#0d47c9` / `#2563eb`), cian tecnológico (`#06b6d4`), esmeralda para estados aprobados (`#10b981`) y tonos cálidos para alertas.
- **Efectos y Profundidad**:
  - Paneles con efecto de vidrio esmerilado translúcido (`backdrop-filter: blur(18px)`).
  - Sombras suaves multicapa y bordes redondeados (`border-radius: 14px` a `24px`).
  - Animaciones fluidas en micro-interacciones, botones y tarjetas.

---

### 2. Desglose de Pantallas y Plantillas Web

#### A. Portal de Inicio (`home/templates/home/index.html`)
- **Barra de Navegación Flotante**: Barra superior estilizada con efecto blur y reducción reactiva de altura al hacer scroll.
- **Sección Hero Principal**: Encabezado visual con texto en gradiente, insignias de estado de la red nacional y accesos directos a las funciones clave.
- **Métricas de Impacto**: 4 paneles con contadores numéricos interactivos (*count-up*) activados automáticamente al entrar en el campo visual del usuario.
- **Mapa de Cobertura Nacional**: Visualizador de Colombia integrado con Leaflet.js, con marcadores interactivos por sede y panel lateral de ciudades con función `flyToSede()`.
- **Módulo de Soluciones**: Tarjetas informativas con detalles de cada servicio (DocsIA, Turnos Virtuales, Red EPS, Farmacovigilancia).
- **Consejos de Autocuidado**: Selector de pestañas segmentadas (*Cadena de Frío*, *Antibióticos*, *Lectura de Recetas*, *Puntos Azules*) con checklists y recomendaciones avaladas.
- **Centro de Noticias & Alertas Sanitarias**: Barra de filtros por categoría con actualización en tiempo real y tarjeta destacada panorámica.
- **Pie de Página Institucional**: Enlaces rápidos, accesos a portales y avisos de cumplimiento normativo (INVIMA y Habeas Data).

#### B. Escáner DocsIA (`DocsIA/templates/DocsIA/escaner.html`)
- Interfaz interactiva de cámara WebCam con captura en tiempo real y selector de archivos (PDF, JPG, PNG, WEBP).
- Visor con animación de escaneo y extracción automática de medicamentos en tarjetas interactivas.
- Acción de vinculación inmediata al perfil del paciente.

#### C. Dashboard del Paciente (`Farmacia/templates/inventario/DashboardCliente.html`)
- Menú lateral de navegación con módulos: *Tratamientos Activos*, *Solicitar Turno*, *Historial de Turnos*, *Radicar Derecho de Petición* y *Mi Cuenta*.
- Listado de medicamentos con información de posología y fuente de prescripción.
- Modal automatizado para generar y radicar *Derecho de Petición* ante medicamentos no disponibles.

#### D. Dashboard de Inventario (`Farmacia/templates/inventario/DashboardInventario.html`)
- Vista para personal de farmacia y EPS con control de stock, lotes, fechas de caducidad y filtros por código CUM.

#### E. Autenticación y Login Biométrico (`Farmacia/templates/Farmacia/`)
- `PharmonyLogin.html` y `PharmonyRegistro.html`:
  - Formularios de acceso con validación en tiempo real.
  - Módulo de cámara web para registro y verificación de rostro con biometría facial.

#### F. Sistema de Turnos y Sala de Espera (`turnos/templates/turnos/`)
- `ver_ticket.html`: Ticket digital con código QR dinámico y estado de turno.
- `cola_turnos.html`: Pantalla optimizada para televisores en salas de espera con avisos visuales y sonoros.
- `atender_turno.html`: Panel de ventanilla para auxiliares farmacéuticos.

#### G. Aplicación Multiplataforma (`PharmonyFront/pharmonyfront/`)
- Cliente desarrollado en **Flutter (Dart)** para plataformas móviles (Android, iOS) y escritorio.

---

### 3. Librerías de Interacción en Cliente

| Librería | Versión | Propósito en el Frontend |
|---|---|---|
| **Leaflet.js** | `1.9.4` | Mapa interactivo de Colombia, georreferenciación de sedes y animaciones cartográficas. |
| **Lucide Icons** | `@latest` | Iconografía vectorial SVG en toda la plataforma. |
| **Motion One** | `@latest` | Transiciones fluidas en pestañas y tarjetas interactivas. |
| **FormKit AutoAnimate** | `1.0.0-beta.6` | Animación automática en el filtrado de listas y noticias. |
| **IntersectionObserver API** | Nativo | Ejecución de contadores numéricos al hacer scroll. |

---

## 📋 Requisitos Previos

- **Python**: Versión `3.11` o superior.
- **Git**: Para clonar el repositorio.
- **Google Gemini API Key**: Obtenida de forma gratuita en [Google AI Studio](https://aistudio.google.com/).
- **Flutter SDK** (Opcional, para la app móvil en `PharmonyFront`): Versión `3.11+`.

---

## ⚡ Guía de Instalación y Ejecución Local

### 1. Clonar el Repositorio

```bash
git clone https://github.com/zSatorii/Pharmony.git
cd Pharmony
```

---

### 2. Configurar el Entorno Virtual

#### En Windows (PowerShell):
```powershell
cd Pharmony
python -m venv venv
.\venv\Scripts\Activate.ps1
```

#### En Linux / macOS (Bash):
```bash
cd Pharmony
python3 -m venv venv
source venv/bin/activate
```

---

### 3. Instalar Dependencias

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

### 4. Configurar Variables de Entorno

Crea el archivo `.env` en la raíz del proyecto (`Pharmony/.env` o en la carpeta superior):

```env
# Clave obligatoria para el escáner DocsIA
GEMINI_API_KEY=tu_api_key_de_gemini_aqui

# Firebase Firestore (Opcional para sincronización en tiempo real)
FIREBASE_CREDENTIALS_PATH=ServiceAccountKey.json
FIREBASE_PROJECT_ID=tu_proyecto_firebase
```

---

### 5. Base de Datos y Migraciones

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

---

### 6. Iniciar el Servidor de Desarrollo

```bash
python manage.py runserver
```

Abre en tu navegador:
- 🌐 **Portal Principal**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- 📷 **Escáner DocsIA**: [http://127.0.0.1:8000/docs-ia/escaner/](http://127.0.0.1:8000/docs-ia/escaner/)
- 🎟️ **Panel de Turnos**: [http://127.0.0.1:8000/turnos/panel/](http://127.0.0.1:8000/turnos/panel/)
- 🔐 **Iniciar Sesión**: [http://127.0.0.1:8000/login/](http://127.0.0.1:8000/login/)
- ⚙️ **Panel de Administración**: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

---

### 7. Cliente Móvil y Desktop (Flutter)

```bash
cd ../PharmonyFront/pharmonyfront

# Instalar dependencias de Flutter
flutter pub get

# Ejecutar en el navegador
flutter run -d chrome

# O ejecutar en dispositivo conectado
flutter run
```

---

## 🔑 Variables de Entorno

| Variable | Requerida | Descripción | Ejemplo |
|---|---|---|---|
| `GEMINI_API_KEY` | **Sí** | Llave de API para el servicio de visión artificial de DocsIA | `AIzaSy...` |
| `FIREBASE_CREDENTIALS_PATH` | No | Ruta al archivo JSON de credenciales de Firebase | `ServiceAccountKey.json` |
| `FIREBASE_PROJECT_ID` | No | Identificador del proyecto en Google Firebase | `pharmony-app` |

---

## 💻 Comandos Disponibles

| Comando | Descripción |
|---|---|
| `python manage.py runserver` | Inicia el servidor de desarrollo local en `http://127.0.0.1:8000/` |
| `python manage.py check` | Comprueba la integridad del proyecto, modelos y templates |
| `python manage.py makemigrations` | Prepara nuevos archivos de migración basados en los modelos |
| `python manage.py migrate` | Ejecuta las migraciones pendientes en la base de datos |
| `python manage.py createsuperuser` | Crea una cuenta con permisos de administrador |
| `python manage.py test` | Ejecuta la suite de pruebas unitarias |
| `python manage.py collectstatic` | Agrupa todos los archivos estáticos para entornos de producción |
| `python manage.py shell` | Consola interactiva de Python con el entorno de Django cargado |

---

## 🗺️ Rutas y Vistas Principales

| Ruta | Nombre de URL | Descripción | Plantilla HTML |
|---|---|---|---|
| `/` | `home:home` | Portal de inicio con mapa de sedes y noticias | `home/templates/home/index.html` |
| `/login/` | `login` | Inicio de sesión tradicional o con biometría facial | `Farmacia/templates/Farmacia/PharmonyLogin.html` |
| `/registro/` | `registro` | Registro de nuevos usuarios con selección de rol | `Farmacia/templates/Farmacia/PharmonyRegistro.html` |
| `/docs-ia/escaner/` | `DocsIA:escaner_ui` | Interfaz de escaneo de fórmulas médicas con IA | `DocsIA/templates/DocsIA/escaner.html` |
| `/api/dashboard-cliente/` | `dashboard_cliente` | Panel de paciente con recetas y derecho de petición | `Farmacia/templates/inventario/DashboardCliente.html` |
| `/api/dashboard-inventario/` | `dashboard_inventario` | Panel de control de stock de medicamentos | `Farmacia/templates/inventario/DashboardInventario.html` |
| `/turnos/panel/` | `turnos:seleccion_panel` | Panel de auxiliares para gestión de ventanilla | `turnos/templates/turnos/seleccion_panel.html` |
| `/turnos/panel/cola/<id>/` | `turnos:cola_turnos` | Pantalla de sala de espera para televisores | `turnos/templates/turnos/cola_turnos.html` |
| `/turnos/ticket/<codigo>/` | `turnos:ver_ticket` | Ticket digital QR con seguimiento de turno | `turnos/templates/turnos/ver_ticket.html` |

---

## 🧪 Pruebas Automatizadas (Testing)

Ejecuta todas las pruebas unitarias del proyecto:

```bash
# Ejecutar todas las pruebas
python manage.py test

# Ejecutar pruebas del módulo de Farmacia
python manage.py test Farmacia.tests
```

---

## 🚢 Despliegue en Producción

### Despliegue con Docker

Ejemplo de `Dockerfile` para empaquetar el backend en `Pharmony/`:

```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev libgl1-mesa-glx libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["gunicorn", "PharmonyBase.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
```

---

## 🔧 Solución de Problemas (Troubleshooting)

### 1. `TemplateSyntaxError: default requires 2 arguments, 1 provided`
- **Causa**: Espacio accidental en la sintaxis de filtros de Django (ejemplo: `{{ sedes_json|default: "[]" }}`).
- **Solución**: Mantener el filtro continuo sin espacios: `{{ sedes_json|default:"[]"|safe }}`.

### 2. Error de clave de API en DocsIA (`No se configuró la API Key de Gemini`)
- **Causa**: Falta la variable `GEMINI_API_KEY` en el archivo `.env`.
- **Solución**: Obtén tu clave en [Google AI Studio](https://aistudio.google.com/) y agrégala al archivo `.env`.

### 3. Permisos de cámara bloqueados en el navegador
- **Causa**: Los navegadores restringen el acceso a la cámara en sitios sin HTTPS o que no sean `localhost`.
- **Solución**: Accede siempre mediante `http://127.0.0.1:8000/` o `http://localhost:8000/` en local, o con certificado SSL/HTTPS en producción.

---

## 👥 Contribución

1. Haz un Fork del repositorio.
2. Crea una rama para tu funcionalidad (`git checkout -b feature/nueva-mejora`).
3. Realiza tus cambios y commits (`git commit -m 'feat: agrega nuevo módulo'`).
4. Sube tu rama (`git push origin feature/nueva-mejora`).
5. Abre un **Pull Request**.

---

## 📄 Licencia

Este proyecto se distribuye bajo la licencia **MIT**. Para más detalles, consulta el archivo [LICENSE](LICENSE).

---

<div align="center">
  <sub>Pharmony · Plataforma de Salud Digital & Gestión Farmacéutica con Inteligencia Artificial · Colombia 2026</sub>
</div>