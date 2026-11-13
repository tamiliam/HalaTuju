"""F1 regression tests: the owner's changes to the slip-check rules (2026-11-13).

Source: ``docs/plans/2026-11-13-f1-slip-check-rule-table.md``, Part 2, Q1 to Q7 as recommended
(Q5 and Q8 keep today's rules). Each test fails on the code before F1 step 3. The matrix
(`test_slip_check_matrix.py`) pins the whole cell; these pin the one rule each change made.
"""
from django.test import TestCase, override_settings

from apps.scholarship import results_route
from apps.scholarship.academic_compare import spm_slip_compare
from apps.scholarship.academic_engine import read_slip
from apps.scholarship.higher_results import _compare_stpm, red_chips, student_higher_check
from apps.scholarship.tests.test_slip_check_matrix import (
    DEGREE, EXACT_READ, GENUINE, SHORT_ROWS, SPM_HELD, SPM_ROWS, STPM_GRADES, STPM_HELD, STPM_ROWS,
    SUBMITTED, UNSURE, _academic, _app, _doc, spm_read, stpm_read)


class Q1SpmShortRead(TestCase):
    def test_a_short_read_names_what_it_missed(self):
        app = _app(SPM_HELD, DEGREE)
        cmp = spm_slip_compare(app.profile, read_slip(_doc(app, 'results_slip', spm_read(SHORT_ROWS))))
        self.assertTrue(cmp['short_read'])
        self.assertEqual(cmp['unchecked'], ['Matematik'])
        self.assertFalse(cmp['complete'])

    def test_a_full_read_names_nothing(self):
        app = _app(SPM_HELD, DEGREE)
        cmp = spm_slip_compare(app.profile, read_slip(_doc(app, 'results_slip', spm_read(SPM_ROWS))))
        self.assertEqual((cmp['unchecked'], cmp['complete']), ([], True))

    def test_fewer_rows_than_the_slip_prints_is_never_complete(self):
        # Review 2026-11-13: six printed, five read, all five typed found - nothing typed is unchecked,
        # yet a row was never seen: not complete, Subjects open, the reason flagged.
        app = _app(SPM_HELD, DEGREE)
        cmp = spm_slip_compare(app.profile, read_slip(_doc(app, 'results_slip', spm_read(SPM_ROWS, 'ENAM'))))
        self.assertEqual((cmp['short_read'], cmp['unchecked']), (True, []))
        self.assertEqual((cmp['complete'], cmp['subjects_open'], cmp['rows_unread']), (False, True, True))


