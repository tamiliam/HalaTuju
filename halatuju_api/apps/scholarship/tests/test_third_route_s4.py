"""Third results route S4 — reviewer requests by name (#37) and wrong slips in the SPM card (#43).

Roadmap: docs/plans/2026-10-25-third-results-route-roadmap.md §5 S4, §5a, §7a (D1, D9, D12, D13,
D13a, D15). Every S4 door in §4 is pinned here: the academic verdict + genuineness ladder, the help
coach, the reviewer request + the upload that resolves it, the reverse move, the team's backfill
note, and D1's read-time promotion of the legacy rows.

The fixtures are the SHAPES of live rows (2026-10-27), never their data: #153 (an STPM certificate,
"Lulus Penuh" bands, in the SPM card of a legacy SPM row with an STPM CGPA on file) and #77 (a
Matriculation OFFER letter in the SPM card, scored `not_results_slip` before C3).
"""
import io
import logging
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.courses import exam_questions as eq
from apps.courses.models import FieldTaxonomy, StpmCourse
from apps.scholarship import anomaly_engine, help_engine, results_route, wrong_slip
from apps.scholarship.academic_engine import student_slip_check
from apps.scholarship.management.commands import note_team_refiled_higher as backfill
from apps.scholarship.models import ApplicantDocument, ResolutionItem, ScholarshipApplication
from apps.scholarship.resolution import doc_match_verdict, resolve_doc_items_for_upload
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_student,
)
from apps.scholarship.verdict_engine import VERDICT_ENGINE_VERSION, build_verdict
from apps.scholarship.verdict_ladder import _academic_red_chips

SPM = {'bm': 'A+', 'eng': 'A', 'hist': 'A', 'math': 'A', 'phy': 'C+', 'chem': 'D', 'bio': 'C+',
       'addmath': 'D'}
DEGREE_ID = 'UH6481001'
#: #153's profile shape: recorded SPM (her last completed form), an STPM CGPA on file, and the
#: `completed_qualifications` list blank (every legacy row) — so `results_held` read SPM.
LEGACY_SPM_WITH_STPM = dict(exam_type='spm', results_exam_type='spm', grades=SPM, stpm_cgpa=3.92,
                            spm_prereq_grades=SPM)
STPM_HELD = dict(exam_type='stpm', results_exam_type='stpm', grades=SPM, stpm_cgpa=3.71,
                 stpm_grades={'PA': 'A', 'MATH_T': 'A-', 'PHYSICS': 'A-'},
                 completed_qualifications=['spm', 'stpm'])
SPM_HELD = dict(exam_type='spm', results_exam_type='spm', grades=SPM)
DEGREE = {'chosen_pathway': '', 'pathway_certainty': 'sure',
          'chosen_programme': {'course_id': DEGREE_ID, 'course_name': 'Ijazah Sarjana Muda X'}}
POLY = {'chosen_pathway': 'poly', 'pathway_certainty': 'sure',
        'chosen_programme': {'course_id': 'POLY-DIP-001', 'course_name': 'Diploma Kejuruteraan'}}
UNDECIDED = {'chosen_pathway': '', 'pathway_certainty': 'uncertain', 'chosen_programme': {}}
#: What a tertiary holder bound for a degree froze at her Step-4 Submit after S3a (D9 + D12): the
#: higher results required, her SPM slip optional. (The factory freezes AFTER stamping the submit,
#: so it would freeze the catalogue's plain "SPM slip required" instead.)
HIGHER_FROZEN = {'captured_at': '2026-10-26T12:00:00+08:00', 'questions': {},
                 'documents': {'ic': 'required', 'results_slip': 'optional', 'higher_results': 'required'}}

#: #153's document: an STPM certificate read by the SPM slip's Gemini schema, scored by C3.
STPM_CERT_READ = {
    'candidate_name': 'PRIYA', 'exam': 'MALAYSIA HIGHER SCHOOL CERTIFICATE 2025',
    'results': [{'subject': 'PENGAJIAN AM', 'grade': '', 'band': 'LULUS PENUH'},
                {'subject': 'MATEMATIK (T)', 'grade': '', 'band': 'LULUS PENUH'},
                {'subject': 'FIZIK', 'grade': '', 'band': 'LULUS PENUH'},
                {'subject': 'KIMIA', 'grade': '', 'band': 'LULUS PENUH'}]}
C3_GENUINE = {'status': 'genuine', 'doc_seen': 'stpm_certificate', 'probability': 1.0,
              'model_version': '1.9.0', 'reason': '16/16 stpm certificate signatures present'}
#: Before C3 an STPM slip was scored against the SPM lists only (live #131, 1.4.0).
PRE_C3_SPM_SCORE = {'status': 'suspect', 'doc_seen': 'results_slip', 'probability': 0.40,
                    'model_version': '1.4.0', 'reason': '6/16 results slip signatures present'}
#: C3 itself reading an STPM page as no result document (ruling 1A, live #256 shape).
C3_NOT_A_RESULT = {'status': 'not_certificate', 'doc_seen': 'certificate', 'probability': 0.09,
                   'model_version': '1.9.0', 'reason': '2/16 certificate signatures present'}
