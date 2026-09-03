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


class TestOptionalRequirements(TestCase):
    """A threshold of ``None`` means that test is NOT APPLIED (Sabah S2a, 2026-09-02).

    ⚠ THE DEFECT THIS CLOSES IS LIVE AND WAS INVISIBLE. Every threshold column was NOT NULL with a
    default, so every test always ran. BrightPath never asked for an STPM requirement, yet a PNGK
    floor of 2.90 was applied to all nine of its STPM applicants for a whole intake — it rejected
    none of them, so nobody found out. An organisation must be able to say "we do not use this
    one", and a missing value is how that becomes sayable.
    """

    def test_no_stpm_requirement_lets_an_stpm_applicant_through_with_no_pngk_at_all(self):
        # With a floor set, a missing PNGK is a rejection — that is unchanged.
        r = evaluate(app(qualification='stpm', stpm_pngk=None), cohort())
        self.assertEqual(r.verdict, 'rejected')
        self.assertEqual(r.category, 'merit')
        # Unticked, the test does not run, so there is nothing to be missing.
        r = evaluate(app(qualification='stpm', stpm_pngk=None), cohort(min_stpm_pngk=None))
        self.assertEqual(r.verdict, 'shortlisted')

    def test_no_academic_requirement_at_all_passes_the_academic_test(self):
        # A programme that sets no results requirement is a legitimate shape, not a hole: it takes
        # an admin clearing every box on a screen that shows which are ticked.
        weak = app(grades=_spm_grades(a=0, bplus=0, lower=9))
        self.assertEqual(evaluate(weak, cohort()).verdict, 'rejected')
        self.assertEqual(
            evaluate(weak, cohort(min_spm_a_count=None, min_spm_bplus_count=None)).verdict,
            'shortlisted')

    def test_each_academic_requirement_can_be_dropped_on_its_own(self):
        # 4 at A- and 4 strong: clears the A- rule exactly, misses the B+ rule by one. This is a
        # REAL case — application #40 was rejected on precisely these counts.
        edge = app(grades=_spm_grades(a=4, bplus=0, lower=5))
        self.assertEqual(evaluate(edge, cohort()).verdict, 'rejected')
        self.assertEqual(evaluate(edge, cohort(min_spm_bplus_count=None)).verdict, 'shortlisted')
        # Dropping the OTHER rule does not rescue it — the counts, not the labels, decide.
        self.assertEqual(evaluate(edge, cohort(min_spm_a_count=None)).verdict, 'rejected')

    def test_no_financial_requirement_passes_with_a_BLANK_bucket_not_a_borrowed_B(self):
        # 'B' means "passed the income test". There was no income test, so claiming 'B' would put
        # a false record on the application. The bucket is an admin filter label, never a gate.
        rich = app(household_income=99000, household_size=1)
        self.assertEqual(evaluate(rich, cohort()).verdict, 'rejected')
        r = evaluate(rich, cohort(income_ceiling=None, per_capita_ceiling=None))
        self.assertEqual(r.verdict, 'shortlisted')
        self.assertEqual(r.bucket, '')

    def test_dropping_only_the_per_capita_rescue_leaves_the_gross_ceiling_biting(self):
        over = app(household_income=7000, household_size=5)   # per-capita 1400, would be rescued
        self.assertEqual(evaluate(over, cohort()).verdict, 'shortlisted')
        r = evaluate(over, cohort(per_capita_ceiling=None))
        self.assertEqual(r.verdict, 'rejected')
        self.assertEqual(r.category, 'need')


class TestMeritRequirement(TestCase):
    """`min_merit_score` — the UPU merit point out of 100, SPM applicants only."""

    def _merit_of(self, application):
        from apps.scholarship.shortlisting import spm_merit
        return spm_merit(application.profile)

    def test_a_merit_floor_rejects_below_and_passes_at_or_above(self):
        strong = app(grades=_spm_grades(a=9, bplus=0, lower=0))
        m = self._merit_of(strong)
        self.assertIsNotNone(m)
        # Unticked by default — every cohort today.
        self.assertEqual(evaluate(strong, cohort()).verdict, 'shortlisted')
        self.assertEqual(evaluate(strong, cohort(min_merit_score=m)).verdict, 'shortlisted')
        r = evaluate(strong, cohort(min_merit_score=m + 1))
        self.assertEqual(r.verdict, 'rejected')
        self.assertEqual(r.category, 'merit')
        self.assertIn('merit point', r.reason)

    def test_it_does_NOT_apply_to_an_stpm_applicant(self):
        # An STPM applicant's comparable figure is the PNGK, which is `min_stpm_pngk`. Applying a
        # 0-100 merit floor to a 0-4 CGPA would reject everyone with STPM results.
        stpm = app(qualification='stpm', stpm_pngk=3.5, grades={})
        self.assertEqual(evaluate(stpm, cohort(min_merit_score=95)).verdict, 'shortlisted')

    def test_an_spm_applicant_with_no_grades_cannot_clear_a_merit_floor(self):
        # Absence is not a low score, but it is not a pass either — say so rather than defaulting.
        r = evaluate(app(grades={}), cohort(min_spm_a_count=None, min_spm_bplus_count=None,
                                           min_merit_score=50))
        self.assertEqual(r.verdict, 'rejected')
        self.assertIn('not available', r.reason)


class TestRejectionWording(TestCase):
    """The reason is stated the way the requirement is SET, not the way it is stored."""

    def test_it_no_longer_reads_as_nine_subjects(self):
        # The column holds the TOTAL strong count, so the old text said "need 4 A- and 5 at B+" —
        # which the owner, who set the rule, read as nine subjects (2026-09-02). It is 4 A- plus
        # one more. Twelve real applicants carry the old wording on their record.
        r = evaluate(app(grades=_spm_grades(a=1, bplus=1, lower=7)), cohort())
        self.assertIn('4 at A- plus 1 more at B+', r.reason)
        self.assertNotIn('need 4 A- and 5 at B+', r.reason)

    def test_it_names_only_the_requirements_that_actually_failed(self):
        r = evaluate(app(grades=_spm_grades(a=3, bplus=2, lower=4)), cohort())
        self.assertIn('3 at A- (need 4)', r.reason)      # this one failed
        self.assertNotIn('at B+ or better (need', r.reason)  # 5 strong — this one passed
