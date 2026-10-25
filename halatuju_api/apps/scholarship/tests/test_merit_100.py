"""Third results route S1 — every route ranks on ONE 0-100 merit (`exam_questions.merit_100`).

Before S1 the admin merit was two numbers on two scales in one column: SPM a 0-100 course-guide
merit, STPM the raw PNGK (1.28-4.00 live). So on "merit, highest first" every STPM holder sorted
BELOW every SPM holder — a 4.00 CGPA ranked under a 40-point SPM merit.

The rule now is the course side's own (`apps/courses/views.py` CalculateCgpaView):
``merit = overall CGPA / 4 x 100``. `StudentProfile.stpm_cgpa` already holds the OVERALL CGPA
(academic x 0.9 + koko x 0.04): the STPM results page stores the calculator's `cgpa` (the overall
figure), never `academic_cgpa`, and no other writer exists.

What this file pins:

1. **SPM merit is byte-identical** — the characterisation values below were measured on the tree
   BEFORE S1 and must not move.
2. **STPM conversion** — 3.7 -> 92.5, 4.0 -> 100.0, two decimals like the course side.
3. **Null is absent, never 0** (#106) — no results, no number; and it sorts LAST both ways.
4. **One definition** — list, detail, sort and the AI profile input all read `merit_100`.
"""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship import profile_engine, serializers_admin
from apps.scholarship.serializers_admin import (
    AdminApplicationDetailSerializer, AdminApplicationListSerializer, _application_merit_score,
)
from apps.scholarship.tests.factories import make_application, make_cohort, make_student

SPM = {'bm': 'A', 'eng': 'A', 'math': 'A+', 'hist': 'A', 'moral': 'A'}
SPM_WEAK = {'bm': 'C', 'eng': 'D', 'math': 'C', 'hist': 'E', 'moral': 'B'}
STPM = {'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A'}


def _p(**fields):
    return StudentProfile(supabase_user_id='m100', **fields)


#: name -> (profile fields, merit BEFORE S1 measured on the old tree, merit AFTER S1).
#: SPM rows: before == after, to the byte. STPM rows: the PNGK became PNGK/4x100.
CASES = {
    'spm_strong':            (dict(exam_type='spm', grades=SPM, coq_score=8.0), 54.2, 54.2),
    'spm_strong_no_coq':     (dict(exam_type='spm', grades=SPM), 46.2, 46.2),
    'spm_weak':              (dict(exam_type='spm', grades=SPM_WEAK, coq_score=5.0), 19.4, 19.4),
    'spm_stream':            (dict(exam_type='spm', grades=dict(SPM, phy='A', chem='B+', bio='A-'),
                                   stream_subjects=['phy', 'chem', 'bio'], coq_score=10.0),
                              88.1, 88.1),
    'form_six_explorer':     (dict(exam_type='stpm', grades=SPM, coq_score=8.0), 54.2, 54.2),
    'mirage_15':             (dict(exam_type='spm', grades=SPM, stpm_grades=STPM, stpm_cgpa=4.0,
                                   coq_score=8.0), 54.2, 54.2),
    'stpm_37':               (dict(exam_type='stpm', stpm_grades=STPM, stpm_cgpa=3.7), 3.7, 92.5),
    'stpm_400':              (dict(exam_type='stpm', stpm_grades=STPM, stpm_cgpa=4.0), 4.0, 100.0),
    'stpm_128':              (dict(exam_type='stpm', stpm_grades=STPM, stpm_cgpa=1.28), 1.28, 32.0),
    'stpm_347':              (dict(exam_type='stpm', stpm_cgpa=3.47), 3.47, 86.75),
    'stpm_333':              (dict(exam_type='stpm', stpm_cgpa=3.33), 3.33, 83.25),
    'recorded_stpm':         (dict(exam_type='spm', grades=SPM, stpm_cgpa=3.5,
                                   results_exam_type='stpm'), 3.5, 87.5),
    'stpm_declared_nothing': (dict(exam_type='stpm'), None, None),
    'spm_no_grades':         (dict(exam_type='spm'), None, None),
    'blank':                 (dict(exam_type=''), None, None),
}