SPM_READ = {'candidate_name': 'PRIYA', 'exam': 'SIJIL PELAJARAN MALAYSIA TAHUN 2025',
            'results': [{'subject': 'BAHASA MELAYU', 'grade': 'A+'}]}
#: #77's document: a Matriculation offer letter in the SPM card (no result rows).
MATRIC_OFFER_READ = {'candidate_name': 'PRIYA',
                     'exam': 'PROGRAM MATRIKULASI KEMENTERIAN PENDIDIKAN SESI 2026/2027'}


def _degree_course():
    FieldTaxonomy.objects.get_or_create(key='s4-test', defaults={
        'name_en': 'X', 'name_ms': 'X', 'name_ta': 'X', 'image_slug': 'x'})
    StpmCourse.objects.get_or_create(course_id=DEGREE_ID, defaults={
        'course_name': 'Ijazah Sarjana Muda X', 'university': 'Universiti Malaya',
        'field_key_id': 's4-test'})


def _app(profile_fields, plan, stage='shortlisted', **kw):
    _degree_course()
    student = make_student(name='Priya', nric='030101-14-1234', **profile_fields)
    return make_application(stage, student=student, **plan, **kw)


def _doc(app, doc_type, fields=None, verdict='ok', authenticity=None, **kw):
    vf = {'fields': fields, 'student_verdict': verdict, 'error': ''} if fields is not None else {}
    if authenticity is not None:
        vf['authenticity'] = authenticity
    return ApplicantDocument.objects.create(application=app, doc_type=doc_type,
                                            storage_path=f'test/{doc_type}/{len(str(fields))}',
                                            vision_fields=vf, **kw)


def _fresh(app):
    return ScholarshipApplication.objects.get(pk=app.pk)


def _academic(app):
    return next(f for f in build_verdict(_fresh(app)) if f['fact'] == 'academic')


def _codes(items):
    return [i['code'] for i in items]


# ── #43: what the SPM card's document IS ─────────────────────────────────────────────────────


class TestTheHigherKind(TestCase):
    def test_153_shape_reads_as_stpm(self):
        app = _app(SPM_HELD, POLY)
        self.assertEqual(wrong_slip.higher_kind(_doc(app, 'results_slip', STPM_CERT_READ)), 'stpm')

    def test_c3_alone_is_a_witness(self):
        """No marker in the read's title (Gemini dropped it) — C3's STPM family still says STPM."""
        app = _app(SPM_HELD, POLY)
        doc = _doc(app, 'results_slip', {**STPM_CERT_READ, 'exam': ''}, authenticity=C3_GENUINE)
        self.assertEqual(wrong_slip.higher_kind(doc), 'stpm')

    def test_an_spm_slip_unread_slip_and_other_slot_say_nothing(self):
        app = _app(SPM_HELD, POLY)
        self.assertEqual(wrong_slip.higher_kind(_doc(app, 'results_slip', SPM_READ)), '')
        self.assertEqual(wrong_slip.higher_kind(_doc(app, 'results_slip', STPM_CERT_READ,
                                                     verdict='review_manually')), '')
        self.assertEqual(wrong_slip.higher_kind(_doc(app, 'semester_result', STPM_CERT_READ)), '')
        self.assertEqual(wrong_slip.higher_kind(None), '')

    def test_77_shape_a_matriculation_offer_is_not_matriculation_results(self):
        """No result rows and no CGPA: it stays the wrong document it is (its own genuineness)."""
        app = _app(SPM_HELD, POLY)
        doc = _doc(app, 'results_slip', MATRIC_OFFER_READ,
                   authenticity={'status': 'not_results_slip', 'doc_seen': 'results_slip',
                                 'model_version': '1.6.0'})
        self.assertEqual(wrong_slip.higher_kind(doc), '')
        self.assertFalse(wrong_slip.spm_genuineness_skipped(doc))

    def test_a_c3_checker_page_with_no_marker_is_not_read_as_stpm(self):
        app = _app(SPM_HELD, POLY)
        doc = _doc(app, 'results_slip', {'candidate_name': 'PRIYA', 'results': [{'subject': 'X'}]},
                   authenticity={**C3_NOT_A_RESULT, 'doc_seen': 'stpm_slip', 'status': 'not_results_slip'})
        self.assertEqual(wrong_slip.higher_kind(doc), '')


