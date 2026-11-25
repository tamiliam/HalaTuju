"""Criteria editor Sprint 1 - the AND/OR criteria tree (`apps.scholarship.criteria`), unit by unit.

Each test type, all/any at each level, empty groups, absent sections, missing results, grade-or-
better counting across all seven grades, the boundaries (== floor passes, just under fails), and
`from_legacy` for the live intake shapes and the model defaults. The equivalence with today's gate
is `test_criteria_equivalence.py`; the replay command is `test_replay_criteria.py`."""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.courses.models import StudentProfile
from apps.scholarship import criteria
from apps.scholarship.birth_state import check as check_birth_state

STRONG = {'bm': 'A', 'eng': 'A', 'math': 'A+', 'hist': 'A', 'moral': 'A', 'sci': 'B+'}
WEAK = {'bm': 'C', 'eng': 'D', 'math': 'C', 'hist': 'E', 'moral': 'C'}


def prof(**f):
    base = dict(supabase_user_id='crit', exam_type='spm', grades=STRONG, household_income=3000,
                household_size=4, nric='050101-10-1234')
    base.update(f)
    return StudentProfile(**base)


def stpm(cgpa, **f):
    return prof(exam_type='stpm', stpm_cgpa=cgpa, results_exam_type='stpm',
                completed_qualifications=['spm', 'stpm'], **f)


def app(profile=None, **f):
    base = dict(profile=profile if profile is not None else prof(), consent_to_contact=True,
                intends_tertiary_2026=True, upu_status='')
    base.update(f)
    return SimpleNamespace(**base)


def results(mode, *groups):
    return {'section': 'results', mode: list(groups)}


def post(*tests):
    return {'route': 'post_spm', 'all': list(tests)}


def spm(*tests):
    return {'route': 'spm', 'all': list(tests)}


def gc(n, g):
    return {'test': 'grade_count', 'at_least': n, 'grade_or_better': g}


PNGK3 = {'test': 'min_pngk', 'value': 3.0}


class TestGradeOrBetter(SimpleTestCase):
    def test_every_grade_counts_itself_and_everything_above(self):
        grades = {f's{i}': g for i, g in enumerate(criteria.GRADES + ('D', 'E', 'G'))}
        for i, g in enumerate(criteria.GRADES):
            with self.subTest(grade=g):
                self.assertEqual(criteria.at_or_better(grades, g), i + 1)

    def test_matches_the_gates_own_counters(self):
        from apps.scholarship import shortlisting as s
        g = {'a': ' a- ', 'b': 'B+', 'c': 'b', 'd': 'C+', 'e': 'c', 'f': 'D', 'g': None}
        self.assertEqual(criteria.at_or_better(g, 'A-'), s.count_spm_a_grades(g))
        self.assertEqual(criteria.at_or_better(g, 'B+'), s.count_spm_strong_grades(g))
        self.assertEqual(criteria.at_or_better(g, 'C'), s.count_spm_credit_grades(g))
        self.assertEqual(criteria.at_or_better({}, 'C'), 0)


