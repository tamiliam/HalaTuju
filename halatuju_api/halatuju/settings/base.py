"""
Django base settings for HalaTuju API.

These settings are shared across all environments.
"""
import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-dev-key-change-in-production')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party apps
    'rest_framework',
    'corsheaders',

    # Local apps
    'apps.courses',
    'apps.reports',
    'apps.scholarship',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'halatuju.middleware.supabase_auth.SupabaseAuthMiddleware',
    'halatuju.middleware.supabase_auth.NricGateMiddleware',
]

ROOT_URLCONF = 'halatuju.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'halatuju.wsgi.application'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-gb'
TIME_ZONE = 'Asia/Kuala_Lumpur'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'halatuju.middleware.supabase_auth.SupabaseAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'halatuju.middleware.supabase_auth.SupabaseIsAuthenticated',
    ],
}

# Supabase Auth settings
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_JWT_SECRET = os.environ.get('SUPABASE_JWT_SECRET', '')
SUPABASE_SERVICE_ROLE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')

# AI APIs for reports
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

# Admin notifications. The env var was set on Cloud Run but never read into
# settings, so getattr(settings, 'ADMIN_NOTIFY_EMAIL', '') silently returned ''
# and every admin-notify email (sponsor interest, profile-complete, Vision-outage
# alert) no-op'd. Reading it here makes those actually send.
ADMIN_NOTIFY_EMAIL = os.environ.get('ADMIN_NOTIFY_EMAIL', '')
# Shared secret guarding the internal cron endpoint (Cloud Scheduler → the running
# api service runs scheduled management commands without a separate Cloud Run Job).
CRON_SECRET = os.environ.get('CRON_SECRET', '')

# Supporting-document upload guardrails (cost + abuse). Env-overridable.
MAX_DOC_SIZE_BYTES = int(os.environ.get('MAX_DOC_SIZE_BYTES', str(8 * 1024 * 1024)))   # 8 MB/file
MAX_DOCS_PER_APPLICATION = int(os.environ.get('MAX_DOCS_PER_APPLICATION', '40'))
# Document-assist (Gemini field extraction on upload): hourly cap per application —
# beyond it the upload still succeeds + Vision/deterministic feedback still run, but
# the billable Gemini call is skipped (student sees a "we'll review manually" note).
DOC_ASSIST_RATE_LIMIT_PER_HOUR = int(os.environ.get('DOC_ASSIST_RATE_LIMIT_PER_HOUR', '15'))
# When True, only call Gemini if the free deterministic presence check is uncertain
# (saves cost). Default False = always extract (richer data for the admin).
DOC_ASSIST_ONLY_WHEN_UNCERTAIN = os.environ.get('DOC_ASSIST_ONLY_WHEN_UNCERTAIN', '') == '1'

# Logging configuration (structured JSON for Cloud Run)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            'format': '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
        },
        'simple': {
            'format': '%(levelname)s %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
