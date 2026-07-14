"""#117 — a retired / unable parent's PENSION is household income the means test was blind to.

A 'retired' parent sits in family.NON_EARNING, so member_income_status returns 'satisfied' and we
never ask what they draw nor count it. The error runs toward UNDERstating income — the direction a
fiscal steward must mind. So, mirroring #126 exactly: ASK FIRST ("does he draw a pension / benefit,
and roughly how much?"), hear the answer, and only on an explicit YES ask for the statement (reusing
the salary_slip slot — no new doc type, no migration). Negation is checked first, so "he gets no
pension" never drags a genuinely-nothing parent into a demand for a document they cannot produce.
"""
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.check2_queries import _gap_sets
from apps.scholarship.income_engine import pension_claim, pension_claimed, pension_members
from apps.scholarship.models import (ResolutionItem, ScholarshipApplication,
                                     ScholarshipCohort)


class TestPensionClaim(TestCase):
    """The classifier — pure, deterministic, negation-first (the #130 protection)."""

    def test_plain_yes_variants(self):
        for t in ('He receives a pension', 'yes he draws a monthly pension',
                  'ada pencen', 'my father gets a PERKESO benefit', 'dia dapat bantuan'):
            with self.subTest(answer=t):
                self.assertEqual(pension_claim(t), 'yes')

    def test_negation_is_read_first(self):
        # "no pension" CONTAINS 'pension' — reading that as a yes would re-form the #130 dead end.
        for t in ('He gets no pension', "He doesn't receive a pension", 'tiada pencen',
                  'no benefit at all', 'tidak dapat bantuan'):
            with self.subTest(answer=t):
                self.assertEqual(pension_claim(t), 'no')

    def test_an_answer_that_never_mentions_it_is_unclear(self):
        for t in ('He is retired and stays home', 'about RM500 a month', ''):
            with self.subTest(answer=t):
                self.assertEqual(pension_claim(t), 'unclear')


class TestPensionChain(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def _app(self, uid='p1', father_occupation='retired'):
        profile = StudentProfile.objects.create(
            supabase_user_id=uid, name='KIRIIYARASAN A/L TESTAN', nric='070101-07-0101',
            household_income=1200, household_size=5,
        )
        # A retired father, mother a homemaker — the father's pension is the invisible income.
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=profile, status='profile_complete',
            profile_completed_at=timezone.now(), income_route='salary',
            father_name='TESTAN A/L RAMU', father_occupation=father_occupation,
            mother_name='TESTAMMAL A/P SAMY', mother_occupation='homemaker',
        )

    def _answer(self, app, text):
        """Answer the ask-first pension clarify exactly as the resolve endpoint does."""
        return ResolutionItem.objects.create(
            application=app, source='check2', code='pension_amount_unknown',
            fact='income', kind='clarify', status='resolved', resolution_text=text,
            resolved_at=timezone.now(), resolved_by='student',
            params={'pension_claim': pension_claim(text)},
        )

    def test_a_retired_parent_is_asked_first(self):
        app = self._app()
        self.assertEqual(pension_members(app), ['father'])
        gaps, _ = _gap_sets(app)
        self.assertIn('pension_amount_unknown', gaps)

    def test_before_any_answer_no_statement_is_demanded(self):
        # Ask-first: nothing is demanded until the student says there is a pension to evidence.
        app = self._app()
        _, proof_wanted = _gap_sets(app)
        self.assertNotIn('father_pension_proof_missing', proof_wanted)

    def test_a_yes_opens_the_pension_statement_request(self):
        app = self._app()
        self._answer(app, 'Yes, my father draws a government pension')
        self.assertTrue(pension_claimed(app, 'father'))
        _, proof_wanted = _gap_sets(app)
        self.assertIn('father_pension_proof_missing', proof_wanted)

    def test_a_no_demands_nothing(self):
        app = self._app('p2')
        self._answer(app, 'He is retired and gets no pension')
        self.assertFalse(pension_claimed(app, 'father'))
        _, proof_wanted = _gap_sets(app)
        self.assertNotIn('father_pension_proof_missing', proof_wanted)

    def test_an_employed_parent_is_not_a_pension_case(self):
        app = self._app('p3', father_occupation='factory')
        self.assertEqual(pension_members(app), [])
        gaps, _ = _gap_sets(app)
        self.assertNotIn('pension_amount_unknown', gaps)