class Q2toQ4StpmCompare(TestCase):
    def _profile(self, **grades):
        return _app({**STPM_HELD, 'stpm_grades': {**STPM_GRADES, **grades}}, DEGREE).profile

    def test_q2_pengajian_am_not_read_is_a_short_read(self):
        missing, mismatched, uncertain, extra, unchecked = _compare_stpm(self._profile(), stpm_read(STPM_ROWS[1:]))
        self.assertEqual((extra, unchecked), ([], ['PENGAJIAN AM']))

    def test_q2_an_unrecognised_row_makes_it_short(self):
        rows = STPM_ROWS + [{'subject': 'XQZW', 'grade': 'B'}]
        out = _compare_stpm(self._profile(BIOLOGY='C'), stpm_read(rows), unrecognised=['XQZW'])
        self.assertEqual(out[3:], ([], ['BIOLOGI']))

    def test_q2_nothing_recognised_names_nothing(self):
        self.assertEqual(_compare_stpm(self._profile(), stpm_read([])), ([], [], [], [], []))

    def test_q3_extra_on_a_full_exact_read_is_red(self):
        app = _app({**STPM_HELD, 'stpm_grades': {**STPM_GRADES, 'BIOLOGY': 'C'}}, DEGREE)
        chk = student_higher_check(_doc(app, 'higher_results', stpm_read(), GENUINE, EXACT_READ))
        self.assertEqual((chk['extra'], chk['grades_status']), (['BIOLOGI'], 'mismatch'))
        self.assertEqual(red_chips(app), 1)

    def test_q3_a_row_an_ai_read_skipped_is_unchecked_not_extra(self):
        # Review 2026-11-13: 3 of 4 rows read, Pengajian Am among them, every row recognised. The
        # skipped KIMIA is amber and named, never a red "not on the slip".
        app = _app(STPM_HELD, DEGREE)
        chk = student_higher_check(_doc(app, 'higher_results', stpm_read(STPM_ROWS[:3]), GENUINE))
        self.assertEqual((chk['extra'], chk['unchecked'], chk['grades_status']), ([], ['KIMIA'], 'pending'))
        self.assertEqual(red_chips(app), 0)

    def test_q3_the_same_skip_on_the_exact_read_is_red(self):
        out = _compare_stpm(self._profile(), stpm_read(STPM_ROWS[:3]), exact=True)
        self.assertEqual(out[3:], (['KIMIA'], []))

    def test_q4_plus_minus_on_an_ai_read_is_uncertain(self):
        out = _compare_stpm(self._profile(PHYSICS='A'), stpm_read())
        self.assertEqual((out[1], [u['subject'] for u in out[2]]), ([], ['FIZIK']))

    def test_q4_plus_minus_on_the_exact_read_stays_a_mismatch(self):
        out = _compare_stpm(self._profile(PHYSICS='A'), stpm_read(), exact=True)
        self.assertEqual(([m['subject'] for m in out[1]], out[2]), (['FIZIK'], []))

    def test_q4_a_different_letter_is_red_on_any_read(self):
        out = _compare_stpm(self._profile(PHYSICS='B'), stpm_read())
        self.assertEqual(([m['subject'] for m in out[1]], out[2]), (['FIZIK'], []))

    def test_q4_the_exact_read_is_told_by_its_stored_record(self):
        app = _app({**STPM_HELD, 'stpm_grades': {**STPM_GRADES, 'PHYSICS': 'A'}}, DEGREE)
        ai = student_higher_check(_doc(app, 'higher_results', stpm_read(), GENUINE))
        exact = student_higher_check(_doc(app, 'higher_results', stpm_read(), GENUINE, EXACT_READ))
        self.assertEqual((ai['grades_status'], exact['grades_status']), ('pending', 'mismatch'))


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class Q6HigherInTheOptionalSpmSlot(TestCase):
    def test_named_but_does_not_hold_a_clean_higher_card(self):
        app = _app(STPM_HELD, DEGREE)
        _doc(app, 'results_slip', stpm_read())
        _doc(app, 'higher_results', stpm_read(), GENUINE)
        fact = _academic(app)
        self.assertEqual(fact['status'], 'verified')
        self.assertIn('results_slip_is_higher', {i['code'] for i in fact['unresolved']})


