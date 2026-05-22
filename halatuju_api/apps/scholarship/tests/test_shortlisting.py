"""Unit tests for the mechanical shortlisting engine (pure, no DB)."""
from types import SimpleNamespace

from django.test import TestCase

from apps.scholarship.shortlisting import evaluate


def cohort(**over):
    base = dict(min_spm_a_count=5, min_stpm_pngk=3.0, bucket_b_margin=1, income_ceiling=5250)
    base.update(over)
    return SimpleNamespace(**base)


def _grades_with_a_count(n):
    """A 10-subject SPM grades dict with exactly ``n`` A's (rest B's). None passes through."""
    if n is None:
        return None
    return {f'sub{i}': ('A' if i < n else 'B') for i in range(10)}


def app(*, qualification='spm', spm_a_count=10, stpm_pngk=None,
        household_income=2500, receives_str=True,
        intends_tertiary_2026=True, consent_to_contact=True):
    """
    Build an application stand-in. Academic + income now live on the linked
    profile (the single source of truth); intent + consent on the application.
    ``spm_a_count`` is expressed as a grades dict the engine tallies itself.
    """
    profile = SimpleNamespace(
        exam_type=qualification,
        grades=_grades_with_a_count(spm_a_count),
        stpm_cgpa=stpm_pngk,
        household_income=household_income,
        receives_str=receives_str,
    )
    return SimpleNamespace(
        profile=profile,
        intends_tertiary_2026=intends_tertiary_2026,
        consent_to_contact=consent_to_contact,
    )


class TestShortlistingEngine(TestCase):

    # --- Bucket A ---
    def test_all_ok_is_bucket_a(self):
        r = evaluate(app(), cohort())
        self.assertEqual((r.status, r.bucket), ('shortlisted', 'A'))

    def test_three_real_candidates_are_bucket_a(self):
        # Priya 10A/RM2500/STR, Nathiyaa 11A/RM5000/STR, Theresa 10A/RM1800/STR
        for a in (
            app(spm_a_count=10, household_income=2500),
            app(spm_a_count=11, household_income=5000),
            app(spm_a_count=10, household_income=1800),
        ):
            self.assertEqual(evaluate(a, cohort()).bucket, 'A')

    # --- Bucket B (exactly one marginal) ---
    def test_academic_marginal_is_bucket_b(self):
        r = evaluate(app(spm_a_count=4), cohort())
        self.assertEqual((r.status, r.bucket), ('shortlisted', 'B'))

    def test_income_marginal_is_bucket_b(self):
        r = evaluate(app(household_income=5500), cohort())  # within 5250 * 1.15
        self.assertEqual(r.bucket, 'B')

    def test_income_over_band_but_str_is_marginal(self):
        r = evaluate(app(household_income=8000, receives_str=True), cohort())
        self.assertEqual(r.bucket, 'B')

    # --- FAIL ---
    def test_low_academic_is_rejected(self):
        r = evaluate(app(spm_a_count=2), cohort())
        self.assertEqual((r.status, r.bucket), ('rejected', ''))

    def test_no_consent_is_rejected(self):
        r = evaluate(app(consent_to_contact=False), cohort())
        self.assertEqual(r.status, 'rejected')

    def test_not_intending_is_rejected(self):
        self.assertEqual(evaluate(app(intends_tertiary_2026=False), cohort()).status, 'rejected')

    def test_two_marginals_is_rejected(self):
        r = evaluate(app(spm_a_count=4, household_income=5500), cohort())
        self.assertEqual(r.status, 'rejected')

    def test_income_over_band_no_str_is_rejected(self):
        r = evaluate(app(household_income=8000, receives_str=False), cohort())
        self.assertEqual(r.status, 'rejected')

    def test_no_income_no_str_is_rejected(self):
        r = evaluate(app(household_income=None, receives_str=False), cohort())
        self.assertEqual(r.status, 'rejected')

    # --- Edge config / STPM ---
    def test_no_income_with_str_is_ok(self):
        r = evaluate(app(household_income=None, receives_str=True), cohort())
        self.assertEqual(r.bucket, 'A')

    def test_no_income_ceiling_skips_income(self):
        r = evaluate(app(household_income=99999, receives_str=False), cohort(income_ceiling=None))
        self.assertEqual(r.bucket, 'A')

    def test_stpm_ok(self):
        r = evaluate(app(qualification='stpm', spm_a_count=None, stpm_pngk=3.5), cohort())
        self.assertEqual(r.bucket, 'A')

    def test_stpm_marginal(self):
        r = evaluate(app(qualification='stpm', spm_a_count=None, stpm_pngk=2.8), cohort())
        self.assertEqual(r.bucket, 'B')

    def test_stpm_fail(self):
        r = evaluate(app(qualification='stpm', spm_a_count=None, stpm_pngk=2.0), cohort())
        self.assertEqual(r.status, 'rejected')

    def test_missing_academic_data_is_rejected(self):
        r = evaluate(app(spm_a_count=None), cohort())
        self.assertEqual(r.status, 'rejected')

    def test_reason_recorded_for_bucket_b(self):
        r = evaluate(app(spm_a_count=4), cohort())
        self.assertIn('academic', r.reason)
