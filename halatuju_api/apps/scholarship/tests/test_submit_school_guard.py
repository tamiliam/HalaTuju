"""A blank school never wipes the stored one at submit, and a submit with no school anywhere is
refused with a field error on `school` (6 live applications had lost their school)."""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import StudentProfile
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.services.profile_sync import sync_profile_fields
from apps.scholarship.tests.factories import make_cohort, make_student
from apps.scholarship.tests.test_api import TEST_JWT_SECRET, _make_token

USER = 'school-guard-user'


class TestSyncKeepsSchool(TestCase):
    def test_blank_or_whitespace_never_overwrites(self):
        p = make_student(supabase_user_id='sg-sync', school='SMK Contoh')
        for blank in ('', '   '):
            sync_profile_fields(p, {'school': blank})
            p.refresh_from_db()
            self.assertEqual(p.school, 'SMK Contoh')

    def test_a_non_blank_school_still_changes_it(self):
        p = make_student(supabase_user_id='sg-sync2', school='')
        self.assertEqual(sync_profile_fields(p, {'school': 'SMK Contoh'}), ['school'])
        sync_profile_fields(p, {'school': 'SMK Lain'})
        p.refresh_from_db()
        self.assertEqual(p.school, 'SMK Lain')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestSubmitSchool(TestCase):
    URL = '/api/v1/scholarship/applications/'

    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort(code='b40-2026', name='B40 2026', year=2026, income_ceiling=5250)

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_make_token(USER)}')

    def _post(self, **over):
        body = {'household_income': 2500, 'receives_str': True, 'consent_to_contact': True}
        body.update(over)
        return self.client.post(self.URL, body, format='json')

    def _school(self):
        return StudentProfile.objects.get(supabase_user_id=USER).school

    def test_blank_sent_keeps_the_stored_school(self):
        make_student(supabase_user_id=USER, nric='080101-14-1234', school='SMK Contoh')
        resp = self._post(school='')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(self._school(), 'SMK Contoh')

    def test_omitted_keeps_the_stored_school(self):
        make_student(supabase_user_id=USER, nric='080101-14-1234', school='SMK Contoh')
        self.assertEqual(self._post().status_code, 201)
        self.assertEqual(self._school(), 'SMK Contoh')

    def test_a_new_school_sent_replaces_it(self):
        make_student(supabase_user_id=USER, nric='080101-14-1234', school='SMK Contoh')
        self.assertEqual(self._post(school='SMK Lain').status_code, 201)
        self.assertEqual(self._school(), 'SMK Lain')

    def test_no_school_anywhere_is_a_400_on_school(self):
        make_student(supabase_user_id=USER, nric='080101-14-1234', school='')
        for sent in ({}, {'school': ''}, {'school': '   '}):
            resp = self._post(**sent)
            self.assertEqual(resp.status_code, 400, sent)
            self.assertIn('school', resp.json())
        self.assertFalse(ScholarshipApplication.objects.filter(profile_id=USER).exists())

    def test_no_school_stored_but_one_sent_is_accepted(self):
        make_student(supabase_user_id=USER, nric='080101-14-1234', school='')
        self.assertEqual(self._post(school='SMK Contoh').status_code, 201)
        self.assertEqual(self._school(), 'SMK Contoh')
