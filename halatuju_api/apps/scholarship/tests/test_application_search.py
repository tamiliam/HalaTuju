"""
Search on the B40 admin applications list.

The endpoint accepts ``?q=`` — a case-insensitive substring matched against the
applicant's name or NRIC (read from the linked StudentProfile). Search composes
with the existing status/bucket/assigned filters and pagination.
"""
import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
ADMIN = 'admin-uid'


def _token(uid):
    return jwt.encode(
        {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
        TEST_JWT_SECRET, algorithm='HS256',
    )


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class ApplicationSearchTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = PartnerAdmin.objects.create(
            supabase_user_id=ADMIN, is_super_admin=True, is_active=True,
            name='Admin', email='admin@example.com',
        )
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

        def mk(uid, name, nric, status='shortlisted', bucket='A', phone='', email=''):
            prof = StudentProfile.objects.create(
                supabase_user_id=uid, name=name, nric=nric,
                contact_phone=phone, contact_email=email,
            )
            return ScholarshipApplication.objects.create(
                cohort=cls.cohort, profile=prof, status=status, bucket=bucket,
            )

        mk('s1', 'Shuhan Raj A/L Loganathen', '080918-08-1813',
           phone='+60 12-345 6789', email='shuhan.b40@mailtest.org')
        mk('s2', 'THARUN A/L JAYAKUMAR', '070707-07-0707', status='submitted')
        mk('s3', 'Aisyah Binti Ali', '060606-06-0606')

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(ADMIN)}')

    def _names(self, body):
        return sorted(a['name'] for a in body['applications'])

    def test_search_by_name(self):
        body = self.client.get('/api/v1/admin/scholarship/applications/?q=shuhan').json()
        self.assertEqual(body['count'], 1)
        # The list serializer renders names uppercased.
        self.assertEqual(body['applications'][0]['name'], 'SHUHAN RAJ A/L LOGANATHEN')

    def test_search_by_nric(self):
        body = self.client.get('/api/v1/admin/scholarship/applications/?q=070707').json()
        self.assertEqual(body['count'], 1)
        self.assertEqual(body['applications'][0]['name'], 'THARUN A/L JAYAKUMAR')

    def test_search_by_phone(self):
        body = self.client.get('/api/v1/admin/scholarship/applications/?q=345 6789').json()
        self.assertEqual(body['count'], 1)
        self.assertEqual(body['applications'][0]['name'], 'SHUHAN RAJ A/L LOGANATHEN')

    def test_search_by_email(self):
        body = self.client.get('/api/v1/admin/scholarship/applications/?q=mailtest.org').json()
        self.assertEqual(body['count'], 1)
        self.assertEqual(body['applications'][0]['name'], 'SHUHAN RAJ A/L LOGANATHEN')

    def test_search_case_insensitive(self):
        body = self.client.get('/api/v1/admin/scholarship/applications/?q=AISYAH').json()
        self.assertEqual(body['count'], 1)

    def test_search_no_match(self):
        body = self.client.get('/api/v1/admin/scholarship/applications/?q=zzzznope').json()
        self.assertEqual(body['count'], 0)
        self.assertEqual(body['applications'], [])

    def test_blank_q_returns_all(self):
        body = self.client.get('/api/v1/admin/scholarship/applications/?q=').json()
        self.assertEqual(body['count'], 3)

    def test_search_composes_with_status_filter(self):
        # "a" matches all three names, but only one is 'submitted'.
        body = self.client.get(
            '/api/v1/admin/scholarship/applications/?q=a&status=submitted').json()
        self.assertEqual(body['count'], 1)
        self.assertEqual(body['applications'][0]['name'], 'THARUN A/L JAYAKUMAR')
