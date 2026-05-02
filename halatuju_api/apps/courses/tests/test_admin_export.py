"""
Tests for the partner admin CSV export.

Covers:
- The full column set (27 columns) added when the export was extended to
  carry every field admins see in the dashboard detail view.
- Email + last sign-in joined from Supabase Auth's auth.users.
- Safety net: auth-table query failure must not break the export.
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

EXPECTED_HEADER = [
    'Name', 'IC', 'Angka Giliran', 'Email', 'Phone', 'School',
    'Gender', 'Nationality',
    'Address', 'Postal Code', 'City', 'State',
    'Family Income', 'Siblings', 'Colorblind', 'Disability',
    'Exam Type', 'SPM Grades', 'STPM Grades', 'STPM CGPA', 'MUET Band',
    'Financial Pressure', 'Travel Willingness',
    'Referral Source', 'Referred By Org',
    'Date Joined', 'Last Sign-In',
]


@override_settings(ROOT_URLCONF='halatuju.urls')
class PartnerStudentExportExpandedColumnsTest(TestCase):
    """Export CSV must carry the full StudentProfile field set."""

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
            angka_giliran='AB123C456',
            phone='012-3456789',
            school='SMK Damansara Jaya',
            gender='female',
            nationality='Warganegara',
            address='12 Jalan Mawar',
            postal_code='47301',
            city='Petaling Jaya',
            preferred_state='Selangor',
            family_income='B40',
            siblings=3,
            colorblind=False,
            disability=False,
            exam_type='spm',
            grades={'bm': 'A', 'eng': 'B+', 'math': 'A'},
            financial_pressure='high',
            travel_willingness='nationwide',
            referral_source='whatsapp',
            referred_by_org=self.org,
        )
        StudentProfile.objects.create(
            supabase_user_id='student-uid-stpm',
            nric='020202-02-2222',
            name='Chong Mei Ling',
            exam_type='stpm',
            stpm_grades={'PA': 'A', 'MATH_T': 'B+'},
            stpm_cgpa=3.67,
            muet_band=4,
            disability=True,
            colorblind=True,
            referred_by_org=self.org,
        )
        StudentProfile.objects.create(
            supabase_user_id='student-uid-ghost',
            nric='',
            name='',
            referred_by_org=self.org,
        )

    def tearDown(self):
        self._decode_patcher.stop()
        self._header_patcher.stop()

    def _read_csv(self, response):
        return list(csv.reader(StringIO(response.content.decode())))

    def _row_for(self, rows, name):
        idx_name = EXPECTED_HEADER.index('Name')
        return next(r for r in rows[1:] if r[idx_name] == name)

    def test_header_is_full_27_columns(self):
        with patch('apps.courses.views_admin._fetch_auth_data', return_value={}):
            response = self.client.get('/api/v1/admin/students/export/')
        self.assertEqual(response.status_code, 200)
        rows = self._read_csv(response)
        self.assertEqual(rows[0], EXPECTED_HEADER)

    def test_full_profile_fields_render_correctly(self):
        with patch('apps.courses.views_admin._fetch_auth_data', return_value={
            'student-uid-1': {'email': 'anita@example.com', 'last_sign_in': '2026-04-30'},
        }):
            response = self.client.get('/api/v1/admin/students/export/')
        rows = self._read_csv(response)
        anita = self._row_for(rows, 'Anita Rao')
        get = lambda col: anita[EXPECTED_HEADER.index(col)]
        self.assertEqual(get('IC'), '010101-01-1111')
        self.assertEqual(get('Angka Giliran'), 'AB123C456')
        self.assertEqual(get('Email'), 'anita@example.com')
        self.assertEqual(get('Phone'), '012-3456789')
        self.assertEqual(get('School'), 'SMK Damansara Jaya')
        self.assertEqual(get('Nationality'), 'Warganegara')
        self.assertEqual(get('Address'), '12 Jalan Mawar')
        self.assertEqual(get('Postal Code'), '47301')
        self.assertEqual(get('City'), 'Petaling Jaya')
        self.assertEqual(get('State'), 'Selangor')
        self.assertEqual(get('Family Income'), 'B40')
        self.assertEqual(get('Siblings'), '3')
        self.assertEqual(get('Colorblind'), 'No')
        self.assertEqual(get('Disability'), 'No')
        self.assertIn('"bm":"A"', get('SPM Grades'))
        self.assertEqual(get('Financial Pressure'), 'high')
        self.assertEqual(get('Travel Willingness'), 'nationwide')
        self.assertEqual(get('Referral Source'), 'whatsapp')
        self.assertEqual(get('Referred By Org'), 'CUMIG')
        self.assertEqual(get('Last Sign-In'), '2026-04-30')

    def test_stpm_specific_columns(self):
        with patch('apps.courses.views_admin._fetch_auth_data', return_value={}):
            response = self.client.get('/api/v1/admin/students/export/')
        rows = self._read_csv(response)
        chong = self._row_for(rows, 'Chong Mei Ling')
        get = lambda col: chong[EXPECTED_HEADER.index(col)]
        self.assertEqual(get('Exam Type'), 'stpm')
        self.assertIn('"PA":"A"', get('STPM Grades'))
        self.assertEqual(get('STPM CGPA'), '3.67')
        self.assertEqual(get('MUET Band'), '4')
        self.assertEqual(get('Disability'), 'Yes')
        self.assertEqual(get('Colorblind'), 'Yes')
        self.assertEqual(get('SPM Grades'), '')

    def test_ghost_row_renders_blanks_not_errors(self):
        with patch('apps.courses.views_admin._fetch_auth_data', return_value={}):
            response = self.client.get('/api/v1/admin/students/export/')
        rows = self._read_csv(response)
        ghost = next(r for r in rows[1:] if r[EXPECTED_HEADER.index('IC')] == '' and r[EXPECTED_HEADER.index('Name')] == '')
        self.assertEqual(ghost[EXPECTED_HEADER.index('Email')], '')
        self.assertEqual(ghost[EXPECTED_HEADER.index('Siblings')], '')
        self.assertEqual(ghost[EXPECTED_HEADER.index('SPM Grades')], '')

    def test_auth_query_failure_does_not_break_export(self):
        # auth.users does not exist in the test DB, so the real call raises
        # and is swallowed. Export must still return a valid CSV.
        response = self.client.get('/api/v1/admin/students/export/')
        self.assertEqual(response.status_code, 200)
        rows = self._read_csv(response)
        self.assertEqual(rows[0], EXPECTED_HEADER)
        for row in rows[1:]:
            self.assertEqual(row[EXPECTED_HEADER.index('Email')], '')
            self.assertEqual(row[EXPECTED_HEADER.index('Last Sign-In')], '')
