"""Route-aware exam-year colours (owner rule, approved 2026-11-01; `exam_years`).

Cohort year C; the route is the results the student holds (`results_route.held`):

    none / SPM only   SPM C−1
    STPM              STPM C−1; SPM C−3
    Matriculation     Matriculation C; SPM C−2
    Asasi             Asasi C; SPM C−2
    Diploma           Diploma C−1 or C; SPM C−4

'current' is the expected year, 'off' any other (amber), '' no year / no expectation (no colour).
"""
from django.test import TestCase
from django.utils import timezone

from apps.scholarship.academic_engine import student_slip_check
from apps.scholarship.exam_years import expected_years, year_status
from apps.scholarship.higher_results import student_higher_check
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import make_application, make_cohort, make_student
from apps.scholarship.tests.factories import create_document


def _app(route, cohort_year=2026):
    student = make_student(results_exam_type=route) if route else make_student()
    return make_application('profile_complete', cohort=make_cohort(year=cohort_year), student=student)


class TheTableTest(TestCase):
    """Every row of the owner's table at C=2026, the rule moving with the cohort, an unknown route."""

    def test_each_route_at_2026(self):
        rows = {
            'spm': {'spm': {'2025'}},
            'stpm': {'stpm': {'2025'}, 'spm': {'2023'}},
            'matric': {'matric': {'2026'}, 'spm': {'2024'}},
            'asasi': {'asasi': {'2026'}, 'spm': {'2024'}},
            'diploma': {'diploma': {'2025', '2026'}, 'spm': {'2022'}},
        }
        for route, want in rows.items():
            with self.subTest(route=route):
                self.assertEqual(expected_years(_app(route)), want)

    def test_statuses_for_an_stpm_student(self):
        app = _app('stpm')
        self.assertEqual(year_status(app, 'stpm', '2025'), 'current')
        self.assertEqual(year_status(app, 'stpm', '2024'), 'off')
        self.assertEqual(year_status(app, 'spm', '2023'), 'current')
        self.assertEqual(year_status(app, 'spm', '2025'), 'off')     # amber now; the old rule's green
        self.assertEqual(year_status(app, 'matric', '2026'), '')     # the route names no such year
        self.assertEqual(year_status(app, 'spm', ''), '')

    def test_a_diploma_accepts_either_year_and_only_one_spm(self):
        app = _app('diploma')
        self.assertEqual([year_status(app, 'diploma', y) for y in ('2025', '2026', '2024')],
                         ['current', 'current', 'off'])
        self.assertEqual([year_status(app, 'spm', y) for y in ('2022', '2023')], ['current', 'off'])

    def test_the_rule_moves_with_the_cohort(self):
        app = _app('stpm', cohort_year=2027)
        self.assertEqual(expected_years(app), {'stpm': {'2026'}, 'spm': {'2024'}})
        self.assertEqual(expected_years(_app('', cohort_year=2027)), {'spm': {'2026'}})

    def test_an_unknown_route_keeps_the_old_rule(self):
        app = _app('')                                    # nothing held or declared
        self.assertEqual(expected_years(app), {'spm': {'2025'}})
        self.assertEqual(year_status(app, 'spm', '2025'), 'current')
        self.assertEqual(year_status(app, 'spm', '2023'), 'off')


def _doc(app, doc_type, fields, **kw):
    return create_document(
        application=app, doc_type=doc_type, storage_path=f'{app.id}/{doc_type}/x', vision_run_at=timezone.now(),
        vision_fields={'fields': fields, 'student_verdict': 'ok', 'warnings': [], 'error': ''}, **kw)


class TheChecksTest(TestCase):
    """The SPM slip check and the higher-results check both read the one rule."""

    def test_the_spm_slip_check_is_route_aware(self):
        exam = 'SIJIL PELAJARAN MALAYSIA TAHUN 2023'
        stpm = _app('stpm')
        self.assertEqual(student_slip_check(_doc(stpm, 'results_slip', {'exam': exam}))['exam_year_status'],
                         'current')
        spm = _app('spm')
        self.assertEqual(student_slip_check(_doc(spm, 'results_slip', {'exam': exam}))['exam_year_status'], 'off')

    def test_the_stpm_results_carry_a_coloured_year(self):
        app = _app('stpm')
        chk = student_higher_check(_doc(app, 'higher_results', {
            'exam': 'SIJIL TINGGI PERSEKOLAHAN MALAYSIA 2025', 'results_kind_detected': 'stpm'}, results_kind='stpm'))
        self.assertEqual((chk['exam_year'], chk['exam_year_status']), ('2025', 'current'))
        chk = student_higher_check(_doc(app, 'higher_results', {
            'exam': 'SIJIL TINGGI PERSEKOLAHAN MALAYSIA', 'exam_year': '2022',
            'results_kind_detected': 'stpm'}, results_kind='stpm'))
        self.assertEqual((chk['exam_year'], chk['exam_year_status']), ('2022', 'off'))

    def test_a_transcript_with_no_year_stays_uncoloured(self):
        app = _app('matric')
        chk = student_higher_check(_doc(app, 'higher_results', {
            'exam': 'TRANSKRIP AKADEMIK / ACADEMIC TRANSCRIPT', 'results_kind_detected': 'matric'},
            results_kind='matric'))
        self.assertEqual((chk['exam_year'], chk['exam_year_status']), ('', ''))
