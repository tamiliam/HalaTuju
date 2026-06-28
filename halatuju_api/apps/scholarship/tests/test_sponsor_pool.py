"""Phase E2 — anonymised sponsor discovery pool.

The load-bearing safety property: a sponsor NEVER sees a name/NRIC/address/phone/
email/school. These tests assert that on every sponsor-facing surface, plus the
eligibility rule, the SPONSOR_POOL_ENABLED gate, approved-sponsor gating, and the
admin generate/publish flow. All on synthetic data; the AI call is mocked.
"""
import json
from unittest.mock import patch

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship import pool
from apps.scholarship.models import (
    Consent, FundingNeed, ScholarshipApplication, ScholarshipCohort, SponsorProfile, Sponsor,
)
from apps.scholarship.profile_engine import _build_prompt, generate_anon_blurb
from apps.scholarship.serializers import (
    SponsorPoolCardSerializer, SponsorPoolDetailSerializer,
)

TEST_JWT_SECRET = 'test-supabase-jwt-secret'

# Distinctive identifying values — if any appears in a sponsor-facing payload, it leaked.
# The secondary `school` is NOW NEVER surfaced (the card's institution is the TARGET
# university, never the school). Everything here — including the PARENTS' — must stay out.
IDENTIFIERS = {
    'name': 'Zxqvbn Identifiable',
    'nric': '050505-10-9999',
    'school': 'SMK Secret School',
    'address': '99 Jalan Rahsia',
    'city': 'Siretown',
    'contact_phone': '012-9998888',
    'contact_email': 'leak@secret.example',
    # Parent/guardian identity must never cross to a sponsor either.
    'parent_name': 'Qwfpgj Guardianperson',
    'parent_nric': '060606-11-7777',
}


def _token(uid, email='', anon=False):
    return jwt.encode(
        {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated',
         'email': email, 'is_anonymous': anon},
        TEST_JWT_SECRET, algorithm='HS256')


def _make_eligible_app(cohort, *, suffix='1', anon_published=True, consent=True):
    """A fully pool-eligible application on synthetic data, with every identifying
    field populated (so leak tests have something to catch)."""
    profile = StudentProfile.objects.create(
        supabase_user_id=f'pool-{suffix}',
        grades={'bm': 'A', 'eng': 'A', 'math': 'A+', 'sci': 'B'},
        exam_type='spm',
        preferred_state='Kedah',
        household_income=1500, household_size=5, receives_str=True, receives_jkm=False,
        name=IDENTIFIERS['name'], nric=IDENTIFIERS['nric'], school=IDENTIFIERS['school'],
        address=IDENTIFIERS['address'], city=IDENTIFIERS['city'],
        contact_phone=IDENTIFIERS['contact_phone'], contact_email=IDENTIFIERS['contact_email'],
        # parent/guardian identity lives in guardians — must never cross to a sponsor.
        guardians=[{'name': IDENTIFIERS['parent_name'], 'nric': IDENTIFIERS['parent_nric'],
                    'relationship': 'mother'}],
    )
    app = ScholarshipApplication.objects.create(
        cohort=cohort, profile=profile, status='recommended',
        field_of_study='engineering', first_in_family=True,
        chosen_programme={'course_name': 'Diploma Test Engineering', 'field_key': 'engineering',
                          'institution': 'Politeknik Test'},
        aspirations='I want to be an engineer.', plans='Study hard.',
        parents_occupation='farmer',
    )
    FundingNeed.objects.create(application=app, categories=['tuition', 'accommodation'], programme_months=24)
    SponsorProfile.objects.create(
        application=app,
        anon_markdown='The student is a determined SPM leaver pursuing engineering in their home state.',
        anon_blurb='A determined SPM leaver pursuing engineering; sponsorship covers monthly living costs.',
        anon_published=anon_published,
    )
    if consent:
        Consent.objects.create(application=app, consent_type='share_with_sponsors', version='e2', is_active=True)
    return app


# ─── pure helpers ────────────────────────────────────────────────────────────

