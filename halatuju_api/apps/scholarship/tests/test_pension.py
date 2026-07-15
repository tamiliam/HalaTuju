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
from apps.scholarship.income_engine import (
    _member_income_documented, _parent_has_income_evidence, informal_income_detail_gap,
    informal_income_members, member_income_status, pension_claim, pension_claimed,
    pension_members, str_earner_income_document_gap,
)
from apps.scholarship.models import (ApplicantDocument, ResolutionItem, ScholarshipApplication,
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


class TestStrRouteSalaryPicture(TestCase):
    """Owner 2026-07-16 (off #117): the STR route settles the B40 verdict, but it must NOT stop the
    system building the household's complete SALARY PICTURE — a fuller sponsor profile. So an
    STR-recipient parent is still inquired about: retired→pension, informal→ask-first, formal→slip.
    The verdict + submission gate are untouched (the STR stays dispositive there)."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='cstr', name='B40', year=2026)

    def _app(self, *, uid, father_occupation, earner='father'):
        profile = StudentProfile.objects.create(
            supabase_user_id=uid, name='KIRIIYARASAN A/L TESTAN', nric='070101-07-0102',
            household_income=1200, household_size=5)
        app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=profile, status='profile_complete',
            profile_completed_at=timezone.now(), income_route='str', income_earner=earner,
            father_name='TESTAN A/L RAMU', father_occupation=father_occupation,
            mother_name='TESTAMMAL A/P SAMY', mother_occupation='homemaker')
        # A live STR tagged to the earner — the doc that used to mask them as 'evidenced'.
        ApplicantDocument.objects.create(
            application=app, doc_type='str', household_member=earner,
            storage_path=f'{app.id}/str/{earner}')
        return app

    def _add_salary(self, app, member='father'):
        ApplicantDocument.objects.create(
            application=app, doc_type='salary_slip', household_member=member,
            storage_path=f'{app.id}/salary_slip/{member}')

    def test_retired_str_earner_is_still_asked_about_pension(self):
        # The #117 case: father retired AND the STR recipient. Pre-fix the STR masked him.
        app = self._app(uid='str-retired', father_occupation='retired')
        self.assertEqual(pension_members(app), ['father'])
        gaps, _ = _gap_sets(app)
        self.assertIn('pension_amount_unknown', gaps)

    def test_informal_str_earner_gets_the_ask_first_clarify(self):
        app = self._app(uid='str-informal', father_occupation='driver')
        self.assertIn('father', informal_income_members(app))
        self.assertTrue(informal_income_detail_gap(app))
        gaps, _ = _gap_sets(app)
        self.assertIn('informal_income_detail', gaps)

    def test_formal_str_earner_is_asked_for_their_salary_slip(self):
        app = self._app(uid='str-formal', father_occupation='factory')
        self.assertEqual(str_earner_income_document_gap(app), 'father')
        _, proof_wanted = _gap_sets(app)
        self.assertIn('father_income_proof_missing', proof_wanted)

    def test_a_documented_str_earner_is_not_re_asked(self):
        # Once the STR earner's OWN salary slip is on file, the salary-picture ask clears.
        app = self._app(uid='str-documented', father_occupation='factory')
        self._add_salary(app)
        self.assertIsNone(str_earner_income_document_gap(app))
        _, proof_wanted = _gap_sets(app)
        self.assertNotIn('father_income_proof_missing', proof_wanted)

    def test_household_size_tick_and_gate_reads_are_unchanged(self):
        # Guard the decoupling: for the means test the STR earner stays 'evidenced' (the STR is
        # dispositive), so member_income_status is still 'satisfied' and the household-size verified
        # tick (which reads household_status_gaps → member_income_status) is untouched.
        app = self._app(uid='str-tick', father_occupation='factory')
        self.assertTrue(_parent_has_income_evidence(app, 'father'))     # STR-aware: still evidenced
        self.assertFalse(_member_income_documented(app, 'father'))      # salary picture: undocumented
        self.assertEqual(member_income_status(app, 'father'), 'satisfied')
