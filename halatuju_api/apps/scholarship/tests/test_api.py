"""Tests for B40 Assistance Programme application intake API."""
import jwt
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import StudentProfile
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
USER_A = 'user-a-123'
USER_B = 'user-b-456'
USER_NO_PROFILE = 'user-c-789'
USER_ANON = 'user-anon-000'


def _make_token(user_id, is_anonymous=False, secret=TEST_JWT_SECRET):
    payload = {'sub': user_id, 'aud': 'authenticated', 'role': 'authenticated'}
    if is_anonymous:
        payload['is_anonymous'] = True
    return jwt.encode(payload, secret, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestApplicationIntake(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(
            code='b40-2026', name='B40 Assistance Programme 2026', year=2026,
            income_ceiling=5250,
        )
        cls.profile_a = StudentProfile.objects.create(
            supabase_user_id=USER_A, nric='080101-14-1234',
            name='Priya', contact_email='priya@example.com',
            # math A, sej A, tamil_lit A+, eko A-, sci A- => 5 A's
            grades={'bm': 'B+', 'eng': 'B+', 'math': 'A', 'sej': 'A',
                    'tamil_lit': 'A+', 'eko': 'A-', 'sci': 'A-'},
        )
        cls.profile_b = StudentProfile.objects.create(
            supabase_user_id=USER_B, nric='080202-14-5678',
            name='Nathiyaa', contact_email='nat@example.com',
        )

    def setUp(self):
        self.client = APIClient()

    def _auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def _payload(self, **over):
        base = {
            'qualification': 'spm',
            'household_income': 2500,
            'receives_str': True,
            'consent_to_contact': True,
        }
        base.update(over)
        return base

    # --- CREATE ---

    def test_create_application_shortlists_bucket_a_and_emails(self):
        # profile_a: 5 A's, RM2500, STR -> all criteria OK -> Bucket A
        self._auth(_make_token(USER_A))
        resp = self.client.post(
            '/api/v1/scholarship/applications/', self._payload(), format='json',
        )
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertEqual(body['cohort_code'], 'b40-2026')
        self.assertEqual(body['status'], 'shortlisted')
        self.assertEqual(body['bucket'], 'A')
        app = ScholarshipApplication.objects.get(id=body['id'])
        self.assertEqual(app.profile_id, USER_A)
        self.assertIsNotNone(app.acknowledged_at)
        self.assertIsNotNone(app.shortlisted_at)
        self.assertIsNotNone(app.decision_email_sent_at)
        # acknowledgement + immediate pass email
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn('priya@example.com', mail.outbox[0].to)

    def test_failing_application_rejected_no_decision_email(self):
        # 2 A's (academic fail) + RM9000 no STR (income fail) -> rejected
        self._auth(_make_token(USER_B))
        resp = self.client.post(
            '/api/v1/scholarship/applications/',
            self._payload(spm_a_count=2, household_income=9000, receives_str=False),
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertEqual(body['status'], 'rejected')
        self.assertEqual(body['bucket'], '')
        app = ScholarshipApplication.objects.get(id=body['id'])
        self.assertIsNone(app.decision_email_sent_at)
        # only the acknowledgement — the fail email is deferred to the command
        self.assertEqual(len(mail.outbox), 1)

    def test_spm_a_count_snapshot_from_profile(self):
        self._auth(_make_token(USER_A))
        resp = self.client.post(
            '/api/v1/scholarship/applications/', self._payload(), format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['spm_a_count'], 5)

    def test_explicit_a_count_overrides_snapshot(self):
        self._auth(_make_token(USER_A))
        resp = self.client.post(
            '/api/v1/scholarship/applications/',
            self._payload(spm_a_count=10), format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['spm_a_count'], 10)

    def test_consent_required(self):
        self._auth(_make_token(USER_A))
        resp = self.client.post(
            '/api/v1/scholarship/applications/',
            self._payload(consent_to_contact=False), format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_duplicate_returns_409(self):
        ScholarshipApplication.objects.create(cohort=self.cohort, profile=self.profile_a)
        self._auth(_make_token(USER_A))
        resp = self.client.post(
            '/api/v1/scholarship/applications/', self._payload(), format='json',
        )
        self.assertEqual(resp.status_code, 409)

    def test_no_open_cohort_returns_409(self):
        ScholarshipCohort.objects.update(is_open=False)
        self._auth(_make_token(USER_A))
        resp = self.client.post(
            '/api/v1/scholarship/applications/', self._payload(), format='json',
        )
        self.assertEqual(resp.status_code, 409)

    def test_anonymous_user_rejected(self):
        self._auth(_make_token(USER_ANON, is_anonymous=True))
        resp = self.client.post(
            '/api/v1/scholarship/applications/', self._payload(), format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_user_without_profile_rejected(self):
        # Non-anonymous user without a profile is blocked by the NRIC gate (403).
        self._auth(_make_token(USER_NO_PROFILE))
        resp = self.client.post(
            '/api/v1/scholarship/applications/', self._payload(), format='json',
        )
        self.assertEqual(resp.status_code, 403)

    # --- LIST / DETAIL ---

    def test_list_own_only(self):
        ScholarshipApplication.objects.create(cohort=self.cohort, profile=self.profile_a)
        ScholarshipApplication.objects.create(cohort=self.cohort, profile=self.profile_b)
        self._auth(_make_token(USER_A))
        resp = self.client.get('/api/v1/scholarship/applications/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['total_count'], 1)
        self.assertEqual(data['applications'][0]['profile_id'], USER_A)

    def test_detail_own(self):
        app = ScholarshipApplication.objects.create(cohort=self.cohort, profile=self.profile_a)
        self._auth(_make_token(USER_A))
        resp = self.client.get(f'/api/v1/scholarship/applications/{app.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['id'], app.id)

    def test_detail_cross_user_404(self):
        app = ScholarshipApplication.objects.create(cohort=self.cohort, profile=self.profile_b)
        self._auth(_make_token(USER_A))
        resp = self.client.get(f'/api/v1/scholarship/applications/{app.id}/')
        self.assertEqual(resp.status_code, 404)

    # --- AUTH ---

    def test_post_requires_auth(self):
        resp = self.client.post(
            '/api/v1/scholarship/applications/', self._payload(), format='json',
        )
        self.assertEqual(resp.status_code, 401)

    def test_get_requires_auth(self):
        resp = self.client.get('/api/v1/scholarship/applications/')
        self.assertEqual(resp.status_code, 401)
