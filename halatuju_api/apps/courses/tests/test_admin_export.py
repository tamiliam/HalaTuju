"""
Tests for the partner admin CSV export.

Covers the Email column added in Sprint follow-up to the students.csv investigation:
auth.users emails are joined into the export by supabase_user_id.
"""
import csv
from io import StringIO
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import (
    PartnerAdmin, PartnerOrganisation, StudentProfile,
)

SUPER_UID = 'super-admin-uid'


@override_settings(ROOT_URLCONF='halatuju.urls')
class PartnerStudentExportEmailColumnTest(TestCase):
    """Export CSV must include Email column populated from auth.users."""

    def setUp(self):
        self.client = APIClient()
        self._header_patcher = patch(
            'halatuju.middleware.supabase_auth.jwt.get_unverified_header',
            return_value={'alg': 'HS256'},
        )
        self._decode_patcher = patch(
            'halatuju.middleware.supabase_auth.jwt.decode',
            return_value={'sub': SUPER_UID, 'aud': 'authenticated', 'role': 'authenticated'},
        )
        self._header_patcher.start()
        self._decode_patcher.start()
        self.client.credentials(HTTP_AUTHORIZATION='Bearer fake-but-patched')

        PartnerAdmin.objects.create(
            supabase_user_id=SUPER_UID,
            email='super@halatuju.com',
            name='Super',
            is_super_admin=True,
        )
        StudentProfile.objects.create(
            supabase_user_id=SUPER_UID,
            nric='990101-01-9999',
            name='Super Admin Profile',
        )

        self.org = PartnerOrganisation.objects.create(code='cumig', name='CUMIG')
        StudentProfile.objects.create(
            supabase_user_id='student-uid-1',
            nric='010101-01-1111',
            name='Anita Rao',
            gender='female',
            preferred_state='Selangor',
            referred_by_org=self.org,
        )
        StudentProfile.objects.create(
            supabase_user_id='student-uid-2',
            nric='',
            name='',
            referred_by_org=self.org,
        )

    def tearDown(self):
        self._decode_patcher.stop()
        self._header_patcher.stop()

    def _read_csv(self, response):
        return list(csv.reader(StringIO(response.content.decode())))

    def test_header_includes_email(self):
        with patch(
            'apps.courses.views_admin._fetch_auth_emails',
            return_value={},
        ):
            response = self.client.get('/api/v1/admin/students/export/')
        self.assertEqual(response.status_code, 200)
        rows = self._read_csv(response)
        self.assertEqual(
            rows[0],
            ['Name', 'IC', 'Email', 'Gender', 'State', 'Exam Type', 'Date Joined'],
        )

    def test_email_is_joined_per_row(self):
        emails = {
            'student-uid-1': 'anita@example.com',
            'student-uid-2': 'ghost@example.com',
        }
        with patch(
            'apps.courses.views_admin._fetch_auth_emails',
            return_value=emails,
        ):
            response = self.client.get('/api/v1/admin/students/export/')
        rows = self._read_csv(response)
        by_uid_index = {row[0]: row for row in rows[1:]}
        anita_row = next(r for r in rows[1:] if r[0] == 'Anita Rao')
        ghost_row = next(r for r in rows[1:] if r[1] == '')
        self.assertEqual(anita_row[2], 'anita@example.com')
        self.assertEqual(ghost_row[2], 'ghost@example.com')

    def test_missing_email_renders_blank(self):
        with patch(
            'apps.courses.views_admin._fetch_auth_emails',
            return_value={'student-uid-1': 'anita@example.com'},
        ):
            response = self.client.get('/api/v1/admin/students/export/')
        rows = self._read_csv(response)
        ghost_row = next(r for r in rows[1:] if r[0] == '')
        self.assertEqual(ghost_row[2], '')

    def test_auth_users_query_failure_does_not_break_export(self):
        # auth.users does not exist in the test sqlite DB, so the real
        # _fetch_auth_emails call will raise inside the cursor and be
        # swallowed. Export must still return a valid CSV with blank emails.
        response = self.client.get('/api/v1/admin/students/export/')
        self.assertEqual(response.status_code, 200)
        rows = self._read_csv(response)
        self.assertEqual(rows[0][2], 'Email')
        for row in rows[1:]:
            self.assertEqual(row[2], '')
