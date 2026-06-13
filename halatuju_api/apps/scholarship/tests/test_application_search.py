"""
Search on the B40 admin applications list.

The endpoint accepts ``?q=`` — a case-insensitive substring matched against the
applicant's name, NRIC, phone, and email. Email covers BOTH homes (the profile's
contact_email AND the application's notify_email — most applicants only have the
latter). Phone and NRIC are matched digits-only on both sides, so a stored
"016-243 9706" / "710829-02-5709" is found by a plain-digit search. Search composes
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

        def mk(uid, name, nric, status='shortlisted', bucket='A', phone='', email='',
               notify_email=''):
            prof = StudentProfile.objects.create(
                supabase_user_id=uid, name=name, nric=nric,
                contact_phone=phone, contact_email=email,
            )
            return ScholarshipApplication.objects.create(
                cohort=cls.cohort, profile=prof, status=status, bucket=bucket,
                notify_email=notify_email,
            )

        mk('s1', 'Shuhan Raj A/L Loganathen', '080918-08-1813',
           phone='+60 12-345 6789', email='shuhan.b40@mailtest.org')
        # THARUN mirrors the real bug: email only in notify_email, contact_email blank.
        mk('s2', 'THARUN A/L JAYAKUMAR', '070707-07-0707', status='submitted',
           notify_email='tharun@notifyonly.test')
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

    def test_search_by_notify_email_when_contact_email_blank(self):
        # Regression: most applicants have an email only in notify_email; the search
        # used to look at contact_email alone, so 67% were unsearchable by email.
        body = self.client.get(
            '/api/v1/admin/scholarship/applications/?q=notifyonly.test').json()
        self.assertEqual(body['count'], 1)
        self.assertEqual(body['applications'][0]['name'], 'THARUN A/L JAYAKUMAR')

    def test_search_by_phone_digits_only(self):
        # Stored "+60 12-345 6789"; officer types plain digits — must still match.
        body = self.client.get(
            '/api/v1/admin/scholarship/applications/?q=0123456789').json()
        self.assertEqual(body['count'], 1)
        self.assertEqual(body['applications'][0]['name'], 'SHUHAN RAJ A/L LOGANATHEN')

    def test_search_by_nric_digits_only(self):
        # Stored "080918-08-1813"; a dash-less search must still match.
        body = self.client.get(
            '/api/v1/admin/scholarship/applications/?q=080918081813').json()
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
