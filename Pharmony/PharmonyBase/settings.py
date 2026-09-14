import os
import json
from pathlib import Path

import dotenv
import firebase_admin
from firebase_admin import credentials

BASE_DIR = Path(__file__).resolve().parent.parent

env_path = BASE_DIR / '.env'
if not env_path.exists():
    env_path = BASE_DIR.parent / '.env'
dotenv.load_dotenv(env_path)

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    raise RuntimeError('Falta DJANGO_SECRET_KEY en el archivo .env.')
is_render = os.getenv('RENDER') is not None
debug_env = os.getenv('DJANGO_DEBUG')
if debug_env is not None:
    DEBUG = debug_env.lower() in ('true', '1', 't')
else:
    DEBUG = not is_render

allowed_hosts_env = os.getenv('DJANGO_ALLOWED_HOSTS')
if allowed_hosts_env:
    ALLOWED_HOSTS = [h.strip() for h in allowed_hosts_env.split(',') if h.strip()]
else:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', '.onrender.com']

render_external_hostname = os.getenv('RENDER_EXTERNAL_HOSTNAME')
if render_external_hostname and render_external_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_external_hostname)

csrf_trusted_env = os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS')
if csrf_trusted_env:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in csrf_trusted_env.split(',') if o.strip()]
else:
    CSRF_TRUSTED_ORIGINS = ['https://*.onrender.com', 'http://localhost:8000', 'http://127.0.0.1:8000']

if render_external_hostname:
    render_origin = f"https://{render_external_hostname}"
    if render_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(render_origin)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'reportlab',
    'corsheaders',
    'Farmacia',
    'home',
    'epsinventario',
    'DocsIA',
    'turnos',
    'pedidos',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'PharmonyBase.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'PharmonyBase.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'es'
TIME_ZONE = 'America/Bogota'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

STATIC_ROOT = BASE_DIR / 'staticfiles'

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

CORS_ALLOWED_ORIGINS = [
    "http://localhost:4200",
    "http://127.0.0.1:4200",
]
CORS_ALLOW_ALL_ORIGINS = True

AUTH_USER_MODEL = 'Farmacia.Usuario'

FIREBASE_CREDENTIALS_JSON = os.getenv('FIREBASE_CREDENTIALS_JSON')
FIREBASE_CREDENTIALS_PATH = os.getenv('FIREBASE_CREDENTIALS_PATH') or os.getenv('FIREBASE_KEYS_PATH') or 'ServiceAccountKey.json'

if not firebase_admin._apps:
    # 1. Intentar desde variable de entorno JSON (útil en Render si se pega el JSON directo)
    if FIREBASE_CREDENTIALS_JSON:
        try:
            cred_dict = json.loads(FIREBASE_CREDENTIALS_JSON)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            print(f"Aviso al inicializar Firebase desde FIREBASE_CREDENTIALS_JSON: {e}")

    # 2. Intentar desde archivo (Secret File en /etc/secrets/ o archivo local)
    if not firebase_admin._apps and FIREBASE_CREDENTIALS_PATH:
        candidate_paths = [
            Path(FIREBASE_CREDENTIALS_PATH),
            BASE_DIR / FIREBASE_CREDENTIALS_PATH,
            BASE_DIR.parent / FIREBASE_CREDENTIALS_PATH,
            Path('/etc/secrets') / FIREBASE_CREDENTIALS_PATH,
            Path('/etc/secrets/ServiceAccountKey.json'),
        ]
        key_path = None
        for p in candidate_paths:
            if p.exists():
                key_path = p
                break
            
        if key_path:
            try:
                cred = credentials.Certificate(str(key_path))
                firebase_admin.initialize_app(cred)
            except Exception as e:
                print(f"Aviso al inicializar Firebase desde archivo: {e}")

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
CSRF_COOKIE_HTTPONLY = False