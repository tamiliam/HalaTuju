"""
Django production settings for HalaTuju API.

Deployed on Cloud Run with Supabase PostgreSQL.
"""
import os
import dj_database_url
from .base import *

DEBUG = False

# Ensure SECRET_KEY is explicitly set in production (no insecure fallback)
if SECRET_KEY == 'django-insecure-dev-key-change-in-production':
    raise ValueError("SECRET_KEY environment variable must be set in production")

# Security settings
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')
ALLOWED_HOSTS = [h.strip() for h in ALLOWED_HOSTS if h.strip()]

CSRF_TRUSTED_ORIGINS = os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',')
CSRF_TRUSTED_ORIGINS = [o.strip() for o in CSRF_TRUSTED_ORIGINS if o.strip()]

# CORS settings — wildcard not allowed in production
_cors_origins = os.environ.get('CORS_ALLOWED_ORIGINS', '')
if _cors_origins == '*':
    raise ValueError(
        "CORS_ALLOWED_ORIGINS='*' is not allowed in production. "
        "Set explicit origins, e.g. 'https://halatuju.web.app,https://halatuju-web-xxxxx.run.app'"
    )
CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_origins.split(',') if o.strip()]

# Cloud Run terminates SSL
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = False  # Cloud Run handles this
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# HSTS (code-health S5): browsers pin HTTPS for 30 days. Conservative — no preload, no
# subdomain pinning (api/web live on their own hosts and are individually HTTPS-only).
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# Rate limits need a SHARED, PERSISTENT cache (code-health S5 #21). The default
# LocMemCache is per-gunicorn-worker, per-instance, and wiped on every cold start — so
# the 40/hour upload throttle (each upload = a billable Vision call) and the 3
# reports/day cap were effectively decorative on Cloud Run autoscale. The database cache
# is free-tier-friendly; the `django_cache` table is created migrate-first via the
# Supabase MCP (deploys don't run manage.py). Dev/test keep LocMemCache (no table needed).
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'django_cache',
    }
}

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

# Email — sent via an SMTP provider (Brevo), NOT a personal Gmail.
# Deploy must set EMAIL_HOST_USER / EMAIL_HOST_PASSWORD to the Brevo SMTP login + key,
# and verify the DEFAULT_FROM_EMAIL sender domain in Brevo. All values are env-driven so no
# personal address ever lives in code.
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp-relay.brevo.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'HalaTuju <noreply@halatuju.xyz>')
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://halatuju.xyz')
