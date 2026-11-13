"""Follow-up to the higher-results-owed fix (owner 2026-11-07, app 278): what an UNDECLARED higher upload
shows, the declare ask's copy once the document is on file, the post-submit route upward, and
typo-tolerant STPM subject names (`stpm_names`). Shapes from a read-only audit; synthetic data only.

Owner principle: everything shown is what the student DECLARED; a tick only when documentary evidence
matches it. Nothing declared, nothing to compare — no tick, no mismatch claim.
"""
from django.test import TestCase, override_settings

from apps.scholarship import higher_owed, results_route
from apps.scholarship.check2_queries import sync_check2_queries
from apps.scholarship.higher_results import red_chips, student_higher_check
from apps.scholarship.models import InterviewSession, ResolutionItem
from apps.scholarship.stpm_marks import stpm_marks
from apps.scholarship.stpm_names import stpm_key, stpm_keyed_rows
from apps.scholarship.tests.factories import TEST_JWT_SECRET, authed_client
from apps.scholarship.tests.test_third_route_higher_owed import _submitted
from apps.scholarship.tests.test_third_route_s4 import SPM, SPM_HELD, _academic, _doc, _fresh

DECLARE = higher_owed.DECLARE_ASK_CODE


def _rows(*pairs):
    return [{'subject': s, 'grade': g} for s, g in pairs]


#: 278's certificate as the AI read it: "PENGAJIAN AM" printed, "PENGJIAN AM" read; CGPA right.
CERT_278 = {'candidate_name': 'PRIYA', 'exam': 'SIJIL TINGGI PERSEKOLAHAN MALAYSIA 2025', 'cgpa': '3.67',
            'cgpa_label': 'PNGK', 'results_kind_detected': 'stpm',
            'results': _rows(('PENGJIAN AM', 'A-'), ('BAHASA MELAYU', 'A'), ('SEJARAH', 'A-'), ('GEOGRAFI', 'A'))}
#: 196's shape: entered PA B+ (and Business), the certificate prints B for PA; both names misread.
STPM_196 = dict(exam_type='stpm', results_exam_type='stpm', grades=SPM, spm_prereq_grades=SPM,
                stpm_grades={'PA': 'B+', 'BUSINESS': 'A-', 'ECONOMICS': 'B', 'SEJARAH': 'B'},
                completed_qualifications=['spm', 'stpm'])
CERT_196 = {'candidate_name': 'PRIYA', 'exam': 'SIJIL TINGGI PERSEKOLAHAN MALAYSIA 2025', 'cgpa': '3.17',
            'cgpa_label': 'PNGK', 'results_kind_detected': 'stpm',
            'results': _rows(('PENGJIAN AM', 'B'), ('PENGJIAN PERNIAGAAN', 'A-'), ('EKONOMI', 'B'), ('SEJARAH', 'B'))}
#: 279 / 341 / 418's shape: the PA misread is the only thing between the slip and a full match.
STPM_279 = {**STPM_196, 'stpm_grades': {'PA': 'B', 'BUSINESS': 'A-', 'ECONOMICS': 'B', 'SEJARAH': 'B'}}


def _codes(items):
    return [i['code'] for i in items]


def _interview_submitted(app):
    type(app).objects.filter(pk=app.pk).update(status='interviewing')
    InterviewSession.objects.create(application=app, status='submitted')
    return _fresh(app)


