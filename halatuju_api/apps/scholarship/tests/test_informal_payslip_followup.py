"""#126 — the system must be able to HEAR the answer it asked for.

The ask-first rule (2026-07-08) suppresses a payslip/EPF demand for an informal earner, because a
fisherman has none and demanding one dead-ends him (#130). But the suppression is keyed on the
OCCUPATION CODE, so it never lifted:

    #126's father is a 'driver' (informal). Check 2 asked "do they get a payslip, or contribute to
    EPF?". The student answered: "My father is a crane driver, also he has payslip, I should upload
    it?" — and NOTHING happened. He asked us a direct question and got silence, while an
    unevidenced RM3,900 household income stood as the basis of a means test.

Now the answer is read once, at the moment it is given, and the suppressed request re-opens if the
student says the payslip exists. The rest of the chain then resumes on its own: once a payslip is
on file, the EPF request follows automatically (employed_epf_members).

The protection this must NOT break: a student who says they have NO payslip is never dragged back
into the dead end. Hence negation is checked first, and only an explicit YES re-opens anything.
"""
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.check2_queries import _gap_sets
from apps.scholarship.income_engine import (informal_payslip_claimed,
                                            payslip_claim)
from apps.scholarship.models import (ResolutionItem, ScholarshipApplication,
                                     ScholarshipCohort)


class TestPayslipClaim(TestCase):
    """The classifier. Pure, deterministic, and conservative by design."""

    def test_the_real_answer_from_126(self):
        self.assertEqual(
            payslip_claim('My Father Is A Crane Driver Also He Has Payslip, I should Upload It?'),
            'yes')

    def test_plain_yes_variants(self):
        for t in ('He has a payslip', 'yes he gets a pay slip every month',
                  'my mother contributes to EPF', 'ada slip gaji', 'dia ada KWSP'):
            with self.subTest(answer=t):
                self.assertEqual(payslip_claim(t), 'yes')

    def test_negation_is_read_first(self):
        # "no payslip" CONTAINS 'payslip'. Reading that as a yes is exactly the failure that would
        # re-trap the #130 fisherman with a document he cannot produce.
        for t in ('He has no payslip', "He doesn't get a payslip", 'no payslip, he is a fisherman',
                  'tiada slip gaji', 'tidak ada KWSP', 'He works without any payslip'):
            with self.subTest(answer=t):
                self.assertEqual(payslip_claim(t), 'no')

    def test_an_answer_that_never_mentions_it_is_unclear(self):
        for t in ('He earns about RM2000 a month', 'he sells fish at the market', ''):
            with self.subTest(answer=t):
                self.assertEqual(payslip_claim(t), 'unclear')

    def test_only_yes_ever_reopens_anything(self):
        # 'no' and 'unclear' must both leave the suppression exactly where it was.
        self.assertNotEqual(payslip_claim('no payslip'), 'yes')
        self.assertNotEqual(payslip_claim('he sells fish'), 'yes')


class TestTheRequestReopens(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def _app(self, uid='u1'):
        profile = StudentProfile.objects.create(
            supabase_user_id=uid, name='HAVINESH A/L R KANNAN', nric='081211-07-0605',
            preferred_state='Pulau Pinang', household_income=3900, household_size=5,
            receives_str=True, receives_jkm=False,
        )
        # #126's shape: father an informal earner ('driver'), mother unemployed, STR route.
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=profile, status='profile_complete',
            profile_completed_at=timezone.now(), income_route='str', income_earner='mother',
            father_name='R KANNAN A/L RAMU', father_occupation='driver',
            mother_name='VIMALA A/P MUNIANDY', mother_occupation='unemployed',
        )

    def _answer(self, app, text):
        """Answer the ask-first clarify exactly as the resolve endpoint does."""
        from apps.scholarship.income_engine import payslip_claim as _claim
        return ResolutionItem.objects.create(
            application=app, source='check2', code='informal_income_detail',
            fact='income', kind='clarify', status='resolved', resolution_text=text,
            resolved_at=timezone.now(), resolved_by='student',
            params={'payslip_claim': _claim(text)},
        )

    def test_before_any_answer_the_payslip_request_is_suppressed(self):
        # The ask-first rule: don't demand a payslip from an informal earner unprompted.
        app = self._app()
        _, proof_wanted = _gap_sets(app)
        self.assertNotIn('father_income_proof_missing', proof_wanted)

    def test_a_yes_reopens_the_fathers_payslip_request(self):
        # THE FIX: the student told us he has one. Ask for it.
        app = self._app()
        self._answer(app, 'My father is a crane driver, also he has payslip, I should upload it?')
        self.assertTrue(informal_payslip_claimed(app))
        _, proof_wanted = _gap_sets(app)
        self.assertIn('father_income_proof_missing', proof_wanted)

    def test_a_no_keeps_the_suppression(self):
        # The #130 fisherman: he told us he has no payslip. Never demand one.
        app = self._app('u2')
        self._answer(app, 'He is a fisherman, he has no payslip')
        self.assertFalse(informal_payslip_claimed(app))
        _, proof_wanted = _gap_sets(app)
        self.assertNotIn('father_income_proof_missing', proof_wanted)

    def test_an_unreadable_answer_keeps_the_suppression(self):
        app = self._app('u3')
        self._answer(app, 'He earns around RM2000')
        _, proof_wanted = _gap_sets(app)
        self.assertNotIn('father_income_proof_missing', proof_wanted)