class TestSpmMeritIsByteIdentical(SimpleTestCase):
    """Characterisation: written and run green against the tree BEFORE S1."""

    def test_the_spm_values_did_not_move(self):
        # Through the admin entry point that existed before S1, so this ran on both trees.
        for name, (fields, before, after) in CASES.items():
            if before is None or name.startswith(('stpm', 'recorded')):
                continue
            with self.subTest(name):
                self.assertEqual(_application_merit_score(SimpleNamespace(profile=_p(**fields))),
                                 before)
                self.assertEqual(after, before)

    def test_merit_100_gives_the_same_spm_values(self):
        from apps.courses.exam_questions import merit_100
        for name, (fields, before, _after) in CASES.items():
            if before is None or name.startswith(('stpm', 'recorded')):
                continue
            with self.subTest(name):
                self.assertEqual(merit_100(_p(**fields)), before)

    def test_the_stream_shape_still_equals_the_engine(self):
        """The SPM branch is the course-guide engine, called the same way as before S1."""
        from apps.courses.engine import calculate_merit_score, prepare_merit_inputs
        from apps.courses.exam_questions import merit_100
        fields = CASES['spm_stream'][0]
        g = dict(fields['grades'])
        g['history'] = g.pop('hist')
        s1, s2, s3 = prepare_merit_inputs(g, fields['stream_subjects'])
        expected = round(calculate_merit_score(s1, s2, s3, fields['coq_score'])['final_merit'], 1)
        self.assertEqual(merit_100(_p(**fields)), expected)

    def test_spm_keeps_one_decimal(self):
        from apps.courses.exam_questions import merit_100
        m = merit_100(_p(**CASES['spm_weak'][0]))
        self.assertEqual(m, round(m, 1))


class TestStpmConversion(SimpleTestCase):
    def test_every_stpm_case_is_cgpa_over_4_times_100(self):
        from apps.courses.exam_questions import merit_100
        for name, (fields, _before, after) in CASES.items():
            if not name.startswith(('stpm', 'recorded')) or after is None:
                continue
            with self.subTest(name):
                self.assertEqual(merit_100(_p(**fields)), after)

    def test_it_is_the_course_sides_rounding(self):
        """`CalculateCgpaView`: merit_percent = round(overall / 4 x 100, 2)."""
        from apps.courses.exam_questions import merit_100
        for cgpa in (2.01, 2.9, 3.13, 3.67, 3.92):
            with self.subTest(cgpa=cgpa):
                self.assertEqual(merit_100(_p(exam_type='stpm', stpm_cgpa=cgpa)),
                                 round(cgpa / 4.0 * 100, 2))

    def test_the_mirage_is_never_ranked_on_typed_stpm_data(self):
        """#15: presence of STPM data never promotes — she ranks on her SPM merit."""
        from apps.courses.exam_questions import merit_100
        self.assertNotIn(merit_100(_p(**CASES['mirage_15'][0])), (4.0, 100.0))


class TestNullIsAbsent(SimpleTestCase):
    def test_no_results_is_none_never_zero(self):
        from apps.courses.exam_questions import merit_100
        for name in ('stpm_declared_nothing', 'spm_no_grades', 'blank'):
            with self.subTest(name):
                self.assertIsNone(merit_100(_p(**CASES[name][0])))
        self.assertIsNone(merit_100(None))

    def test_a_cgpa_outside_0_to_4_is_absent_not_a_figure(self):
        """S1 review: a 0 stored before the calculator answered, or a hand-sent 40, must not rank."""
        from apps.courses.exam_questions import merit_100
        for cgpa in (0, 0.0, -1, 4.01, 40):
            with self.subTest(cgpa=cgpa):
                self.assertIsNone(merit_100(_p(exam_type='stpm', stpm_cgpa=cgpa)))
        self.assertEqual(merit_100(_p(exam_type='stpm', stpm_cgpa=4.0)), 100.0)

    def test_an_application_without_a_profile_is_none(self):
        self.assertIsNone(_application_merit_score(SimpleNamespace(profile=None)))