class TestTheStudentNeverComparesAWrongSlip(TestCase):
    """#153's shape: no missing subjects, no grade mismatch, 'Lulus Penuh' never an E."""

    def test_no_spm_comparison_and_no_grade_advice(self):
        app = _app(SPM_HELD, POLY)
        doc = _doc(app, 'results_slip', STPM_CERT_READ)
        chk = student_slip_check(doc)
        self.assertEqual((chk['subjects'], chk['results']), ('not_spm', 'not_spm'))
        self.assertEqual((chk['missing'], chk['mismatched'], chk['uncertain']), ([], [], []))
        self.assertEqual(chk['higher_kind'], 'stpm')
        self.assertEqual(chk['exam_year'], '')                     # never an "SPM 2025"
        self.assertEqual(help_engine.verdict_for_document(doc), '')   # never "change your grades"
        self.assertEqual(doc_match_verdict(doc), 'ok')               # kept, never held or red

    def test_the_name_is_still_checked(self):
        app = _app(SPM_HELD, POLY)
        doc = _doc(app, 'results_slip', STPM_CERT_READ, verdict='name_mismatch')
        self.assertEqual(student_slip_check(doc)['name'], 'mismatch')
        self.assertEqual(help_engine.verdict_for_document(doc), 'slip_name_mismatch')

    def test_a_real_spm_slip_is_compared_as_before(self):
        app = _app(SPM_HELD, POLY)
        chk = student_slip_check(_doc(app, 'results_slip', {**SPM_READ, 'results': [
            {'subject': 'BAHASA MELAYU', 'grade': 'A+'}, {'subject': 'SEJARAH', 'grade': 'B'}]}))
        self.assertNotIn('higher_kind', chk)
        self.assertEqual(chk['results'], 'mismatch')                 # typed A, slip B


class TestTheReviewerSeesWhatItIs(TestCase):
    def test_the_engine_version_moved(self):
        self.assertGreaterEqual(VERDICT_ENGINE_VERSION, '2026-10-27.1')   # .2: #388 (higher_owed)

    def test_153_shape_shows_no_false_chips(self):
        app = _app(SPM_HELD, POLY)
        _doc(app, 'results_slip', STPM_CERT_READ)
        f = _academic(app)
        codes = _codes(f['unresolved'])
        self.assertIn('results_slip_is_higher', codes)
        for false_chip in ('academic_missing_subjects', 'academic_grade_mismatch',
                           'academic_grade_band_mismatch', 'academic_grade_uncertain', 'grades_unverified'):
            self.assertNotIn(false_chip, codes)
        item = next(i for i in f['unresolved'] if i['code'] == 'results_slip_is_higher')
        self.assertEqual(item['params'], {'kind': 'STPM'})
        self.assertEqual(f['status'], 'review')
        self.assertNotIn("'E'", repr(f))                             # Lulus Penuh never read as E
        self.assertEqual(_academic_red_chips(_fresh(app)), 0)

    def test_a_wrong_person_stpm_slip_still_reds_the_name(self):
        app = _app(SPM_HELD, POLY)
        _doc(app, 'results_slip', STPM_CERT_READ, verdict='name_mismatch')
        self.assertEqual(_academic_red_chips(_fresh(app)), 1)
        self.assertIn('results_slip_name_mismatch', _codes(_academic(app)['unresolved']))

    @override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
    def test_a_pre_c3_spm_list_score_is_no_signal(self):
        """Scored against the SPM lists alone (1.4.0): not a measurement of an STPM slip → no step,
        no "may not be genuine" caveat, no anomaly — the card is Probable on the base band."""
        app = _app(SPM_HELD, POLY)
        doc = _doc(app, 'results_slip', STPM_CERT_READ, authenticity=PRE_C3_SPM_SCORE)
        self.assertTrue(wrong_slip.spm_genuineness_skipped(doc))
        f = _academic(app)
        self.assertNotIn('document_not_genuine', _codes(f['unresolved']))
        self.assertEqual(f['status'], 'review')
        self.assertIsNone(anomaly_engine._detect_document_not_genuine(_fresh(app)))

    @override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
    def test_c3s_own_verdict_stands_whatever_it_says(self):
        """C3 (1.9.0) chose the family itself: its not_<type> (ruling 1A) is never contradicted."""
        app = _app(SPM_HELD, POLY)
        doc = _doc(app, 'results_slip', {**STPM_CERT_READ, 'exam': 'TAHUN STPM 2025'},
                   authenticity=C3_NOT_A_RESULT)
        self.assertEqual(wrong_slip.higher_kind(doc), 'stpm')
        self.assertFalse(wrong_slip.spm_genuineness_skipped(doc))
        f = _academic(app)
        self.assertIn('document_not_genuine', _codes(f['unresolved']))
        self.assertEqual(f['status'], 'recommend')                  # C3's step 2 (not_<type>): Unsure
        self.assertIsNotNone(anomaly_engine._detect_document_not_genuine(_fresh(app)))

    @override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
    def test_c3_genuine_keeps_the_card_where_c3_put_it(self):
        app = _app(SPM_HELD, POLY)
        _doc(app, 'results_slip', STPM_CERT_READ, authenticity=C3_GENUINE)
        f = _academic(app)
        self.assertNotIn('document_not_genuine', _codes(f['unresolved']))
        self.assertEqual(f['status'], 'review')

    def test_an_spm_slip_is_untouched(self):
        app = _app(SPM_HELD, POLY)
        _doc(app, 'results_slip', {**SPM_READ, 'results': [{'subject': 'BAHASA MELAYU', 'grade': 'A+'}]})
        self.assertNotIn('results_slip_is_higher', _codes(_academic(app)['unresolved']))