class TestValidate(SimpleTestCase):
    def test_good_trees(self):
        good = {'all': [results('any', post(PNGK3, {'test': 'min_merit', 'value': 80}),
                                spm(gc(3, 'C'), {'test': 'min_upu_merit', 'value': 70})),
                        {'section': 'income', 'all': [{'test': 'household_income_max', 'rm': 5860},
                                                      {'test': 'income_per_person_under', 'rm': 1584}]},
                        {'section': 'born_in', 'any': ['sabah', 'wp_labuan']}],
                'flag': [{'test': 'course_start_year', 'allowed': [2025, 2026]}]}
        self.assertEqual(criteria.validate_tree(good), [])
        self.assertEqual(criteria.validate_tree({'all': []}), [])
        self.assertEqual(criteria.validate_tree({'all': [results('all', post(), spm())]}), [])
        self.assertEqual(criteria.validate_tree({'all': [results('any', spm())]}), [])     # blank floor shape
        # a 0 count is today's "0 set" bar (asks only that SPM grades be given)
        self.assertEqual(criteria.validate_tree({'all': [results('any', spm(gc(0, 'A-')))]}), [])

    def test_bad_trees_are_refused_not_repaired(self):
        bad = [
            [], {'all': [], 'x': 1}, {'all': [{'section': 'grades', 'any': [1]}]},
            {'all': [results('any', spm()), results('all', spm())]},
            {'all': [{'section': 'results', 'any': []}]},
            {'all': [{'section': 'results', 'any': [spm()], 'all': [spm()]}]},
            {'all': [results('any', spm(gc(-1, 'C')))]},
            {'all': [results('any', spm(gc(3, 'D')))]},
            {'all': [results('any', spm(gc(3, 'C'), gc(4, 'C')))]},
            {'all': [results('any', spm({'test': 'min_pngk', 'value': 3}))]},
            {'all': [results('any', post({'test': 'min_pngk', 'value': -1}))]},
            {'all': [results('any', post(PNGK3), post(PNGK3))]},
            {'all': [{'section': 'income', 'any': [{'test': 'household_income_max', 'rm': 'x'}]}]},
            {'all': [{'section': 'born_in', 'all': ['sabah']}]},
            {'all': [{'section': 'born_in', 'any': ['atlantis']}]},
            {'all': [], 'flag': [{'test': 'course_start_year', 'allowed': []}]},
            {'all': [], 'flag': [{'test': 'course_start_year', 'allowed': ['soon']}]},
        ]
        for tree in bad:
            with self.subTest(tree=tree):
                self.assertNotEqual(criteria.validate_tree(tree), [])


class TestVoidSpmDoor(SimpleTestCase):
    """Owner ruling 2026-11-25 (c): an SPM group that cannot fail anyone, beside a post-SPM group
    under 'any', would let every SPM holder through - refused, never stored."""
    MERIT0 = {'test': 'min_upu_merit', 'value': 0}

    def test_refused_under_any(self):
        for door in (spm(), spm(gc(0, 'A-'), gc(0, 'C')), spm(self.MERIT0), spm(gc(0, 'C'), self.MERIT0)):
            with self.subTest(door=door):
                self.assertEqual(criteria.validate_tree({'all': [results('any', post(PNGK3), door)]}),
                                 [criteria.VOID_SPM_DOOR])
        self.assertIn('would let every SPM holder through', criteria.VOID_SPM_DOOR)
        self.assertIn('add a rule', criteria.VOID_SPM_DOOR)
        self.assertIn('switch it off', criteria.VOID_SPM_DOOR)

    def test_a_rule_that_can_fail_makes_it_valid(self):
        for door in (spm(gc(1, 'C')), spm({'test': 'min_upu_merit', 'value': 80}),
                     spm(gc(0, 'A-'), gc(3, 'C'), self.MERIT0)):
            with self.subTest(door=door):
                self.assertEqual(criteria.validate_tree({'all': [results('any', post(PNGK3), door)]}), [])

    def test_not_refused_under_all_or_without_a_post_spm_group(self):
        self.assertEqual(criteria.validate_tree({'all': [results('all', post(PNGK3), spm(gc(0, 'C')))]}), [])
        self.assertEqual(criteria.validate_tree({'all': [results('any', spm(gc(0, 'C'), self.MERIT0))]}), [])