class Q7OneDegreeTest(TestCase):
    STALE = {'chosen_pathway': 'stpm', 'pathway_certainty': 'sure',
             'chosen_programme': {'course_name': 'Ijazah Sarjana Muda Kejuruteraan Awam',
                                  'institution': 'Universiti Malaya'}}

    def test_a_stale_code_under_a_degree_name_is_asked_before_submit(self):
        app = _app(SPM_HELD, self.STALE)
        self.assertEqual(results_route.destination(app), results_route.POST_SPM)
        self.assertTrue(results_route.degree_bound(app))
        self.assertEqual(results_route.higher_need(app), 'required_with_slip')

    def test_a_post_spm_course_still_asks_nothing(self):
        app = _app(SPM_HELD, {'chosen_pathway': 'matric', 'pathway_certainty': 'sure', 'chosen_programme': {}})
        self.assertEqual(results_route.higher_need(app), '')

    def _plan(self, code, name):
        return {'chosen_pathway': code, 'pathway_certainty': 'sure',
                'chosen_programme': {'course_name': name, 'institution': 'X'}}

    def test_pismp_preparatory_and_american_degree_program_are_not_asked_before_submit(self):
        # Review 2026-11-13, narrowed: the widening is withheld from the before-submit ask ONLY;
        # they stay degree-bound for the award, the funding estimate and the owed cap (TD-617).
        for code, name in (('tvet_other', 'American Degree Program'),
                           ('mara', 'Program Persediaan Ijazah Luar Negara'),
                           ('pismp', 'Ijazah Sarjana Muda Pendidikan')):
            with self.subTest(name):
                app = _app(SPM_HELD, self._plan(code, name))
                self.assertTrue(results_route.degree_bound(app))
                self.assertEqual(results_route.higher_need(app), '')

    def test_american_degree_programme_spellings_are_not_asked_before_submit(self):
        for name in ('American Degree Programme', 'American Degree Programmes',
                     'american  degree   programme', 'AMERICAN DEGREE PROGRAM', 'American Degree Programs'):
            with self.subTest(name):
                app = _app(SPM_HELD, self._plan('tvet_other', name))
                self.assertEqual(results_route.higher_need(app), '')

    def test_american_degree_transfer_program_and_plain_degree_programme_are_still_asked(self):
        for name in ('American Degree Transfer Program', 'Degree Programme in Business'):
            with self.subTest(name):
                app = _app(SPM_HELD, self._plan('tvet_other', name))
                self.assertEqual(results_route.higher_need(app), 'required_with_slip')

    def test_stpm_holder_on_an_american_degree_programme_keeps_the_main_answer(self):
        app = _app(STPM_HELD, self._plan('tvet_other', 'American Degree Programme'))
        self.assertTrue(results_route._q7_widening_withheld(app))
        # A tertiary (STPM) holder already holds higher results: nothing more is asked before submit.
        self.assertEqual(results_route.higher_need(app), '')

    def test_a_saved_catalogue_course_id_decides_by_the_course_not_the_name(self):
        plan = self._plan('stpm', 'Ijazah Sarjana Muda Kejuruteraan Awam')
        plan['chosen_programme']['course_id'] = 'SOME-COURSE'
        app = _app(SPM_HELD, plan)
        self.assertFalse(results_route.degree_bound(app))
        self.assertEqual(results_route.higher_need(app), '')

    def test_a_degree_programme_name_with_no_code_is_asked_before_submit(self):
        # "Degree Programme" is not the American Degree Program.
        app = _app(SPM_HELD, self._plan('', 'Bachelor of Engineering (Hons) Degree Programme'))
        self.assertEqual(results_route.higher_need(app), 'required_with_slip')

    def test_251_stale_form_six_code_under_a_degree_programme_is_degree_bound_and_sized_as_one(self):
        # #251's shape: 'stpm' + "... Degree Programme ..." + no course id. Degree-bound, so RM2,000
        # and the 'degree' estimate (origin/main), never Form Six sizing; asked before submit (Q7).
        from apps.scholarship.award import proposed_award_amount
        from apps.scholarship.funding_estimate import classify_pathway
        app = _app(SPM_HELD, self._plan('stpm', "Bachelor's Degree Programme in Accounting"))
        self.assertTrue(results_route.degree_bound(app))
        self.assertEqual(str(proposed_award_amount(app)), '2000')
        self.assertEqual(classify_pathway(app), 'degree')
        self.assertEqual(results_route.higher_need(app), 'required_with_slip')

    @override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
    def test_a_matric_code_under_a_degree_name_keeps_the_owed_cap(self):
        from apps.scholarship import higher_owed
        app = _app(SPM_HELD, self._plan('matric', 'Ijazah Sarjana Muda Kejuruteraan'), SUBMITTED)
        _doc(app, 'results_slip', spm_read(SPM_ROWS), GENUINE)
        self.assertTrue(results_route.degree_bound(app))
        self.assertTrue(higher_owed.undeclared(app))
        fact = _academic(app)
        self.assertEqual(fact['status'], UNSURE)
        self.assertIn('higher_results_not_declared', {i['code'] for i in fact['unresolved']})

    def test_form_six_code_never_wins_over_a_degree_name(self):
        # The owner's Q7 case stays: an old Form Six code + a degree course name is asked before submit.
        app = _app(SPM_HELD, self._plan('stpm', 'Ijazah Sarjana Muda Kejuruteraan Awam'))
        self.assertEqual(results_route.higher_need(app), 'required_with_slip')