# ── D15: "Move it to STPM results" ───────────────────────────────────────────────────────────


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestMoveItToStpmResults(TestCase):
    URL = '/api/v1/scholarship/results/refile-to-higher/'

    def _post(self, app, doc):
        return authed_client(app.profile).post(self.URL, {'document_id': doc.id}, format='json')

    def test_offered_only_where_the_higher_card_is_shown_and_before_submit(self):
        degree = _app(STPM_HELD, DEGREE)
        self.assertTrue(student_slip_check(_doc(degree, 'results_slip', STPM_CERT_READ))['move_offered'])
        poly = _app(STPM_HELD, POLY)                         # D12: post-SPM → no higher card
        self.assertFalse(student_slip_check(_doc(poly, 'results_slip', STPM_CERT_READ))['move_offered'])
        done = _app(STPM_HELD, DEGREE, stage='profile_complete')
        chk = student_slip_check(_doc(done, 'results_slip', STPM_CERT_READ))
        self.assertFalse(chk['move_offered'])
        self.assertFalse(chk['actions_open'])

    def test_the_move_keeps_the_file_rereads_it_and_writes_the_note(self):
        app = _app(STPM_HELD, DEGREE)
        doc = _doc(app, 'results_slip', STPM_CERT_READ, authenticity=C3_GENUINE)
        path = doc.storage_path
        with self.assertLogs('apps.scholarship.results_route', logging.INFO) as logs:
            r = self._post(app, doc)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['results_kind'], 'stpm')
        doc.refresh_from_db()
        self.assertEqual((doc.doc_type, doc.results_kind, doc.storage_path), ('higher_results', 'stpm', path))
        self.assertEqual((doc.vision_fields, doc.vision_fields_run_at, doc.vision_run_at), ({}, None, None))
        from apps.scholarship.services.blockers import _stuck_unread_documents
        self.assertIn(doc.id, [d.id for d in _stuck_unread_documents(50)])   # the live sweep re-reads it
        self.assertIsNone(doc.superseded_at)
        self.assertIn('AUDIT results_refiled_to_higher', ' '.join(logs.output))
        app.refresh_from_db()
        note = app.results_change_notes[-1]
        self.assertEqual((note['kind'], note['document_id'], note['results_kind'], note['by']),
                         ('refiled_higher', doc.id, 'stpm', 'student'))
        self.assertFalse(note['submitted'])

    def test_one_live_higher_results_upload(self):
        app = _app(STPM_HELD, DEGREE)
        older = _doc(app, 'higher_results', {'candidate_name': 'PRIYA', 'results_kind_detected': 'stpm',
                                             'cgpa': '3.78'}, results_kind='stpm')
        doc = _doc(app, 'results_slip', STPM_CERT_READ)
        results_route.refile_to_higher(_fresh(app), doc, 'stpm')
        live = ApplicantDocument.objects.filter(application=app, doc_type='higher_results',
                                                superseded_at__isnull=True)
        self.assertEqual(live.count(), 1)
        older.refresh_from_db()
        self.assertTrue(older.superseded_at is not None or live.first().id == older.id)

    def test_a_different_kind_then_gets_the_s3_note(self):
        app = _app(STPM_HELD, DEGREE)
        doc = _doc(app, 'results_slip', {**STPM_CERT_READ, 'exam': 'KEPUTUSAN PROGRAM MATRIKULASI',
                                         'cgpa': '3.50'})
        self.assertEqual(wrong_slip.higher_kind(doc), 'matric')
        self.assertEqual(self._post(app, doc).status_code, 200)
        doc.refresh_from_db()
        self.assertEqual(doc.results_kind, 'matric')
        doc.vision_fields = {'student_verdict': 'ok', 'fields': {      # the live re-read, simulated
            'candidate_name': 'PRIYA', 'cgpa': '3.50', 'results_kind_detected': 'matric'}}
        doc.save(update_fields=['vision_fields'])
        from apps.scholarship.higher_results import student_higher_check
        self.assertEqual(student_higher_check(ApplicantDocument.objects.get(pk=doc.pk))['note'], 'kind_differs')

    def test_refused_after_submit(self):
        for stage in ('profile_complete', 'interviewing', 'awarded'):
            with self.subTest(stage=stage):
                app = _app(STPM_HELD, DEGREE, stage=stage)
                doc = _doc(app, 'results_slip', STPM_CERT_READ)
                r = self._post(app, doc)
                self.assertEqual((r.status_code, r.json()['code']), (409, 'application_submitted'))
                doc.refresh_from_db()
                self.assertEqual(doc.doc_type, 'results_slip')
                self.assertEqual(doc.vision_fields['fields']['exam'], STPM_CERT_READ['exam'])
                self.assertEqual(_fresh(app).results_change_notes or [], [])

    def test_refused_for_an_spm_slip_and_where_no_higher_card_is_shown(self):
        app = _app(STPM_HELD, DEGREE)
        spm = _doc(app, 'results_slip', SPM_READ)
        self.assertEqual(self._post(app, spm).json()['code'], 'not_a_higher_result')
        poly = _app(STPM_HELD, POLY)
        doc = _doc(poly, 'results_slip', STPM_CERT_READ)
        r = self._post(poly, doc)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'higher_card_not_shown'))
        doc.refresh_from_db()
        self.assertEqual(doc.doc_type, 'results_slip')


