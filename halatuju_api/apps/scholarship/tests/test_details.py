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
                # 2026-06 redesign: the structured roster is compulsory (not yet filled).
                'family_done': False,
                'complete': False,
            },
        )

    def _make_complete(self):
        """Set up all seven completeness parts: quiz, story, funding, docs
        (S22 + S23: ic + results_slip + parent_ic + one income proof), consent,
        address, guardian docs."""
        self.profile.student_signals = {'x': {'y': 1}}
        self.profile.address = 'No. 12, Jalan ABC, Taman XYZ'
        self.profile.postal_code = '62100'
        self.profile.city = 'Putrajaya'
        self.profile.save()
        self.app.aspirations = 'Be an accountant'
        self.app.plans = 'Study hard every day'
        self.app.daily_life = 'Help at home each evening'
        self.app.fears = 'Worried about textbook costs'
        # Gate v2: STR route + father earner so the STR doc satisfies the route.
        self.app.income_route, self.app.income_earner = 'str', 'father'
        # 2026-06 redesign: the structured family roster is compulsory.
        self.app.father_name, self.app.father_occupation = 'AROON A/L SAMY', 'driver'
        self.app.mother_name, self.app.mother_occupation = 'KOMATHI A/P RAMAN', 'homemaker'
        self.app.siblings_in_school, self.app.siblings_in_tertiary = 1, 0
        self.app.save()
        FundingNeed.objects.create(application=self.app, categories=['living'], programme_months=36)
        ApplicantDocument.objects.create(application=self.app, doc_type='ic', storage_path='x')
        ApplicantDocument.objects.create(application=self.app, doc_type='results_slip', storage_path='y')
        ApplicantDocument.objects.create(application=self.app, doc_type='offer_letter', storage_path='o')
        ApplicantDocument.objects.create(application=self.app, doc_type='parent_ic', storage_path='z')
        ApplicantDocument.objects.create(application=self.app, doc_type='str', storage_path='s')
        Consent.objects.create(application=self.app, version='t', is_active=True)

    def test_quiz_done_from_signals(self):
        self.profile.student_signals = {'field_interest': {'it': 5}}
        self.profile.save()
        self.assertTrue(application_completeness(self.app)['quiz_done'])

    def test_complete_when_all_present(self):
        # S5: complete = quiz + story + funding + compulsory docs + consent
        self._make_complete()
        self.assertTrue(application_completeness(self.app)['complete'])

    def test_details_done_requires_aspirations_plans_daily_and_fears(self):
        # aspirations + plans + daily_life + fears all required now.
        self.app.aspirations = 'Be an engineer'
        self.app.plans = ''
        self.app.daily_life = 'Help at home'
        self.app.fears = 'Textbook costs'
        self.app.justification = 'Family cannot fund'
        self.app.save()
        self.assertFalse(application_completeness(self.app)['details_done'])

        self.app.plans = 'Study hard'
        self.app.daily_life = ''   # missing daily_life still blocks
        self.app.save()
        self.assertFalse(application_completeness(self.app)['details_done'])

        self.app.daily_life = 'Help at home'
        self.app.fears = ''        # missing fears still blocks
        self.app.save()
        self.assertFalse(application_completeness(self.app)['details_done'])

        self.app.fears = 'Textbook costs'
        self.app.save()
        self.assertTrue(application_completeness(self.app)['details_done'])

    def test_documents_done_false_when_no_docs(self):
        """documents_done is False when no documents uploaded."""
        self.assertFalse(application_completeness(self.app)['documents_done'])

    def test_documents_done_false_when_only_ic(self):
        """documents_done is False when only IC is present (results_slip missing)."""
        ApplicantDocument.objects.create(application=self.app, doc_type='ic', storage_path='x')
        self.assertFalse(application_completeness(self.app)['documents_done'])

    def test_documents_done_false_when_income_proof_missing(self):
        """S23: ic + results_slip + parent_ic is no longer enough — income proof required too."""
        ApplicantDocument.objects.create(application=self.app, doc_type='ic', storage_path='x')
        ApplicantDocument.objects.create(application=self.app, doc_type='results_slip', storage_path='y')
        ApplicantDocument.objects.create(application=self.app, doc_type='parent_ic', storage_path='z')
        self.assertFalse(application_completeness(self.app)['documents_done'])

    def test_documents_done_true_with_str_route(self):
        """Gate v2: STR route (father) — ic + results + offer_letter + parent_ic + STR."""
        self.app.income_route, self.app.income_earner = 'str', 'father'
        self.app.save()
        for dt in ('ic', 'results_slip', 'offer_letter', 'parent_ic', 'str'):
            ApplicantDocument.objects.create(application=self.app, doc_type=dt, storage_path=dt)
        self.assertTrue(application_completeness(self.app)['documents_done'])

    def test_documents_done_true_with_salary_route(self):
        """Gate v2: salary route (father working) — IC + salary slip tagged to the member."""
        self.app.income_route, self.app.income_working_members = 'salary', ['father']
        self.app.save()
        for dt in ('ic', 'results_slip', 'offer_letter'):
            ApplicantDocument.objects.create(application=self.app, doc_type=dt, storage_path=dt)
        ApplicantDocument.objects.create(application=self.app, doc_type='parent_ic',
                                         storage_path='pi', household_member='father')
        ApplicantDocument.objects.create(application=self.app, doc_type='salary_slip',
                                         storage_path='ss', household_member='father')
        self.assertTrue(application_completeness(self.app)['documents_done'])

    def test_epf_alone_does_not_satisfy_salary_route(self):
        """Gate v2: EPF does NOT substitute the compulsory salary slip."""
        self.app.income_route, self.app.income_working_members = 'salary', ['father']
        self.app.save()
        for dt in ('ic', 'results_slip', 'offer_letter'):
            ApplicantDocument.objects.create(application=self.app, doc_type=dt, storage_path=dt)
        ApplicantDocument.objects.create(application=self.app, doc_type='parent_ic',
                                         storage_path='pi', household_member='father')
        ApplicantDocument.objects.create(application=self.app, doc_type='epf',
                                         storage_path='e', household_member='father')
        self.assertFalse(application_completeness(self.app)['documents_done'])   # slip still required
        ApplicantDocument.objects.create(application=self.app, doc_type='salary_slip',
                                         storage_path='ss', household_member='father')
        self.assertTrue(application_completeness(self.app)['documents_done'])

    def test_documents_done_false_when_parent_ic_missing(self):
        """S22: parent_ic is compulsory for everyone (not just minors)."""
        ApplicantDocument.objects.create(application=self.app, doc_type='ic', storage_path='x')
        ApplicantDocument.objects.create(application=self.app, doc_type='results_slip', storage_path='y')
        ApplicantDocument.objects.create(application=self.app, doc_type='str', storage_path='s')
        self.assertFalse(application_completeness(self.app)['documents_done'])

    def test_complete_requires_documents_consent_and_address(self):
        """S14: complete now gates on compulsory documents AND active consent AND address."""
        # quiz + story + funding only — not complete (docs + consent + address missing)
        self.profile.student_signals = {'x': {'y': 1}}
        self.profile.save()
        self.app.aspirations = 'Be an accountant'
        self.app.plans = 'Study hard every day'
        self.app.daily_life = 'Help at home each evening'
        self.app.fears = 'Worried about textbook costs'
        self.app.income_route, self.app.income_earner = 'str', 'father'
        self.app.save()
        FundingNeed.objects.create(application=self.app, categories=['living'], programme_months=36)
        self.assertFalse(application_completeness(self.app)['complete'])

        # + compulsory documents (gate v2: ic + results_slip + offer_letter + the STR
        # route's earner IC + STR) — still not complete (consent + address missing)
        for dt in ('ic', 'results_slip', 'offer_letter', 'parent_ic', 'str'):
            ApplicantDocument.objects.create(application=self.app, doc_type=dt, storage_path=dt)
        self.assertFalse(application_completeness(self.app)['complete'])

        # + active consent — still not complete (address missing)
        Consent.objects.create(application=self.app, version='t', is_active=True)
        self.assertFalse(application_completeness(self.app)['complete'])

        # + address — still not complete (the family roster is compulsory now)
        self.profile.address = 'No. 12, Jalan ABC'
        self.profile.postal_code = '62100'
        self.profile.city = 'Putrajaya'
        self.profile.save()
        self.assertFalse(application_completeness(self.app)['complete'])

        # + the structured family roster — now complete
        self.app.father_name, self.app.father_occupation = 'AROON A/L SAMY', 'driver'
        self.app.mother_name, self.app.mother_occupation = 'KOMATHI A/P RAMAN', 'homemaker'
        self.app.siblings_in_school, self.app.siblings_in_tertiary = 1, 0
        self.app.save()
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
                'daily_life': 'Help at home each evening', 'fears': 'Worried about fees',
                # S23: programme_months now compulsory for funding_done.
                'funding_need': {'categories': ['device', 'living'], 'programme_months': 36},
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
                'siblings_studying_count': 2,
                'family_context': 'Father ill; mother is the sole earner.',
                'daily_life': 'Wake at 5am, help at home, then school.',
            }, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body['first_in_family'])
        self.assertEqual(body['parents_occupation'], 'Factory worker')
        self.assertEqual(body['siblings_studying_count'], 2)
        self.assertEqual(body['family_context'], 'Father ill; mother is the sole earner.')
        self.assertEqual(body['daily_life'], 'Wake at 5am, help at home, then school.')

    def test_patch_saves_income_declared_and_rejects_bad_member(self):
        """Phase 2A: the declared-income map round-trips; an unknown member key is rejected."""
        self._auth(USER_A)
        ok = self.client.patch(
            f'/api/v1/scholarship/applications/{self.app_a.id}/',
            {'income_route': 'salary', 'income_working_members': ['father'],
             'income_declared': {'father': 1500}}, format='json')
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()['income_declared'], {'father': 1500})
        bad = self.client.patch(
            f'/api/v1/scholarship/applications/{self.app_a.id}/',
            {'income_declared': {'cousin': 900}}, format='json')
        self.assertEqual(bad.status_code, 400)

    def test_patch_saves_income_nonearning_and_rejects_bad_member(self):
        """Phase 2B: unemployment detail {member:{reason,since}} round-trips; bad key rejected."""
        self._auth(USER_A)
        ok = self.client.patch(
            f'/api/v1/scholarship/applications/{self.app_a.id}/',
            {'income_nonearning': {'father': {'reason': 'retrenched', 'since': '2025-03'}}},
            format='json')
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()['income_nonearning'],
                         {'father': {'reason': 'retrenched', 'since': '2025-03'}})
        bad = self.client.patch(
            f'/api/v1/scholarship/applications/{self.app_a.id}/',
            {'income_nonearning': {'cousin': {'reason': 'x'}}}, format='json')
        self.assertEqual(bad.status_code, 400)

    def test_patch_saves_long_parents_occupation(self):
        """Regression: parents_occupation is now a TextField, not varchar(255).
        A student's sentence-or-two answer (e.g. >255 chars) used to overflow the
        column and silently roll back the whole Story save."""
        self._auth(USER_A)
        long_answer = (
            'My mother works as a Grab driver and is the sole breadwinner of our '
            'family. My father does not provide any financial support and there is '
            'no contact with him. ' * 3
        ).strip()   # ~480 chars, comfortably over the old 255
        resp = self.client.patch(
            f'/api/v1/scholarship/applications/{self.app_a.id}/',
            {'parents_occupation': long_answer, 'aspirations': 'Be a teacher'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['parents_occupation'], long_answer)
        # The co-submitted narrative persisted too (no rollback).
        self.assertEqual(body['aspirations'], 'Be a teacher')
        self.app_a.refresh_from_db()
        self.assertEqual(self.app_a.parents_occupation, long_answer)

    def test_patch_rejects_spam_length_story_field(self):
        """Anti-spam: a free-text field over STORY_TEXT_MAX (5000) is a clean 400,
        not a 500/DB rollback. Guards against tens-of-thousands-of-char floods."""
        self._auth(USER_A)
        resp = self.client.patch(
            f'/api/v1/scholarship/applications/{self.app_a.id}/',
            {'parents_occupation': 'x' * 5001}, format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('parents_occupation', resp.json())

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

    def test_legacy_siblings_studying_boolean_is_ignored(self):
        """TD-061: the dropped siblings_studying boolean is no longer a field —
        an older client sending it must not 400; it's simply ignored."""
        self._auth(USER_A)
        resp = self.client.patch(
            f'/api/v1/scholarship/applications/{self.app_a.id}/',
            {'siblings_studying': True, 'siblings_studying_count': 2}, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertNotIn('siblings_studying', body)  # field gone from the serializer
        self.assertEqual(body['siblings_studying_count'], 2)

    def test_story_fields_defaults_are_correct(self):
        """New boolean fields default False; text fields default empty string."""
        self._auth(USER_A)
        resp = self.client.get(f'/api/v1/scholarship/applications/{self.app_a.id}/')
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body['first_in_family'])
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

    def test_patch_rejects_spam_length_funding_note(self):
        """Anti-spam: an over-cap funding_note is a clean 400 (nested under
        funding_need), not an unbounded write."""
        self._auth(USER_A)
        resp = self.client.patch(
            f'/api/v1/scholarship/applications/{self.app_a.id}/',
            {'funding_need': {'categories': ['living'], 'funding_note': 'x' * 5001}},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_funding_done_true_when_categories_and_months_set(self):
        """S23: funding_done is True when at least one category AND programme_months set."""
        self._auth(USER_A)
        resp = self.client.patch(
            f'/api/v1/scholarship/applications/{self.app_a.id}/',
            {'funding_need': {'categories': ['living'], 'programme_months': 36}}, format='json',
        )
        self.assertTrue(resp.json()['completeness']['funding_done'])

    def test_funding_done_false_when_categories_empty(self):
        """funding_done is False when categories list is empty (even with programme_months)."""
        self._auth(USER_A)
        url = f'/api/v1/scholarship/applications/{self.app_a.id}/'
        self.client.patch(url, {'funding_need': {'categories': ['living'], 'programme_months': 36}}, format='json')
        resp = self.client.patch(url, {'funding_need': {'categories': []}}, format='json')
        self.assertFalse(resp.json()['completeness']['funding_done'])

    def test_funding_done_false_when_programme_months_null(self):
        """S23: funding_done is False when programme_months is missing, even with a category."""
        self._auth(USER_A)
        resp = self.client.patch(
            f'/api/v1/scholarship/applications/{self.app_a.id}/',
            {'funding_need': {'categories': ['living']}}, format='json',
        )
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

    def test_minor_non_parent_consent_letter_optional(self):
        """The guardianship letter is now OPTIONAL — a non-parent guardian
        (grandparent etc.) is complete without it."""
        app = self._make_minor_app()
        Consent.objects.create(
            application=app, version='t', is_active=True,
            granted_by='guardian', guardian_name='Grandma',
            guardian_relationship='grandparent',
        )
        # No letter uploaded → still done (letter is optional now).
        self.assertTrue(application_completeness(app)['guardian_docs_done'])
        # Uploading one is still fine.
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


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestRequirementsOnThePayload(TestCase):
    """Sprint 3b — the Documents tab is TOLD what to ask for; it no longer decides.

    Written against the wire, not against `requirements.py`, because the point of this sprint is
    that the two sides now agree — and only a response body can show that. `test_requirements.py`
    proves the seam resolves correctly; these prove the answer reaches the student.

    ⚠ EVERY CASE BELOW SETS A PROGRAMME. The default fixtures in this file do not, so an
    application built the easy way takes the no-programme fallback — which is exactly how Sprint
    3a's near-miss stayed invisible through 5018 passing tests. One case deliberately leaves the
    catalogue EMPTY beside a set programme, because that is production's shape for any
    organisation onboarded before somebody remembers to seed.
    """

    @classmethod
    def setUpTestData(cls):
        from apps.courses.models import PartnerOrganisation
        from apps.scholarship.models import Programme
        cls.org = PartnerOrganisation.objects.create(code='req-org', name='Req Org')
        cls.programme = Programme.objects.create(
            organisation=cls.org, code='req-programme', name_en='Req Programme')
        cls.cohort = ScholarshipCohort.objects.create(
            code='req-c', name='Req', year=2026, programme=cls.programme)
        cls.profile = StudentProfile.objects.create(
            supabase_user_id=USER_A, nric='080303-14-9999')
        cls.app = ScholarshipApplication.objects.create(
            cohort=cls.cohort, profile=cls.profile, status='shortlisted', bucket='A')

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(USER_A)}')

    def _documents(self):
        resp = self.client.get(f'/api/v1/scholarship/applications/{self.app.id}/')
        self.assertEqual(resp.status_code, 200)
        return resp.json()['requirements']['documents']

    def _seed(self):
        from django.core.management import call_command
        call_command('seed_application_catalogue', verbosity=0)

    def _set(self, code, state):
        from apps.scholarship.models import ApplicationItem, ProgrammeApplicationItem
        item = ApplicationItem.objects.get(kind='document', code=code)
        ProgrammeApplicationItem.objects.update_or_create(
            programme=self.programme, item=item, defaults={'state': state})

    def test_the_payload_carries_exactly_the_documents_and_questions_blocks(self):
        # Sprint 3b pinned this at {'documents'} precisely so that Sprint 4 adding 'questions'
        # would be a deliberate edit to this test — this is that edit (2026-08-24). Still an
        # exact-set assertion, so a third block appearing one day is again a loud change.
        self._seed()
        resp = self.client.get(f'/api/v1/scholarship/applications/{self.app.id}/')
        self.assertEqual(set(resp.json()['requirements']), {'documents', 'questions'})
        self.assertEqual(set(self._documents()), {'required', 'optional'})
        self.assertEqual(set(resp.json()['requirements']['questions']), {'required', 'optional'})

    def test_a_seeded_catalogue_asks_for_what_the_gate_enforces(self):
        # The whole point: what the student is SHOWN is now the same list the submission gate
        # checks. `income_proof` is the income route engine as one switch, not a card.
        self._seed()
        docs = self._documents()
        self.assertEqual(docs['required'],
                         ['ic', 'income_proof', 'offer_letter', 'results_slip'])
        self.assertEqual(docs['optional'],
                         ['electricity_bill', 'photo', 'school_leaving_cert',
                          'statement_of_intent', 'water_bill'])

    def test_an_empty_catalogue_beside_a_programme_still_asks_for_everything(self):
        # PRODUCTION'S SHAPE. Not "what should happen" — what the rows actually look like for an
        # organisation whose catalogue nobody has seeded. An empty answer here would render a
        # Documents tab with no cards at all and mark nothing compulsory.
        from apps.scholarship.models import ApplicationItem
        self.assertEqual(ApplicationItem.objects.count(), 0)
        docs = self._documents()
        self.assertEqual(docs['required'],
                         ['ic', 'income_proof', 'offer_letter', 'results_slip'])
        self.assertIn('water_bill', docs['optional'])

    def test_a_programme_promoting_a_bill_to_required_reaches_the_student(self):
        self._seed()
        self._set('water_bill', 'required')
        docs = self._documents()
        self.assertIn('water_bill', docs['required'])
        self.assertNotIn('water_bill', docs['optional'])
        # ⚠ The two lines above pass on their own even if EVERYTHING is reported as required —
        # which is a real way to get this wrong, and it is the shape the Documents tab would
        # render as a wall of red asterisks. So assert the other bill did NOT move.
        self.assertIn('electricity_bill', docs['optional'])
        self.assertNotIn('electricity_bill', docs['required'])

    def test_a_document_switched_off_appears_in_neither_list(self):
        # "Off" is not a third list the front end has to interpret — it is absence, which is the
        # only state that can safely mean "do not draw this".
        self._seed()
        self._set('statement_of_intent', 'off')
        docs = self._documents()
        self.assertNotIn('statement_of_intent', docs['required'] + docs['optional'])

    def test_a_core_document_cannot_be_switched_off_via_the_payload_either(self):
        self._seed()
        self._set('ic', 'off')
        self.assertIn('ic', self._documents()['required'])

    def test_the_lists_are_sorted(self):
        # So a payload diff means a real change, not dict ordering.
        self._seed()
        docs = self._documents()
        self.assertEqual(docs['required'], sorted(docs['required']))
        self.assertEqual(docs['optional'], sorted(docs['optional']))

    # ── Sprint 4: the questions block (mirrors the document cases above) ──────

    def _questions(self):
        resp = self.client.get(f'/api/v1/scholarship/applications/{self.app.id}/')
        self.assertEqual(resp.status_code, 200)
        return resp.json()['requirements']['questions']

    def _setq(self, code, state):
        from apps.scholarship.models import ApplicationItem, ProgrammeApplicationItem
        item = ApplicationItem.objects.get(kind='question', code=code)
        ProgrammeApplicationItem.objects.update_or_create(
            programme=self.programme, item=item, defaults={'state': state})

    def test_the_seeded_question_defaults_reach_the_student(self):
        self._seed()
        q = self._questions()
        self.assertEqual(q['required'],
                         ['address', 'aspirations', 'consent', 'daily_life',
                          'family_roster', 'fears', 'funding', 'plans'])
        self.assertEqual(q['optional'], ['anything_else', 'justification'])

    def test_a_question_switched_off_appears_in_neither_list_and_its_neighbour_stays(self):
        # Off is absence — the wizard does not draw the field. And the neighbour NOT moving is
        # what distinguishes "this question went" from "everything went".
        self._seed()
        self._setq('aspirations', 'off')
        q = self._questions()
        self.assertNotIn('aspirations', q['required'] + q['optional'])
        self.assertIn('plans', q['required'])

    def test_a_core_question_cannot_be_switched_off_via_the_payload_either(self):
        self._seed()
        self._setq('consent', 'off')
        self.assertIn('consent', self._questions()['required'])

    def test_an_empty_catalogue_beside_a_programme_still_asks_every_question(self):
        # PRODUCTION'S SHAPE (the 3a rule, question kind): unconfigured means "as today",
        # never "asks nothing" — an empty answer here would blank the story tab's markers
        # while the server kept gating.
        from apps.scholarship.models import ApplicationItem
        self.assertEqual(ApplicationItem.objects.filter(kind='question').count(), 0)
        q = self._questions()
        self.assertIn('aspirations', q['required'])
        self.assertIn('anything_else', q['optional'])