class TestSpmDoorBesideAFloor(SimpleTestCase):
    """Owner ruling 2026-11-25 (a): beside a post-SPM group the SPM group is an alternative door,
    and a post-SPM holder who uses it faces EVERY SPM test, the UPU merit included (review round 2,
    F1: floor 3.0 + merit 80 let STPM PNGK 1.0 with no SPM grades through)."""
    MERIT80 = {'test': 'min_upu_merit', 'value': 80}

    def test_floor_plus_merit_only_no_longer_passes_everyone(self):
        sec = results('any', post(PNGK3), spm(self.MERIT80))
        self.assertEqual(criteria.results_ok(stpm(1.0, spm_prereq_grades={}), sec), (False, 'PNGK 1.0 below 3.0'))
        for merit, ok in ((80.0, True), (79.9, False), (None, False)):
            with self.subTest(merit=merit), mock.patch('apps.scholarship.criteria.spm_merit', return_value=merit):
                self.assertEqual(criteria.results_ok(stpm(1.0, spm_prereq_grades=WEAK), sec)[0], ok)

    def test_credit_zero_plus_merit(self):
        sec = results('any', post(PNGK3), spm(gc(0, 'C'), self.MERIT80))
        self.assertFalse(criteria.results_ok(stpm(1.0, spm_prereq_grades={}), sec)[0])
        with mock.patch('apps.scholarship.criteria.spm_merit', return_value=70.0):
            self.assertFalse(criteria.results_ok(stpm(1.0, spm_prereq_grades=WEAK), sec)[0])
        with mock.patch('apps.scholarship.criteria.spm_merit', return_value=85.0):
            self.assertTrue(criteria.results_ok(stpm(1.0, spm_prereq_grades=WEAK), sec)[0])

    def test_the_merit_is_spm_merit_on_their_spm_grades(self):
        from apps.scholarship.shortlisting import spm_merit
        p = stpm(1.0, spm_prereq_grades=STRONG)
        m = spm_merit(p)
        self.assertIsNotNone(m)
        for need, ok in ((m, True), (m + 0.1, False)):
            sec = results('any', post(PNGK3), spm({'test': 'min_upu_merit', 'value': need}))
            self.assertEqual(criteria.results_ok(p, sec)[0], ok)

    def test_all_mode_reason_names_the_merit(self):
        sec = results('all', post(PNGK3), spm(self.MERIT80))
        with mock.patch('apps.scholarship.criteria.spm_merit', return_value=70.0):
            self.assertEqual(criteria.results_ok(stpm(3.5, spm_prereq_grades=WEAK), sec),
                             (False, 'merit point 70.0 below 80'))
        self.assertEqual(criteria.results_ok(stpm(3.5, spm_prereq_grades={}), sec),
                         (False, 'SPM grades not provided'))

    def test_blank_floor_keeps_d3(self):
        sec = results('any', spm(self.MERIT80))
        with mock.patch('apps.scholarship.criteria.spm_merit', return_value=10.0):
            self.assertEqual(criteria.results_ok(stpm(1.0, spm_prereq_grades={}), sec), (True, ''))
            self.assertEqual(criteria.results_ok(stpm(1.0, spm_prereq_grades=WEAK), sec), (True, ''))