class TestTheTeamsMoveBackfill(TestCase):
    """The command for the six documents the team moved on 2026-10-26 (D15)."""

    def _six(self):
        out = []
        for app_id, doc_id in backfill.MOVED:
            app = _app(STPM_HELD, DEGREE, id=app_id)
            ApplicantDocument.objects.create(pk=doc_id, application=app, doc_type='higher_results',
                                             results_kind='stpm', storage_path=f'test/{doc_id}')
            out.append(app)
        return out

    def _run(self, *args):
        buf = io.StringIO()
        call_command('note_team_refiled_higher', *args, stdout=buf)
        return buf.getvalue()

    def test_report_only_by_default(self):
        apps = self._six()
        out = self._run()
        self.assertIn('REPORT ONLY', out)
        self.assertEqual(out.count(': write'), 6)
        self.assertTrue(all(not _fresh(a).results_change_notes for a in apps))

    def test_apply_writes_the_team_note_once(self):
        apps = self._six()
        self._run('--apply')
        out = self._run('--apply')                                      # idempotent
        self.assertIn('0 note(s) written', out)
        self.assertEqual(out.count('already_noted'), 6)
        for app in apps:
            notes = _fresh(app).results_change_notes
            self.assertEqual(len(notes), 1)
            self.assertEqual((notes[0]['kind'], notes[0]['by'], notes[0]['results_kind']),
                             ('refiled_higher', 'team', 'stpm'))
            self.assertTrue(notes[0]['at'].startswith('2026-10-26'))

    def test_a_document_no_longer_live_is_skipped(self):
        apps = self._six()
        ApplicantDocument.objects.filter(application=apps[0]).update(doc_type='results_slip')
        out = self._run('--apply')
        self.assertIn('skip:', out)
        self.assertFalse(_fresh(apps[0]).results_change_notes)


