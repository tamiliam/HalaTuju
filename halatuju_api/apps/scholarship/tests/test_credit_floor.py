"""Request #30 (2026-10-06) — an intake year can require a minimum number of SPM grades at C or
better: `ScholarshipCohort.min_spm_credit_count`.

THIS DECIDES WHO QUALIFIES FOR MONEY, so the owner's rulings are pinned here as tests:

  * SPM HAS NO C- GRADE. "C or better" = A+, A, A-, B+, B, C+, C — the SPM credits (kepujian).
    D, E, G, and anything unknown or blank, do not count.
  * It is a TOTAL across every SPM subject, exactly as the B+ rung counts the TOTAL at B+ or
    better. The organisation's sanity check: 8 A's and no C's PASSES a "6 at C or better" rule.
  * THE VALUE IS THE SWITCH: NULL = not applied, a number turns it on, 0 is a real requirement
    everybody passes. No companion tick.
  * It arrives NULL on every existing intake year (no default, nothing backfilled).
"""
from django.test import SimpleTestCase, TestCase, override_settings

from apps.scholarship.models import ScholarshipCohort
from apps.scholarship.services import score_application
from apps.scholarship.shortlisting import (
    CREDIT_GRADES, count_spm_credit_grades, evaluate,
)
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_programme,
    make_student,
)

#: Every SPM grade there is, best first (SPM has no C-).
SPM_GRADES = ('A+', 'A', 'A-', 'B+', 'B', 'C+', 'C', 'D', 'E', 'G')

#: Only the credit floor is applied, so a verdict can only turn on it. STR => the income test
#: passes; the STPM floor is cleared so an STPM applicant is not tested on PNGK either.
ONLY_CREDITS = dict(min_spm_a_count=None, min_spm_bplus_count=None, min_stpm_pngk=None,
                    min_merit_score=None)


#: How `evaluate` introduces an academic failure; `_academic_ok` writes what follows it.
FLOOR = 'academic floor: '


def _grades(*letters):
    return {f'subject{i}': g for i, g in enumerate(letters)}


class TestWhatCounts(SimpleTestCase):
    def test_the_seven_credit_grades_and_nothing_else(self):
        self.assertEqual(CREDIT_GRADES, {'A+', 'A', 'A-', 'B+', 'B', 'C+', 'C'})

    def test_it_is_the_course_engines_credit_set(self):
        # The course selector's own definition of an SPM credit. Two sets with one meaning must
        # not drift; this is the test that says so.
        from apps.courses.engine import CREDIT_GRADES as COURSE_CREDIT_GRADES
        self.assertEqual(CREDIT_GRADES, COURSE_CREDIT_GRADES)

    def test_every_grade_from_A_plus_to_C_counts_once(self):
        self.assertEqual(count_spm_credit_grades(_grades(*SPM_GRADES)), 7)

    def test_D_E_G_and_unknown_or_blank_strings_do_not_count(self):
        # 'C-' is not an SPM grade (it IS an STPM one); 'TH' is "tidak hadir" (absent).
        junk = _grades('D', 'E', 'G', 'C-', 'TH', '', ' ', 'X', None, 5)
        self.assertEqual(count_spm_credit_grades(junk), 0)

    def test_case_and_padding_are_read_as_the_A_rung_reads_them(self):
        self.assertEqual(count_spm_credit_grades(_grades('c+', ' c ', 'b')), 3)

    def test_no_grades_is_zero_credits(self):
        self.assertEqual(count_spm_credit_grades({}), 0)
        self.assertEqual(count_spm_credit_grades(None), 0)


class _Engine(TestCase):
    def _run(self, grades, **cohort):
        c = make_cohort(**{**ONLY_CREDITS, **cohort})
        s = make_student(grades=grades, receives_str=True)
        return evaluate(make_application(cohort=c, student=s), c)


