"""Django settings for the replay job ONLY (`DJANGO_SETTINGS_MODULE=replay.settings` in the image).

The tree's own `halatuju.settings.base`, then:
  * the database from `REPLAY_DATABASE_URL` alone (the `replay_ro` role, session pooler), no persistent
    connection;
  * every setting whose name says KEY / SECRET / TOKEN / PASSWORD / DSN blanked (SECRET_KEY gets a random
    throwaway), so even a key that slipped into the environment is not used;
  * a refusing email backend; DEBUG off; logging off (the harness prints only scrubbed lines).
Not used by the tests or the live service.
"""
import os
import secrets

from halatuju.settings import base as _base

globals().update({k: v for k, v in vars(_base).items() if k.isupper()})

_SECRET_WORDS = ('KEY', 'SECRET', 'TOKEN', 'PASSWORD', 'DSN', 'CREDENTIAL')
for _name in [k for k in list(globals()) if k.isupper() and any(w in k for w in _SECRET_WORDS)]:
    if isinstance(globals()[_name], str):
        globals()[_name] = ''
    elif isinstance(globals()[_name], dict):
        globals()[_name] = {k: '' for k in globals()[_name]}
SECRET_KEY = secrets.token_hex(32)

DEBUG = False
ALLOWED_HOSTS = []


def _database():
    import dj_database_url
    url = os.environ.get('REPLAY_DATABASE_URL', '')
    if not url:
        return {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}   # build checks only
    db = dj_database_url.parse(url, conn_max_age=0)
    db['CONN_HEALTH_CHECKS'] = False
    db['ATOMIC_REQUESTS'] = False
    return {'default': db}


DATABASES = _database()
EMAIL_BACKEND = __package__ + '.guards.RefusingEmailBackend'
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
LOGGING = {'version': 1, 'disable_existing_loggers': True,
           'handlers': {'null': {'class': 'logging.NullHandler'}},
           'root': {'handlers': ['null'], 'level': 'CRITICAL'}}