class TestPoolHelpers(TestCase):
    def test_pool_ref_stable_and_non_sequential(self):
        self.assertEqual(pool.pool_ref(7), pool.pool_ref(7))
        self.assertNotEqual(pool.pool_ref(7), pool.pool_ref(8))
        self.assertTrue(pool.pool_ref(7).startswith('S-'))
        self.assertNotIn('7', pool.pool_ref(7).replace('S-', ''))  # not the raw id

    def test_academic_band_spm_and_stpm(self):
        spm = StudentProfile(exam_type='spm', grades={'bm': 'A', 'eng': 'A'})
        self.assertTrue(pool.academic_band(spm).startswith('SPM'))
        stpm = StudentProfile(exam_type='stpm', stpm_cgpa=3.5)
        self.assertIn('3.5', pool.academic_band(stpm))


# ─── eligibility ─────────────────────────────────────────────────────────────

class TestEligibility(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def test_eligible_with_published_and_consent(self):
        app = _make_eligible_app(self.cohort)
        self.assertTrue(pool.is_pool_eligible(app))
        self.assertIn(app.id, list(pool.eligible_pool_queryset(ScholarshipApplication).values_list('id', flat=True)))

    def test_not_eligible_without_anon_publish(self):
        app = _make_eligible_app(self.cohort, anon_published=False)
        self.assertFalse(pool.is_pool_eligible(app))
        self.assertNotIn(app.id, list(pool.eligible_pool_queryset(ScholarshipApplication).values_list('id', flat=True)))

    def test_not_eligible_without_consent(self):
        app = _make_eligible_app(self.cohort, consent=False)
        self.assertFalse(pool.is_pool_eligible(app))

    def test_not_eligible_when_consent_withdrawn(self):
        app = _make_eligible_app(self.cohort)
        app.consents.update(is_active=False)
        self.assertFalse(pool.is_pool_eligible(app))


# ─── allowlist: no identifying field may leak ────────────────────────────────

class TestAllowlistNoLeak(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def _assert_no_identifiers(self, payload):
        blob = json.dumps(payload)
        for label, value in IDENTIFIERS.items():
            self.assertNotIn(value, blob, f'{label} leaked into sponsor payload')

    def test_card_leaks_nothing(self):
        app = _make_eligible_app(self.cohort)
        data = SponsorPoolCardSerializer(app).data
        self._assert_no_identifiers(data)        # also scans the new course/institution/blurb
        self.assertEqual(data['state'], 'Kedah')       # state-level region IS allowed
        self.assertEqual(data['field'], 'engineering')
        self.assertEqual(data['course'], 'Diploma Test Engineering')
        self.assertTrue(data['blurb'])

    def test_detail_leaks_nothing(self):
        app = _make_eligible_app(self.cohort)
        data = SponsorPoolDetailSerializer(app).data
        self._assert_no_identifiers(data)
        self.assertIn('anon_profile', data)

    def test_institution_is_target_university_never_school(self):
        # institution = the TARGET university (chosen programme), shown to every sponsor;
        # the secondary school is never surfaced, with or without any context.
        app = _make_eligible_app(self.cohort)
        for ctx in (None, {'is_trusted': True}):
            data = SponsorPoolCardSerializer(app, context=ctx or {}).data
            self.assertEqual(data['institution'], 'Politeknik Test')
            self.assertNotIn(IDENTIFIERS['school'], json.dumps(data))

    def test_institution_blank_when_target_unknown(self):
        # No institution on the chosen programme → '' so the card falls back to course-only.
        app = _make_eligible_app(self.cohort)
        app.chosen_programme = {'course_name': 'Diploma Test Engineering', 'field_key': 'engineering'}
        app.save(update_fields=['chosen_programme'])
        data = SponsorPoolCardSerializer(app).data
        self.assertEqual(data['institution'], '')
        self.assertEqual(data['course'], 'Diploma Test Engineering')

    def test_course_falls_back_to_field(self):
        app = _make_eligible_app(self.cohort)
        app.chosen_programme = {}
        app.save(update_fields=['chosen_programme'])
        data = SponsorPoolCardSerializer(app).data
        self.assertEqual(data['course'], 'engineering')

    def test_blurb_passthrough(self):
        app = _make_eligible_app(self.cohort)
        data = SponsorPoolCardSerializer(app).data
        self.assertIn('sponsorship covers monthly living costs', data['blurb'])


# ─── card blurb generation (card-strict, mocked Gemini) ──────────────────────

class TestAnonBlurb(TestCase):
    def test_empty_source_skips_the_model(self):
        with patch('apps.scholarship.profile_engine._call_gemini_text') as m:
            self.assertEqual(generate_anon_blurb(None, ''), '')
            m.assert_not_called()

    def test_clips_to_twenty_words(self):
        with patch('apps.scholarship.profile_engine._call_gemini_text',
                   return_value={'markdown': ' '.join(f'w{i}' for i in range(30))}):
            out = generate_anon_blurb(None, 'an anonymous profile')
        self.assertLessEqual(len(out.rstrip('…').split(' ')), 20)
        self.assertTrue(out.endswith('…'))

    def test_strips_wrapping_quotes(self):
        with patch('apps.scholarship.profile_engine._call_gemini_text',
                   return_value={'markdown': '"A determined leaver."'}):
            out = generate_anon_blurb(None, 'profile')
        self.assertEqual(out, 'A determined leaver.')

    def test_engine_error_returns_empty(self):
        with patch('apps.scholarship.profile_engine._call_gemini_text',
                   return_value={'error': 'boom'}):
            self.assertEqual(generate_anon_blurb(None, 'profile'), '')


class TestProgressState(TestCase):
    """F2: the coarse, non-identifying progress band on a sponsor's student card."""
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def test_none_until_sponsored(self):
        app = _make_eligible_app(self.cohort)  # not yet sponsored
        self.assertIsNone(pool.derive_progress_state(app))
        self.assertIsNone(SponsorPoolCardSerializer(app).data['progress_state'])

    def test_on_track_when_sponsored(self):
        app = _make_eligible_app(self.cohort)
        app.status = 'sponsored'
        app.save(update_fields=['status'])
        self.assertEqual(pool.derive_progress_state(app), 'on_track')
        self.assertEqual(SponsorPoolCardSerializer(app).data['progress_state'], 'on_track')

    def test_progress_state_not_an_identifier(self):
        app = _make_eligible_app(self.cohort)
        app.status = 'sponsored'
        app.save(update_fields=['status'])
        blob = json.dumps(SponsorPoolCardSerializer(app).data)
        for label, value in IDENTIFIERS.items():
            self.assertNotIn(value, blob, f'{label} leaked alongside progress_state')

    # F9a — the real band derived from the latest SemesterResult.
    def _sponsored(self):
        app = _make_eligible_app(self.cohort, suffix='ps')
        app.status = 'sponsored'
        app.save(update_fields=['status'])
        return app

    def test_band_semester_completed_with_good_cgpa(self):
        from apps.scholarship.models import SemesterResult
        app = self._sponsored()
        SemesterResult.objects.create(application=app, semester='2026 S1', cgpa='3.50')
        self.assertEqual(pool.derive_progress_state(app), 'semester_completed')

    def test_band_needs_attention_with_low_cgpa(self):
        from apps.scholarship.models import SemesterResult
        app = self._sponsored()
        SemesterResult.objects.create(application=app, semester='2026 S1', cgpa='1.80')
        self.assertEqual(pool.derive_progress_state(app), 'needs_attention')

    def test_band_graduated_overrides_cgpa(self):
        from apps.scholarship.models import SemesterResult
        app = self._sponsored()
        SemesterResult.objects.create(application=app, semester='Final', cgpa='1.50', graduated=True)
        self.assertEqual(pool.derive_progress_state(app), 'graduated')

    def test_latest_result_wins(self):
        from apps.scholarship.models import SemesterResult
        app = self._sponsored()
        SemesterResult.objects.create(application=app, semester='2025 S2', cgpa='1.50')
        SemesterResult.objects.create(application=app, semester='2026 S1', cgpa='3.20')
        self.assertEqual(pool.derive_progress_state(app), 'semester_completed')


# ─── the anonymous prompt must not carry name/school ─────────────────────────

class TestAnonPrompt(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def test_profile_prompt_redacts_name_but_allows_school(self):
        # One profile, PII-redacted (2026-06-15): the NAME is withheld, but the school
        # name is allowed under the revised policy.
        app = _make_eligible_app(self.cohort)
        prompt = _build_prompt(app)
        self.assertNotIn(IDENTIFIERS['name'], prompt)   # name redacted
        self.assertIn(IDENTIFIERS['school'], prompt)    # school allowed


# ─── TD-074b: the pre-publish identifier scan ────────────────────────────────

class TestAnonScan(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        self.profile = _make_eligible_app(self.cohort).profile  # carries the IDENTIFIERS

    def test_clean_blurb_passes(self):
        self.assertEqual(
            pool.scan_anon_for_identifiers('The student is a determined SPM leaver in engineering.', self.profile), [])

    def test_catches_name(self):
        self.assertIn('name', pool.scan_anon_for_identifiers('The student, Zxqvbn, is bright.', self.profile))

    def test_catches_school_distinctive_token(self):
        # The STRICT relay scanner still blocks school. "Secret" is the distinctive part.
        self.assertIn('school', pool.scan_anon_for_identifiers('Studied at a Secret institution.', self.profile))

    def test_catches_city(self):
        self.assertIn('city', pool.scan_anon_for_identifiers('Lives in Siretown these days.', self.profile))

    def test_profile_pii_allows_school_and_city(self):
        # The PROFILE scanner (2026-06-15 policy) allows school + town/state; it only
        # blocks name/NRIC/phone/email.
        self.assertEqual(pool.scan_profile_pii('Studied at a Secret institution in Siretown.', self.profile), [])
        self.assertIn('name', pool.scan_profile_pii('The student, Zxqvbn, is bright.', self.profile))

    def test_catches_nric_phone_email(self):
        txt = 'Reach 050505-10-9999 or 012-999 8888 or leak@secret.example'
        f = pool.scan_anon_for_identifiers(txt, self.profile)
        self.assertIn('nric', f)
        self.assertIn('phone', f)
        self.assertIn('email', f)

    def test_empty_text_or_no_profile(self):
        self.assertEqual(pool.scan_anon_for_identifiers('', self.profile), [])
        self.assertEqual(pool.scan_anon_for_identifiers('anything', None), [])


# ─── sponsor browse endpoints: flag + approval gating ────────────────────────

@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestSponsorBrowse(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.app = _make_eligible_app(cls.cohort)
        Sponsor.objects.create(supabase_user_id='spon-ok', name='S', email='s@x.com',
                               phone='0123', source='friend', consent_at=timezone.now(), status='approved')
        Sponsor.objects.create(supabase_user_id='spon-pending', name='P', email='p@x.com', status='pending')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid, "x@x.com")}')

    @override_settings(SPONSOR_POOL_ENABLED=False)
    def test_pool_404_when_flag_off(self):
        self._auth('spon-ok')
        self.assertEqual(self.client.get('/api/v1/sponsor/pool/').status_code, 404)

    @override_settings(SPONSOR_POOL_ENABLED=True)
    def test_approved_sponsor_sees_anonymised_cards(self):
        self._auth('spon-ok')
        r = self.client.get('/api/v1/sponsor/pool/')
        self.assertEqual(r.status_code, 200)
        students = r.json()['students']
        self.assertTrue(any(s['ref'] == pool.pool_ref(self.app.id) for s in students))
        self._assert_clean(r.json())

    @override_settings(SPONSOR_POOL_ENABLED=True)
    def test_pending_sponsor_forbidden(self):
        self._auth('spon-pending')
        self.assertEqual(self.client.get('/api/v1/sponsor/pool/').status_code, 403)

    @override_settings(SPONSOR_POOL_ENABLED=True)
    def test_detail_ok_and_clean(self):
        self._auth('spon-ok')
        r = self.client.get(f'/api/v1/sponsor/pool/{self.app.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('anon_profile', r.json())
        self._assert_clean(r.json())

    @override_settings(SPONSOR_POOL_ENABLED=True)
    def test_detail_404_for_ineligible(self):
        ineligible = _make_eligible_app(self.cohort, suffix='2', anon_published=False)
        self._auth('spon-ok')
        self.assertEqual(self.client.get(f'/api/v1/sponsor/pool/{ineligible.id}/').status_code, 404)

    def _assert_clean(self, payload):
        blob = json.dumps(payload)
        for value in IDENTIFIERS.values():
            self.assertNotIn(value, blob)


# ─── F1: public landing counter ──────────────────────────────────────────────

@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestSponsorPoolCount(TestCase):
    """The public /sponsor/pool/count/ endpoint feeds the F1 landing's live counter:
    no auth, count-only, and flag-gated (dark until go-live)."""
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.app = _make_eligible_app(cls.cohort)
        _make_eligible_app(cls.cohort, suffix='2')  # a second eligible student
        _make_eligible_app(cls.cohort, suffix='3', anon_published=False)  # NOT in the pool

    def setUp(self):
        self.client = APIClient()  # deliberately unauthenticated — this is a public endpoint

    @override_settings(SPONSOR_POOL_ENABLED=False)
    def test_count_hidden_when_flag_off(self):
        r = self.client.get('/api/v1/sponsor/pool/count/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {'count': 0, 'enabled': False})

    @override_settings(SPONSOR_POOL_ENABLED=True)
    def test_count_reflects_eligible_pool_when_on(self):
        r = self.client.get('/api/v1/sponsor/pool/count/')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body['enabled'])
        self.assertEqual(body['count'], 2)  # only the two anon-published + consented apps

    @override_settings(SPONSOR_POOL_ENABLED=True)
    def test_count_leaks_no_student_data(self):
        r = self.client.get('/api/v1/sponsor/pool/count/')
        blob = json.dumps(r.json())
        for value in IDENTIFIERS.values():
            self.assertNotIn(value, blob)
        self.assertEqual(set(r.json().keys()), {'count', 'enabled'})


# ─── admin generate / publish the anonymous profile ──────────────────────────

@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestAdminAnonProfile(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        PartnerAdmin.objects.create(supabase_user_id='rev', role='reviewer', is_active=True, name='Rev', email='r@x.com')
        PartnerAdmin.objects.create(supabase_user_id='vie', role='admin', is_active=True, name='Vie', email='v@x.com')

    def setUp(self):
        self.client = APIClient()
        self.app = _make_eligible_app(self.cohort, anon_published=False)
        self.app.assigned_to = PartnerAdmin.objects.get(supabase_user_id='rev')
        self.app.save(update_fields=['assigned_to'])

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid, "x@x.com")}')

    def test_reviewer_can_publish(self):
        # The profile is generated at the verdict; the publish endpoint flips it live.
        self._auth('rev')
        pub = self.client.post(f'/api/v1/admin/scholarship/applications/{self.app.id}/anon-profile/publish/',
                               {'publish': True}, format='json')
        self.assertEqual(pub.status_code, 200, pub.content)
        sp = SponsorProfile.objects.get(application=self.app)
        self.assertTrue(sp.anon_published)
        self.assertIsNotNone(sp.anon_published_at)

    def test_publish_requires_generated_anon(self):
        self._auth('rev')
        # SponsorProfile exists (anon_markdown set by fixture) — clear it to test the gate.
        SponsorProfile.objects.filter(application=self.app).update(anon_markdown='')
        r = self.client.post(f'/api/v1/admin/scholarship/applications/{self.app.id}/anon-profile/publish/', {}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'no_anon')

    def test_publish_blocked_when_blurb_leaks_identifier(self):
        # TD-074b: a blurb that contains the student's name cannot be published.
        self._auth('rev')
        SponsorProfile.objects.filter(application=self.app).update(
            anon_markdown=f"The student {IDENTIFIERS['name'].split()[0]} is determined.")
        r = self.client.post(f'/api/v1/admin/scholarship/applications/{self.app.id}/anon-profile/publish/',
                             {'publish': True}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'anon_identifier_leak')
        self.assertIn('name', r.json()['fields'])
        self.app.sponsor_profile.refresh_from_db()
        self.assertFalse(self.app.sponsor_profile.anon_published)  # stayed unpublished

    def test_viewer_forbidden(self):
        self._auth('vie')
        r = self.client.post(f'/api/v1/admin/scholarship/applications/{self.app.id}/anon-profile/publish/',
                             {'publish': True}, format='json')
        self.assertEqual(r.status_code, 403)
