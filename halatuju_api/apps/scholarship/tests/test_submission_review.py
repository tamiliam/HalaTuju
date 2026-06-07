"""Tests for Check 2 STEP 1 — the deterministic submission-review facts ledger
(``submission_review.py``). Pure rules, no LLM.
"""
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.models import (
    ApplicantDocument, FundingNeed, ScholarshipApplication, ScholarshipCohort,
)
from apps.scholarship.submission_review import (
    build_facts_ledger, completeness_gaps, submission_review,
)


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        self.profile = StudentProfile.objects.create(
            supabase_user_id=f'sr-{self.id()}',
            name='Priya Devi', nric='030101-14-1234', school='SMK Taman',
            exam_type='SPM', household_income=1200, household_size=5,
            preferred_state='Selangor', receives_str=True, receives_jkm=False,
        )
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='shortlisted',
            aspirations='I want to become a teacher.', plans='Sit STPM, then IPG.',
            parents_occupation='Rubber tapper', field_of_study='Education',
        )

    def _ledger(self):
        return {r['claim']: r for r in build_facts_ledger(self.app)}


class TestFactsLedger(_Base):
    def test_emits_core_claims_with_verification(self):
        led = self._ledger()
        # identity-backed name; no IC uploaded → identity verdict is a gap → unverified.
        self.assertEqual(led['name']['verification'], 'unverified')
        self.assertEqual(led['name']['source'], 'identity_verdict')
        # self-reported structured fields.
        self.assertEqual(led['school']['verification'], 'reported')
        self.assertEqual(led['household_size']['verification'], 'reported')
        # student's own words.
        self.assertEqual(led['motivation']['verification'], 'student_words')
        self.assertEqual(led['plans']['verification'], 'student_words')

    def test_blank_claims_are_omitted(self):
        # family_context / daily_life were never set → no row.
        led = self._ledger()
        self.assertNotIn('family_context', led)
        self.assertNotIn('daily_life', led)

    def test_zero_value_is_kept(self):
        self.app.siblings_in_school = 0
        self.app.siblings_in_tertiary = 0
        self.app.save()
        led = self._ledger()
        self.assertIn('siblings_in_school', led)
        self.assertEqual(led['siblings_in_school']['value'], '0')

    def test_first_in_family_verified_when_no_tertiary_sibling(self):
        self.app.first_in_family = True
        self.app.siblings_in_tertiary = 0
        self.app.save()
        led = self._ledger()
        self.assertEqual(led['first_in_family']['verification'], 'verified')

    def test_first_in_family_unverified_when_sibling_in_tertiary(self):
        self.app.first_in_family = True
        self.app.siblings_in_tertiary = 1
        self.app.save()
        led = self._ledger()
        self.assertEqual(led['first_in_family']['verification'], 'unverified')

    def test_first_in_family_omitted_when_not_claimed(self):
        self.app.first_in_family = False
        self.app.save()
        self.assertNotIn('first_in_family', self._ledger())

    def test_motivation_falls_back_to_letter_of_intent(self):
        self.app.aspirations = ''
        self.app.save()
        ApplicantDocument.objects.create(
            application=self.app, doc_type='statement_of_intent',
            storage_path=f'{self.app.id}/statement_of_intent/x',
            vision_fields={'text': 'Teaching has been my calling since I tutored my cousins.'},
            vision_fields_run_at=timezone.now(),
        )
        led = self._ledger()
        self.assertIn('motivation', led)
        self.assertIn('Teaching', led['motivation']['value'])


class TestCompletenessGaps(_Base):
    def _codes(self):
        return {g['code'] for g in completeness_gaps(self.app)}

    def test_transport_gap_only_for_stpm(self):
        # Residential / unknown pathway → no transport question.
        self.assertNotIn('transport_cost_unknown', self._codes())
        # STPM → daily travel cost is worth asking.
        self.app.chosen_pathway = 'stpm'
        self.app.pathway_certainty = 'sure'
        self.app.save()
        self.assertIn('transport_cost_unknown', self._codes())

    def test_device_gap_unless_ticked(self):
        self.assertIn('device_status_unknown', self._codes())
        FundingNeed.objects.create(application=self.app, categories=['device'])
        self.assertNotIn('device_status_unknown', self._codes())

    def test_motivation_gap_when_no_aspirations_or_letter(self):
        self.app.aspirations = ''
        self.app.save()
        self.assertIn('motivation_missing', self._codes())

    def test_no_motivation_gap_when_aspirations_present(self):
        self.assertNotIn('motivation_missing', self._codes())

    def test_sibling_level_unknown_with_legacy_count_only(self):
        self.app.siblings_studying_count = 2  # no split → can't derive
        self.app.save()
        self.assertIn('sibling_level_unknown', self._codes())

    def test_sibling_level_known_with_split(self):
        self.app.siblings_in_tertiary = 1
        self.app.save()
        self.assertNotIn('sibling_level_unknown', self._codes())


class TestAggregate(_Base):
    def test_submission_review_shape(self):
        out = submission_review(self.app)
        self.assertEqual(set(out), {'ledger', 'completeness', 'consistency'})
        self.assertIsInstance(out['ledger'], list)
        self.assertIsInstance(out['completeness'], list)
        self.assertIsInstance(out['consistency'], list)
