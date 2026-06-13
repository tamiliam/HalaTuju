"""
Tests for search + filter on the partner admin students list.

The list endpoint accepts ``?q=`` (name / NRIC / phone / email, case-insensitive;
phone+NRIC matched digits-only so separators never block a hit; email also covers
the student's application notify_email), ``?exam=`` (spm|stpm) and ``?source=`` (an
exact referral_source), and returns the distinct ``source_options`` for the filter
dropdown. Filters compose with the existing server-side pagination.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort

SUPER_UID = 'super-admin-uid'


@override_settings(ROOT_URLCONF='halatuju.urls')
class StudentSearchFilterTest(TestCase):
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
            supabase_user_id=SUPER_UID, email='super@halatuju.com',
            name='Super', is_super_admin=True,
        )

        def mk(uid, name, nric, exam, source, phone='', email=''):
            return StudentProfile.objects.create(
                supabase_user_id=uid, name=name, nric=nric,
                exam_type=exam, referral_source=source,
                contact_phone=phone, contact_email=email,
            )

        mk('u1', 'Aisyah Binti Ali', '050101-01-0001', 'spm', 'whatsapp',
           phone='+60 11-1077 0412', email='aisyah.smc@mailtest.org')
        mk('u2', 'Bala A/L Raju', '040202-02-0002', 'stpm', 'google')
        chong = mk('u3', 'Chong Wei', '030303-03-0003', 'spm', 'whatsapp')
        mk('u4', 'Aisha Khan', '020404-04-0004', 'stpm', 'cumig')
        mk('u5', 'Devi A/P Suren', '010505-05-0005', 'spm', '')  # blank source

        # Chong has no contact_email but applied for B40 — his email lives in the
        # application's notify_email (the real-data shape the search must cover).
        cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        ScholarshipApplication.objects.create(
            cohort=cohort, profile=chong, status='shortlisted', bucket='A',
            notify_email='chong.notify@dirtest.org',
        )

    def tearDown(self):
        self._decode_patcher.stop()
        self._header_patcher.stop()

    def _names(self, body):
        return sorted(s['name'] for s in body['students'])

    def test_search_by_name_substring(self):
        body = self.client.get('/api/v1/admin/students/?q=ais').json()
        # "Aisyah Binti Ali" + "Aisha Khan", case-insensitive.
        self.assertEqual(body['count'], 2)
        self.assertEqual(self._names(body), ['Aisha Khan', 'Aisyah Binti Ali'])

    def test_search_by_nric_substring(self):
        body = self.client.get('/api/v1/admin/students/?q=030303').json()
        self.assertEqual(body['count'], 1)
        self.assertEqual(body['students'][0]['name'], 'Chong Wei')

    def test_search_by_phone(self):
        body = self.client.get('/api/v1/admin/students/?q=1077 0412').json()
        self.assertEqual(body['count'], 1)
        self.assertEqual(body['students'][0]['name'], 'Aisyah Binti Ali')

    def test_search_by_email(self):
        body = self.client.get('/api/v1/admin/students/?q=mailtest.org').json()
        self.assertEqual(body['count'], 1)
        self.assertEqual(body['students'][0]['name'], 'Aisyah Binti Ali')

    def test_search_by_phone_digits_only(self):
        # Stored "+60 11-1077 0412"; a plain-digit search must still match.
        body = self.client.get('/api/v1/admin/students/?q=01110770412').json()
        self.assertEqual(body['count'], 1)
        self.assertEqual(body['students'][0]['name'], 'Aisyah Binti Ali')

    def test_search_by_nric_digits_only(self):
        # Stored "030303-03-0003"; a dash-less search must still match.
        body = self.client.get('/api/v1/admin/students/?q=030303030003').json()
        self.assertEqual(body['count'], 1)
        self.assertEqual(body['students'][0]['name'], 'Chong Wei')

    def test_search_by_application_notify_email(self):
        # Email lives only in the B40 application's notify_email (contact_email blank).
        body = self.client.get('/api/v1/admin/students/?q=dirtest.org').json()
        self.assertEqual(body['count'], 1)
        self.assertEqual(body['students'][0]['name'], 'Chong Wei')

    def test_filter_by_exam(self):
        body = self.client.get('/api/v1/admin/students/?exam=stpm').json()
        self.assertEqual(body['count'], 2)
        self.assertEqual(self._names(body), ['Aisha Khan', 'Bala A/L Raju'])

    def test_invalid_exam_is_ignored(self):
        body = self.client.get('/api/v1/admin/students/?exam=diploma').json()
        self.assertEqual(body['count'], 5)

    def test_filter_by_source(self):
        body = self.client.get('/api/v1/admin/students/?source=whatsapp').json()
        self.assertEqual(body['count'], 2)
        self.assertEqual(self._names(body), ['Aisyah Binti Ali', 'Chong Wei'])

    def test_source_options_distinct_sorted_no_blanks(self):
        body = self.client.get('/api/v1/admin/students/').json()
        self.assertEqual(body['source_options'], ['cumig', 'google', 'whatsapp'])

    def test_filters_compose(self):
        body = self.client.get('/api/v1/admin/students/?exam=spm&source=whatsapp').json()
        self.assertEqual(body['count'], 2)
        body = self.client.get('/api/v1/admin/students/?q=chong&source=whatsapp').json()
        self.assertEqual(body['count'], 1)
        self.assertEqual(body['students'][0]['name'], 'Chong Wei')

    def test_source_options_stable_under_filtering(self):
        # The dropdown lists every visible source, not just those on the
        # filtered result set.
        body = self.client.get('/api/v1/admin/students/?exam=stpm').json()
        self.assertEqual(body['source_options'], ['cumig', 'google', 'whatsapp'])