# ── #37: the reviewer asks for results BY NAME ───────────────────────────────────────────────


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestRequestsByName(TestCase):
    def setUp(self):
        self.admin = make_admin(super_admin=True)

    def _request(self, app, **body):
        return authed_client(self.admin).post(
            f'/api/v1/admin/scholarship/applications/{app.id}/resolution-items/',
            {'kind': 'doc', 'prompt': 'Please upload it.', 'fact': 'academic', **body}, format='json')

    def _upload(self, app, item, fields):
        def _extract(a, doc, *args, **kw):
            doc.vision_fields = {'fields': fields, 'student_verdict': 'ok', 'error': ''}
            doc.save(update_fields=['vision_fields'])
        with patch('apps.scholarship.vision.ocr_document_full', return_value={'text': '', 'error': None}), \
             patch('apps.scholarship.vision.run_vision_match_for_document', return_value=None), \
             patch('apps.scholarship.views.DocumentListCreateView._maybe_extract_fields',
                   side_effect=_extract):
            return authed_client(app.profile).post('/api/v1/scholarship/documents/', {
                'doc_type': item.doc_type, 'request_code': item.code,
                'storage_path': f'{app.id}/{item.doc_type}/{item.code}', 'original_filename': 'r.pdf',
                'size': 1000}, format='json')

    def test_a_matriculation_request_lands_in_higher_results_and_closes(self):
        app = _app(SPM_HELD, POLY, stage='profile_complete')
        r = self._request(app, doc_type='higher_results', results_kind='matric')
        self.assertEqual(r.status_code, 200, r.content)
        item = ResolutionItem.objects.get(application=app, source='officer')
        self.assertEqual((item.doc_type, item.params.get('results_kind')), ('higher_results', 'matric'))
        self.assertEqual(results_route.upload_kind(_fresh(app), item.code), 'matric')
        up = self._upload(app, item, {'candidate_name': 'PRIYA', 'cgpa': '3.50',
                                      'results_kind_detected': 'matric'})
        self.assertEqual(up.status_code, 201, up.content)
        doc = ApplicantDocument.objects.get(pk=up.json()['id'])
        self.assertEqual((doc.doc_type, doc.results_kind, doc.request_code),
                         ('higher_results', 'matric', item.code))
        item.refresh_from_db()
        self.assertEqual(item.status, 'resolved')

    def test_the_kind_defaults_to_the_one_on_file(self):
        app = _app(STPM_HELD, DEGREE, stage='profile_complete', requirements_snapshot=HIGHER_FROZEN)
        self._request(app, doc_type='higher_results')
        self.assertEqual(ResolutionItem.objects.get(application=app, source='officer')
                         .params.get('results_kind'), 'stpm')

    def test_no_kind_anywhere_is_refused(self):
        app = _app(SPM_HELD, POLY, stage='profile_complete')
        r = self._request(app, doc_type='higher_results')
        self.assertEqual((r.status_code, r.json()['error']), (400, 'results_kind_required'))
        self.assertFalse(ResolutionItem.objects.filter(application=app, source='officer').exists())
        r = self._request(app, doc_type='higher_results', results_kind='phd')
        self.assertEqual(r.status_code, 400)

    def test_an_spm_request_after_a_higher_only_submission_works(self):
        app = _app(STPM_HELD, DEGREE, stage='profile_complete', requirements_snapshot=HIGHER_FROZEN)
        _doc(app, 'higher_results', {'candidate_name': 'PRIYA', 'cgpa': '3.78',
                                     'results_kind_detected': 'stpm'}, results_kind='stpm')
        self.assertEqual(self._request(app, doc_type='results_slip').status_code, 200)
        item = ResolutionItem.objects.get(application=app, source='officer')
        up = self._upload(app, item, SPM_READ)
        self.assertEqual(up.status_code, 201, up.content)
        item.refresh_from_db()
        self.assertEqual(item.status, 'resolved')
        doc = ApplicantDocument.objects.get(pk=up.json()['id'])
        self.assertEqual((doc.doc_type, doc.superseded_at), ('results_slip', None))

    def test_an_stpm_result_does_not_answer_an_spm_request(self):
        app = _app(STPM_HELD, DEGREE, stage='profile_complete', requirements_snapshot=HIGHER_FROZEN)
        self._request(app, doc_type='results_slip')
        item = ResolutionItem.objects.get(application=app, source='officer')
        self.assertEqual(self._upload(app, item, STPM_CERT_READ).status_code, 201)
        item.refresh_from_db()
        self.assertEqual(item.status, 'open')                          # kept; the request stands

    def test_an_spm_slip_does_not_answer_a_higher_request(self):
        app = _app(STPM_HELD, DEGREE, stage='profile_complete', requirements_snapshot=HIGHER_FROZEN)
        self._request(app, doc_type='higher_results', results_kind='stpm')
        item = ResolutionItem.objects.get(application=app, source='officer')
        self._upload(app, item, {'candidate_name': 'PRIYA', 'exam': 'SIJIL PELAJARAN MALAYSIA',
                                 'results_kind_detected': 'spm'})
        item.refresh_from_db()
        self.assertEqual(item.status, 'open')

    def test_requests_only_while_open_request_40(self):
        app = _app(STPM_HELD, DEGREE)                                  # still at the Documents step
        r = self._request(app, doc_type='higher_results', results_kind='stpm')
        self.assertEqual((r.status_code, r.json()['error']), (400, 'querying_closed'))

    def test_no_automatic_spm_ask_d9(self):
        """A tertiary applicant with no SPM slip: the system raises no SPM request by itself."""
        from apps.scholarship.resolution import sync_resolution_items
        app = _app(STPM_HELD, DEGREE, stage='profile_complete', requirements_snapshot=HIGHER_FROZEN)
        _doc(app, 'higher_results', {'candidate_name': 'PRIYA', 'cgpa': '3.78',
                                     'results_kind_detected': 'stpm'}, results_kind='stpm')
        sync_resolution_items(_fresh(app))
        self.assertEqual(list(ResolutionItem.objects.filter(application=app, doc_type='results_slip')
                              .values_list('code', 'source')), [])

    def test_a_system_item_is_answered_as_before(self):
        app = _app(SPM_HELD, POLY, stage='profile_complete')
        item = ResolutionItem.objects.create(application=app, source='system', code='results_slip_missing',
                                             fact='academic', kind='doc', doc_type='results_slip')
        doc = _doc(app, 'results_slip', SPM_READ)
        self.assertEqual(resolve_doc_items_for_upload(_fresh(app), doc), 'ok')
        item.refresh_from_db()
        self.assertEqual(item.status, 'resolved')


# ── D1: the legacy rows, promoted at READ time only on a recognised STPM document ────────────


