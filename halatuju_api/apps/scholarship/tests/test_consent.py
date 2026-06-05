"""Tests for consent + minor/guardian gate (Sprint 5a)."""
import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import StudentProfile
from apps.scholarship.models import Consent, ScholarshipApplication, ScholarshipCohort
from apps.scholarship.services import CONSENT_VERSION, age_from_nric, is_minor

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
ADULT = 'consent-adult'
MINOR = 'consent-minor'


def _token(uid, secret=TEST_JWT_SECRET):
    return jwt.encode(
        {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
        secret, algorithm='HS256',
    )


class TestAgeMinor(TestCase):
    def test_age_parses_valid_nric(self):
        self.assertIsInstance(age_from_nric('030101-14-1234'), int)

    def test_age_none_for_unparseable(self):
        self.assertIsNone(age_from_nric(''))
        self.assertIsNone(age_from_nric('xx'))

    def test_is_minor_distinguishes(self):
        self.assertFalse(is_minor(StudentProfile(nric='030101-14-1234')))  # 2003 -> adult
        self.assertTrue(is_minor(StudentProfile(nric='110101-14-1234')))   # 2011 -> minor
        self.assertFalse(is_minor(None))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestConsentApi(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.adult = StudentProfile.objects.create(supabase_user_id=ADULT, nric='030101-14-1234')
        cls.minor = StudentProfile.objects.create(supabase_user_id=MINOR, nric='110101-14-5678')
        cls.app_adult = ScholarshipApplication.objects.create(
            cohort=cls.cohort, profile=cls.adult, status='shortlisted',
        )
        cls.app_minor = ScholarshipApplication.objects.create(
            cohort=cls.cohort, profile=cls.minor, status='shortlisted',
        )

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _make_ready(self, app, profile, *, parent_ic=True, ic_nric=None, ic_name=None):
        """Bring an application to consent-ready (passes consent_blockers): quiz +
        story + address + funding done, and ic + results_slip + parent_ic + income
        proof uploaded, with the student's OWN ic OCR matching the profile name/NRIC.
        Minor tests pass parent_ic=False and add their own OCR'd parent_ic for the
        guardian gate."""
        from django.utils import timezone
        from apps.scholarship.models import ApplicantDocument, FundingNeed
        if ic_name:
            profile.name = ic_name
        elif not profile.name:
            profile.name = 'Student Name'
        profile.student_signals = {'aptitude': 'science'}
        profile.address, profile.postal_code, profile.city = '1 Jalan Test', '50000', 'KL'
        profile.save()
        app.aspirations, app.plans = 'Become an engineer.', 'Study hard and apply.'
        app.daily_life, app.fears = 'I help at home each evening.', 'I worry about textbook costs.'
        # Gate v2: a consent-ready income cluster = STR route, father earner (no BC),
        # with the earner IC + the STR doc; plus the now-compulsory offer letter.
        app.income_route, app.income_earner = 'str', 'father'
        app.save()
        FundingNeed.objects.update_or_create(
            application=app, defaults={'categories': ['tuition'], 'programme_months': 24})
        now = timezone.now()
        ApplicantDocument.objects.create(
            application=app, doc_type='ic', storage_path='x/ic',
            vision_nric=ic_nric or profile.nric, vision_name=ic_name or profile.name,
            vision_run_at=now, vision_error='')
        ApplicantDocument.objects.create(application=app, doc_type='results_slip', storage_path='x/r')
        ApplicantDocument.objects.create(application=app, doc_type='offer_letter', storage_path='x/o')
        ApplicantDocument.objects.create(application=app, doc_type='str', storage_path='x/s')
        if parent_ic:
            ApplicantDocument.objects.create(application=app, doc_type='parent_ic', storage_path='x/pi')

    def _ic_doc(self, app):
        from apps.scholarship.models import ApplicantDocument
        return ApplicantDocument.objects.filter(application=app, doc_type='ic').first()

    def test_adult_self_consent(self):
        self._make_ready(self.app_adult, self.adult)
        self._auth(ADULT)
        resp = self.client.post('/api/v1/scholarship/consent/', {'locale': 'en'}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['version'], CONSENT_VERSION)
        self.assertEqual(resp.json()['granted_by'], 'self')

    def test_consent_blocked_until_profile_complete(self):
        """The new gate: an incomplete application cannot give consent, and the
        response lists every outstanding item at once."""
        self._auth(ADULT)
        resp = self.client.post('/api/v1/scholarship/consent/', {'locale': 'en'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['error'], 'consent_not_ready')
        blockers = set(resp.json()['blockers'])
        # All five outstanding categories surface together (not one at a time).
        self.assertTrue({'quiz_incomplete', 'story_incomplete', 'funding_incomplete',
                         'ic_missing', 'results_slip_missing'}.issubset(blockers))

    def test_minor_requires_guardian(self):
        self._make_ready(self.app_minor, self.minor, parent_ic=False)
        self._add_parent_ic_with_ocr(nric='700101-14-1234', name='Parent Name')
        self._auth(MINOR)
        resp = self.client.post('/api/v1/scholarship/consent/', {'granted_by': 'self'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def _add_parent_ic_with_ocr(self, *, nric='700101-14-1234', name='Parent Name'):
        """S19 helper: parent_ic doc with Vision OCR fields populated so the
        view's hard-gate name+NRIC match has something to compare against."""
        from django.utils import timezone
        from apps.scholarship.models import ApplicantDocument
        return ApplicantDocument.objects.create(
            application=self.app_minor, doc_type='parent_ic', storage_path='x/p',
            vision_nric=nric, vision_name=name,
            vision_run_at=timezone.now(), vision_error='',
        )

    def test_minor_with_guardian_ok(self):
        # S17/S19: parent_ic uploaded with OCR; typed name + NRIC must match.
        self._make_ready(self.app_minor, self.minor, parent_ic=False)
        self._add_parent_ic_with_ocr(nric='700101-14-1234', name='Parent Name')
        self._auth(MINOR)
        resp = self.client.post('/api/v1/scholarship/consent/', {
            'granted_by': 'guardian', 'guardian_name': 'Parent Name',
            'guardian_relationship': 'mother',
            'guardian_nric': '700101-14-1234',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['guardian_name'], 'Parent Name')
        self.assertEqual(resp.json()['guardian_nric'], '700101-14-1234')

    def test_minor_rejected_without_parent_ic(self):
        """parent_ic is part of the completeness gate now (compulsory for everyone),
        so a missing parent_ic surfaces as a consent_not_ready blocker rather than
        the old single 'parent_ic_required' error."""
        self._make_ready(self.app_minor, self.minor, parent_ic=False)  # everything but parent_ic
        self._auth(MINOR)
        resp = self.client.post('/api/v1/scholarship/consent/', {
            'granted_by': 'guardian', 'guardian_name': 'Parent',
            'guardian_relationship': 'mother',
            'guardian_nric': '700101-14-1234',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['error'], 'consent_not_ready')
        self.assertIn('parent_ic_missing:father', resp.json()['blockers'])   # member-qualified (STR earner)

    def test_minor_non_parent_ok_without_letter(self):
        """The guardianship letter is now OPTIONAL — a non-parent guardian
        (grandparent etc.) can consent without it (was a hard block before)."""
        self._make_ready(self.app_minor, self.minor, parent_ic=False)
        self._add_parent_ic_with_ocr(nric='500101-14-1234', name='Grandma')
        self._auth(MINOR)
        resp = self.client.post('/api/v1/scholarship/consent/', {
            'granted_by': 'guardian', 'guardian_name': 'Grandma',
            'guardian_relationship': 'grandparent',
            'guardian_nric': '500101-14-1234',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['guardian_relationship'], 'grandparent')

    def test_minor_non_parent_ok_with_letter(self):
        """Both docs uploaded + non-parent relationship → 201 accept."""
        from apps.scholarship.models import ApplicantDocument
        self._make_ready(self.app_minor, self.minor, parent_ic=False)
        self._add_parent_ic_with_ocr(nric='500101-14-1234', name='Grandma')
        ApplicantDocument.objects.create(
            application=self.app_minor, doc_type='guardianship_letter', storage_path='x/l',
        )
        self._auth(MINOR)
        resp = self.client.post('/api/v1/scholarship/consent/', {
            'granted_by': 'guardian', 'guardian_name': 'Grandma',
            'guardian_relationship': 'grandparent',
            'guardian_nric': '500101-14-1234',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['guardian_relationship'], 'grandparent')

    def test_invalid_relationship_rejected(self):
        """Free-text gibberish is rejected by the serializer (400 with field error)."""
        self._add_parent_ic_with_ocr()
        self._auth(MINOR)
        resp = self.client.post('/api/v1/scholarship/consent/', {
            'granted_by': 'guardian', 'guardian_name': 'X',
            'guardian_relationship': 'random-typed-text',
            'guardian_nric': '700101-14-1234',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('guardian_relationship', resp.json())

    # ─── S19 hard-gate tests ───────────────────────────────────────────────

    def test_minor_rejected_when_typed_nric_mismatches_parent_ic(self):
        """S19: typed parent NRIC must match the parent_ic Vision OCR.
        Was a soft anomaly flag in S17; lawyers won't accept anyone being
        able to type a fake parent NRIC in someone else's session."""
        self._make_ready(self.app_minor, self.minor, parent_ic=False)
        self._add_parent_ic_with_ocr(nric='700101-14-1234', name='Parent Name')
        self._auth(MINOR)
        resp = self.client.post('/api/v1/scholarship/consent/', {
            'granted_by': 'guardian', 'guardian_name': 'Parent Name',
            'guardian_relationship': 'mother',
            'guardian_nric': '710101-14-9999',  # wrong NRIC
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['error'], 'parent_ic_nric_mismatch')

    def test_minor_rejected_when_typed_name_mismatches_parent_ic(self):
        """S19: typed parent name must match (token-set) the parent_ic Vision OCR."""
        self._make_ready(self.app_minor, self.minor, parent_ic=False)
        self._add_parent_ic_with_ocr(nric='700101-14-1234', name='Real Parent Name')
        self._auth(MINOR)
        resp = self.client.post('/api/v1/scholarship/consent/', {
            'granted_by': 'guardian', 'guardian_name': 'Totally Different Person',
            'guardian_relationship': 'mother',
            'guardian_nric': '700101-14-1234',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['error'], 'parent_ic_name_mismatch')

    def test_minor_rejected_when_guardian_nric_missing(self):
        """S19: guardian_nric is now required alongside name + relationship."""
        self._make_ready(self.app_minor, self.minor, parent_ic=False)
        self._add_parent_ic_with_ocr()
        self._auth(MINOR)
        resp = self.client.post('/api/v1/scholarship/consent/', {
            'granted_by': 'guardian', 'guardian_name': 'Parent',
            'guardian_relationship': 'mother',
            # guardian_nric omitted
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        # The first guardian-required check fires (combined error message).
        self.assertIn('error', resp.json())

    def test_nric_match_strips_hyphens(self):
        """S19: typed NRIC with hyphens must match Vision-OCR NRIC without
        hyphens (and vice versa) — comparison strips non-digits."""
        self._make_ready(self.app_minor, self.minor, parent_ic=False)
        self._add_parent_ic_with_ocr(nric='700101141234', name='Parent Name')  # no hyphens
        self._auth(MINOR)
        resp = self.client.post('/api/v1/scholarship/consent/', {
            'granted_by': 'guardian', 'guardian_name': 'Parent Name',
            'guardian_relationship': 'mother',
            'guardian_nric': '700101-14-1234',  # with hyphens
        }, format='json')
        self.assertEqual(resp.status_code, 201)

    def test_consent_supersedes_prior(self):
        self._make_ready(self.app_adult, self.adult)
        self._auth(ADULT)
        self.client.post('/api/v1/scholarship/consent/', {}, format='json')
        self.client.post('/api/v1/scholarship/consent/', {}, format='json')
        self.assertEqual(
            Consent.objects.filter(application=self.app_adult, is_active=True).count(), 1,
        )
        self.assertEqual(Consent.objects.filter(application=self.app_adult).count(), 2)

    # ─── Consent-readiness gate: student IC identity (name + NRIC) ─────────

    def test_ic_nric_mismatch_blocks_consent(self):
        self._make_ready(self.app_adult, self.adult)
        ic = self._ic_doc(self.app_adult)
        ic.vision_nric = '999999-99-9999'   # doesn't match the profile NRIC
        ic.save()
        self._auth(ADULT)
        resp = self.client.post('/api/v1/scholarship/consent/', {}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['error'], 'consent_not_ready')
        self.assertIn('ic_nric_mismatch', resp.json()['blockers'])

    def test_ic_name_mismatch_blocks_consent(self):
        # A name mismatch blocks ONLY when the NRIC ALSO fails (a genuinely wrong
        # IC). With a matching NRIC the name mismatch is treated as a soft OCR miss
        # and does not block — see test_ic_name_mismatch_with_nric_match_allowed.
        self._make_ready(self.app_adult, self.adult)
        ic = self._ic_doc(self.app_adult)
        ic.vision_nric = '999999-99-9999'             # NRIC also wrong → genuine wrong IC
        ic.vision_name = 'Totally Different Person'    # disjoint tokens → mismatch
        ic.save()
        self._auth(ADULT)
        resp = self.client.post('/api/v1/scholarship/consent/', {}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('ic_name_mismatch', resp.json()['blockers'])

    def test_ic_name_mismatch_with_nric_match_allowed(self):
        # The hard key is the NRIC. A flaky name OCR (e.g. a locality picked up as
        # the name) must NOT block a student whose NRIC verified.
        self._make_ready(self.app_adult, self.adult)
        ic = self._ic_doc(self.app_adult)
        ic.vision_name = 'TAMAN SRI LAYANG'            # name OCR miss; NRIC still matches
        ic.save()
        self._auth(ADULT)
        resp = self.client.post('/api/v1/scholarship/consent/', {}, format='json')
        # Not blocked by the name; consent goes through (or fails only on other gates).
        if resp.status_code == 400:
            self.assertNotIn('ic_name_mismatch', resp.json().get('blockers', []))

    def test_ic_partial_name_does_not_block(self):
        """A subset name (same person, shorter/longer form) passes — NRIC is the
        hard identity key, so 'partial' is allowed."""
        self._make_ready(self.app_adult, self.adult, ic_name='Priya Devi Kumar')
        ic = self._ic_doc(self.app_adult)
        ic.vision_name = 'Priya Kumar'   # subset of the profile name → 'partial'
        ic.save()
        self._auth(ADULT)
        resp = self.client.post('/api/v1/scholarship/consent/', {}, format='json')
        self.assertEqual(resp.status_code, 201)

    def test_ic_unreadable_blocks_consent(self):
        """OCR ran but read nothing usable (poor image) → re-upload."""
        self._make_ready(self.app_adult, self.adult)
        ic = self._ic_doc(self.app_adult)
        ic.vision_nric, ic.vision_name, ic.vision_error = '', '', ''
        ic.save()
        self._auth(ADULT)
        resp = self.client.post('/api/v1/scholarship/consent/', {}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('ic_unreadable', resp.json()['blockers'])

    def test_ic_service_down_blocks_consent(self):
        """A Vision service error (down / quota / config) → try later, not re-upload."""
        self._make_ready(self.app_adult, self.adult)
        ic = self._ic_doc(self.app_adult)
        ic.vision_error = 'API quota exceeded'
        ic.save()
        self._auth(ADULT)
        resp = self.client.post('/api/v1/scholarship/consent/', {}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('ic_service_down', resp.json()['blockers'])

    def test_ready_application_has_no_blockers(self):
        self._make_ready(self.app_adult, self.adult)
        self._auth(ADULT)
        resp = self.client.get('/api/v1/scholarship/consent/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['blockers'], [])

    def test_get_returns_blockers_when_incomplete(self):
        self._auth(ADULT)
        resp = self.client.get('/api/v1/scholarship/consent/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('blockers', resp.json())
        self.assertIn('ic_missing', resp.json()['blockers'])

    def test_get_consent_status_minor(self):
        self._auth(MINOR)
        resp = self.client.get('/api/v1/scholarship/consent/')
        self.assertEqual(resp.status_code, 200)
        # S19: GET surfaces student context + parent_ic OCR values so the FE
        # can render parent-voice text + run the live mismatch check in one fetch.
        body = resp.json()
        self.assertIn('student_name', body)
        self.assertIn('student_nric', body)
        self.assertIn('student_gender', body)
        self.assertIn('parent_ic_vision_nric', body)
        self.assertIn('parent_ic_vision_name', body)
        self.assertTrue(resp.json()['is_minor'])
        self.assertEqual(resp.json()['consent_version'], CONSENT_VERSION)

    def test_consent_requires_auth(self):
        resp = self.client.post('/api/v1/scholarship/consent/', {}, format='json')
        self.assertEqual(resp.status_code, 401)


class TestIncomeGateV2(TestCase):
    """Gate v2 (2026-06-05): route-aware compulsory income docs + a compulsory offer
    letter + grandfathering for already-submitted apps. Tested directly against
    `income_doc_blockers` / `consent_blockers` / `application_completeness`."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='gv2', name='B40', year=2026)

    def _app(self, *, route='', earner='', members=None, submitted=False):
        import uuid
        prof = StudentProfile.objects.create(
            supabase_user_id=str(uuid.uuid4()), nric='030101-14-1234', name='Student')
        app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=prof, status='shortlisted',
            income_route=route, income_earner=earner, income_working_members=members or [])
        if submitted:
            from django.utils import timezone
            app.status, app.profile_completed_at = 'profile_complete', timezone.now()
            app.save()
        return app

    def _doc(self, app, doc_type, member=''):
        from apps.scholarship.models import ApplicantDocument
        return ApplicantDocument.objects.create(
            application=app, doc_type=doc_type, storage_path=f'x/{doc_type}/{member}',
            household_member=member)

    def _blockers(self, app):
        from apps.scholarship.services import income_doc_blockers
        return income_doc_blockers(app)

    # ── route-aware income requirements ──────────────────────────────────────
    def test_blank_route_is_income_incomplete(self):
        self.assertEqual(self._blockers(self._app(route='')), ['income_incomplete'])

    def test_str_father_needs_earner_ic_and_str_no_bc(self):
        app = self._app(route='str', earner='father')
        # STR doc leads, then the earner IC (matches the Documents-UI display order);
        # the IC code is member-qualified so the checklist names the earner.
        self.assertEqual(self._blockers(app), ['str_missing', 'parent_ic_missing:father'])
        self._doc(app, 'parent_ic')
        self._doc(app, 'str')
        self.assertEqual(self._blockers(app), [])   # father → patronymic, no BC

    def test_str_mother_also_needs_birth_certificate(self):
        app = self._app(route='str', earner='mother')
        self._doc(app, 'parent_ic')
        self._doc(app, 'str')
        self.assertEqual(self._blockers(app), ['birth_certificate_missing'])
        self._doc(app, 'birth_certificate')
        self.assertEqual(self._blockers(app), [])

    def test_salary_mother_needs_ic_slip_and_bc(self):
        app = self._app(route='salary', members=['mother'])
        self.assertEqual(set(self._blockers(app)),
                         {'parent_ic_missing:mother', 'salary_slip_missing:mother', 'birth_certificate_missing'})
        self._doc(app, 'parent_ic', member='mother')
        self._doc(app, 'salary_slip', member='mother')
        self._doc(app, 'birth_certificate')   # single household doc, untagged
        self.assertEqual(self._blockers(app), [])

    def test_salary_epf_does_not_substitute_salary_slip(self):
        app = self._app(route='salary', members=['father'])
        self._doc(app, 'parent_ic', member='father')
        self._doc(app, 'epf', member='father')           # EPF present...
        self.assertEqual(self._blockers(app), ['salary_slip_missing:father'])  # ...slip still required

    def test_salary_multi_member_each_member_checked(self):
        app = self._app(route='salary', members=['father', 'mother'])
        self._doc(app, 'parent_ic', member='father')
        self._doc(app, 'salary_slip', member='father')   # father complete; mother's missing
        b = set(self._blockers(app))
        self.assertEqual(b, {'parent_ic_missing:mother', 'salary_slip_missing:mother', 'birth_certificate_missing'})

    def test_salary_tagging_is_member_scoped(self):
        # Father's slip must NOT satisfy the mother's requirement (tag-scoped).
        app = self._app(route='salary', members=['mother'])
        self._doc(app, 'parent_ic', member='father')     # wrong member
        self._doc(app, 'salary_slip', member='father')
        self.assertEqual(set(self._blockers(app)),
                         {'parent_ic_missing:mother', 'salary_slip_missing:mother', 'birth_certificate_missing'})

    # ── offer letter + documents_done + grandfather ──────────────────────────
    def test_offer_letter_compulsory(self):
        from apps.scholarship.services import consent_blockers
        app = self._app(route='str', earner='father')
        self._doc(app, 'parent_ic')
        self._doc(app, 'str')
        self.assertIn('offer_letter_missing', consent_blockers(app))   # income done, offer not

    def test_documents_done_strict_for_new_submission(self):
        from apps.scholarship.services import application_completeness
        app = self._app(route='str', earner='father')          # shortlisted
        for dt in ('ic', 'results_slip', 'parent_ic', 'str'):
            self._doc(app, dt)
        self.assertFalse(application_completeness(app)['documents_done'])  # no offer letter
        self._doc(app, 'offer_letter')
        self.assertTrue(application_completeness(app)['documents_done'])

    def test_grandfathered_submitted_app_keeps_old_bar(self):
        from apps.scholarship.services import application_completeness
        # Already submitted, blank route, no offer letter — but the OLD docs present.
        app = self._app(route='', submitted=True)
        for dt in ('ic', 'results_slip', 'parent_ic', 'str'):
            self._doc(app, dt)
        # Lenient (old) bar for a submitted app → stays done, so revert never fires.
        self.assertTrue(application_completeness(app)['documents_done'])
