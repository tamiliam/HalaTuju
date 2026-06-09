"""Unit tests for the S8 shortlisting engine (pure, no DB)."""
from types import SimpleNamespace

from django.test import TestCase

from apps.scholarship.shortlisting import evaluate, count_spm_a_grades, count_spm_strong_grades


def cohort(**over):
    base = dict(min_spm_a_count=4, min_spm_bplus_count=5, min_stpm_pngk=2.9,
                income_ceiling=5860, per_capita_ceiling=1584)
    base.update(over)
    return SimpleNamespace(**base)


def _spm_grades(a=4, bplus=1, lower=4):
    """SPM grades dict: `a` A's, `bplus` B+'s, `lower` B's."""
    g, i = {}, 0
    for _ in range(a):
        g[f's{i}'] = 'A'; i += 1
    for _ in range(bplus):
        g[f's{i}'] = 'B+'; i += 1
    for _ in range(lower):
        g[f's{i}'] = 'B'; i += 1
    return g


def app(*, qualification='spm', grades=-1, stpm_pngk=None,
        household_income=3000, household_size=5, receives_str=False,
        intends_tertiary_2026=True, consent_to_contact=True, upu_status=''):
    profile = SimpleNamespace(
        exam_type=qualification,
        grades=_spm_grades() if grades == -1 else grades,
        stpm_cgpa=stpm_pngk,
        household_income=household_income,
        household_size=household_size,
        receives_str=receives_str,
    )
    return SimpleNamespace(
        profile=profile,
        intends_tertiary_2026=intends_tertiary_2026,
        consent_to_contact=consent_to_contact,
        upu_status=upu_status,
    )


class TestShortlistingEngine(TestCase):

    # --- Income: STR fast-path (bucket A) ---
    def test_str_recipient_is_shortlisted_bucket_a(self):
        r = evaluate(app(receives_str=True, household_income=99999, household_size=1), cohort())
        self.assertEqual((r.verdict, r.bucket), ('shortlisted', 'A'))

    # --- Income: B40 by gross income (bucket B) — 2026-06 policy ---
    def test_b40_gross_income_passes_bucket_b(self):
        # At/under the RM5,860 B40 line → in, regardless of household size.
        r = evaluate(app(receives_str=False, household_income=3000, household_size=5), cohort())
        self.assertEqual((r.verdict, r.bucket), ('shortlisted', 'B'))

    def test_b40_gross_small_family_high_per_capita_still_passes(self):
        # THE policy change: RM5,500 household with only 2 people (per-capita RM2,750 >
        # RM1,584) — under the OLD per-capita-first rule this was REJECTED; now the gross
        # income is B40 (<= RM5,860) so the applicant is shortlisted.
        r = evaluate(app(household_income=5500, household_size=2), cohort())
        self.assertEqual((r.verdict, r.bucket), ('shortlisted', 'B'))

    def test_at_the_ceiling_passes(self):
        self.assertEqual(evaluate(app(household_income=5860, household_size=1), cohort()).verdict, 'shortlisted')

    # --- Income: per-capita is now only a SAFETY NET above the B40 ceiling ---
    def test_large_family_above_household_ceiling_still_passes(self):
        # RM7,000 household > RM5,860, but 7000/5 = 1400 < 1584 → rescued by per-capita.
        self.assertEqual(evaluate(app(household_income=7000, household_size=5), cohort()).verdict, 'shortlisted')

    def test_above_ceiling_high_per_capita_rejected(self):
        # RM8,000 household, 2 people → above the B40 line AND per-capita RM4,000 >= RM1,584.
        self.assertEqual(evaluate(app(household_income=8000, household_size=2), cohort()).verdict, 'rejected')

    def test_t20_rejected(self):
        self.assertEqual(evaluate(app(household_income=13000, household_size=4), cohort()).verdict, 'rejected')

    def test_no_str_no_income_data_rejected(self):
        self.assertEqual(evaluate(app(household_income=None, household_size=None), cohort()).verdict, 'rejected')

    # --- Academic floor (SPM ≥4 A- AND ≥5 at B+) ---
    def test_exactly_floor_passes(self):
        r = evaluate(app(grades=_spm_grades(a=4, bplus=1, lower=4), receives_str=True), cohort())
        self.assertEqual(r.verdict, 'shortlisted')

    def test_four_a_no_bplus_rejected(self):
        r = evaluate(app(grades=_spm_grades(a=4, bplus=0, lower=5), receives_str=True), cohort())
        self.assertEqual(r.verdict, 'rejected')
        self.assertIn('academic', r.reason)

    def test_three_a_rejected(self):
        self.assertEqual(evaluate(app(grades=_spm_grades(a=3, bplus=3, lower=3), receives_str=True), cohort()).verdict, 'rejected')

    def test_a_minus_counts_as_a(self):
        g = {'s0': 'A-', 's1': 'A-', 's2': 'A-', 's3': 'A-', 's4': 'B+', 's5': 'B'}
        self.assertEqual(evaluate(app(grades=g, receives_str=True), cohort()).verdict, 'shortlisted')

    def test_missing_grades_rejected(self):
        self.assertEqual(evaluate(app(grades=None, receives_str=True), cohort()).verdict, 'rejected')

    # --- STPM floor (PNGK ≥ 2.9) ---
    def test_stpm_at_floor_passes(self):
        self.assertEqual(evaluate(app(qualification='stpm', grades=None, stpm_pngk=2.9, receives_str=True), cohort()).verdict, 'shortlisted')

    def test_stpm_below_floor_rejected(self):
        self.assertEqual(evaluate(app(qualification='stpm', grades=None, stpm_pngk=2.8, receives_str=True), cohort()).verdict, 'rejected')

    def test_stpm_missing_rejected(self):
        self.assertEqual(evaluate(app(qualification='stpm', grades=None, stpm_pngk=None, receives_str=True), cohort()).verdict, 'rejected')

    # --- Hard gates ---
    def test_no_consent_rejected(self):
        self.assertEqual(evaluate(app(consent_to_contact=False, receives_str=True), cohort()).verdict, 'rejected')

    def test_not_intending_rejected(self):
        self.assertEqual(evaluate(app(intends_tertiary_2026=False, receives_str=True), cohort()).verdict, 'rejected')

    def test_ipts_only_rejected(self):
        r = evaluate(app(upu_status='ipts', receives_str=True), cohort())
        self.assertEqual(r.verdict, 'rejected')
        self.assertIn('IPTS', r.reason)

    def test_public_pathway_not_blocked_by_ipts_gate(self):
        self.assertEqual(evaluate(app(upu_status='public_other', receives_str=True), cohort()).verdict, 'shortlisted')

    # --- grade counters ---
    def test_grade_counters(self):
        g = _spm_grades(a=4, bplus=2, lower=3)
        self.assertEqual(count_spm_a_grades(g), 4)
        self.assertEqual(count_spm_strong_grades(g), 6)