class TestD1Promotion(TestCase):
    def test_promoted_only_with_a_recognised_stpm_document(self):
        app = _app(LEGACY_SPM_WITH_STPM, UNDECIDED)
        self.assertEqual(eq.results_held(_fresh(app).profile), 'spm')          # data alone: never (#15)
        _doc(app, 'results_slip', SPM_READ)
        self.assertEqual(eq.results_held(_fresh(app).profile), 'spm')          # an SPM slip: no
        _doc(app, 'results_slip', STPM_CERT_READ)
        profile = _fresh(app).profile
        self.assertEqual(eq.results_held(profile), 'stpm')
        self.assertEqual(eq.merit_100(profile), 98.0)                          # 3.92 / 4 x 100
        # read time only: nothing written to the profile
        profile.refresh_from_db()
        self.assertEqual((profile.results_exam_type, profile.completed_qualifications), ('spm', []))

    def test_a_higher_results_upload_read_as_stpm_results_is_a_witness(self):
        app = _app(LEGACY_SPM_WITH_STPM, UNDECIDED)
        _doc(app, 'higher_results', {'candidate_name': 'PRIYA', 'cgpa': '3.92',
                                     'results_kind_detected': 'stpm'})
        self.assertEqual(eq.results_held(_fresh(app).profile), 'stpm')

    def test_the_move_does_not_drop_her_to_spm_while_the_sweep_rereads(self):
        app = _app(LEGACY_SPM_WITH_STPM, UNDECIDED)
        doc = _doc(app, 'results_slip', STPM_CERT_READ, authenticity=C3_GENUINE)
        results_route.refile_to_higher(_fresh(app), doc, 'stpm')          # read cleared
        self.assertEqual(eq.results_held(_fresh(app).profile), 'stpm')
        doc.refresh_from_db()
        doc.vision_fields = {'student_verdict': 'ok', 'fields': {'results_kind_detected': 'spm'}}
        doc.save(update_fields=['vision_fields'])                           # re-read: an SPM slip after all
        self.assertEqual(eq.results_held(_fresh(app).profile), 'spm')

    def test_a_superseded_document_is_not_a_witness(self):
        from django.utils import timezone
        app = _app(LEGACY_SPM_WITH_STPM, UNDECIDED)
        _doc(app, 'results_slip', STPM_CERT_READ, superseded_at=timezone.now())
        self.assertEqual(eq.results_held(_fresh(app).profile), 'spm')

    def test_no_stpm_data_or_a_non_legacy_row_is_never_promoted(self):
        no_data = _app(SPM_HELD, UNDECIDED)
        _doc(no_data, 'results_slip', STPM_CERT_READ)
        self.assertEqual(eq.results_held(_fresh(no_data).profile), 'spm')
        recorded = _app({**LEGACY_SPM_WITH_STPM, 'completed_qualifications': ['spm']}, UNDECIDED)
        _doc(recorded, 'results_slip', STPM_CERT_READ)
        self.assertEqual(eq.results_held(_fresh(recorded).profile), 'spm')     # an S2b completion stands

    def test_without_the_scholarship_witness_the_rule_is_unchanged(self):
        app = _app(LEGACY_SPM_WITH_STPM, UNDECIDED)
        _doc(app, 'results_slip', STPM_CERT_READ)
        with patch.object(eq, 'STPM_DOCUMENT_WITNESS', None):
            self.assertEqual(eq.results_held(_fresh(app).profile), 'spm')

    def test_153_end_to_end_the_higher_card_asks_and_the_move_is_offered(self):
        app = _app(LEGACY_SPM_WITH_STPM, UNDECIDED)
        doc = _doc(app, 'results_slip', STPM_CERT_READ, authenticity=C3_GENUINE)
        from apps.scholarship import requirements
        states = requirements.resolve(_fresh(app), 'document')
        self.assertEqual(states.get('higher_results'), 'required')
        self.assertEqual(states.get('results_slip'), 'optional')                # D9
        self.assertTrue(student_slip_check(ApplicantDocument.objects.get(pk=doc.pk))['move_offered'])


