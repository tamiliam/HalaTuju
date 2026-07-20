"""Phase E2 — anonymised sponsor discovery pool.

The load-bearing safety property: a sponsor NEVER sees a name/NRIC/address/phone/
email/school. These tests assert that on every sponsor-facing surface, plus the
eligibility rule, the SPONSOR_POOL_ENABLED gate, approved-sponsor gating, and the
admin generate/publish flow. All on synthetic data; the AI call is mocked.
"""
import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import jwt
from django.db.models import Q, Sum
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship import pool
from apps.scholarship.models import (
    Consent, FundingNeed, ScholarshipApplication, ScholarshipCohort, SponsorProfile, Sponsor,
    Sponsorship,
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


# ─── funded grace window (owner 2026-07-21) ──────────────────────────────────
@override_settings(POOL_FUNDED_GRACE_HOURS=48)
class TestFundedGraceWindow(TestCase):
    """A just-funded student LINGERS in the DISPLAY pool for POOL_FUNDED_GRACE_HOURS as a
    read-only "Funded" card, but is never in the FUNDABLE pool (no double-funding, not counted
    as waiting), and drops off once the window passes."""
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='g', name='B40', year=2026)

    def _ids(self, qs):
        return list(qs.values_list('id', flat=True))

    def _fund(self, app, *, hours_ago):
        app.status = 'awarded'
        app.awarded_at = timezone.now() - timedelta(hours=hours_ago)
        app.save(update_fields=['status', 'awarded_at'])

    def test_recommended_is_in_both_pools(self):
        app = _make_eligible_app(self.cohort, suffix='rec')
        self.assertIn(app.id, self._ids(pool.eligible_pool_queryset(ScholarshipApplication)))
        self.assertIn(app.id, self._ids(pool.display_pool_queryset(ScholarshipApplication)))

    def test_recently_funded_shows_in_display_but_is_not_fundable(self):
        app = _make_eligible_app(self.cohort, suffix='fund')
        self._fund(app, hours_ago=1)
        # Visible to sponsors (grace window)…
        self.assertIn(app.id, self._ids(pool.display_pool_queryset(ScholarshipApplication)))
        # …but NOT fundable and NOT counted as still-waiting (the strict pool).
        self.assertNotIn(app.id, self._ids(pool.eligible_pool_queryset(ScholarshipApplication)))
        self.assertFalse(pool.is_pool_eligible(app))

    def test_funded_past_the_window_drops_off(self):
        app = _make_eligible_app(self.cohort, suffix='old')
        self._fund(app, hours_ago=49)          # past the 48h grace window
        self.assertNotIn(app.id, self._ids(pool.display_pool_queryset(ScholarshipApplication)))

    def test_card_funded_flag(self):
        rec = _make_eligible_app(self.cohort, suffix='cardrec')
        fund = _make_eligible_app(self.cohort, suffix='cardfund')
        self._fund(fund, hours_ago=2)
        self.assertFalse(SponsorPoolCardSerializer(rec).data['funded'])
        self.assertTrue(SponsorPoolCardSerializer(fund).data['funded'])


# ─── allowlist: no identifying field may leak ────────────────────────────────

