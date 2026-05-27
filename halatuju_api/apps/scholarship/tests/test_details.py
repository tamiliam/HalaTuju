"""Tests for STEP 2 deeper-info + funding need + completeness (Sprint 4a)."""
import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import StudentProfile
from apps.scholarship.models import ApplicantDocument, FundingNeed, ScholarshipApplication, ScholarshipCohort
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
            {
                'quiz_done': False,
                'details_done': False,
                'funding_done': False,
                'documents_done': False,
                'complete': False,
            },
        )

    def test_quiz_done_from_signals(self):
        self.profile.student_signals = {'field_interest': {'it': 5}}
        self.profile.save()
        self.assertTrue(application_completeness(self.app)['quiz_done'])

    def test_complete_when_all_present(self):
        self.profile.student_signals = {'x': {'y': 1}}
        self.profile.save()
        self.app.aspirations = 'Be an accountant'
        self.app.plans = 'Study hard every day'
        self.app.save()
        # S3: funding_done requires at least one category, not a positive total
        FundingNeed.objects.create(application=self.app, categories=['living'])
        self.assertTrue(application_completeness(self.app)['complete'])

    def test_details_done_requires_aspirations_and_plans(self):
        # aspirations + plans both required — justification no longer counts
        self.app.aspirations = 'Be an engineer'
        self.app.plans = ''
        self.app.justification = 'Family cannot fund'
        self.app.save()
        self.assertFalse(application_completeness(self.app)['details_done'])

        self.app.aspirations = ''
        self.app.plans = 'Study hard'
        self.app.save()
        self.assertFalse(application_completeness(self.app)['details_done'])

        self.app.aspirations = 'Be an engineer'
        self.app.plans = 'Study hard'
        self.app.save()
        self.assertTrue(application_completeness(self.app)['details_done'])

    def test_documents_done_false_when_no_docs(self):
        """documents_done is False when no documents uploaded."""
        self.assertFalse(application_completeness(self.app)['documents_done'])

    def test_documents_done_false_when_only_ic(self):
        """documents_done is False when only IC is present (results_slip missing)."""
        ApplicantDocument.objects.create(application=self.app, doc_type='ic', storage_path='x')
        self.assertFalse(application_completeness(self.app)['documents_done'])

    def test_documents_done_true_when_both_compulsory_present(self):
        """documents_done is True when both ic and results_slip are uploaded."""
        ApplicantDocument.objects.create(application=self.app, doc_type='ic', storage_path='x')
        ApplicantDocument.objects.create(application=self.app, doc_type='results_slip', storage_path='y')
        self.assertTrue(application_completeness(self.app)['documents_done'])

    def test_complete_not_affected_by_documents_done(self):
        """complete is still quiz_done & details_done & funding_done — documents_done does not gate it."""
        self.profile.student_signals = {'x': {'y': 1}}
        self.profile.save()
        self.app.aspirations = 'Be an accountant'
        self.app.plans = 'Study hard every day'
        self.app.save()
        FundingNeed.objects.create(application=self.app, categories=['living'])
        result = application_completeness(self.app)
        # complete is True even without documents — S5 will add the documents gate
        self.assertTrue(result['complete'])
        self.assertFalse(result['documents_done'])


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
                'aspirations': 'Become an auditor', 'plans': 'Work hard every day',
                # S3: funding_done requires at least one category; include categories here
                'funding_need': {
                    'laptop': 2000, 'monthly_allowance': 300, 'allowance_months': 10,
                    'categories': ['device', 'living'],
                },
            }, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['aspirations'], 'Become an auditor')
        self.assertEqual(body['plans'], 'Work hard every day')
        self.assertEqual(body['funding_need']['total'], 2000 + 300 * 10)
        self.assertTrue(body['completeness']['details_done'])
        self.assertTrue(body['completeness']['funding_done'])
        self.assertFalse(body['completeness']['quiz_done'])  # no quiz signals yet

    def test_patch_saves_story_narrative_fields(self):
        """All 5 new Your story fields persist and read back."""
        self._auth(USER_A)
        resp = self.client.patch(
            f'/api/v1/scholarship/applications/{self.app_a.id}/',
            {
                'first_in_family': True,
                'parents_occupation': 'Factory worker',
                'siblings_studying': True,
                'family_context': 'Father ill; mother is the sole earner.',
                'daily_life': 'Wake at 5am, help at home, then school.',
            }, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body['first_in_family'])
        self.assertEqual(body['parents_occupation'], 'Factory worker')
        self.assertTrue(body['siblings_studying'])
        self.assertEqual(body['family_context'], 'Father ill; mother is the sole earner.')
        self.assertEqual(body['daily_life'], 'Wake at 5am, help at home, then school.')

    def test_story_fields_defaults_are_correct(self):
        """New boolean fields default False; text fields default empty string."""
        self._auth(USER_A)
        resp = self.client.get(f'/api/v1/scholarship/applications/{self.app_a.id}/')
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body['first_in_family'])
        self.assertFalse(body['siblings_studying'])
        self.assertEqual(body['parents_occupation'], '')
        self.assertEqual(body['family_context'], '')
        self.assertEqual(body['daily_life'], '')

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

    # ── S3: funding redesign fields ───────────────────────────────────────────

    def test_patch_saves_s3_funding_fields(self):
        """categories, funding_note, programme_months and other_desc all persist."""
        self._auth(USER_A)
        resp = self.client.patch(
            f'/api/v1/scholarship/applications/{self.app_a.id}/',
            {
                'funding_need': {
                    'categories': ['living', 'transport', 'books'],
                    'programme_months': 36,
                    'funding_note': 'I will try for PTPTN as well.',
                    'other_desc': 'Glasses',
                },
            }, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        fn = resp.json()['funding_need']
        self.assertEqual(fn['categories'], ['living', 'transport', 'books'])
        self.assertEqual(fn['programme_months'], 36)
        self.assertEqual(fn['funding_note'], 'I will try for PTPTN as well.')
        self.assertEqual(fn['other_desc'], 'Glasses')

    def test_funding_done_true_when_categories_nonempty(self):
        """funding_done is True when at least one category is ticked."""
        self._auth(USER_A)
        resp = self.client.patch(
            f'/api/v1/scholarship/applications/{self.app_a.id}/',
            {'funding_need': {'categories': ['living']}}, format='json',
        )
        self.assertTrue(resp.json()['completeness']['funding_done'])

    def test_funding_done_false_when_categories_empty(self):
        """funding_done is False when categories list is empty."""
        self._auth(USER_A)
        # First set categories, then clear them
        url = f'/api/v1/scholarship/applications/{self.app_a.id}/'
        self.client.patch(url, {'funding_need': {'categories': ['living']}}, format='json')
        resp = self.client.patch(url, {'funding_need': {'categories': []}}, format='json')
        self.assertFalse(resp.json()['completeness']['funding_done'])

    def test_funding_done_false_when_no_funding_need(self):
        """funding_done is False when no FundingNeed row exists yet (DoesNotExist path)."""
        # app_b has no funding_need yet
        self._auth(USER_B)
        resp = self.client.get(f'/api/v1/scholarship/applications/{self.app_b.id}/')
        self.assertFalse(resp.json()['completeness']['funding_done'])

    def test_s3_funding_fields_defaults_on_new_row(self):
        """A newly created FundingNeed row has empty categories, blank funding_note, null programme_months."""
        self._auth(USER_A)
        resp = self.client.patch(
            f'/api/v1/scholarship/applications/{self.app_a.id}/',
            {'funding_need': {'laptop': 0}}, format='json',
        )
        fn = resp.json()['funding_need']
        self.assertEqual(fn['categories'], [])
        self.assertEqual(fn['funding_note'], '')
        self.assertIsNone(fn['programme_months'])
