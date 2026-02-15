"""
Django development settings for HalaTuju API.
"""
import os
from .base import *

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# CORS settings for local development
CORS_ALLOW_ALL_ORIGINS = True

# Database - Use DATABASE_URL if set, otherwise SQLite
DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    # Supabase PostgreSQL
    # Format: postgresql://postgres.PROJECT_REF:PASSWORD@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres
    import dj_database_url
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600)
    }
else:
    # SQLite for local development without Supabase
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Use simple logging format in development
LOGGING['handlers']['console']['formatter'] = 'simple'
