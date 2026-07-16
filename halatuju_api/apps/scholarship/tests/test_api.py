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
        # Academic data is never posted — it is read from the profile. The form
        # only collects the financial write-back fields + per-application fields.
        base = {
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
        # S8: scored silently — status stays 'submitted', verdict stored, no decision email yet
        self.assertEqual(body['status'], 'submitted')
        self.assertEqual(body['bucket'], 'A')
        app = ScholarshipApplication.objects.get(id=body['id'])
        self.assertEqual(app.profile_id, USER_A)
        self.assertEqual(app.verdict, 'shortlisted')
        self.assertIsNotNone(app.acknowledged_at)
        self.assertIsNotNone(app.decision_due_at)
        self.assertIsNone(app.shortlisted_at)          # set only on release
        self.assertIsNone(app.decision_email_sent_at)  # decision email is deferred
        # only the acknowledgement is sent at submit
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('priya@example.com', mail.outbox[0].to)

    def test_closed_cohort_blocks_new_application(self):
        # Intake closed → no NEW application, even though the profile qualifies.
        self.cohort.is_open = False
        self.cohort.save(update_fields=['is_open'])
        self._auth(_make_token(USER_A))
        resp = self.client.post(
            '/api/v1/scholarship/applications/', self._payload(), format='json',
        )
        self.assertEqual(resp.status_code, 409)
        self.assertFalse(ScholarshipApplication.objects.filter(profile_id=USER_A).exists())

    def test_closed_cohort_blocks_even_with_explicit_code(self):
        # An explicit cohort_code must not bypass the is_open gate.
        self.cohort.is_open = False
        self.cohort.save(update_fields=['is_open'])
        self._auth(_make_token(USER_A))
        resp = self.client.post(
            '/api/v1/scholarship/applications/',
            self._payload(cohort_code='b40-2026'), format='json',
        )
        self.assertEqual(resp.status_code, 409)
        self.assertIn(resp.json().get('code'), ('applications_closed', None))
        self.assertFalse(ScholarshipApplication.objects.filter(profile_id=USER_A).exists())

    def test_intake_endpoint_public_reflects_open_state(self):
        # No auth required (NRIC-gate whitelisted). Reflects the cohort's is_open.
        r_open = self.client.get('/api/v1/scholarship/intake/')
        self.assertEqual(r_open.status_code, 200)
        self.assertTrue(r_open.json()['open'])
        self.cohort.is_open = False
        self.cohort.save(update_fields=['is_open'])
        r_closed = self.client.get('/api/v1/scholarship/intake/')
        self.assertFalse(r_closed.json()['open'])

    def test_declaration_name_promoted_to_profile_name(self):
        # The deliberate "as in IC" declaration signature becomes the canonical
        # profile name. The About Me field is pre-filled from the Google sign-in
        # handle (e.g. "Priya") and can't be trusted; the declaration is gated +
        # deliberate, so it wins — and the frozen intake snapshot reflects it.
        self._auth(_make_token(USER_A))
        resp = self.client.post(
            '/api/v1/scholarship/applications/',
            self._payload(declaration_name='PRIYA A/P KRISHNAN'),
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.profile_a.refresh_from_db()
        self.assertEqual(self.profile_a.name, 'PRIYA A/P KRISHNAN')
        app = ScholarshipApplication.objects.get(id=resp.json()['id'])
        self.assertEqual(app.intake_snapshot['profile']['name'], 'PRIYA A/P KRISHNAN')

    def test_no_declaration_name_leaves_profile_name(self):
        # Without a signature, profile.name is untouched (no junk overwrite).
        self._auth(_make_token(USER_A))
        resp = self.client.post(
            '/api/v1/scholarship/applications/', self._payload(), format='json')
        self.assertEqual(resp.status_code, 201)
        self.profile_a.refresh_from_db()
        self.assertEqual(self.profile_a.name, 'PRIYA')   # unchanged by submit; CAPS-normalised on save

    def test_failing_application_rejected_no_decision_email(self):
        # profile_b has no grades (0 A's -> academic fail) + RM9000 no STR (income fail) -> rejected
        self._auth(_make_token(USER_B))
        resp = self.client.post(
            '/api/v1/scholarship/applications/',
            self._payload(household_income=9000, receives_str=False),
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        # S8: scored silently — status stays 'submitted', verdict='rejected', no decision email
        self.assertEqual(body['status'], 'submitted')
        self.assertEqual(body['bucket'], '')
        app = ScholarshipApplication.objects.get(id=body['id'])
        self.assertEqual(app.verdict, 'rejected')
        self.assertIsNone(app.decision_email_sent_at)
        self.assertIsNotNone(app.decision_due_at)
        # only the acknowledgement — the decision email is deferred to the scheduler
        self.assertEqual(len(mail.outbox), 1)

    def test_spm_a_count_derived_from_profile(self):
        # The A-count is computed live from profile.grades, never posted.
        self._auth(_make_token(USER_A))
        resp = self.client.post(
            '/api/v1/scholarship/applications/', self._payload(), format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['spm_a_count'], 5)

    def test_financial_fields_written_back_to_profile_and_snapshot_frozen(self):
        # The form's financial fields are synced to the canonical profile, and a
        # frozen intake_snapshot records what was declared at submit time.
        self._auth(_make_token(USER_A))
        resp = self.client.post(
            '/api/v1/scholarship/applications/',
            self._payload(household_income=1800, household_size=6, receives_str=True),
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.profile_a.refresh_from_db()
        self.assertEqual(self.profile_a.household_income, 1800)
        self.assertEqual(self.profile_a.household_size, 6)
        self.assertTrue(self.profile_a.receives_str)
        app = ScholarshipApplication.objects.get(id=resp.json()['id'])
        snap = app.intake_snapshot
        self.assertEqual(snap['profile']['household_income'], 1800)
        self.assertEqual(snap['profile']['spm_a_count'], 5)
        self.assertIn('captured_at', snap)

    def test_about_me_and_family_fields_written_back_to_profile(self):
        # S9 commit-on-submit: About Me + My Family scalar fields + parent
        # (guardians) + call language sync to the canonical profile. NRIC is NOT
        # written here (claim path only) — posting it must not change the profile.
        self._auth(_make_token(USER_A))
        resp = self.client.post(
            '/api/v1/scholarship/applications/',
            self._payload(
                name='Priya Devi', school='SMK Taman Desa',
                preferred_state='Selangor', contact_phone='012-345 6789',
                preferred_call_language='ta',
                guardians=[{'name': 'Rajan', 'phone': '011-2222 3333'}],
                nric='999999-99-9999',  # ignored by this endpoint
            ),
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.profile_a.refresh_from_db()
        self.assertEqual(self.profile_a.name, 'PRIYA DEVI')   # normalised to CAPS on save
        self.assertEqual(self.profile_a.school, 'SMK Taman Desa')
        self.assertEqual(self.profile_a.preferred_state, 'Selangor')
        self.assertEqual(self.profile_a.contact_phone, '012-345 6789')
        self.assertEqual(self.profile_a.preferred_call_language, 'ta')
        self.assertEqual(self.profile_a.guardians, [{'name': 'Rajan', 'phone': '011-2222 3333'}])
        # NRIC unchanged — the apply endpoint never writes it.
        self.assertEqual(self.profile_a.nric, '080101-14-1234')
        # Snapshot captures the committed About-Me values.
        snap = ScholarshipApplication.objects.get(id=resp.json()['id']).intake_snapshot
        self.assertEqual(snap['profile']['preferred_state'], 'Selangor')
        self.assertEqual(snap['profile']['preferred_call_language'], 'ta')

    def test_referral_source_resolves_to_partner_org(self):
        # A known referring-org code links the profile to the PartnerOrganisation;
        # a generic source (no matching row) leaves the FK unset.
        from apps.courses.models import PartnerOrganisation
        org = PartnerOrganisation.objects.create(code='cumig', name='CUMIG')
        self._auth(_make_token(USER_A))
        resp = self.client.post(
            '/api/v1/scholarship/applications/',
            self._payload(referral_source='cumig'), format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.profile_a.refresh_from_db()
        self.assertEqual(self.profile_a.referral_source, 'cumig')
        self.assertEqual(self.profile_a.referred_by_org_id, org.pk)

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

    def test_expired_application_does_not_block_reapply(self):
        # An auto-closed ('expired') application must NOT block a fresh start — the
        # reminder system promises the student they may restart.
        ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile_a, status='expired')
        self._auth(_make_token(USER_A))
        resp = self.client.post(
            '/api/v1/scholarship/applications/', self._payload(), format='json',
        )
        self.assertEqual(resp.status_code, 201)

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
