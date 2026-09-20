"""Access audit on the admin applicant-record read (security item D).

Opening a single applicant's detail must emit ONE structured log line carrying the
admin id + application id. A Cloud Logging metric counts these per admin, and an
alert fires if one admin reads more than 30 records in 10 minutes (the scrape
signal). The line must contain a row pk only — never the applicant's name/NRIC.
"""
import importlib
import logging
import pkgutil

import jwt
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
ADMIN = 'admin-uid'
AUDIT_LOGGER = 'apps.scholarship.views_admin'


def _token(uid):
    return jwt.encode(
        {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
        TEST_JWT_SECRET, algorithm='HS256',
    )


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class AccessAuditTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = PartnerAdmin.objects.create(
            supabase_user_id=ADMIN, is_super_admin=True, is_active=True,
            name='Admin', email='admin@example.com',
        )
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        prof = StudentProfile.objects.create(
            supabase_user_id='s1', name='Shuhan Raj A/L Loganathen', nric='080918-08-1813',
        )
        cls.app = ScholarshipApplication.objects.create(
            cohort=cls.cohort, profile=prof, status='shortlisted', bucket='A',
        )

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(ADMIN)}')

    def test_detail_read_emits_one_audit_line_with_ids(self):
        with self.assertLogs(AUDIT_LOGGER, level='INFO') as cm:
            resp = self.client.get(f'/api/v1/admin/scholarship/applications/{self.app.pk}/')
        self.assertEqual(resp.status_code, 200)
        audit = [m for m in cm.output if 'applicant_detail_read' in m]
        self.assertEqual(len(audit), 1, cm.output)
        line = audit[0]
        self.assertIn(f'admin_id={self.admin.id}', line)
        self.assertIn(f'app_id={self.app.pk}', line)

    def test_audit_line_carries_no_pii(self):
        with self.assertLogs(AUDIT_LOGGER, level='INFO') as cm:
            self.client.get(f'/api/v1/admin/scholarship/applications/{self.app.pk}/')
        line = next(m for m in cm.output if 'applicant_detail_read' in m)
        # Never leak name/NRIC into the access log (it ships to Cloud Logging).
        self.assertNotIn('Shuhan', line)
        self.assertNotIn('080918', line)

    def test_denied_read_emits_no_audit_line(self):
        # A partner has no B40 access — a 403 must NOT produce a read-audit line.
        PartnerAdmin.objects.create(
            supabase_user_id='partner-uid', role='partner', is_active=True,
            name='Partner', email='partner@example.com',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("partner-uid")}')
        # assertLogs fails if nothing logs, so log a sentinel and assert only it appears.
        with self.assertLogs(AUDIT_LOGGER, level='INFO') as cm:
            resp = self.client.get(f'/api/v1/admin/scholarship/applications/{self.app.pk}/')
            logging.getLogger(AUDIT_LOGGER).info('sentinel')
        self.assertEqual(resp.status_code, 403)
        self.assertFalse([m for m in cm.output if 'applicant_detail_read' in m])


class AuditLoggerNameTest(SimpleTestCase):
    """EVERY module of the `views_admin` package must log under the PACKAGE's name.

    ⚠ ADDED AT CODE HEALTH H11 (2026-09-20) BECAUSE A BITE-CHECK CAME BACK SILENT. The H11
    brief named this as a known trip-wire — "twelve `assertLogs('apps.scholarship.views_admin')`
    sites break on a new logger name" — and switching a submodule to `logging.getLogger(__name__)`
    turned NONE of them red. It cannot: `assertLogs` on a parent records everything that
    propagates up from its children, and every one of those tests then matches on the MESSAGE,
    not on the logger. So the belief that the suite was holding the audit stream together was
    wrong, and had been wrong all along.

    The damage a submodule logger would do is not in the tests, it is in production: the
    Cloud Logging metric this file's docstring describes counts lines by logger name, and an
    audit line arriving as `apps.scholarship.views_admin.intake_years` is a line the scrape
    alert never sees. One name, one stream, one metric.
    """

    PACKAGE = 'apps.scholarship.views_admin'

    def _submodule_loggers(self):
        views_admin = importlib.import_module(self.PACKAGE)
        for info in pkgutil.iter_modules(views_admin.__path__):
            module = importlib.import_module(f'{self.PACKAGE}.{info.name}')
            found = getattr(module, 'logger', None)
            if isinstance(found, logging.Logger):
                yield info.name, found

    def test_every_submodule_logs_under_the_package_name(self):
        wrong = [f'{name}: logs as "{lg.name}"'
                 for name, lg in self._submodule_loggers() if lg.name != AUDIT_LOGGER]
        self.assertEqual(
            wrong, [],
            f'A module in {self.PACKAGE} binds a logger of its own name. Write the package name '
            f'out in full — `logging.getLogger("{AUDIT_LOGGER}")` — never `__name__`, which in a '
            f'submodule reads `{AUDIT_LOGGER}.<module>` and drops every line it carries out of '
            f'the audit metric.\n' + '\n'.join(wrong))

    def test_the_scan_actually_found_some(self):
        """THE FLOOR. If the package is ever renamed or flattened, the loop above would find
        nothing and pass for ever while watching nothing — the same failure this arc keeps
        meeting. Three is well under the number that carry a logger today."""
        found = list(self._submodule_loggers())
        self.assertGreaterEqual(
            len(found), 3,
            f'Fewer than three {self.PACKAGE} submodules were found to carry a logger '
            f'({[n for n, _ in found]}). Either the package moved or this guard stopped '
            f'seeing it, and it is now vacuous.')
