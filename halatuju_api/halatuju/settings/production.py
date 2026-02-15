"""
Django production settings for HalaTuju API.

Deployed on Cloud Run with Supabase PostgreSQL.
"""
import os
import dj_database_url
from .base import *

DEBUG = False

# Security settings
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')
ALLOWED_HOSTS = [h.strip() for h in ALLOWED_HOSTS if h.strip()]

CSRF_TRUSTED_ORIGINS = os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',')
CSRF_TRUSTED_ORIGINS = [o.strip() for o in CSRF_TRUSTED_ORIGINS if o.strip()]

# CORS settings
_cors_origins = os.environ.get('CORS_ALLOWED_ORIGINS', '')
if _cors_origins == '*':
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_origins.split(',') if o.strip()]

# Cloud Run terminates SSL
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = False  # Cloud Run handles this
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Database - Supabase PostgreSQL
# Supports DATABASE_URL or individual DB_* env vars (avoids URL-encoding issues)
DATABASE_URL = os.environ.get('DATABASE_URL')
DB_HOST = os.environ.get('DB_HOST')

if DB_HOST:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'HOST': DB_HOST,
            'PORT': os.environ.get('DB_PORT', '5432'),
            'NAME': os.environ.get('DB_NAME', 'postgres'),
            'USER': os.environ.get('DB_USER', 'postgres'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'CONN_MAX_AGE': 600,
        }
    }
elif DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600)
    }
else:
    raise ValueError("DATABASE_URL or DB_HOST environment variable is required in production")

# Sentry for error tracking
SENTRY_DSN = os.environ.get('SENTRY_DSN', '')
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
        environment='production',
    )

# Static files - use whitenoise for Cloud Run
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
