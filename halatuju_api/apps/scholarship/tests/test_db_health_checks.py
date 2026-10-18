"""Org request #32 (2026-10-08): a dead persistent DB connection must be replaced, not reused.

The network link between Cloud Run and Supabase reset idle connections. `CONN_MAX_AGE = 600` kept
the dead one, and the next three requests 500'd with `connection already closed` / `SSL SYSCALL
error: EOF` (one per worker that held a dead connection). `CONN_HEALTH_CHECKS = True` makes the
first query of each request ping a reused connection and quietly reconnect if it is dead.

Two halves are pinned:
  * SETTINGS — `production.py` really carries it, on BOTH branches (`DB_HOST` and `DATABASE_URL`).
    Loaded in a SUBPROCESS: importing `production` in-process would mutate the shared `MIDDLEWARE`
    list the test run is using (it `insert`s whitenoise into the list `base.py` owns).
  * BEHAVIOUR — with the production values, Django's own request-start reset
    (`close_old_connections`) followed by a query DISCARDS a dead connection (and on Postgres
    reconnects); with the flag off the dead one is handed straight back to the view. No real Postgres is needed: the
    wrapper is the test database's own engine, and "dead" is `is_usable()` answering False, which
    is exactly what the psycopg2 backend's ping returns on a reset socket.
"""
import json
import os
import subprocess
import sys
from unittest import mock

from django.conf import settings
from django.db import connections
from django.test import SimpleTestCase

_LOAD = (
    'import json, halatuju.settings.production as p; '
    'd = p.DATABASES["default"]; '
    'print(json.dumps({"age": d.get("CONN_MAX_AGE"), "hc": d.get("CONN_HEALTH_CHECKS")}))'
)


def _production_db(**env_over):
    env = {k: v for k, v in os.environ.items() if k not in ('SENTRY_DSN', 'DJANGO_SETTINGS_MODULE')}
    # Empty, not absent: production reads them with `os.environ.get`, so '' is "not set".
    env.update({'SECRET_KEY': 'test-only-not-a-secret', 'DB_HOST': '', 'DATABASE_URL': ''})
    env.update(env_over)
    out = subprocess.run([sys.executable, '-c', _LOAD], cwd=str(settings.BASE_DIR), env=env,
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


class ProductionSettingsCarryHealthChecks(SimpleTestCase):

    def test_the_db_host_branch(self):
        db = _production_db(DB_HOST='db.example.invalid')
        self.assertIs(db['hc'], True)
        self.assertEqual(db['age'], 600)

    def test_the_database_url_branch(self):
        db = _production_db(DATABASE_URL='postgres://u:p@db.example.invalid:5432/postgres')
        self.assertIs(db['hc'], True)
        self.assertEqual(db['age'], 600)


class ADeadConnectionIsReplaced(SimpleTestCase):
    """Drives a private wrapper, never the shared test connection."""

    databases = {'default'}   # the probe opens its own connection to the test database

    def _wrapper(self, health_checks):
        base = connections['default']
        cfg = dict(base.settings_dict, CONN_MAX_AGE=600, CONN_HEALTH_CHECKS=health_checks)
        w = type(base)(cfg, alias='hc_probe')
        self.addCleanup(w.close)
        return w

    def _a_request_after_the_link_reset(self, w):
        """How many times Django DISCARDS the connection between request start and first query.

        Counted rather than compared by identity: on the in-memory SQLite test database (the
        `-n auto` run) Django's `close()` is a deliberate no-op, so the object never changes even
        though Django did decide to drop it. On Postgres that same `close()` is what forces the
        reconnect the next line then makes."""
        w.ensure_connection()
        with mock.patch.object(w, 'is_usable', return_value=False), \
                mock.patch.object(w, 'close', wraps=w.close) as close:
            w.close_if_unusable_or_obsolete()   # what `close_old_connections` does at request start
            self.assertEqual(close.call_count, 0, 'not yet old and no error: kept at request start')
            with w.cursor() as c:                 # the request's first query
                c.execute('SELECT 1')
        self.assertIsNotNone(w.connection)
        return close.call_count

    def test_with_health_checks_on_the_dead_connection_is_discarded(self):
        self.assertEqual(self._a_request_after_the_link_reset(self._wrapper(health_checks=True)), 1)

    def test_with_health_checks_off_the_dead_connection_reaches_the_view(self):
        # The 2026-10-08 behaviour. If this ever starts failing, Django changed underneath us and
        # the test above no longer proves the flag is what does the work.
        self.assertEqual(self._a_request_after_the_link_reset(self._wrapper(health_checks=False)), 0)