class TestTheFloor(_Engine):
    def test_EIGHT_As_and_no_Cs_PASS_a_six_credit_floor(self):
        # The organisation's own sanity check. A's are credits; zero C's is not zero credits.
        r = self._run(_grades(*['A'] * 8), min_spm_credit_count=6)
        self.assertEqual(r.verdict, 'shortlisted')

    def test_five_credits_and_three_Ds_FAIL_a_six_credit_floor(self):
        r = self._run(_grades('A', 'B+', 'B', 'C+', 'C', 'D', 'D', 'D'), min_spm_credit_count=6)
        self.assertEqual((r.verdict, r.category), ('rejected', 'merit'))
        self.assertEqual(r.reason, FLOOR + '5 at C or better (need 6)')

    def test_exactly_at_the_floor_passes(self):
        r = self._run(_grades('A', 'B+', 'B', 'C+', 'C', 'C', 'D', 'D'), min_spm_credit_count=6)
        self.assertEqual(r.verdict, 'shortlisted')

    def test_D_E_G_and_unknown_grades_do_not_lift_a_student_over_the_floor(self):
        r = self._run(_grades('A', 'A', 'B', 'C', 'C', 'D', 'E', 'G', 'C-', 'TH', ''),
                      min_spm_credit_count=6)
        self.assertEqual(r.reason, FLOOR + '5 at C or better (need 6)')


class TestTheValueIsTheSwitch(_Engine):
    def test_BLANK_means_not_applied_even_with_zero_credits(self):
        r = self._run(_grades('D', 'D', 'E', 'G'), min_spm_credit_count=None)
        self.assertEqual(r.verdict, 'shortlisted')

    def test_ZERO_is_a_requirement_everybody_passes_exactly_as_the_neighbours_zero(self):
        # The neighbours: a 0 floor on the A- or B+ rung never fails anybody. Same here.
        for floors in ({'min_spm_credit_count': 0}, {'min_spm_a_count': 0},
                       {'min_spm_bplus_count': 0}):
            with self.subTest(**floors):
                self.assertEqual(self._run(_grades('D', 'E'), **floors).verdict, 'shortlisted')
                self.assertEqual(self._run({}, **floors).verdict, 'shortlisted')

    def test_it_arrives_BLANK_on_a_new_intake_year_too(self):
        # No default — unlike the A- and B+ rungs, which still default to the flagship's 4 and 5.
        field = ScholarshipCohort._meta.get_field('min_spm_credit_count')
        self.assertFalse(field.has_default())
        self.assertTrue(field.null)
        self.assertIsNone(make_cohort().min_spm_credit_count)


class TestBesideTheOtherRungs(_Engine):
    RUNGS = dict(min_spm_a_count=4, min_spm_bplus_count=5, min_spm_credit_count=6)

    def test_failing_ONLY_the_C_rule_gives_ONLY_that_reason(self):
        # 4 A's (A- rule met), 5 at B+ or better (B+ rule met), 5 credits (C rule missed by one).
        r = self._run(_grades('A', 'A', 'A', 'A', 'B+', 'D', 'D', 'E'), **self.RUNGS)
        self.assertEqual((r.verdict, r.category), ('rejected', 'merit'))
        self.assertEqual(r.reason, FLOOR + '5 at C or better (need 6)')

    def test_clearing_all_three_passes(self):
        r = self._run(_grades('A', 'A', 'A', 'A', 'B+', 'C', 'D', 'E'), **self.RUNGS)
        self.assertEqual(r.verdict, 'shortlisted')

    def test_failing_all_three_names_them_in_rung_order(self):
        r = self._run(_grades('A', 'B', 'D', 'D'), **self.RUNGS)
        self.assertEqual(r.reason, FLOOR + '; '.join((
            '1 at A- (need 4)',
            '1 at B+ or better (need 4 at A- plus 1 more at B+)',
            '2 at C or better (need 6)')))


class TestSTPMApplicantsAreUntouched(_Engine):
    """The SPM rungs never test an applicant whose results are STPM — the same branch skips all
    three. Their comparable figure is the PNGK (`min_stpm_pngk`)."""

    def _stpm(self, **cohort):
        c = make_cohort(**{**ONLY_CREDITS, 'min_spm_credit_count': 6, **cohort})
        s = make_student(exam_type='stpm', results_exam_type='stpm', stpm_cgpa=3.5,
                         grades=_grades('D', 'D', 'E'), receives_str=True)
        return evaluate(make_application(cohort=c, student=s), c)

    def test_a_credit_floor_does_not_reject_an_stpm_applicant_with_no_spm_credits(self):
        self.assertEqual(self._stpm().verdict, 'shortlisted')
        self.assertEqual(self._stpm(min_stpm_pngk=2.9).verdict, 'shortlisted')

    def test_the_stpm_applicant_is_still_tested_on_the_PNGK(self):
        r = self._stpm(min_stpm_pngk=3.6)
        self.assertEqual(r.reason, FLOOR + 'PNGK 3.5 below 3.6')


