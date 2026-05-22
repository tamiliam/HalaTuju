"""Tests for STEP 2 deeper-info + funding need + completeness (Sprint 4a)."""
import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import StudentProfile
from apps.scholarship.models import FundingNeed, ScholarshipApplication, ScholarshipCohort
from apps.scholarship.services import application_completeness

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
USER_A = 'detail-user-a'
USER_B = 'detail-user-b'


def _token(uid, secret=TEST_JWT_SECRET):
    return jwt.encode(
        {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
        secret, algorithm='HS256',
    )


class TestFundingNeedModel(TestCase):
    def setUp(self):
        self.cohort = ScholarshipCohort.objects.create(code='c', name='P', year=2026)
        self.profile = StudentProfile.objects.create(supabase_user_id='m1', nric='080101-14-1234')
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='shortlisted',
        )

    def test_total_defaults_zero(self):
        self.assertEqual(FundingNeed.objects.create(application=self.app).total, 0)

    def test_total_sums_line_items_with_allowance(self):
        fn = FundingNeed.objects.create(
            application=self.app, tuition_gap=1000, laptop=2000, books=500,
            monthly_allowance=300, allowance_months=10, other=200,
        )
        self.assertEqual(fn.total, 1000 + 2000 + 500 + 300 * 10 + 200)  # 6700


class TestCompleteness(TestCase):
    def setUp(self):
        self.cohort = ScholarshipCohort.objects.create(code='c', name='P', year=2026)
        self.profile = StudentProfile.objects.create(supabase_user_id='m2', nric='080101-14-2222')
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='shortlisted',
        )

    def test_all_incomplete_initially(self):
        self.assertEqual(
            application_completeness(self.app),
            {'quiz_done': False, 'details_done': False, 'funding_done': False, 'complete': False},
        )

    def test_quiz_done_from_signals(self):
        self.profile.student_signals = {'field_interest': {'it': 5}}
        self.profile.save()
        self.assertTrue(application_completeness(self.app)['quiz_done'])

    def test_complete_when_all_present(self):
        self.profile.student_signals = {'x': {'y': 1}}
        self.profile.save()
        self.app.aspirations = 'Be an accountant'
        self.app.justification = 'Family cannot fund'
        self.app.save()
        FundingNeed.objects.create(application=self.app, laptop=2000)
        self.assertTrue(application_completeness(self.app)['complete'])


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestDetailsApi(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40 Programme', year=2026)
        cls.cohort2 = ScholarshipCohort.objects.create(code='c2', name='B40 Programme 2', year=2025)
        cls.profile_a = StudentProfile.objects.create(supabase_user_id=USER_A, nric='080101-14-1234')
        cls.profile_b = StudentProfile.objects.create(supabase_user_id=USER_B, nric='080202-14-5678')
        cls.app_a = ScholarshipApplication.objects.create(
            cohort=cls.cohort, profile=cls.profile_a, status='shortlisted', bucket='A',
        )
        cls.app_b = ScholarshipApplication.objects.create(
            cohort=cls.cohort, profile=cls.profile_b, status='shortlisted', bucket='A',
        )
        # rejected app for profile_a — in a different cohort to satisfy the unique constraint
        cls.rejected_a = ScholarshipApplication.objects.create(
            cohort=cls.cohort2, profile=cls.profile_a, status='rejected',
        )

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def test_patch_saves_details_and_funding(self):
        self._auth(USER_A)
        resp = self.client.patch(
            f'/api/v1/scholarship/applications/{self.app_a.id}/',
            {
                'aspirations': 'Become an auditor', 'justification': 'Low income family',
                'funding_need': {'laptop': 2000, 'monthly_allowance': 300, 'allowance_months': 10},
            }, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['aspirations'], 'Become an auditor')
        self.assertEqual(body['funding_need']['total'], 2000 + 300 * 10)
        self.assertTrue(body['completeness']['details_done'])
        self.assertTrue(body['completeness']['funding_done'])
        self.assertFalse(body['completeness']['quiz_done'])  # no quiz signals yet

    def test_patch_funding_idempotent_update(self):
        self._auth(USER_A)
        url = f'/api/v1/scholarship/applications/{self.app_a.id}/'
        self.client.patch(url, {'funding_need': {'laptop': 2000}}, format='json')
        resp = self.client.patch(url, {'funding_need': {'laptop': 3500}}, format='json')
        self.assertEqual(resp.json()['funding_need']['laptop'], 3500)
        self.assertEqual(FundingNeed.objects.filter(application=self.app_a).count(), 1)

    def test_patch_rejected_is_forbidden(self):
        self._auth(USER_A)
        resp = self.client.patch(
            f'/api/v1/scholarship/applications/{self.rejected_a.id}/',
            {'aspirations': 'x'}, format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_patch_cross_user_404(self):
        self._auth(USER_A)
        resp = self.client.patch(
            f'/api/v1/scholarship/applications/{self.app_b.id}/',
            {'aspirations': 'x'}, format='json',
        )
        self.assertEqual(resp.status_code, 404)

    def test_get_includes_completeness_and_funding(self):
        self._auth(USER_A)
        resp = self.client.get(f'/api/v1/scholarship/applications/{self.app_a.id}/')
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn('completeness', body)
        self.assertIn('funding_need', body)

    def test_patch_requires_auth(self):
        resp = self.client.patch(
            f'/api/v1/scholarship/applications/{self.app_a.id}/',
            {'aspirations': 'x'}, format='json',
        )
        self.assertEqual(resp.status_code, 401)
