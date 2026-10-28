"""STPM CGPA sprint C3 (2026-10-28) — the cockpit's STPM check marks (`stpm_marks`).

Owner ruling: the cockpit's STPM grades and CGPA come from onboarding and are counter-checked
against the uploaded STPM results; a match gets a check mark, a difference a marker. Synthetic data
only — no real student. Cases: match, differ, no document, a subject not on the document, an SPM
slip filed in the card, an unread document, "not calculated", an SPM student, and the served payload.
"""
from django.test import TestCase, override_settings

from apps.scholarship.models import ApplicantDocument
from apps.scholarship.stpm_marks import stpm_marks
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_student,
)

# PA + three: PNGK (4.00 + 3.67 + 3.67 + 3.33) / 4 = 3.67.
GRADES = {'PA': 'A', 'MATH_T': 'A-', 'PHYSICS': 'A-', 'CHEMISTRY': 'B+'}
HELD = dict(exam_type='stpm', results_exam_type='stpm', grades={'bm': 'A'}, stpm_grades=GRADES,
            stpm_cgpa=3.10, completed_qualifications=['spm', 'stpm'])
ROWS = [{'subject': 'PENGAJIAN AM', 'grade': 'A'}, {'subject': 'MATEMATIK (T)', 'grade': 'A-'},
        {'subject': 'FIZIK', 'grade': 'A-'}, {'subject': 'KIMIA', 'grade': 'B+'}]
READ = {'candidate_name': 'TEST CALON', 'exam': 'SIJIL TINGGI PERSEKOLAHAN MALAYSIA 2025',
        'cgpa': '3.67', 'cgpa_label': 'PNGK', 'results_kind_detected': 'stpm', 'results': ROWS}


def _app(**profile):
    student = make_student(name='Test Calon', nric='030101-14-5678', **{**HELD, **profile})
    return make_application('profile_complete', student=student)


def _doc(app, fields, verdict='ok', doc_type='higher_results'):
    return ApplicantDocument.objects.create(
        application=app, doc_type=doc_type, storage_path=f'test/{doc_type}',
        vision_fields={'fields': fields, 'student_verdict': verdict, 'error': ''})


class TestTheStpmMarks(TestCase):
    def test_every_grade_and_the_cgpa_match(self):
        app = _app()
        _doc(app, READ)
        m = stpm_marks(app)
        self.assertEqual({k: v['status'] for k, v in m['grades'].items()},
                         {'PA': 'match', 'MATH_T': 'match', 'PHYSICS': 'match', 'CHEMISTRY': 'match'})
        self.assertEqual((m['cgpa'], m['cgpa_doc']), ('match', 3.67))

    def test_a_grade_that_differs_carries_the_documents_grade(self):
        app = _app()
        rows = ROWS[:3] + [{'subject': 'KIMIA', 'grade': 'B'}]
        _doc(app, {**READ, 'results': rows, 'cgpa': '3.58'})
        m = stpm_marks(app)
        self.assertEqual(m['grades']['CHEMISTRY'], {'status': 'differ', 'doc': 'B'})
        self.assertEqual(m['grades']['PA']['status'], 'match')
        self.assertEqual((m['cgpa'], m['cgpa_doc']), ('differ', 3.58))

    def test_the_cgpa_agrees_only_within_one_hundredth(self):
        app = _app()
        _doc(app, {**READ, 'cgpa': '3.68'})
        self.assertEqual(stpm_marks(app)['cgpa'], 'match')
        app2 = _app()
        _doc(app2, {**READ, 'cgpa': '3.70'})
        self.assertEqual(stpm_marks(app2)['cgpa'], 'differ')

    def test_an_unlabelled_figure_that_differs_is_never_called_a_difference(self):
        app = _app()
        _doc(app, {**READ, 'cgpa': '3.20', 'cgpa_label': ''})    # may be one semester's GPA
        self.assertIsNone(stpm_marks(app)['cgpa'])

    def test_no_document_no_marks(self):
        m = stpm_marks(_app())
        self.assertEqual((m['grades'], m['cgpa'], m['cgpa_doc']), ({}, None, None))

    def test_a_subject_not_on_the_document_has_no_mark(self):
        app = _app()
        _doc(app, {**READ, 'results': ROWS[:3]})
        self.assertNotIn('CHEMISTRY', stpm_marks(app)['grades'])

    def test_an_unread_document_has_no_marks(self):
        app = _app()
        _doc(app, READ, verdict='review_manually')
        m = stpm_marks(app)
        self.assertEqual((m['grades'], m['cgpa']), ({}, None))

    def test_an_spm_slip_in_the_card_has_no_marks(self):
        app = _app()
        _doc(app, {**READ, 'results_kind_detected': 'spm'})
        self.assertEqual(stpm_marks(app)['grades'], {})

    def test_fewer_than_pa_and_three_is_not_calculated(self):
        app = _app(stpm_grades={'PA': 'A', 'MATH_T': 'A-', 'PHYSICS': 'A-'})
        _doc(app, READ)
        m = stpm_marks(app)
        self.assertEqual(m['cgpa'], 'not_calculated')
        self.assertEqual(m['grades']['PA']['status'], 'match')       # the grades still check
        self.assertEqual(stpm_marks(_app(stpm_grades={'PA': 'A'}))['cgpa'], 'not_calculated')

    def test_an_spm_student_has_none(self):
        student = make_student(exam_type='spm', results_exam_type='spm', grades={'bm': 'A'})
        self.assertIsNone(stpm_marks(make_application('profile_complete', student=student)))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=False)
class TestTheCockpitIsServedTheMarks(TestCase):
    def test_the_detail_payload_carries_stpm_marks(self):
        app = _app()
        _doc(app, READ)
        admin = make_admin('super', super_admin=True)
        r = authed_client(admin).get(f'/api/v1/admin/scholarship/applications/{app.id}/')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['stpm_marks']['cgpa'], 'match')
        self.assertEqual(body['stpm_marks']['grades']['MATH_T'], {'status': 'match', 'doc': 'A-'})
        self.assertEqual(list(body)[-1], 'programme')       # the gift's key stays last