class TestWhatTheStudentIsTold(TestCase):
    """The reason is stored on the application at scoring (`shortlist_reason`). Staff read it on
    the admin payload; since the request #31 review (2026-10-08) it is no longer served to the
    student, and no round threshold reaches a student or sponsor anywhere: the apply page's
    criteria are the gift's own copy and are deliberately never derived from the thresholds
    (decisions.md 2026-09-09)."""

    def _scored(self, floor, grades):
        c = make_cohort(**{**ONLY_CREDITS, 'min_spm_a_count': 4, 'min_spm_credit_count': floor})
        app = make_application(cohort=c, student=make_student(grades=grades, receives_str=True))
        score_application(app)
        app.refresh_from_db()
        return app

    def test_a_set_floor_is_named_in_the_stored_reason(self):
        app = self._scored(6, _grades('A', 'A', 'A', 'A', 'D'))
        self.assertEqual((app.verdict, app.rejection_category), ('rejected', 'merit'))
        self.assertEqual(app.shortlist_reason, FLOOR + '4 at C or better (need 6)')

    def test_a_blank_floor_is_never_mentioned(self):
        app = self._scored(None, _grades('A', 'A', 'D'))   # fails the A- rule, zero C's
        self.assertEqual(app.shortlist_reason, FLOOR + '2 at A- (need 4)')
        self.assertNotIn('C or better', app.shortlist_reason)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheAdminScreens(TestCase):
    """Read and write through the real intake-year endpoints, exactly as the B+ rung is."""

    @classmethod
    def setUpTestData(cls):
        cls.programme = make_programme()
        cls.admin = make_admin('org_admin', owning_org=cls.programme.organisation)

    def setUp(self):
        self.client = authed_client(self.admin)

    def _years(self):
        return f'/api/v1/admin/scholarship/programmes/{self.programme.id}/years/'

    def _year(self, c):
        return f'/api/v1/admin/scholarship/intake-years/{c.id}/'

    def _cohort(self, **kw):
        return make_cohort(programme=self.programme, is_active=True, is_open=False, **kw)

    def _create(self, code, **body):
        return self.client.post(self._years(), {'code': code, 'name': code, 'year': 2027, **body},
                                format='json')

    def test_create_stores_and_serves_it(self):
        r = self._create('cr-set', min_spm_credit_count=6)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['requirements']['min_spm_credit_count'], 6)
        self.assertEqual(ScholarshipCohort.objects.get(code='cr-set').min_spm_credit_count, 6)

    def test_create_without_it_leaves_it_blank_and_serves_null(self):
        r = self._create('cr-none')
        self.assertIsNone(r.data['requirements']['min_spm_credit_count'])
        self.assertIsNone(ScholarshipCohort.objects.get(code='cr-none').min_spm_credit_count)

    def test_the_list_serves_it_beside_the_B_plus_rung(self):
        self._cohort(code='cr-list', min_spm_credit_count=5)
        row = self.client.get(self._years()).data['years'][0]
        self.assertEqual(row['requirements']['min_spm_credit_count'], 5)
        keys = list(row['requirements'])
        self.assertEqual(keys.index('min_spm_credit_count'), keys.index('min_spm_bplus_count') + 1)

    def test_patch_sets_then_blank_or_null_unticks(self):
        c = self._cohort(code='cr-patch')
        for sent, stored in ((6, 6), (0, 0), ('', None), (3, 3), (None, None)):
            with self.subTest(sent=sent):
                r = self.client.patch(self._year(c), {'min_spm_credit_count': sent}, format='json')
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.data['requirements']['min_spm_credit_count'], stored)
                c.refresh_from_db()
                self.assertEqual(c.min_spm_credit_count, stored)

    def test_a_patch_that_does_not_mention_it_leaves_it_alone(self):
        c = self._cohort(code='cr-alone', min_spm_credit_count=6)
        self.client.patch(self._year(c), {'name': 'Renamed', 'min_spm_a_count': 3}, format='json')
        c.refresh_from_db()
        self.assertEqual(c.min_spm_credit_count, 6)

    def _refused(self, field, bad, kept):
        c = self._cohort(**{field: kept})   # a fresh code per call (subtests share a transaction)
        r = self.client.patch(self._year(c), {field: bad, 'name': 'Renamed'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual((r.data['code'], r.data['field']), ('bad_requirement', field))
        c.refresh_from_db()
        self.assertEqual(getattr(c, field), kept)
        self.assertNotEqual(c.name, 'Renamed')   # refused WHOLE: nothing else in the PATCH lands

    def test_a_typo_the_screen_forwards_is_refused_and_the_rule_stays_on(self):
        # ⚠ What the browser really sends for a typo since the request #30 review: the TEXT typed
        # (`intakeYears.num`), not NaN-turned-null — which this endpoint would have read as
        # "untick" and switched the rule off. The web half is `intakeYears.test.ts`.
        for bad in ('six', '6 credits', '6,0', -1):
            with self.subTest(bad=bad):
                self._refused('min_spm_credit_count', bad, 6)

    def test_a_COUNT_must_be_a_whole_number_and_never_a_boolean(self):
        # `int(6.9)` is 6 and `int(True)` is 1: a different bar from the one sent, silently.
        for field in ('min_spm_a_count', 'min_spm_bplus_count', 'min_spm_credit_count'):
            for bad in (6.9, 0.5, True, False, '6.5'):
                with self.subTest(field=field, bad=bad):
                    self._refused(field, bad, 4)

    def test_a_whole_valued_decimal_is_that_count(self):
        c = self._cohort(code='cr-six-point-oh')
        r = self.client.patch(self._year(c), {'min_spm_credit_count': 6.0, 'min_spm_a_count': 4.0,
                                              'min_spm_bplus_count': '5'}, format='json')
        self.assertEqual(r.status_code, 200)
        c.refresh_from_db()
        self.assertEqual((c.min_spm_a_count, c.min_spm_bplus_count, c.min_spm_credit_count),
                         (4, 5, 6))
        self.assertIsInstance(c.min_spm_credit_count, int)

    def test_the_FLOAT_requirements_keep_their_decimals_but_must_be_finite(self):
        c = self._cohort(code='cr-floats')
        r = self.client.patch(self._year(c), {'min_stpm_pngk': 2.95, 'min_merit_score': '80.5'},
                              format='json')
        self.assertEqual(r.status_code, 200)
        c.refresh_from_db()
        self.assertEqual((c.min_stpm_pngk, c.min_merit_score), (2.95, 80.5))
        # Reachable from a box now that a typo travels as text: float('nan') parses, and a NaN
        # floor compares False against every PNGK.
        for bad in ('nan', 'Infinity', '-inf', True):
            with self.subTest(bad=bad):
                self._refused('min_stpm_pngk', bad, 2.9)

    def test_creating_a_year_refuses_the_same_values(self):
        for bad in (6.9, True, 'six'):
            with self.subTest(bad=bad):
                r = self._create('cr-new-bad', min_spm_credit_count=bad)
                self.assertEqual((r.status_code, r.data['field']), (400, 'min_spm_credit_count'))
                self.assertFalse(ScholarshipCohort.objects.filter(code='cr-new-bad').exists())

    def test_moving_it_is_audited_from_what_to_what(self):
        c = self._cohort(code='cr-audit')
        with self.assertLogs('apps.scholarship.views_admin', level='INFO') as logs:
            self.client.patch(self._year(c), {'min_spm_credit_count': 6}, format='json')
        line = [m for m in logs.output if 'intake_year_requirements_set' in m]
        self.assertEqual(len(line), 1)
        self.assertIn('min_spm_credit_count:None->6', line[0])
