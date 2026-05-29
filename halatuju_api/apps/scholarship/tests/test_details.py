"""Tests for STEP 2 deeper-info + funding need + completeness (Sprint 4a)."""
import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import StudentProfile
from apps.scholarship.models import (
    ApplicantDocument, Consent, FundingNeed, ScholarshipApplication, ScholarshipCohort,
)
from apps.scholarship.services import application_completeness

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
USER_A = 'detail-user-a'
USER_B = 'detail-user-b'


def _token(uid, secret=TEST_JWT_SECRET):
    return jwt.encode(
        {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
        secret, algorithm='HS256',
    )


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
                'consent_done': False,
                'address_done': False,
                # S17: adult by default (no profile NRIC → not a minor) → trivially True.
                'guardian_docs_done': True,
                'complete': False,
            },
        )

    def _make_complete(self):
        """Set up all seven completeness parts: quiz, story, funding, docs
        (S22: ic + results_slip + parent_ic), consent, address, guardian docs."""
        self.profile.student_signals = {'x': {'y': 1}}
        self.profile.address = 'No. 12, Jalan ABC, Taman XYZ'
        self.profile.postal_code = '62100'
        self.profile.city = 'Putrajaya'
        self.profile.save()
        self.app.aspirations = 'Be an accountant'
        self.app.plans = 'Study hard every day'
        self.app.save()
        FundingNeed.objects.create(application=self.app, categories=['living'])
        ApplicantDocument.objects.create(application=self.app, doc_type='ic', storage_path='x')
        ApplicantDocument.objects.create(application=self.app, doc_type='results_slip', storage_path='y')
        ApplicantDocument.objects.create(application=self.app, doc_type='parent_ic', storage_path='z')
        Consent.objects.create(application=self.app, version='t', is_active=True)

    def test_quiz_done_from_signals(self):
        self.profile.student_signals = {'field_interest': {'it': 5}}
        self.profile.save()
        self.assertTrue(application_completeness(self.app)['quiz_done'])

    def test_complete_when_all_present(self):
        # S5: complete = quiz + story + funding + compulsory docs + consent
        self._make_complete()
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

    def test_documents_done_true_when_all_three_compulsory_present(self):
        """S22: documents_done is True when ic + results_slip + parent_ic are all uploaded."""
        ApplicantDocument.objects.create(application=self.app, doc_type='ic', storage_path='x')
        ApplicantDocument.objects.create(application=self.app, doc_type='results_slip', storage_path='y')
        ApplicantDocument.objects.create(application=self.app, doc_type='parent_ic', storage_path='z')
        self.assertTrue(application_completeness(self.app)['documents_done'])

    def test_documents_done_false_when_parent_ic_missing(self):
        """S22: parent_ic is now compulsory for everyone (not just minors)."""
        ApplicantDocument.objects.create(application=self.app, doc_type='ic', storage_path='x')
        ApplicantDocument.objects.create(application=self.app, doc_type='results_slip', storage_path='y')
        self.assertFalse(application_completeness(self.app)['documents_done'])

    def test_complete_requires_documents_consent_and_address(self):
        """S14: complete now gates on compulsory documents AND active consent AND address."""
        # quiz + story + funding only — not complete (docs + consent + address missing)
        self.profile.student_signals = {'x': {'y': 1}}
        self.profile.save()
        self.app.aspirations = 'Be an accountant'
        self.app.plans = 'Study hard every day'
        self.app.save()
        FundingNeed.objects.create(application=self.app, categories=['living'])
        self.assertFalse(application_completeness(self.app)['complete'])

        # + compulsory documents — still not complete (consent + address missing)
        ApplicantDocument.objects.create(application=self.app, doc_type='ic', storage_path='x')
        ApplicantDocument.objects.create(application=self.app, doc_type='results_slip', storage_path='y')
        ApplicantDocument.objects.create(application=self.app, doc_type='parent_ic', storage_path='z')
        self.assertFalse(application_completeness(self.app)['complete'])

        # + active consent — still not complete (address missing)
        Consent.objects.create(application=self.app, version='t', is_active=True)
        self.assertFalse(application_completeness(self.app)['complete'])

        # + address — now complete
        self.profile.address = 'No. 12, Jalan ABC'
        self.profile.postal_code = '62100'
        self.profile.city = 'Putrajaya'
        self.profile.save()
        self.assertTrue(application_completeness(self.app)['complete'])

    def test_address_done_requires_street_postal_and_city(self):
        """address_done is True only when street + postal + city all present (state is set on /apply)."""
        # No address — False
        self.assertFalse(application_completeness(self.app)['address_done'])

        # Only street — still False
        self.profile.address = 'No. 12'
        self.profile.save()
        self.assertFalse(application_completeness(self.app)['address_done'])

        # Street + postal but no city — False
        self.profile.postal_code = '62100'
        self.profile.save()
        self.assertFalse(application_completeness(self.app)['address_done'])

        # All three — True
        self.profile.city = 'Putrajaya'
        self.profile.save()
        self.assertTrue(application_completeness(self.app)['address_done'])

        # Blank-string treated as empty
        self.profile.address = '   '
        self.profile.save()
        self.assertFalse(application_completeness(self.app)['address_done'])

    def test_consent_done_false_when_no_consent(self):
        self.assertFalse(application_completeness(self.app)['consent_done'])

    def test_consent_done_true_with_active_consent(self):
        Consent.objects.create(application=self.app, version='t', is_active=True)
        self.assertTrue(application_completeness(self.app)['consent_done'])

    def test_consent_done_false_when_withdrawn(self):
        """A withdrawn (inactive) consent does not count."""
        Consent.objects.create(application=self.app, version='t', is_active=False)
        self.assertFalse(application_completeness(self.app)['consent_done'])


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
                'funding_need': {'categories': ['device', 'living']},
            }, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['aspirations'], 'Become an auditor')
        self.assertEqual(body['plans'], 'Work hard every day')
        self.assertEqual(body['funding_need']['categories'], ['device', 'living'])
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

    def test_patch_saves_address_to_profile(self):
        """S14: address fields submitted via the details PATCH land on the profile,
        and the address shows up pre-filled on the next read."""
        self._auth(USER_A)
        resp = self.client.patch(
            f'/api/v1/scholarship/applications/{self.app_a.id}/',
            {
                'address': 'No. 12, Jalan ABC, Taman XYZ',
                'postal_code': '62100',
                'city': 'Putrajaya',
            }, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        # Read serializer exposes the profile-sourced address fields
        self.assertEqual(body['address'], 'No. 12, Jalan ABC, Taman XYZ')
        self.assertEqual(body['postal_code'], '62100')
        self.assertEqual(body['city'], 'Putrajaya')
        # Profile is the actual home for the data
        self.profile_a.refresh_from_db()
        self.assertEqual(self.profile_a.address, 'No. 12, Jalan ABC, Taman XYZ')
        self.assertEqual(self.profile_a.postal_code, '62100')
        self.assertEqual(self.profile_a.city, 'Putrajaya')
        # address_done now True; complete still False without quiz/story/funding/docs/consent
        self.assertTrue(body['completeness']['address_done'])
        self.assertFalse(body['completeness']['complete'])

    def test_patch_saves_siblings_studying_count(self):
        """S15: PATCH writes siblings_studying_count to the application."""
        self._auth(USER_A)
        resp = self.client.patch(
            f'/api/v1/scholarship/applications/{self.app_a.id}/',
            {'siblings_studying_count': 3}, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['siblings_studying_count'], 3)
        self.app_a.refresh_from_db()
        self.assertEqual(self.app_a.siblings_studying_count, 3)

    def test_patch_clears_siblings_studying_count_with_null(self):
        """S15: PATCH null clears the count (student edited from N back to blank)."""
        self.app_a.siblings_studying_count = 2
        self.app_a.save()
        self._auth(USER_A)
        resp = self.client.patch(
            f'/api/v1/scholarship/applications/{self.app_a.id}/',
            {'siblings_studying_count': None}, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()['siblings_studying_count'])
        self.app_a.refresh_from_db()
        self.assertIsNone(self.app_a.siblings_studying_count)

    def test_patch_rejects_negative_siblings_studying_count(self):
        """S15: serializer rejects negative counts (data-entry guard)."""
        self._auth(USER_A)
        resp = self.client.patch(
            f'/api/v1/scholarship/applications/{self.app_a.id}/',
            {'siblings_studying_count': -1}, format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_legacy_siblings_studying_boolean_still_accepted(self):
        """Back-compat: older clients still emit siblings_studying — must not 400."""
        self._auth(USER_A)
        resp = self.client.patch(
            f'/api/v1/scholarship/applications/{self.app_a.id}/',
            {'siblings_studying': True}, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.app_a.refresh_from_db()
        self.assertTrue(self.app_a.siblings_studying)

    def test_story_fields_defaults_are_correct(self):
        """New boolean fields default False; text fields default empty string."""
        self._auth(USER_A)
        resp = self.client.get(f'/api/v1/scholarship/applications/{self.app_a.id}/')
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body['first_in_family'])
        self.assertFalse(body['siblings_studying'])
        self.assertIsNone(body['siblings_studying_count'])
        self.assertEqual(body['parents_occupation'], '')
        self.assertEqual(body['family_context'], '')
        self.assertEqual(body['daily_life'], '')

    def test_patch_funding_idempotent_update(self):
        """Two PATCHes upsert a single FundingNeed row (no duplicates)."""
        self._auth(USER_A)
        url = f'/api/v1/scholarship/applications/{self.app_a.id}/'
        self.client.patch(url, {'funding_need': {'categories': ['living']}}, format='json')
        resp = self.client.patch(
            url, {'funding_need': {'categories': ['living', 'transport']}}, format='json',
        )
        self.assertEqual(resp.json()['funding_need']['categories'], ['living', 'transport'])
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
        """categories, funding_note, programme_months all persist."""
        self._auth(USER_A)
        resp = self.client.patch(
            f'/api/v1/scholarship/applications/{self.app_a.id}/',
            {
                'funding_need': {
                    'categories': ['living', 'transport', 'books'],
                    'programme_months': 36,
                    'funding_note': 'I will try for PTPTN as well.',
                },
            }, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        fn = resp.json()['funding_need']
        self.assertEqual(fn['categories'], ['living', 'transport', 'books'])
        self.assertEqual(fn['programme_months'], 36)
        self.assertEqual(fn['funding_note'], 'I will try for PTPTN as well.')

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
            # an empty funding_need payload still triggers get_or_create
            {'funding_need': {}}, format='json',
        )
        fn = resp.json()['funding_need']
        self.assertEqual(fn['categories'], [])
        self.assertEqual(fn['funding_note'], '')
        self.assertIsNone(fn['programme_months'])


# ─── S17: minor consent flow (guardian docs + relationship choices) ─────────

class TestGuardianDocsDone(TestCase):
    """guardian_docs_done is True for adults, conditionally True for minors."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c-s17', name='M', year=2026)

    def _make_minor_app(self):
        """Profile with a 2010-born NRIC → age ~16 → minor."""
        profile = StudentProfile.objects.create(
            supabase_user_id='minor-s17',
            name='Mark Benjamin',
            nric='100318-14-0635',
        )
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=profile, status='shortlisted',
        )

    def _make_adult_app(self):
        profile = StudentProfile.objects.create(
            supabase_user_id='adult-s17',
            name='Adult Person',
            nric='710101-14-1234',
        )
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=profile, status='shortlisted',
        )

    def test_adult_is_trivially_done(self):
        app = self._make_adult_app()
        self.assertTrue(application_completeness(app)['guardian_docs_done'])

    def test_minor_with_no_active_consent_is_done(self):
        """S22: parent_ic moved to documents_done (universal). guardian_docs_done
        for minors only checks the additional guardianship_letter, and only when
        the consenting adult is non-parent. With no active consent yet, the
        letter check is deferred → trivially True."""
        app = self._make_minor_app()
        self.assertTrue(application_completeness(app)['guardian_docs_done'])

    def test_minor_non_parent_consent_requires_letter(self):
        """S22: minor + non-parent guardian still needs the letter."""
        app = self._make_minor_app()
        # Active consent with grandparent relationship → letter required.
        Consent.objects.create(
            application=app, version='t', is_active=True,
            granted_by='guardian', guardian_name='Grandma',
            guardian_relationship='grandparent',
        )
        self.assertFalse(application_completeness(app)['guardian_docs_done'])
        # Upload guardianship_letter → done.
        ApplicantDocument.objects.create(
            application=app, doc_type='guardianship_letter', storage_path='x/l',
        )
        self.assertTrue(application_completeness(app)['guardian_docs_done'])

    def test_minor_father_consent_no_letter_needed(self):
        app = self._make_minor_app()
        Consent.objects.create(
            application=app, version='t', is_active=True,
            granted_by='guardian', guardian_name='Dad',
            guardian_relationship='father',
        )
        # Father relationship → no letter required → done.
        self.assertTrue(application_completeness(app)['guardian_docs_done'])
