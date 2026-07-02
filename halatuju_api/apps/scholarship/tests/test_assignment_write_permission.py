"""Assignment-based review permission (2026-07).

A view-all 'admin' can WRITE only on the applications assigned to them (their READ scope stays
all); a reviewer writes only their assigned; super writes any; partner none. The write action
under test is the mentoring-candidate PATCH (a minimal per-application mutation) — it exercises
the shared ``_require_app_write`` gate that every per-application write now routes through.
"""
import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort

TEST_JWT_SECRET = 'test-supabase-jwt-secret'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestAssignmentBasedWrite(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superadmin = PartnerAdmin.objects.create(
            supabase_user_id='super-uid', is_super_admin=True, is_active=True,
            name='Super', email='super@example.com')
        cls.admin = PartnerAdmin.objects.create(
            supabase_user_id='admin-uid', role='admin', is_active=True,
            name='View-All Admin', email='admin@example.com')
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='rev-uid', role='reviewer', is_active=True,
            name='Reviewer', email='rev@example.com')
        cls.partner = PartnerAdmin.objects.create(
            supabase_user_id='partner-uid', role='partner', is_active=True,
            name='Partner', email='partner@example.com')
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        self.client = APIClient()
        p1 = StudentProfile.objects.create(supabase_user_id='s1', nric='030101-14-0001', name='A')
        p2 = StudentProfile.objects.create(supabase_user_id='s2', nric='030101-14-0002', name='B')
        # X assigned to the admin; Y assigned to the reviewer.
        self.appX = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p1, status='shortlisted',
            profile_completed_at=timezone.now(), assigned_to=self.admin)
        self.appY = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p2, status='shortlisted',
            profile_completed_at=timezone.now(), assigned_to=self.reviewer)

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _write(self, app):
        return self.client.patch(
            f'/api/v1/admin/scholarship/applications/{app.id}/',
            {'mentoring_candidate': True}, format='json')

    def _read(self, app):
        return self.client.get(f'/api/v1/admin/scholarship/applications/{app.id}/')

    # --- admin: reads all, writes only assigned ---------------------------------
    def test_admin_can_write_assigned(self):
        self._auth('admin-uid')
        self.assertEqual(self._write(self.appX).status_code, 200)
        self.appX.refresh_from_db()
        self.assertTrue(self.appX.mentoring_candidate)

    def test_admin_cannot_write_unassigned(self):
        self._auth('admin-uid')
        self.assertEqual(self._write(self.appY).status_code, 403)
        self.appY.refresh_from_db()
        self.assertFalse(self.appY.mentoring_candidate)

    def test_admin_reads_all_including_unassigned(self):
        self._auth('admin-uid')
        self.assertEqual(self._read(self.appX).status_code, 200)
        self.assertEqual(self._read(self.appY).status_code, 200)   # not assigned, but read-all

    # --- reviewer: assigned only (read + write) ---------------------------------
    def test_reviewer_can_write_assigned(self):
        self._auth('rev-uid')
        self.assertEqual(self._write(self.appY).status_code, 200)

    def test_reviewer_cannot_write_unassigned(self):
        self._auth('rev-uid')
        self.assertEqual(self._write(self.appX).status_code, 403)

    def test_reviewer_read_is_assigned_scoped(self):
        self._auth('rev-uid')
        self.assertEqual(self._read(self.appY).status_code, 200)
        self.assertEqual(self._read(self.appX).status_code, 403)

    # --- super: any -------------------------------------------------------------
    def test_super_can_write_any(self):
        self._auth('super-uid')
        self.assertEqual(self._write(self.appX).status_code, 200)
        self.assertEqual(self._write(self.appY).status_code, 200)

    # --- partner: no B40 at all -------------------------------------------------
    def test_partner_cannot_write(self):
        self._auth('partner-uid')
        self.assertEqual(self._write(self.appX).status_code, 403)

    def test_partner_cannot_read_b40(self):
        self._auth('partner-uid')
        self.assertEqual(self._read(self.appX).status_code, 403)

    # --- role endpoint exposes the caller's admin id (FE canWrite comparison) ---
    def test_role_endpoint_returns_admin_id(self):
        self._auth('admin-uid')
        r = self.client.get('/api/v1/admin/role/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['admin_id'], self.admin.id)