class TestResults(SimpleTestCase):
    def test_absent_section_is_not_checked(self):
        self.assertEqual(criteria.results_ok(prof(grades={}), None), (True, ''))
        r = criteria.evaluate(app(prof(grades={})), {'all': []})
        self.assertEqual(r.verdict, 'shortlisted')

    def test_post_spm_group_needs_a_final_post_spm_result(self):
        sec = results('any', post(PNGK3))
        self.assertEqual(criteria.results_ok(prof(), sec), (False, 'no post-SPM results (PNGK floor 3)'))
        for kind in ('stpm', 'matric', 'asasi', 'diploma'):      # still studying reads SPM
            with self.subTest(still_studying=kind):
                ok, why = criteria.results_ok(prof(exam_type=kind), sec)
                self.assertEqual((ok, why), (False, 'no post-SPM results (PNGK floor 3)'))
        self.assertEqual(criteria.results_ok(prof(), results('any', post())), (False, 'no post-SPM results'))

    def test_empty_post_spm_group_passes_any_final_result(self):
        self.assertEqual(criteria.results_ok(stpm(None), results('any', post())), (True, ''))

    def test_min_pngk_boundaries(self):
        sec = results('any', post(PNGK3))
        self.assertEqual(criteria.results_ok(stpm(3.0), sec), (True, ''))
        self.assertEqual(criteria.results_ok(stpm(2.99), sec), (False, 'PNGK 2.99 below 3.0'))
        self.assertEqual(criteria.results_ok(stpm(None), sec), (False, 'STPM PNGK not provided'))
        dip = prof(exam_type='diploma', higher_cgpa=2.995, higher_institution_type='public',
                   results_exam_type='diploma', completed_qualifications=['spm', 'diploma'])
        self.assertEqual(criteria.results_ok(dip, sec), (True, ''))      # 2.995 rounds to 3.00
        mat = prof(exam_type='matric', higher_cgpa=3.5, results_exam_type='matric',
                   completed_qualifications=['spm', 'matric'])
        self.assertEqual(criteria.results_ok(mat, sec), (False, 'Matriculation co-curriculum score not provided'))

    def test_min_merit_is_the_post_spm_merit_out_of_100(self):
        sec = results('any', post({'test': 'min_merit', 'value': 80}))
        for merit, want in ((80.0, (True, '')), (79.99, (False, 'post-SPM merit 79.99 below 80')),
                            (None, (False, 'post-SPM merit not available (need 80)'))):
            with self.subTest(merit=merit), mock.patch('apps.courses.public.merit_100', return_value=merit):
                self.assertEqual(criteria.results_ok(stpm(3.5), sec), want)

    def test_grade_count_boundaries_for_every_grade(self):
        grades = {f's{i}': g for i, g in enumerate(criteria.GRADES)}     # one of each: n at G = index + 1
        for i, g in enumerate(criteria.GRADES):
            with self.subTest(grade=g):
                ok, _ = criteria.results_ok(prof(grades=grades), results('any', spm(gc(i + 1, g))))
                self.assertTrue(ok)
                ok, why = criteria.results_ok(prof(grades=grades), results('any', spm(gc(i + 2, g))))
                self.assertFalse(ok)
                self.assertIn(f'{i + 1} at {g}', why)

    def test_reasons_keep_todays_wording(self):
        sec = results('any', spm(gc(4, 'A-'), gc(5, 'B+'), gc(6, 'C')))
        self.assertEqual(criteria.results_ok(prof(grades=WEAK), sec),
                         (False, '0 at A- (need 4); 0 at B+ or better (need 4 at A- plus 1 more at B+); '
                                 '3 at C or better (need 6)'))
        self.assertEqual(criteria.results_ok(prof(grades=WEAK), results('any', spm(gc(5, 'B+')))),
                         (False, '0 at B+ or better (need 5 at B+ or better)'))

    def test_upu_merit_boundaries_and_spm_holders_only(self):
        sec = results('any', spm({'test': 'min_upu_merit', 'value': 70}))
        for merit, want in ((70.0, (True, '')), (69.9, (False, 'merit point 69.9 below 70')),
                            (None, (False, 'merit point not available (need 70)'))):
            with self.subTest(merit=merit), mock.patch('apps.scholarship.criteria.spm_merit', return_value=merit):
                self.assertEqual(criteria.results_ok(prof(), sec), want)
                self.assertEqual(criteria.results_ok(stpm(2.0), sec), (True, ''))    # D3

    def test_empty_spm_group_passes_everyone(self):
        sec = results('any', spm())
        for p in (prof(), prof(grades={}), stpm(1.0)):
            self.assertEqual(criteria.results_ok(p, sec), (True, ''))

    def test_post_spm_holder_with_no_spm_grades_on_a_grade_rule(self):
        sec = results('any', spm(gc(3, 'C')))
        self.assertEqual(criteria.results_ok(stpm(3.5, spm_prereq_grades={}), sec),
                         (False, 'SPM-only intake: SPM grades not provided'))
        self.assertEqual(criteria.results_ok(stpm(3.5, spm_prereq_grades=WEAK), sec), (True, ''))

    def test_any_is_a_real_any_and_all_needs_both(self):
        both = stpm(2.5, spm_prereq_grades=WEAK)                     # below floor, 3 credits
        anyt = results('any', post(PNGK3), spm(gc(3, 'C')))
        allt = results('all', post(PNGK3), spm(gc(3, 'C')))
        self.assertEqual(criteria.results_ok(both, anyt), (True, ''))
        self.assertEqual(criteria.results_ok(both, allt), (False, 'PNGK 2.5 below 3.0'))
        good = stpm(3.2, spm_prereq_grades=WEAK)
        self.assertEqual(criteria.results_ok(good, allt), (True, ''))
        # 'any' failing: the student's OWN group speaks.
        weak = stpm(2.5, spm_prereq_grades={'bm': 'D'})
        self.assertEqual(criteria.results_ok(weak, anyt), (False, 'PNGK 2.5 below 3.0'))
        self.assertEqual(criteria.results_ok(prof(grades={'bm': 'D'}), anyt),
                         (False, '0 at C or better (need 3)'))
        self.assertEqual(criteria.results_ok(weak, allt),
                         (False, 'PNGK 2.5 below 3.0; 0 at C or better (need 3)'))

    def test_spm_group_off_is_the_cgpa_trap(self):
        sec = results('any', post(PNGK3))
        self.assertEqual(criteria.results_ok(prof(), sec), (False, 'no post-SPM results (PNGK floor 3)'))
        r = criteria.evaluate(app(prof()), {'all': [sec]})
        self.assertEqual((r.verdict, r.category, r.reason),
                         ('rejected', 'merit', 'academic floor: no post-SPM results (PNGK floor 3)'))