# ── The adversarial review's findings (2026-10-27) ───────────────────────────────────────────


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestReviewFindings(TestCase):
    def test_1_a_requested_upload_read_in_our_outage_never_promotes(self):
        """Reviewer asks for STPM results; the student uploads anything; our read fails."""
        app = _app(LEGACY_SPM_WITH_STPM, UNDECIDED, stage='profile_complete')
        item = ResolutionItem.objects.create(application=app, source='officer', code='officer_1',
                                             kind='doc', doc_type='higher_results', fact='academic',
                                             params={'results_kind': 'stpm'})
        _doc(app, 'higher_results', {}, verdict='review_manually', results_kind='stpm',
             request_code=item.code)
        self.assertEqual(eq.results_held(_fresh(app).profile), 'spm')

    def test_1_a_fresh_unread_upload_never_promotes(self):
        app = _app(LEGACY_SPM_WITH_STPM, UNDECIDED)
        ApplicantDocument.objects.create(application=app, doc_type='higher_results', results_kind='stpm',
                                         storage_path='test/fresh')
        self.assertEqual(eq.results_held(_fresh(app).profile), 'spm')

    def test_2_a_higher_result_never_buries_a_live_spm_slip(self):
        from apps.scholarship import promotion
        app = _app(SPM_HELD, POLY)
        spm = _doc(app, 'results_slip', SPM_READ, authenticity={'status': 'suspect', 'model_version': '1.9.0'})
        stpm = _doc(app, 'results_slip', STPM_CERT_READ, authenticity=C3_GENUINE)
        self.assertEqual(promotion.doc_quality(stpm)[0], 0)              # never a usable SPM slip
        self.assertFalse(promotion.should_promote(stpm, spm, usable=wrong_slip.fills_spm_slot(stpm)))
        self.assertTrue(promotion.should_promote(spm, stpm, usable=True))   # the reverse does

    def test_2_the_upload_keeps_the_live_spm_slip(self):
        app = _app(SPM_HELD, POLY)
        spm = _doc(app, 'results_slip', SPM_READ, authenticity={'status': 'suspect', 'model_version': '1.9.0'})

        def _extract(a, doc, *args, **kw):
            doc.vision_fields = {'fields': STPM_CERT_READ, 'student_verdict': 'ok', 'error': '',
                                 'authenticity': C3_GENUINE}
            doc.save(update_fields=['vision_fields'])
        with patch('apps.scholarship.vision.ocr_document_full', return_value={'text': '', 'error': None}), \
             patch('apps.scholarship.vision.run_vision_match_for_document', return_value=None), \
             patch('apps.scholarship.views.DocumentListCreateView._maybe_extract_fields', side_effect=_extract):
            r = authed_client(app.profile).post('/api/v1/scholarship/documents/', {
                'doc_type': 'results_slip', 'storage_path': f'{app.id}/results_slip/stpm',
                'original_filename': 'stpm.pdf', 'size': 1000}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        spm.refresh_from_db()
        self.assertIsNone(spm.superseded_at)

    def test_2_a_higher_result_does_not_close_the_system_spm_ask(self):
        app = _app(SPM_HELD, POLY, stage='profile_complete')
        item = ResolutionItem.objects.create(application=app, source='system', code='results_slip_missing',
                                             fact='academic', kind='doc', doc_type='results_slip')
        doc = _doc(app, 'results_slip', STPM_CERT_READ)
        resolve_doc_items_for_upload(_fresh(app), doc)
        item.refresh_from_db()
        self.assertEqual(item.status, 'open')
        self.assertIn('results_slip_missing', _codes(_academic(app)['unresolved']))

    def test_2_but_never_asks_a_tertiary_holder_for_spm_d9(self):
        app = _app(STPM_HELD, DEGREE, stage='profile_complete', requirements_snapshot={
            'captured_at': '2026-10-01T00:00:00+00:00', 'questions': {},
            'documents': {'ic': 'required', 'results_slip': 'required'}})
        _doc(app, 'results_slip', STPM_CERT_READ)
        self.assertNotIn('results_slip_missing', _codes(_academic(app)['unresolved']))

    def test_3_trial_and_offer_titles_and_unread_tables_are_not_results(self):
        app = _app(LEGACY_SPM_WITH_STPM, UNDECIDED)
        for fields in ({**STPM_CERT_READ, 'exam': 'PEPERIKSAAN PERCUBAAN STPM 2025'},
                       {**STPM_CERT_READ, 'exam': 'STPM TRIAL EXAMINATION'},
                       {**STPM_CERT_READ, 'exam': 'SURAT TAWARAN PROGRAM MATRIKULASI'}):
            with self.subTest(exam=fields['exam']):
                doc = _doc(app, 'results_slip', fields, authenticity=C3_GENUINE)
                self.assertEqual(wrong_slip.higher_kind(doc), '')
                doc.delete()
        for fields in ({'candidate_name': 'PRIYA', 'results_kind_detected': 'stpm'},          # no rows / CGPA
                       {'exam': 'STPM TRIAL', 'cgpa': '3.5', 'results_kind_detected': 'stpm'}):
            with self.subTest(higher=str(fields)):
                doc = _doc(app, 'higher_results', fields, results_kind='stpm')
                self.assertEqual(eq.results_held(_fresh(app).profile), 'spm')
                doc.delete()
        _doc(app, 'higher_results', {'cgpa': '3.92', 'results_kind_detected': 'stpm'}, results_kind='stpm')
        self.assertEqual(eq.results_held(_fresh(app).profile), 'stpm')

    def test_4_a_promoted_row_may_still_save_its_results_fields(self):
        from apps.courses.serializers import ProfileUpdateSerializer
        app = _app(LEGACY_SPM_WITH_STPM, UNDECIDED)
        _doc(app, 'results_slip', STPM_CERT_READ)
        profile = _fresh(app).profile
        self.assertEqual(eq.results_held(profile), 'stpm')
        ser = ProfileUpdateSerializer(profile, data={'results_exam_type': 'spm', 'exam_type': 'spm'},
                                      partial=True)
        self.assertTrue(ser.is_valid(), ser.errors)
        # the same rule "after": still STPM held (data + document stand), so nothing is lowered and
        # the results fields are SAVED, not dropped as a demotion
        self.assertEqual(ser.validated_data.get('results_exam_type'), 'spm')
        ser.save()
        self.assertEqual(eq.results_held(_fresh(app).profile), 'stpm')

    def test_5_a_closed_request_carries_no_kind(self):
        app = _app(SPM_HELD, POLY, stage='profile_complete')
        ResolutionItem.objects.create(application=app, source='officer', code='officer_1', kind='doc',
                                      doc_type='higher_results', fact='academic', status='resolved',
                                      params={'results_kind': 'matric'})
        self.assertEqual(results_route.upload_kind(_fresh(app), 'officer_1'), '')

    def test_5_a_double_tap_moves_and_notes_once(self):
        app = _app(STPM_HELD, DEGREE)
        doc = _doc(app, 'results_slip', STPM_CERT_READ)
        stale = ApplicantDocument.objects.get(pk=doc.pk)          # the second tap's stale copy
        results_route.refile_to_higher(_fresh(app), doc, 'stpm')
        results_route.refile_to_higher(_fresh(app), stale, 'stpm')
        self.assertEqual([n['kind'] for n in _fresh(app).results_change_notes], ['refiled_higher'])

    def test_5_the_team_note_is_as_of_the_move(self):
        self.assertFalse(backfill._note_for(2680)['submitted'])
