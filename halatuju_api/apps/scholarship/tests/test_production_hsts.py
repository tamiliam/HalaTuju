"""SEC-12 / TD-520 (A1.9): the API pins HTTPS for a year, still without preload or subdomains.

Loaded in a SUBPROCESS for the reason `test_db_health_checks.py` gives: importing `production`
in-process mutates the shared MIDDLEWARE list the test run is using.
"""
import json
import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase

_LOAD = (
    'import json, halatuju.settings.production as p; '
    'print(json.dumps([p.SECURE_HSTS_SECONDS, p.SECURE_HSTS_INCLUDE_SUBDOMAINS, p.SECURE_HSTS_PRELOAD]))'
)


class ProductionHsts(SimpleTestCase):

    def test_one_year_no_preload_no_subdomains(self):
        env = {k: v for k, v in os.environ.items() if k not in ('SENTRY_DSN', 'DJANGO_SETTINGS_MODULE')}
        env.update({'SECRET_KEY': 'test-only-not-a-secret', 'DB_HOST': 'db.example.invalid', 'DATABASE_URL': ''})
        out = subprocess.run([sys.executable, '-c', _LOAD], cwd=str(settings.BASE_DIR), env=env,
                             capture_output=True, text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr)
        seconds, subdomains, preload = json.loads(out.stdout.strip().splitlines()[-1])
        self.assertEqual(seconds, 60 * 60 * 24 * 365)
        self.assertIs(subdomains, False)
        self.assertIs(preload, False)