class TestIncome(SimpleTestCase):
    CEIL = {'test': 'household_income_max', 'rm': 5860}
    PP = {'test': 'income_per_person_under', 'rm': 1584}

    def sec(self, mode, *tests):
        return {'section': 'income', mode: list(tests)}

    def test_absent_section(self):
        self.assertEqual(criteria.income_ok(prof(household_income=None), None),
                         (True, '', 'no financial requirement set for this programme'))

    def test_str_passes_in_either_mode(self):
        for mode in criteria.MODES:
            self.assertEqual(criteria.income_ok(prof(receives_str=True, household_income=99999),
                                                self.sec(mode, self.CEIL, self.PP)), (True, 'A', 'STR recipient'))

    def test_any_is_todays_rescue_rule(self):
        s = self.sec('any', self.CEIL, self.PP)
        self.assertEqual(criteria.income_ok(prof(household_income=5860), s)[:2], (True, 'B'))
        self.assertEqual(criteria.income_ok(prof(household_income=7000, household_size=5), s)[:2], (True, 'B'))
        self.assertEqual(criteria.income_ok(prof(household_income=7920, household_size=5), s),
                         (False, '', 'income RM7920 > RM5860 and per-capita RM1584 >= RM1584'))
        self.assertEqual(criteria.income_ok(prof(household_income=7000, household_size=None), s),
                         (False, '', 'income RM7000 > RM5860 and household size not provided'))
        for inc in (None, 0):
            self.assertEqual(criteria.income_ok(prof(household_income=inc), s),
                             (False, '', 'no STR and household income not provided'))

    def test_single_tests(self):
        self.assertEqual(criteria.income_ok(prof(household_income=5861), self.sec('all', self.CEIL)),
                         (False, '', 'income RM5861 > RM5860'))
        self.assertEqual(criteria.income_ok(prof(household_income=6000, household_size=4), self.sec('any', self.PP)),
                         (True, 'B', 'income RM6000 above B40 ceiling but per-capita RM1500 < RM1584'))
        self.assertEqual(criteria.income_ok(prof(household_income=6000, household_size=None), self.sec('any', self.PP)),
                         (False, '', 'income RM6000 > RMNone and household size not provided'))

    def test_all_needs_both(self):
        s = self.sec('all', self.CEIL, self.PP)
        self.assertEqual(criteria.income_ok(prof(household_income=5000, household_size=4), s)[:2], (True, 'B'))
        self.assertEqual(criteria.income_ok(prof(household_income=5000, household_size=3), s),
                         (False, '', 'income RM5000 <= RM5860 but per-capita RM1667 >= RM1584'))
        self.assertEqual(criteria.income_ok(prof(household_income=7000, household_size=9), s),
                         (False, '', 'income RM7000 > RM5860'))
        self.assertEqual(criteria.income_ok(prof(household_income=5000, household_size=None), s),
                         (False, '', 'income RM5000 <= RM5860 but household size not provided'))