def _278():
    """SPM only, degree-bound, interviewing with its session submitted, the team's split STPM upload."""
    app = _interview_submitted(_submitted(profile=SPM_HELD))
    doc = _doc(app, 'higher_results', CERT_278, results_kind='stpm')
    return _fresh(app), doc


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class TestPoint1And2UndeclaredComparesNothing(TestCase):
    def test_278_no_subject_or_grade_claim_and_no_kind_tick(self):
        app, doc = _278()
        chk = student_higher_check(doc)
        self.assertEqual((chk['kind_status'], chk['grades_status'], chk['missing'], chk['mismatched']),
                         ('', 'not_compared', [], []))
        self.assertEqual(chk['kind_detected'], 'stpm')          # the read is kept, only never TICKED
        self.assertEqual(chk['note'], '')
        self.assertEqual(red_chips(app), 0)                     # was the red Results chip
        f = _academic(app)
        codes = _codes(f['unresolved']) + _codes(f['evidence'])
        for code in ('higher_results_subjects_missing', 'higher_results_grade_mismatch',
                     'higher_results_kind_ok', 'higher_results_kind_differs', 'higher_results_cgpa_mismatch',
                     'higher_results_subjects_unrecognised'):
            self.assertNotIn(code, codes)
        self.assertIn(higher_owed.UNDECLARED_ON_FILE_CODE, _codes(f['unresolved']))   # the one that speaks
        self.assertEqual(f['status'], 'recommend')
        self.assertEqual(chk['cgpa_status'], 'pending')        # CGPA unchanged: read, nothing to check

    def test_an_spm_slip_in_the_card_is_still_named(self):
        app = _interview_submitted(_submitted(profile=SPM_HELD))
        doc = _doc(app, 'higher_results', {**CERT_278, 'results_kind_detected': 'spm'}, results_kind='stpm')
        self.assertEqual(student_higher_check(doc)['kind_status'], 'spm')

    def test_a_declared_students_upload_still_compares(self):
        app = _submitted(profile=STPM_196)
        doc = _doc(app, 'higher_results', CERT_196, results_kind='stpm')
        chk = student_higher_check(doc)
        # F1 Q4 (rule table 2026-11-13): PA B+ typed, B read by the AI is unsure (amber), not red.
        self.assertEqual((chk['kind_status'], chk['grades_status']), ('match', 'pending'))
        self.assertEqual([u['subject'] for u in chk['uncertain']], ['PENGJIAN AM'])   # as read


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class TestPoint3DocOnFile(TestCase):
    def _item(self, app):
        return ResolutionItem.objects.get(application=app, source='check2', code=DECLARE)

    def test_raised_with_the_document_already_on_file(self):
        app, _doc_ = _278()
        sync_check2_queries(app)
        self.assertEqual(self._item(app).params, {higher_owed.DOC_ON_FILE: True})
        self.assertEqual(self._item(app).status, 'open')        # the late ask, interview submitted

    def test_the_upload_arrives_after_the_ask(self):
        app = _submitted(profile=SPM_HELD)
        sync_check2_queries(app)
        self.assertEqual(self._item(app).params, {})
        _doc(app, 'higher_results', CERT_278, results_kind='')
        sync_check2_queries(_fresh(app))
        self.assertEqual(self._item(app).params, {higher_owed.DOC_ON_FILE: True})

    def test_every_other_ask_is_untouched(self):
        item = ResolutionItem(code='payslip_requested', params={'household_member': 'father'})
        higher_owed.refresh_params(None, item)
        self.assertEqual(item.params, {'household_member': 'father'})


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   DOC_GENUINENESS_CHECK_ENABLED=True, THIRD_ROUTE_OPEN=True)
class TestPoint5MovingUpAfterSubmitAndInterview(TestCase):
    """`_never_demote_held_results` guards DOWNWARD moves only: an SPM-only student may declare her
    higher results on the onboarding pages after submit, even after her interview was submitted."""

    STPM_SAVE = {'exam_type': 'stpm', 'results_exam_type': 'stpm', 'completed_qualifications': ['spm', 'stpm'],
                 'stpm_grades': {'PA': 'A-', 'BAHASA_MELAYU': 'A', 'SEJARAH': 'A-', 'GEOGRAFI': 'A'}}

    def test_up_to_stpm_then_the_ask_closes(self):
        app, _doc_ = _278()
        sync_check2_queries(app)
        r = authed_client(app.profile).put('/api/v1/profile/', self.STPM_SAVE, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        app = _fresh(app)
        self.assertEqual(results_route.held_kind(app), 'stpm')
        self.assertFalse(higher_owed.undeclared(app))
        sync_check2_queries(app)
        self.assertEqual(ResolutionItem.objects.get(application=app, code=DECLARE).status, 'resolved')
        f = _academic(app)
        self.assertIn('higher_results_kind_ok', _codes(f['evidence']))   # declared now: it can tick

    def test_up_to_a_third_route_kind(self):
        app = _interview_submitted(_submitted(profile=SPM_HELD))
        r = authed_client(app.profile).put('/api/v1/profile/', {
            'exam_type': 'matric', 'results_exam_type': 'matric', 'higher_cgpa': 3.5, 'higher_koko': 8,
            'completed_qualifications': ['spm', 'matric']}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(results_route.held_kind(_fresh(app)), 'matric')


class TestPoint6TypoTolerantNames(TestCase):
    def test_the_live_misreads_map(self):
        self.assertEqual(stpm_key('PENGJIAN AM'), 'PA')
        self.assertEqual(stpm_key('PENGJIAN PERNIAGAAN'), 'BUSINESS')
        self.assertEqual(stpm_key('PENGJIAN PERNIAGAN'), 'BUSINESS')    # two slips in a long name
        self.assertEqual(stpm_key('950 MATEMATIK (T)'), 'MATH_T')        # exact, unchanged

    def test_what_never_maps(self):
        self.assertIsNone(stpm_key('MATEMATIK'))          # one edit from both T and M: ambiguous
        self.assertIsNone(stpm_key('PENGAJIAN AM 1'))     # 343's per-paper rows: a digit is not a typo
        self.assertIsNone(stpm_key('IC'))                 # too short for any slip
        self.assertIsNone(stpm_key('PENGJIAN AN'))        # two slips in a 10-letter name
        self.assertIsNone(stpm_key('PENGJIAN AM', taken={'PA'}))   # PA already printed exactly

    def test_never_onto_a_subject_printed_exactly_on_the_same_page(self):
        f = {'results_kind_detected': 'stpm', 'results': _rows(('PENGAJIAN AM', 'A'), ('PENGJIAN AM', 'B'))}
        self.assertEqual([k for _n, k, _g in stpm_keyed_rows(f)], ['PA', None])

    def test_no_near_match_on_a_page_not_read_as_stpm(self):
        f = {'results_kind_detected': 'matric', 'results': _rows(('PENGJIAN AM', 'A'))}
        self.assertEqual([k for _n, k, _g in stpm_keyed_rows(f)], [None])


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class TestPoint6OnTheCard(TestCase):
    def test_196_the_hidden_pa_mismatch_now_shows(self):
        app = _submitted(profile=STPM_196)
        _doc(app, 'higher_results', CERT_196, results_kind='stpm')
        f = _academic(app)
        # F1 Q4 (rule table 2026-11-13): a +/- difference on an AI read shows as unsure, not red.
        pa = [i for i in f['unresolved'] if i['code'] == 'higher_results_grade_uncertain']
        self.assertEqual([(i['params']['typed'], i['params']['slip']) for i in pa], [('B+', 'B')])
        self.assertNotIn('higher_results_grade_mismatch', _codes(f['unresolved']))

    def test_279_the_set_can_tick(self):
        app = _submitted(profile=STPM_279)
        _doc(app, 'higher_results', CERT_196, results_kind='stpm')
        app = _fresh(app)
        self.assertEqual(stpm_marks(app)['all_subjects'], 'match')
        self.assertEqual(stpm_marks(app)['grades']['PA'], {'status': 'match', 'doc': 'B'})

    def test_an_unrecognised_row_is_named_and_blocks_the_tick(self):
        app = _submitted(profile=STPM_279)
        cert = {**CERT_196, 'results': CERT_196['results'] + _rows(('PENGAJIAN AM 1', 'A'))}
        _doc(app, 'higher_results', cert, results_kind='stpm')
        app = _fresh(app)
        f = _academic(app)
        item = next(i for i in f['unresolved'] if i['code'] == 'higher_results_subjects_unrecognised')
        self.assertEqual(item['params'], {'subjects': 'PENGAJIAN AM 1'})
        self.assertEqual(stpm_marks(app)['all_subjects'], 'pending')
        self.assertNotEqual(f['status'], 'verified')
        self.assertEqual(red_chips(app), 0)                        # amber, never red

    def test_not_named_on_a_page_not_read_as_stpm(self):
        app = _submitted(profile=STPM_279)
        cert = {**CERT_196, 'results_kind_detected': 'matric',
                'results': CERT_196['results'] + _rows(('MATHEMATICS 1', 'A'))}
        doc = _doc(app, 'higher_results', cert, results_kind='stpm')
        self.assertEqual(student_higher_check(doc)['unrecognised'], [])