class TestAllowlistNoLeak(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def _assert_no_identifiers(self, payload):
        blob = json.dumps(payload)
        for label, value in IDENTIFIERS.items():
            if label == 'school':
                continue  # owner 2026-07-18: the secondary school IS shown to sponsors
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

    def test_institution_is_target_and_school_is_secondary(self):
        # institution = the TARGET university (chosen programme); school = the SECONDARY
        # school attended (owner 2026-07-18) — two distinct fields.
        app = _make_eligible_app(self.cohort)
        for ctx in (None, {'is_trusted': True}):
            data = SponsorPoolCardSerializer(app, context=ctx or {}).data
            self.assertEqual(data['institution'], 'Politeknik Test')
            self.assertEqual(data['school'], IDENTIFIERS['school'])   # the secondary school, shown

    def test_institution_blank_when_target_unknown(self):
        # No institution on the chosen programme → '' so the card falls back to course-only.
        app = _make_eligible_app(self.cohort)
        app.chosen_programme = {'course_name': 'Diploma Test Engineering', 'field_key': 'engineering'}
        app.save(update_fields=['chosen_programme'])
        data = SponsorPoolCardSerializer(app).data
        self.assertEqual(data['institution'], '')
        self.assertEqual(data['course'], 'Diploma Test Engineering')

    def test_course_falls_back_to_field(self):
        # No programme → the field taxonomy DISPLAY name (Fix-1 d), not the raw key. 'engineering'
        # is a seeded taxonomy key, so the card shows its proper display name.
        app = _make_eligible_app(self.cohort)
        app.chosen_programme = {}
        app.save(update_fields=['chosen_programme'])
        data = SponsorPoolCardSerializer(app).data
        self.assertEqual(data['course'], 'Engineering & Technical')

    def test_stpm_card_shows_institution_and_track(self):
        # Owner 2026-07-17: the institution (incl. a Form-6 school) IS shown, from the single
        # chosen_programme.institution field; the STPM track is appended to the programme.
        app = _make_eligible_app(self.cohort)
        app.chosen_programme = {'course_name': 'Tingkatan Enam',
                                'institution': 'Sekolah Menengah Kebangsaan Maxwell'}
        app.pre_u_institution = 'SMK MAXWELL'          # abbreviated duplicate — NOT the source
        app.chosen_pathway = 'stpm'
        app.pre_u_track = 'sains'
        app.save(update_fields=['chosen_programme', 'pre_u_institution', 'chosen_pathway', 'pre_u_track'])
        data = SponsorPoolCardSerializer(app).data
        self.assertEqual(data['institution'], 'Sekolah Menengah Kebangsaan Maxwell')  # shown, from cp.institution
        self.assertEqual(data['course'], 'Tingkatan Enam (Sains)')                    # track appended
        self.assertNotIn('SMK MAXWELL', json.dumps(data))         # the pre_u duplicate is never used

    def test_mis_slotted_offer_never_shows_junk(self):
        # #125: an institution name in the course slot + a 'Tarikh…' line in the institution slot
        # must never surface. With no catalogue course_id, course falls to the pre-U label and the
        # date-junk institution is dropped.
        app = _make_eligible_app(self.cohort)
        app.chosen_programme = {'course_name': 'Politeknik Sultan Idris Shah',
                                'institution': 'Tarikh dan Masa Daftar: 15 JUN 2026 (8.00 PAGI)'}
        app.chosen_pathway = 'asasi'
        app.save(update_fields=['chosen_programme', 'chosen_pathway'])
        data = SponsorPoolCardSerializer(app).data
        self.assertNotIn('Tarikh', json.dumps(data))
        self.assertEqual(data['institution'], '')
        self.assertEqual(data['course'], 'Asasi')

    def test_blurb_passthrough(self):
        app = _make_eligible_app(self.cohort)
        data = SponsorPoolCardSerializer(app).data
        self.assertIn('sponsorship covers monthly living costs', data['blurb'])

    def test_reporting_date_iso_and_null(self):
        from datetime import date
        app = _make_eligible_app(self.cohort)
        app.reporting_date = date(2026, 9, 1)
        app.save(update_fields=['reporting_date'])
        self.assertEqual(SponsorPoolCardSerializer(app).data['reporting_date'], '2026-09-01')
        app.reporting_date = None
        app.save(update_fields=['reporting_date'])
        self.assertIsNone(SponsorPoolCardSerializer(app).data['reporting_date'])

    def test_new_fields_leak_nothing(self):
        # field_image_slug + reporting_date are in the payload — must carry no identifier.
        from datetime import date
        app = _make_eligible_app(self.cohort)
        app.reporting_date = date(2026, 9, 1)
        app.save(update_fields=['reporting_date'])
        data = SponsorPoolCardSerializer(app).data
        self.assertIn('field_image_slug', data)
        self.assertIn('reporting_date', data)
        self._assert_no_identifiers(data)


class TestFieldImageSlug(TestCase):
    """The catalogue-first resolution chain (a)/(b)/(c) for the card's field artwork."""
    @classmethod
    def setUpTestData(cls):
        from apps.courses.models import Course, FieldTaxonomy
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        # Test-only taxonomy keys (the 37 canonical rows are migration-seeded — avoid a clash).
        cls.tax_eng = FieldTaxonomy.objects.create(
            key='zz_eng', name_en='Engineering', name_ms='Kejuruteraan',
            name_ta='பொறியியல்', image_slug='slug-eng')
        cls.tax_health = FieldTaxonomy.objects.create(
            key='zz_health', name_en='Health', name_ms='Kesihatan',
            name_ta='சுகாதாரம்', image_slug='slug-health')
        cls.course = Course.objects.create(
            course_id='PT001', course='Diploma Kej', level='Diploma', department='X',
            field='Eng', field_key=cls.tax_health)

    def _slug(self, app):
        return SponsorPoolCardSerializer(app).data['field_image_slug']

    def test_a_course_id_wins_via_field_key(self):
        # The confirmed course's OWN field_key (health) beats the broad field_of_study (eng).
        app = _make_eligible_app(self.cohort, suffix='a')
        app.field_of_study = 'zz_eng'
        app.chosen_programme = {'course_id': 'PT001', 'course_name': 'Diploma Kej'}
        app.save(update_fields=['field_of_study', 'chosen_programme'])
        self.assertEqual(self._slug(app), 'slug-health')

    def test_b_field_of_study_key_when_no_course_id(self):
        app = _make_eligible_app(self.cohort, suffix='b')
        app.field_of_study = 'zz_eng'
        app.chosen_programme = {'course_name': 'Something', 'institution': 'X'}  # no course_id
        app.save(update_fields=['field_of_study', 'chosen_programme'])
        self.assertEqual(self._slug(app), 'slug-eng')

    def test_c_unknown_key_returns_blank(self):
        app = _make_eligible_app(self.cohort, suffix='c')
        app.field_of_study = 'no_such_field'
        app.chosen_programme = {}
        app.save(update_fields=['field_of_study', 'chosen_programme'])
        self.assertEqual(self._slug(app), '')

    def test_c_missing_course_row_falls_through_to_field(self):
        # A course_id that isn't in the catalogue → fall through to (b).
        app = _make_eligible_app(self.cohort, suffix='d')
        app.field_of_study = 'zz_health'
        app.chosen_programme = {'course_id': 'GHOST999'}
        app.save(update_fields=['field_of_study', 'chosen_programme'])
        self.assertEqual(self._slug(app), 'slug-health')


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
        app.status = 'active'
        app.save(update_fields=['status'])
        self.assertEqual(pool.derive_progress_state(app), 'on_track')
        self.assertEqual(SponsorPoolCardSerializer(app).data['progress_state'], 'on_track')

    def test_progress_state_not_an_identifier(self):
        app = _make_eligible_app(self.cohort)
        app.status = 'active'
        app.save(update_fields=['status'])
        blob = json.dumps(SponsorPoolCardSerializer(app).data)
        for label, value in IDENTIFIERS.items():
            if label == 'school':
                continue  # owner 2026-07-18: the secondary school IS shown to sponsors
            self.assertNotIn(value, blob, f'{label} leaked alongside progress_state')

    # F9a — the real band derived from the latest SemesterResult.
    def _sponsored(self):
        app = _make_eligible_app(self.cohort, suffix='ps')
        app.status = 'active'
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
        for label, value in IDENTIFIERS.items():
            if label == 'school':
                continue  # owner 2026-07-18: the secondary school IS shown to sponsors
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


# ─── funding bar: funded_amount seam (partial-funding forward-compat) ─────────

class TestFundedAmount(TestCase):
    """funded_amount = sum of HOLDING (offered+active) sponsorships. '0' for every
    pooled student today (funding is full-or-nothing and a funded student leaves the
    pool); drives the funding bar and is ready for partial funding (TD-075)."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def test_zero_when_unfunded(self):
        app = _make_eligible_app(self.cohort)
        self.assertEqual(SponsorPoolCardSerializer(app).data['funded_amount'], '0')

    def test_sums_holding_and_ignores_lapsed(self):
        app = _make_eligible_app(self.cohort)
        sponsor = Sponsor.objects.create(supabase_user_id='spon-1', email='s@example.com',
                                         name='S', status='approved')
        Sponsorship.objects.create(sponsor=sponsor, application=app,
                                   amount=Decimal('500'), status='offered')
        # A lapsed allocation no longer holds balance → must not count.
        Sponsorship.objects.create(sponsor=sponsor, application=app,
                                   amount=Decimal('999'), status='lapsed')
        self.assertEqual(Decimal(SponsorPoolCardSerializer(app).data['funded_amount']),
                         Decimal('500'))

    def test_annotated_queryset_branch_zero(self):
        # Mirror the list view's annotation: the funded_total attr is set (None) even with
        # no sponsorships, so the serializer reads it rather than firing a per-card query.
        _make_eligible_app(self.cohort)
        _make_eligible_app(self.cohort, suffix='2')
        qs = pool.eligible_pool_queryset(ScholarshipApplication).annotate(
            funded_total=Sum('sponsorships__amount',
                             filter=Q(sponsorships__status__in=Sponsorship.HOLDING)),
        )
        data = SponsorPoolCardSerializer(qs, many=True).data
        self.assertEqual([c['funded_amount'] for c in data], ['0', '0'])


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