class TestBornInAndFlag(SimpleTestCase):
    def test_born_in(self):
        tree = {'all': [{'section': 'born_in', 'any': ['sabah']}]}
        self.assertEqual(criteria.evaluate(app(prof(nric='050101-12-1234')), tree).verdict, 'shortlisted')
        r = criteria.evaluate(app(prof(nric='050101-10-1234')), tree)
        self.assertEqual((r.verdict, r.category, r.reason),
                         ('rejected', 'ineligible', check_birth_state('050101-10-1234', ['sabah'])[1]))
        self.assertEqual(criteria.evaluate(app(prof(nric='')), {'all': []}).verdict, 'shortlisted')

    def test_course_start_year_is_a_flag_only(self):
        tree = {'all': [], 'flag': [{'test': 'course_start_year', 'allowed': [2026]}]}
        self.assertIsNone(criteria.start_year_flag(app(), {'all': []}))
        for year, state in ((2026, 'inside'), (2024, 'outside'), (None, 'unknown')):
            with self.subTest(year=year), mock.patch('apps.scholarship.start_year.possible_start_years',
                                                     return_value=SimpleNamespace(year=year)):
                self.assertEqual(criteria.start_year_flag(app(), tree)['state'], state)
        self.assertEqual(criteria.evaluate(app(), tree).verdict, 'shortlisted')

    def test_hard_gates_keep_their_order(self):
        tree = {'all': [{'section': 'born_in', 'any': ['sabah']}]}
        self.assertEqual(criteria.evaluate(app(consent_to_contact=False), tree).reason, 'no consent to contact')
        self.assertEqual(criteria.evaluate(app(intends_tertiary_2026=False), tree).category, 'ineligible')
        self.assertEqual(criteria.evaluate(app(upu_status='ipts'), tree).reason, 'IPTS-only — outside programme scope')
        dip = prof(exam_type='diploma', higher_cgpa=3.5, higher_institution_type='private', nric='050101-12-1234',
                   results_exam_type='diploma', completed_qualifications=['spm', 'diploma'])
        self.assertTrue(criteria.evaluate(app(dip), tree).reason.startswith('Diploma from a private college'))


def cohort(**f):
    base = dict(code='x', min_spm_a_count=None, min_spm_bplus_count=None, min_spm_credit_count=None,
                min_stpm_pngk=None, min_merit_score=None, income_ceiling=None, per_capita_ceiling=None,
                allowed_birth_states=[], allowed_start_years=[])
    base.update(f)
    return SimpleNamespace(**base)


PNGK2 = {'test': 'min_pngk', 'value': 2.0}
#: The live intakes' settings exactly as the lead read them on 25 Nov (review round 1).
PENINSULA = ['johor', 'kedah', 'kelantan', 'melaka', 'negeri_sembilan', 'pahang', 'perak', 'perlis',
             'pulau_pinang', 'selangor', 'terengganu', 'wp_kuala_lumpur', 'wp_putrajaya']
COHORT_1 = cohort(code='b40-2026', min_spm_a_count=4, min_spm_bplus_count=5, income_ceiling=5860,
                  per_capita_ceiling=1584)
COHORT_3 = cohort(code='2026-bpb-s', min_spm_a_count=0, min_spm_bplus_count=0, min_spm_credit_count=3,
                  min_stpm_pngk=2.0, min_merit_score=0, income_ceiling=5860, per_capita_ceiling=1180,
                  allowed_birth_states=['sabah', 'wp_labuan'])
COHORT_4 = cohort(code='bpb-gss-ipoh-2026', min_spm_credit_count=3, min_stpm_pngk=2.0, income_ceiling=5860,
                  per_capita_ceiling=1000)