class Q7MoneyUnchangedFromMain(TestCase):
    """F1 must not move money. Expected values were produced by running origin/main's own
    `results_route.py` (award.py and funding_estimate.py are byte-identical to origin/main) on
    these exact applications (SPM held, no course id), 2026-11-13: the award amount
    (`proposed_award_amount`; None = course start unknown) and the funding route (`classify_pathway`)."""
    EXPECTED = [   # (pathway code, programme name, award, funding route) - origin/main
        ('stpm', "Bachelor's Degree Programme in Accounting", '2000', 'degree'),
        ('stpm', 'Ijazah Sarjana Muda Kejuruteraan Awam', '2000', 'degree'),
        ('stpm', 'Tingkatan Enam', None, 'stpm'),
        ('stpm', '', None, 'stpm'),
        ('matric', 'Ijazah Sarjana Muda Kejuruteraan', '2000', 'degree'),
        ('asasi', 'Ijazah Sarjana Muda Sains', '2000', 'degree'),
        ('diploma', 'Ijazah Sarjana Muda Perakaunan', '2000', 'degree'),
        ('pismp', 'Ijazah Sarjana Muda Pendidikan', '2000', 'degree'),
        ('mara', 'Program Persediaan Ijazah Luar Negara', '2000', 'degree'),
        ('tvet_other', 'American Degree Program', '2000', 'degree'),
        ('', 'American Degree Program', '2000', 'degree'),
        ('', 'Bachelor of Engineering (Hons) Degree Programme', '2000', 'degree'),
        ('', 'Program Persediaan Ijazah Luar Negara', '2000', 'degree'),
        ('university', 'Ijazah Sarjana Muda Undang-Undang', '2000', 'degree'),
        ('university', 'Diploma Kejuruteraan Mekanikal', '2000', 'university'),
        ('poly', 'Diploma Kejuruteraan Elektrik', '2000', 'poly'),
    ]

    def test_award_and_funding_route_equal_main(self):
        from apps.scholarship.award import proposed_award_amount
        from apps.scholarship.funding_estimate import classify_pathway
        for code, name, award, route in self.EXPECTED:
            with self.subTest(code=code, name=name):
                app = _app(SPM_HELD, {'chosen_pathway': code, 'pathway_certainty': 'sure',
                                      'chosen_programme': {'course_name': name, 'institution': 'X'}})
                amount = proposed_award_amount(app)
                self.assertEqual((None if amount is None else str(amount), classify_pathway(app)), (award, route))


class Q4StpmAmberOnTheInterviewAgenda(TestCase):
    def test_the_stpm_grade_amber_is_carried_to_the_interview(self):
        # Review 2026-11-13: as the SPM `academic_grade_uncertain` is.
        from apps.scholarship.views_admin.interviews import interview_agenda_full
        app = _app({**STPM_HELD, 'stpm_grades': {**STPM_GRADES, 'PHYSICS': 'A'}}, DEGREE)
        _doc(app, 'higher_results', stpm_read(cgpa='3.75'), GENUINE)
        agenda = interview_agenda_full(app)
        self.assertIn(('needs_interview', 'higher_results_grade_uncertain'),
                      {(e['kind'], e['code']) for e in agenda})