class TestOneDefinition(SimpleTestCase):
    def test_the_admin_merit_is_merit_100(self):
        from apps.courses import exam_questions
        app = SimpleNamespace(profile=_p(**CASES['stpm_37'][0]))
        with mock.patch.object(exam_questions, 'merit_100', return_value=12.34) as m:
            self.assertEqual(_application_merit_score(app), 12.34)
        m.assert_called_once_with(app.profile)

    def test_the_ai_profile_input_reads_the_same_figure(self):
        app = SimpleNamespace(profile=_p(**CASES['stpm_37'][0]))
        self.assertEqual(profile_engine._merit(app), '92.5')
        self.assertEqual(profile_engine._merit(SimpleNamespace(profile=_p(exam_type='stpm'))),
                         'not provided')

    def test_the_prompt_version_moved_with_the_input(self):
        # S1 changed what `Merit score:` carries for an STPM holder (3.7 -> 92.5).
        self.assertGreaterEqual(profile_engine.PROMPT_VERSION, '2026-10-25.1')


TEST_JWT_SECRET = 'test-supabase-jwt-secret'
ADMIN = 'm100-admin'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheListSortInterleavesRoutes(TestCase):
    """Before S1 every STPM holder sorted below every SPM holder on "merit, highest first"."""

    @classmethod
    def setUpTestData(cls):
        PartnerAdmin.objects.create(supabase_user_id=ADMIN, is_super_admin=True, is_active=True,
                                    name='Admin', email='m100@example.com')
        cls.cohort = make_cohort(code='m100', name='B40', year=2026)
        rows = [
            ('Spm Strong', dict(exam_type='spm', grades=SPM, coq_score=8.0)),        # 54.2
            ('Spm Weak', dict(exam_type='spm', grades=SPM_WEAK, coq_score=5.0)),     # 19.4
            ('Stpm Top', dict(exam_type='stpm', stpm_grades=STPM, stpm_cgpa=3.92)),  # 98.0
            ('Stpm Mid', dict(exam_type='stpm', stpm_grades=STPM, stpm_cgpa=1.6)),   # 40.0
            ('No Results', dict(exam_type='stpm')),                                  # None
        ]
        cls.apps = {}
        for i, (name, fields) in enumerate(rows):
            prof = make_student(supabase_user_id=f'm100-{i}', nric=f'05010{i}-14-000{i}',
                                name=name, household_income=2000, **fields)
            cls.apps[name] = make_application('shortlisted', cohort=cls.cohort, student=prof)

    def _list(self, params):
        import jwt
        token = jwt.encode({'sub': ADMIN, 'aud': 'authenticated', 'role': 'authenticated'},
                           TEST_JWT_SECRET, algorithm='HS256')
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        r = self.client.get('/api/v1/admin/scholarship/applications/' + params)
        self.assertEqual(r.status_code, 200)
        return r.json()['applications']

    def test_merit_desc_interleaves_stpm_and_spm(self):
        rows = self._list('?sort=merit&dir=desc')
        self.assertEqual([a['name'] for a in rows],
                         ['STPM TOP', 'SPM STRONG', 'STPM MID', 'SPM WEAK', 'NO RESULTS'])
        self.assertEqual([a['merit_score'] for a in rows], [98.0, 54.2, 40.0, 19.4, None])

    def test_merit_asc_keeps_the_absent_merit_last(self):
        """#106: a blank merit is absence from the ordering, not the lowest score."""
        rows = self._list('?sort=merit&dir=asc')
        self.assertEqual([a['name'] for a in rows],
                         ['SPM WEAK', 'STPM MID', 'SPM STRONG', 'STPM TOP', 'NO RESULTS'])

    def test_list_and_detail_show_the_same_figure(self):
        for name, app in self.apps.items():
            with self.subTest(name):
                listed = AdminApplicationListSerializer(app).data['merit_score']
                detail = AdminApplicationDetailSerializer(app).data['merit_score']
                self.assertEqual(listed, detail)
        self.assertEqual(AdminApplicationListSerializer(self.apps['Stpm Top']).data['merit_score'],
                         98.0)

    def test_the_raw_pngk_is_still_served_beside_it(self):
        # The PNGK is a fact of its own (the shortlist floor reads it); only the RANK moved.
        self.assertEqual(
            AdminApplicationListSerializer(self.apps['Stpm Top']).data['stpm_pngk'], 3.92)


def test_serializers_admin_keeps_no_second_conversion():
    """Source guard: the `/ 4` conversion lives in `merit_100` only."""
    import inspect
    src = inspect.getsource(serializers_admin._application_merit_score)
    assert 'stpm_cgpa' not in src and 'calculate_merit_score' not in src