COHORT_5 = cohort(code='bpb-deg-dip-2026', min_stpm_pngk=3.0, income_ceiling=5860, per_capita_ceiling=900,
                  allowed_birth_states=PENINSULA, allowed_start_years=[2025, 2026])
DEFAULTS = cohort(min_spm_a_count=4, min_spm_bplus_count=5, min_stpm_pngk=2.9, per_capita_ceiling=1584)


def income(ceiling, pc):
    return {'section': 'income', 'any': [{'test': 'household_income_max', 'rm': ceiling},
                                         {'test': 'income_per_person_under', 'rm': pc}]}


class TestFromLegacy(SimpleTestCase):
    def test_cohort_1_no_floor_is_spm_only(self):
        self.assertEqual(criteria.from_legacy(COHORT_1), {'all': [
            results('any', spm(gc(4, 'A-'), gc(5, 'B+'))), income(5860, 1584)]})

    def test_cohort_3_keeps_its_zero_bars(self):
        self.assertEqual(criteria.from_legacy(COHORT_3), {'all': [
            results('any', post(PNGK2), spm(gc(0, 'A-'), gc(0, 'B+'), gc(3, 'C'),
                                            {'test': 'min_upu_merit', 'value': 0})),
            income(5860, 1180), {'section': 'born_in', 'any': ['sabah', 'wp_labuan']}]})

    def test_cohort_4(self):
        self.assertEqual(criteria.from_legacy(COHORT_4), {'all': [
            results('any', post(PNGK2), spm(gc(3, 'C'))), income(5860, 1000)]})

    def test_cohort_5_floor_with_no_spm_bar_is_the_cgpa_trap(self):
        self.assertEqual(criteria.from_legacy(COHORT_5), {'all': [
            results('any', post(PNGK3)), income(5860, 900), {'section': 'born_in', 'any': PENINSULA}],
            'flag': [{'test': 'course_start_year', 'allowed': [2025, 2026]}]})
        plain = criteria.from_legacy(COHORT_5, keep_empty_spm=True)
        self.assertEqual(plain['all'][0], results('any', post(PNGK3), spm()))
        self.assertIs(criteria.tree_for_migration, criteria.from_legacy)

    def test_the_trap_is_decided_by_shape_not_by_code(self):
        for c, has_spm in ((cohort(code='other', min_stpm_pngk=2.5), False),
                           (cohort(min_stpm_pngk=2.5, min_spm_a_count=0, min_merit_score=0), False),
                           (cohort(min_stpm_pngk=2.5, min_merit_score=50.0), True),
                           (cohort(min_stpm_pngk=2.5, min_spm_credit_count=1), True),
                           (cohort(code='bpb-deg-dip-2026', min_stpm_pngk=3.0, min_spm_credit_count=5), True)):
            with self.subTest(c=repr(c)):
                groups = criteria.from_legacy(c)['all'][0]['any']
                self.assertEqual([g['route'] for g in groups], ['post_spm', 'spm'] if has_spm else ['post_spm'])

    def test_model_defaults(self):
        self.assertEqual(criteria.from_legacy(DEFAULTS), {'all': [
            results('any', post({'test': 'min_pngk', 'value': 2.9}), spm(gc(4, 'A-'), gc(5, 'B+'))),
            {'section': 'income', 'any': [{'test': 'income_per_person_under', 'rm': 1584}]}]})

    def test_nothing_set_and_merit_and_every_tree_validates(self):
        self.assertEqual(criteria.from_legacy(cohort()), {'all': []})
        self.assertEqual(criteria.from_legacy(cohort(min_merit_score=80.0))['all'][0],
                         results('any', spm({'test': 'min_upu_merit', 'value': 80.0})))
        for c in (COHORT_1, COHORT_3, COHORT_4, COHORT_5, DEFAULTS, cohort()):
            self.assertEqual(criteria.validate_tree(criteria.from_legacy(c)), [])
        for c in (COHORT_1, COHORT_3, COHORT_4, DEFAULTS, cohort()):
            self.assertEqual(criteria.validate_tree(criteria.from_legacy(c, keep_empty_spm=True)), [])
        # --plain on intake 5 is the trap left on: a comparison view that validate refuses.
        self.assertEqual(criteria.validate_tree(criteria.from_legacy(COHORT_5, keep_empty_spm=True)),
                         [criteria.VOID_SPM_DOOR])

    def test_from_legacy_never_builds_a_void_spm_door(self):
        # ruling (b): only a count or a merit above 0 counts as a bar.
        shapes = [dict(min_stpm_pngk=3.0, min_merit_score=80.0),
                  dict(min_stpm_pngk=3.0, min_spm_credit_count=0, min_merit_score=80.0),
                  dict(min_stpm_pngk=2.0, min_spm_a_count=0, min_spm_bplus_count=0, min_spm_credit_count=0,
                       min_merit_score=0),
                  dict(min_stpm_pngk=2.0, min_merit_score=0), dict(min_stpm_pngk=0.0, min_spm_a_count=0)]
        for f in shapes:
            with self.subTest(f=f):
                self.assertEqual(criteria.validate_tree(criteria.from_legacy(cohort(**f))), [])
        self.assertTrue(criteria.has_spm_bar(COHORT_3))          # credit 3 keeps its group
        self.assertFalse(criteria.has_spm_bar(COHORT_5))
        self.assertEqual([g['route'] for g in criteria.from_legacy(COHORT_3)['all'][0]['any']], ['post_spm', 'spm'])
        self.assertEqual([g['route'] for g in criteria.from_legacy(COHORT_5)['all'][0]['any']], ['post_spm'])

    def test_refused_trees_names_bad_intakes_by_id_and_code_only(self):
        good = cohort(code='ok', id=1, min_stpm_pngk=2.0)
        case = cohort(code='case', id=2, allowed_birth_states=['Sabah'])
        junk = cohort(code='junk', id=3, allowed_start_years=['soon'])
        out = criteria.refused_trees([good, case, junk, COHORT_1, COHORT_3, COHORT_4, COHORT_5])
        self.assertEqual([(i, c) for i, c, _ in out], [(2, 'case'), (3, 'junk')])
        self.assertEqual(out[0][2], ['born_in must be any: [distinct state keys]'])
        self.assertEqual(out[1][2], ['course_start_year needs allowed: [years]'])

    def test_a_zero_bar_on_a_blank_floor_still_asks_for_spm_grades(self):
        from apps.scholarship import shortlisting
        c = cohort(min_spm_a_count=0, min_spm_bplus_count=5)
        for p in (stpm(3.5, spm_prereq_grades={}), prof(grades=WEAK)):
            a = app(p)
            with self.subTest(p=p.exam_type):
                self.assertEqual(criteria.evaluate(a, criteria.from_legacy(c)), shortlisting.evaluate(a, c))
        self.assertEqual(criteria.evaluate(app(stpm(3.5, spm_prereq_grades={})), criteria.from_legacy(c)).reason,
                         'academic floor: SPM-only intake: SPM grades not provided')
        self.assertIn('need 0 at A- plus 5 more at B+',
                      criteria.evaluate(app(prof(grades=WEAK)), criteria.from_legacy(c)).reason)

    def test_birth_states_and_years_go_through_their_readers(self):
        tree = criteria.from_legacy(cohort(allowed_birth_states='sabah', allowed_start_years=['soon']))
        self.assertEqual(criteria.birth_states(tree), ['sabah'])
        self.assertEqual(tree['flag'], [{'test': 'course_start_year', 'allowed': []}])
        a = app()
        a.cohort = cohort(allowed_start_years=['soon'])
        from apps.scholarship import start_year
        with mock.patch('apps.scholarship.start_year.possible_start_years',
                        return_value=SimpleNamespace(year=2026)):
            self.assertEqual(criteria.start_year_flag(a, tree), start_year.reading(a))
            self.assertIsNotNone(criteria.start_year_flag(a, tree))   # junk years: the rule stays ON
