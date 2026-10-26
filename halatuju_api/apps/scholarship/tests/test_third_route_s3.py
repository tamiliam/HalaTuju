"""Third results route S3a + S3b — the higher-results upload (2026-10-26; rulings D6 D9 D12 D13).

Roadmap: docs/plans/2026-10-25-third-results-route-roadmap.md §5 S3, §7a. Every door in §4 marked
S3 is pinned here: requirements resolve + the submit snapshot, completeness (both arms), consent
blockers, red / unreadable blockers, resolution tickets, promotion, upload → extraction →
detection, the Academic verdict + ladder, the help coach, and the two student actions.
"""
import logging
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.courses import exam_questions as eq
from apps.courses.models import FieldTaxonomy, StpmCourse, StudentProfile
from apps.courses.serializers import ProfileUpdateSerializer
from apps.scholarship import requirements, results_kind, results_route
from apps.scholarship.higher_results import (
    TICKETS, match_verdict, student_higher_check, verdict_academic,
)
from apps.scholarship.models import ApplicantDocument, Consent, FundingNeed, ScholarshipApplication
from apps.scholarship.services.completeness import application_completeness
from apps.scholarship.services.consent_blockers import consent_blockers
from apps.scholarship.services.blockers import document_red_blockers, document_unreadable_blockers
from apps.scholarship.services.offer_sync import revert_if_profile_incomplete
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_application, make_cohort, make_student, matched_str_pair,
)
from apps.scholarship.verdict_engine import VERDICT_ENGINE_VERSION, build_verdict

SPM = {f'sub{i}': 'A' for i in range(10)}
STPM = {'PA': 'A', 'MATH_T': 'A-', 'PHYSICS': 'A-'}           # academic CGPA (4+3.67+3.67)/3 = 3.78
DEGREE_ID = 'UH6481001'
SPM_COURSE_ID = 'UA4224001'

STPM_HELD = dict(exam_type='stpm', results_exam_type='stpm', grades=SPM, stpm_grades=STPM,
                 stpm_cgpa=3.71, completed_qualifications=['spm', 'stpm'])
DIPLOMA_HELD = dict(exam_type='diploma', results_exam_type='diploma', grades=SPM, higher_cgpa=3.2,
                    higher_institution_type='public', completed_qualifications=['spm', 'diploma'])
MATRIC_HELD = dict(exam_type='matric', results_exam_type='matric', grades=SPM, higher_cgpa=3.5,
                   higher_koko=8, completed_qualifications=['spm', 'matric'])
SPM_HELD = dict(exam_type='spm', results_exam_type='spm', grades=SPM)

DEGREE = {'chosen_pathway': '', 'pathway_certainty': 'sure',
          'chosen_programme': {'course_id': DEGREE_ID, 'course_name': 'Ijazah Sarjana Muda X'}}
MATRIC_PATHWAY = {'chosen_pathway': 'matric', 'pathway_certainty': 'sure', 'chosen_programme': {}}
# Review fix 4: 'matric' / 'stpm' on a TERTIARY holder is a stale autofill (undecided), so the
# "post-SPM pathway, higher results typed" acceptance case is a pathway she has NOT passed.
POLY_PATHWAY = {'chosen_pathway': 'poly', 'pathway_certainty': 'sure',
                'chosen_programme': {'course_id': 'POLY-DIP-001', 'course_name': 'Diploma Kejuruteraan'}}
UNDECIDED = {'chosen_pathway': '', 'pathway_certainty': 'uncertain', 'chosen_programme': {}}

STPM_READ = {'candidate_name': 'PRIYA', 'exam': 'SIJIL TINGGI PERSEKOLAHAN MALAYSIA 2025',
             'cgpa': '3.78', 'results_kind_detected': 'stpm',
             'results': [{'subject': 'PENGAJIAN AM', 'grade': 'A'},
                         {'subject': 'MATEMATIK (T)', 'grade': 'A-'},
                         {'subject': 'FIZIK', 'grade': 'A-'}]}


def _degree_course():
    FieldTaxonomy.objects.get_or_create(key='s3-test', defaults={
        'name_en': 'X', 'name_ms': 'X', 'name_ta': 'X', 'image_slug': 'x'})
    StpmCourse.objects.get_or_create(course_id=DEGREE_ID, defaults={
        'course_name': 'Ijazah Sarjana Muda X', 'university': 'Universiti Malaya',
        'field_key_id': 's3-test'})


def _app(profile_fields, plan, stage='shortlisted', **kw):
    _degree_course()
    student = make_student(name='Priya', nric='030101-14-1234', **profile_fields)
    return make_application(stage, student=student, **plan, **kw)


def _doc(app, doc_type, fields=None, verdict='ok', **kw):
    vf = {'fields': fields, 'student_verdict': verdict, 'error': ''} if fields is not None else {}
    return ApplicantDocument.objects.create(application=app, doc_type=doc_type,
                                            storage_path=f'test/{doc_type}', vision_fields=vf, **kw)


def _states(app):
    fresh = ScholarshipApplication.objects.get(pk=app.pk)
    return requirements.resolve(fresh, 'document')


# ── D12: which results upload is required follows the chosen course ──────────────────────────


class TestDestination(TestCase):
    def setUp(self):
        _degree_course()

    def _dest(self, **plan):
        return results_route.destination(ScholarshipApplication(**plan))

    def test_a_degree_from_the_stpm_catalogue_is_a_degree(self):
        self.assertEqual(self._dest(chosen_programme={'course_id': DEGREE_ID}), 'degree')

    def test_a_course_from_the_spm_catalogue_is_post_spm_whatever_the_code(self):
        self.assertEqual(self._dest(chosen_pathway='university',
                                    chosen_programme={'course_id': SPM_COURSE_ID}), 'post_spm')

    def test_the_programme_wins_over_a_stale_pathway_code(self):
        """Live: an STPM holder with chosen_pathway='stpm' (her Form Six letter's autofill) and a degree."""
        self.assertEqual(self._dest(chosen_pathway='stpm',
                                    chosen_programme={'course_id': DEGREE_ID}), 'degree')

    def test_every_post_spm_pathway_code_including_pismp(self):
        for code in ('matric', 'stpm', 'asasi', 'poly', 'kkom', 'pismp', 'iljtm', 'ilkbs', 'diploma'):
            with self.subTest(code=code):
                self.assertEqual(self._dest(chosen_pathway=code), 'post_spm')

    def test_degree_code_and_an_offer_named_degree(self):
        self.assertEqual(self._dest(chosen_pathway='degree'), 'degree')
        self.assertEqual(self._dest(chosen_programme={'course_name': 'Bachelor of Science'}), 'degree')

    def test_a_pismp_offer_by_name_is_post_spm(self):
        self.assertEqual(self._dest(chosen_programme={
            'course_name': 'Ijazah Sarjana Muda Perguruan dengan Kepujian'}), 'post_spm')

    def test_a_passed_pre_u_code_on_a_tertiary_holder_is_a_stale_autofill_fix_4(self):
        """Lead's ruling: live #196 / #147 — an STPM holder whose stored pathway is 'stpm' or 'matric'
        (her own Form Six / college letter's autofill) with no course is undecided, so the results
        held decide. An SPM holder's 'stpm' is still where she is going; a polytechnic is still post-SPM."""
        stpm = make_student(**STPM_HELD)
        for code in ('stpm', 'matric', 'asasi'):
            with self.subTest(code=code):
                self.assertEqual(results_route.destination(
                    ScholarshipApplication(profile=stpm, chosen_pathway=code)), '')
        self.assertEqual(results_route.destination(
            ScholarshipApplication(profile=make_student(**DIPLOMA_HELD), chosen_pathway='diploma')), '')
        self.assertEqual(results_route.destination(
            ScholarshipApplication(profile=stpm, chosen_pathway='poly')), 'post_spm')
        self.assertEqual(results_route.destination(
            ScholarshipApplication(profile=make_student(**SPM_HELD), chosen_pathway='stpm')), 'post_spm')

    def test_nothing_chosen_or_a_bare_university_code_is_undecided(self):
        self.assertEqual(self._dest(), '')
        self.assertEqual(self._dest(chosen_pathway='university'), '')
        self.assertEqual(self._dest(chosen_pathway='ipts'), '')


class TestTheRequirementRule(TestCase):
    def test_university_bound_stpm_higher_required_spm_optional(self):
        s = _states(_app(STPM_HELD, DEGREE))
        self.assertEqual((s['higher_results'], s['results_slip']), ('required', 'optional'))

    def test_post_spm_pathway_with_stpm_typed_only_the_spm_slip(self):
        s = _states(_app(STPM_HELD, POLY_PATHWAY))
        self.assertEqual(s['results_slip'], 'required')
        self.assertNotIn('higher_results', s)

    def test_undecided_diploma_holder_higher_required(self):
        s = _states(_app(DIPLOMA_HELD, UNDECIDED))
        self.assertEqual((s['higher_results'], s['results_slip']), ('required', 'optional'))

    def test_undecided_spm_holder_unchanged(self):
        s = _states(_app(SPM_HELD, UNDECIDED))
        self.assertEqual(s['results_slip'], 'required')
        self.assertNotIn('higher_results', s)

    def test_owner_ruling_spm_only_holder_bound_for_a_degree_needs_both(self):
        """Owner 2026-10-26: a degree needs post-SPM results — the higher card is REQUIRED before
        submit, and her SPM slip stays required too (the 7 live rows of this shape)."""
        s = _states(_app(SPM_HELD, DEGREE))
        self.assertEqual((s['results_slip'], s['higher_results']), ('required', 'required'))

    def test_the_ruling_leaves_a_submitted_one_alone(self):
        frozen = {'captured_at': '2026-10-01T00:00:00+00:00', 'questions': {},
                  'documents': {'ic': 'required', 'results_slip': 'required'}}
        s = _states(_app(SPM_HELD, DEGREE, stage='profile_complete', requirements_snapshot=frozen))
        self.assertNotIn('higher_results', s)

    def test_never_escalates_beyond_the_programme_fix_5(self):
        app = ScholarshipApplication.objects.get(pk=_app(STPM_HELD, DEGREE).pk)
        self.assertEqual(results_route.map_documents(app, {'results_slip': 'optional'}),
                         {'results_slip': 'optional', 'higher_results': 'optional'})
        for state in ('off', 'unknown', None):
            with self.subTest(state=str(state)):
                resolved = {'results_slip': state} if state else {}
                self.assertEqual(results_route.map_documents(app, resolved), resolved)

    def test_a_tertiary_holder_with_a_stale_pre_u_code_is_asked_for_higher_results(self):
        s = _states(_app(STPM_HELD, {'chosen_pathway': 'stpm', 'pathway_certainty': 'sure',
                                     'chosen_programme': {}}))
        self.assertEqual((s['higher_results'], s['results_slip']), ('required', 'optional'))

    def test_the_freeze_stores_the_mapping(self):
        app = _app(STPM_HELD, DEGREE)
        snap = requirements.freeze(app, save=False)
        self.assertEqual(snap['documents']['higher_results'], 'required')

    def test_a_submitted_application_keeps_its_frozen_requirement(self):
        """A pre-S3a snapshot names no higher_results: SPM slip required, for ever."""
        frozen = {'captured_at': '2026-09-01T00:00:00+00:00', 'questions': {},
                  'documents': {'ic': 'required', 'results_slip': 'required'}}
        app = _app(STPM_HELD, DEGREE, stage='profile_complete', requirements_snapshot=frozen)
        s = _states(app)
        self.assertEqual(s['results_slip'], 'required')
        self.assertNotIn('higher_results', s)

    def test_payload_carries_the_answer(self):
        app = ScholarshipApplication.objects.get(pk=_app(STPM_HELD, DEGREE).pk)
        payload = requirements.payload_for(app, 'document')
        self.assertIn('higher_results', payload['required'])
        self.assertIn('results_slip', payload['optional'])


# ── The gates: completeness, consent, red / unreadable blockers, submit ──────────────────────


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheGates(TestCase):
    def _complete(self, app, results=('higher_results',)):
        FundingNeed.objects.create(application=app, categories=['living'], programme_months=36)
        for dt in ('ic', 'offer_letter'):
            _doc(app, dt)
        for dt in results:
            _doc(app, dt, STPM_READ if dt == 'higher_results' else None)
        matched_str_pair(app)
        Consent.objects.create(application=app, version='t', is_active=True)
        ScholarshipApplication.objects.filter(pk=app.id).update(
            income_route='str', income_earner='father', father_name='AROON',
            father_occupation='driver', mother_name='KOMATHI', mother_occupation='homemaker',
            siblings_in_school=1, siblings_in_tertiary=0)
        return ScholarshipApplication.objects.get(pk=app.pk)

    def _profile_extras(self, **f):
        return dict(school='SMK X', student_signals={'field_interest': {'it': 5}},
                    address='No. 1 Jalan ABC', postal_code='62100', city='Putrajaya',
                    household_income=2500, receives_str=True, **f)

    @patch('apps.scholarship.services.confirmation.send_profile_complete_admin_email')
    def test_acceptance_university_bound_stpm_submits_with_higher_results_and_no_spm_slip(self, _m):
        app = self._complete(_app(self._profile_extras(**STPM_HELD), DEGREE,
                                  aspirations='a', plans='p', daily_life='d', fears='f'))
        self.assertTrue(application_completeness(app)['documents_done'])
        self.assertNotIn('results_slip_missing', consent_blockers(app))
        self.assertNotIn('higher_results_missing', consent_blockers(app))
        r = authed_client(app.profile).post(f'/api/v1/scholarship/applications/{app.id}/confirm/')
        self.assertEqual(r.status_code, 200, r.content)
        app.refresh_from_db()
        self.assertEqual(app.requirements_snapshot['documents']['higher_results'], 'required')
        # …and once submitted under that frozen requirement, it is NOT un-submitted by the
        # grandfathered arm, which used to demand an SPM slip (the additive OR).
        self.assertTrue(application_completeness(app)['documents_done'])
        self.assertFalse(revert_if_profile_incomplete(app))

    def test_acceptance_post_spm_pathway_stpm_typed_cannot_submit_without_the_spm_slip(self):
        app = self._complete(_app(self._profile_extras(**STPM_HELD), POLY_PATHWAY), results=())
        self.assertIn('results_slip_missing', consent_blockers(app))
        self.assertNotIn('higher_results_missing', consent_blockers(app))
        self.assertFalse(application_completeness(app)['documents_done'])
        _doc(app, 'results_slip')
        self.assertTrue(application_completeness(app)['documents_done'])

    def test_a_degree_bound_stpm_applicant_without_higher_results_is_blocked(self):
        app = self._complete(_app(self._profile_extras(**STPM_HELD), DEGREE), results=())
        self.assertIn('higher_results_missing', consent_blockers(app))
        self.assertNotIn('results_slip_missing', consent_blockers(app))
        self.assertFalse(application_completeness(app)['documents_done'])

    def test_D9_an_optional_spm_slip_never_blocks(self):
        app = self._complete(_app(self._profile_extras(**STPM_HELD), DEGREE))
        _doc(app, 'results_slip', {'candidate_name': 'SOMEONE ELSE', 'results': []},
             verdict='name_mismatch')
        _doc(app, 'results_slip', {'candidate_name': ''}, verdict='unreadable')
        self.assertNotIn('results_slip_name_mismatch', document_red_blockers(app))
        self.assertNotIn('results_slip_unreadable', document_unreadable_blockers(app))
        self.assertTrue(application_completeness(app)['documents_done'])

    def test_higher_results_in_another_name_blocks_like_the_spm_slip(self):
        app = self._complete(_app(self._profile_extras(**STPM_HELD), DEGREE), results=())
        _doc(app, 'higher_results', {**STPM_READ, 'candidate_name': 'SOMEONE ELSE'},
             verdict='name_mismatch')
        self.assertIn('higher_results_name_mismatch', document_red_blockers(app))
        self.assertFalse(application_completeness(app)['documents_done'])

    def test_an_unreadable_higher_upload_blocks(self):
        app = self._complete(_app(self._profile_extras(**STPM_HELD), DEGREE), results=())
        _doc(app, 'higher_results', {}, verdict='unreadable')
        self.assertIn('higher_results_unreadable', document_unreadable_blockers(app))

    def test_an_spm_only_degree_bound_applicant_is_blocked_without_higher_results(self):
        app = self._complete(_app(self._profile_extras(**SPM_HELD), DEGREE), results=('results_slip',))
        self.assertIn('higher_results_missing', consent_blockers(app))
        self.assertFalse(application_completeness(app)['documents_done'])

    def test_an_spm_applicant_is_unchanged(self):
        app = self._complete(_app(self._profile_extras(**SPM_HELD), MATRIC_PATHWAY), results=())
        self.assertIn('results_slip_missing', consent_blockers(app))
        self.assertNotIn('higher_results', requirements.resolve(app, 'document'))

    def test_legacy_submitted_arm_still_needs_the_spm_slip_under_a_pre_s3a_snapshot(self):
        frozen = {'captured_at': '2026-09-01T00:00:00+00:00', 'questions': {},
                  'documents': {'ic': 'required', 'results_slip': 'required'}}
        app = self._complete(_app(self._profile_extras(**STPM_HELD), DEGREE, stage='profile_complete',
                                  requirements_snapshot=frozen))
        _doc(app, 'parent_ic')
        self.assertFalse(application_completeness(app)['documents_done'])   # unchanged: no slip


# ── S3b: detection, the student's check, the notes ─────────────────────────────────────────


class TestDetection(SimpleTestCase):
    def test_fixed_markers(self):
        self.assertEqual(results_kind.detect('MAJLIS PEPERIKSAAN MALAYSIA SIJIL TINGGI PERSEKOLAHAN '
                                             'MALAYSIA 2025 PNGK 3.67'), 'stpm')
        self.assertEqual(results_kind.detect('KEPUTUSAN PEPERIKSAAN PROGRAM MATRIKULASI PNGK 3.5'),
                         'matric')
        self.assertEqual(results_kind.detect('PUSAT ASASI SAINS CGPA 3.10'), 'asasi')
        self.assertEqual(results_kind.detect('DIPLOMA IN ACCOUNTANCY TRANSCRIPT CGPA 3.0'), 'diploma')
        self.assertEqual(results_kind.detect('SIJIL PELAJARAN MALAYSIA TAHUN 2025 BAHASA MELAYU A'),
                         'spm')

    def test_cannot_tell_is_never_a_disagreement(self):
        self.assertEqual(results_kind.detect(''), '')
        self.assertEqual(results_kind.detect('ASASI SAINS DIPLOMA PERAKAUNAN'), '')    # two ways
        self.assertEqual(results_kind.detect('DIPLOMASI ANTARABANGSA'), '')            # whole words
        self.assertEqual(results_kind.detect('SPM CGPA 3.0'), '')                       # SPM has no CGPA

    def test_a_muet_slip_is_not_stpm(self):
        self.assertEqual(results_kind.detect('MAJLIS PEPERIKSAAN MALAYSIA MUET BAND 4'), '')

    def test_fallback_reads_the_exam_title(self):
        self.assertEqual(results_kind.detect_from_fields(
            {'exam': 'Sijil Tinggi Persekolahan Malaysia'}), 'stpm')


class TestTheStudentCheck(TestCase):
    def test_a_clean_stpm_upload_has_no_note(self):
        app = _app(STPM_HELD, DEGREE)
        chk = student_higher_check(_doc(app, 'higher_results', STPM_READ))
        self.assertEqual((chk['name'], chk['kind_status'], chk['cgpa_status'], chk['grades_status']),
                         ('match', 'match', 'match', 'match'))
        self.assertEqual(chk['note'], '')
        self.assertEqual(chk['cgpa_entered'], 3.78)    # the slip's own (academic) scale

    def test_note_D_an_spm_slip_in_the_card(self):
        app = _app(STPM_HELD, DEGREE)
        chk = student_higher_check(_doc(app, 'higher_results', {
            'candidate_name': 'PRIYA', 'exam': 'SIJIL PELAJARAN MALAYSIA', 'results_kind_detected': 'spm'}))
        self.assertEqual((chk['note'], chk['note_kind']), ('spm_slip', 'stpm'))

    def test_note_B_another_higher_kind_links_to_its_page(self):
        app = _app(STPM_HELD, DEGREE)
        chk = student_higher_check(_doc(app, 'higher_results', {
            'candidate_name': 'PRIYA', 'cgpa': '3.5', 'results_kind_detected': 'matric'}))
        self.assertEqual((chk['note'], chk['note_path']), ('kind_differs', '/onboarding/higher-grades'))

    def test_note_C_grades_differ(self):
        app = _app(STPM_HELD, DEGREE)
        read = {**STPM_READ, 'results': [{'subject': 'PENGAJIAN AM', 'grade': 'B'},
                                         {'subject': 'KIMIA', 'grade': 'A'}]}
        chk = student_higher_check(_doc(app, 'higher_results', read))
        self.assertEqual(chk['note'], 'grades_differ')
        self.assertEqual(chk['missing'], ['KIMIA'])
        self.assertEqual(chk['mismatched'], [{'subject': 'PENGAJIAN AM', 'typed': 'A', 'slip': 'B'}])
        self.assertEqual(chk['note_path'], '/onboarding/stpm-grades')

    def test_note_C_a_third_route_cgpa_that_differs(self):
        app = _app(MATRIC_HELD, DEGREE)
        chk = student_higher_check(_doc(app, 'higher_results', {
            'candidate_name': 'PRIYA', 'cgpa': '3.10', 'cgpa_label': 'PNGK', 'results_kind_detected': 'matric'}))
        self.assertEqual((chk['cgpa_status'], chk['note']), ('mismatch', 'grades_differ'))

    def test_note_C_cgpa_tolerance_and_only_a_cumulative_figure_fix_7(self):
        app = _app(MATRIC_HELD, DEGREE)                      # entered 3.50
        near = student_higher_check(_doc(app, 'higher_results', {
            'candidate_name': 'PRIYA', 'cgpa': '3.54', 'cgpa_label': 'PNGK', 'results_kind_detected': 'matric'}))
        self.assertEqual((near['cgpa_status'], near['note']), ('match', ''))
        for label in ('', 'PNG', 'GPA SEMESTER 2'):
            with self.subTest(label=label):
                sem = student_higher_check(_doc(app, 'higher_results', {
                    'candidate_name': 'PRIYA', 'cgpa': '3.10', 'cgpa_label': label,
                    'results_kind_detected': 'matric'}))
                self.assertEqual((sem['cgpa_status'], sem['note']), ('pending', ''))

    def test_unread_says_nothing(self):
        app = _app(STPM_HELD, DEGREE)
        chk = student_higher_check(_doc(app, 'higher_results'))
        self.assertEqual((chk['readable'], chk['note'], chk['kind_status']), (None, '', ''))
        self.assertEqual(match_verdict(_doc(app, 'higher_results')), 'pending')

    def test_a_note_is_never_a_mismatch_so_the_upload_is_promoted(self):
        app = _app(STPM_HELD, DEGREE)
        doc = _doc(app, 'higher_results', {'candidate_name': 'PRIYA', 'results_kind_detected': 'spm'})
        self.assertEqual(match_verdict(doc), 'ok')

    def test_the_tickets(self):
        self.assertEqual(set(TICKETS), {'higher_results_missing', 'higher_results_unreadable',
                                        'higher_results_name_mismatch'})
        from apps.scholarship.resolution import CODE_TO_TICKET, STUDENT_DOC_REQUEST_CODES
        self.assertTrue(set(TICKETS) <= set(CODE_TO_TICKET))
        self.assertIn('higher_results_missing', STUDENT_DOC_REQUEST_CODES)
        self.assertNotIn('higher_results_name_mismatch', STUDENT_DOC_REQUEST_CODES)

    def test_the_help_coach_stays_quiet(self):
        from apps.scholarship.help_engine import verdict_for_document
        app = _app(STPM_HELD, DEGREE)
        self.assertEqual(verdict_for_document(_doc(app, 'higher_results', {
            'candidate_name': 'X', 'results_kind_detected': 'spm'}, verdict='name_mismatch')), '')


class TestTheUploadRead(TestCase):
    """Upload → extraction → detection: the kind detected from the OCR text is stored beside the
    Gemini read; the upload's own `results_kind` is the results held (D13)."""

    def test_extract_stores_the_detection(self):
        from apps.scholarship.higher_results import extract
        app = _app(STPM_HELD, DEGREE)
        doc = _doc(app, 'higher_results')
        ex = extract(doc, {'text': 'PROGRAM MATRIKULASI PNGK 3.50'}, lambda: None,
                     lambda text, dt, **kw: {'fields': {'candidate_name': 'PRIYA', 'cgpa': '3.50'},
                                             'warnings': [], 'error': ''})
        self.assertEqual(ex['fields']['results_kind_detected'], 'matric')
        self.assertEqual(ex['fields']['results_kind_markers'], ['matric'])

    def test_registered_with_the_reader(self):
        from apps.scholarship import vision
        from apps.scholarship.views import SUPPORTING_NAME_CHECK_TYPES
        self.assertIn('higher_results', vision.GEMINI_EXTRACT_DOC_TYPES)
        self.assertIn('higher_results', vision._FIELD_SCHEMAS)
        self.assertIn('higher_results', SUPPORTING_NAME_CHECK_TYPES)

    def test_the_upload_kind_is_the_results_held(self):
        self.assertEqual(results_route.upload_kind(_app(DIPLOMA_HELD, DEGREE)), 'diploma')
        self.assertEqual(results_route.upload_kind(_app(SPM_HELD, DEGREE)), '')


# ── S3b: the reviewer's Academic card ────────────────────────────────────────────────────────


class TestTheAcademicCard(TestCase):
    def _academic(self, app):
        return next(f for f in build_verdict(ScholarshipApplication.objects.get(pk=app.pk))
                    if f['fact'] == 'academic')

    def test_the_engine_version_moved(self):
        # S3 moved it to 2026-10-26.3; S4 (#43, the wrong-slip card) moved it on — pinned there.
        self.assertGreaterEqual(VERDICT_ENGINE_VERSION, '2026-10-26.3')

    def test_missing_is_a_gap_and_asks_for_higher_results(self):
        f = self._academic(_app(STPM_HELD, DEGREE))
        self.assertEqual(f['status'], 'gap')
        self.assertEqual([i['code'] for i in f['unresolved']], ['higher_results_missing'])

    def test_clean_higher_results_without_an_spm_slip(self):
        app = _app(STPM_HELD, DEGREE)
        _doc(app, 'higher_results', STPM_READ)
        f = self._academic(app)
        codes = {i['code'] for i in f['evidence']}
        self.assertIn('higher_results_not_checked', codes)
        self.assertIn('higher_results_cgpa_ok', codes)
        self.assertNotIn('results_slip_missing', {i['code'] for i in f['unresolved']})   # D9
        self.assertEqual(f['status'], 'verified')

    @override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
    def test_not_checked_holds_the_card_at_probable(self):
        app = _app(STPM_HELD, DEGREE)
        _doc(app, 'higher_results', STPM_READ)
        self.assertEqual(self._academic(app)['status'], 'review')

    def test_another_kind_is_reviewed_and_named(self):
        app = _app(STPM_HELD, DEGREE)
        _doc(app, 'higher_results', {'candidate_name': 'PRIYA', 'cgpa': '3.5',
                                     'results_kind_detected': 'matric'})
        f = self._academic(app)
        item = next(i for i in f['unresolved'] if i['code'] == 'higher_results_kind_differs')
        self.assertEqual(item['params'], {'held': 'STPM', 'seen': 'Matriculation'})
        self.assertNotEqual(f['status'], 'verified')

    def test_an_spm_slip_on_file_is_compared_too(self):
        app = _app(STPM_HELD, DEGREE)
        _doc(app, 'higher_results', STPM_READ)
        _doc(app, 'results_slip', {'candidate_name': 'PRIYA', 'results': []})
        f = self._academic(app)
        self.assertIn('grades_unverified', {i['code'] for i in f['unresolved']})

    def test_the_spm_route_is_untouched(self):
        f = self._academic(_app(SPM_HELD, MATRIC_PATHWAY))
        self.assertEqual([i['code'] for i in f['unresolved']], ['results_slip_missing'])


# ── D13: the two student actions ─────────────────────────────────────────────────────────────


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestMoveItToTheSpmSlip(TestCase):
    def test_the_slip_moves_keeps_its_file_and_is_read_again_as_an_spm_slip(self):
        app = _app(STPM_HELD, DEGREE)
        read = {'candidate_name': 'PRIYA', 'exam': 'SIJIL PELAJARAN MALAYSIA', 'results_kind_detected': 'spm'}
        doc = _doc(app, 'higher_results', read, results_kind='stpm')
        with self.assertLogs('apps.scholarship.results_route', logging.INFO) as logs:
            r = authed_client(app.profile).post('/api/v1/scholarship/results/refile-to-spm/',
                                                {'document_id': doc.id}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        doc.refresh_from_db()
        self.assertEqual((doc.doc_type, doc.storage_path, doc.results_kind), ('results_slip', 'test/higher_results', ''))
        # review fix 6: the higher-results read is cleared, so the live self-heal sweep (never a
        # local checkout) reads it again as an SPM slip — exactly the shape the sweep selects
        self.assertEqual((doc.vision_fields, doc.vision_fields_run_at, doc.vision_run_at), ({}, None, None))
        from apps.scholarship.services.blockers import _stuck_unread_documents
        self.assertIn(doc.id, [d.id for d in _stuck_unread_documents(50)])
        self.assertIsNone(doc.superseded_at)
        self.assertIn('AUDIT results_refiled_to_spm', ' '.join(logs.output))
        app.refresh_from_db()
        self.assertEqual([n['kind'] for n in app.results_change_notes], ['refiled_spm'])   # fix 3
        self.assertFalse(app.results_change_notes[0]['submitted'])
        app = ScholarshipApplication.objects.get(pk=app.pk)
        blockers = consent_blockers(app)
        self.assertIn('higher_results_missing', blockers)          # the card asks again
        self.assertNotIn('results_slip_missing', blockers)          # the SPM card is satisfied

    def test_one_live_slip_per_slot(self):
        app = _app(STPM_HELD, DEGREE)
        old = _doc(app, 'results_slip', {'candidate_name': 'PRIYA', 'results': []})
        doc = _doc(app, 'higher_results', {'candidate_name': 'PRIYA', 'results_kind_detected': 'spm'})
        results_route.refile_to_spm(app, doc)
        live = ApplicantDocument.objects.filter(application=app, doc_type='results_slip',
                                                superseded_at__isnull=True)
        self.assertEqual(live.count(), 1)
        old.refresh_from_db()
        self.assertTrue(old.superseded_at is not None or live.first().id == old.id)

    def test_refused_once_submitted_fix_1(self):
        for stage in ('profile_complete', 'interviewing', 'awarded'):
            with self.subTest(stage=stage):
                app = _app(STPM_HELD, DEGREE, stage=stage)
                doc = _doc(app, 'higher_results', {'candidate_name': 'PRIYA', 'results_kind_detected': 'spm'})
                r = authed_client(app.profile).post('/api/v1/scholarship/results/refile-to-spm/',
                                                    {'document_id': doc.id}, format='json')
                self.assertEqual((r.status_code, r.json()['code']), (409, 'application_submitted'))
                doc.refresh_from_db()
                self.assertEqual(doc.doc_type, 'higher_results')
                self.assertEqual(doc.vision_fields['fields']['candidate_name'], 'PRIYA')
                self.assertFalse(app.resolution_items.filter(code='higher_results_missing').exists())

    def test_the_note_offers_no_action_after_submit(self):
        app = _app(STPM_HELD, DEGREE, stage='profile_complete')
        doc = _doc(app, 'higher_results', {'candidate_name': 'PRIYA', 'results_kind_detected': 'spm'})
        self.assertFalse(student_higher_check(doc)['actions_open'])
        before = _app(STPM_HELD, DEGREE)
        self.assertTrue(student_higher_check(_doc(before, 'higher_results', {
            'candidate_name': 'PRIYA', 'results_kind_detected': 'spm'}))['actions_open'])

    def test_refused_when_it_does_not_read_as_an_spm_slip(self):
        app = _app(STPM_HELD, DEGREE)
        doc = _doc(app, 'higher_results', STPM_READ)
        r = authed_client(app.profile).post('/api/v1/scholarship/results/refile-to-spm/',
                                            {'document_id': doc.id}, format='json')
        self.assertEqual(r.status_code, 400)
        doc.refresh_from_db()
        self.assertEqual(doc.doc_type, 'higher_results')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestOnlySpmResults(TestCase):
    def _post(self, app, **body):
        return authed_client(app.profile).post('/api/v1/scholarship/results/spm-only/', body,
                                               format='json')

    def test_clears_the_higher_results_and_keeps_spm(self):
        app = _app(STPM_HELD, DEGREE)
        with self.assertLogs('apps.scholarship.results_route', logging.INFO) as logs:
            r = self._post(app)
        self.assertEqual(r.status_code, 200, r.content)
        p = StudentProfile.objects.get(pk=app.profile.pk)
        self.assertEqual((p.stpm_grades, p.stpm_cgpa, p.higher_cgpa), ({}, None, None))
        self.assertEqual(p.grades, SPM)
        self.assertEqual(eq.results_held(p), 'spm')
        self.assertIn('AUDIT results_cleared_to_spm', logs.output[-1])
        app.refresh_from_db()
        # review fix 3: ALWAYS a reviewer note — she may have been shortlisted on that CGPA
        self.assertEqual(len(app.results_change_notes), 1)
        note = app.results_change_notes[0]
        self.assertEqual((note['kind'], note['cleared'], note['cgpa'], note['submitted']),
                         ('only_spm', 'stpm', 3.71, False))
        from apps.scholarship.serializers_admin import AdminApplicationDetailSerializer
        self.assertIn('results_change_notes', AdminApplicationDetailSerializer.Meta.fields)

    def test_spm_grades_held_only_in_the_stpm_block_become_the_record(self):
        app = _app({**STPM_HELD, 'grades': {}, 'spm_prereq_grades': {'bm': 'A', 'eng': 'B'}}, DEGREE)
        self.assertEqual(self._post(app).status_code, 200)
        p = StudentProfile.objects.get(pk=app.profile.pk)
        self.assertEqual((p.grades, p.results_exam_type), ({'bm': 'A', 'eng': 'B'}, 'spm'))

    def test_refused_once_submitted_and_nothing_is_wiped_fix_2(self):
        for stage in ('profile_complete', 'interviewing', 'awarded'):
            with self.subTest(stage=stage):
                app = _app(STPM_HELD, DEGREE, stage=stage)
                with patch('apps.scholarship.services.intake.score_application') as score:
                    r = self._post(app)
                score.assert_not_called()
                self.assertEqual((r.status_code, r.json()['code']), (409, 'application_submitted'))
                p = StudentProfile.objects.get(pk=app.profile.pk)
                self.assertEqual((p.stpm_grades, p.stpm_cgpa), (STPM, 3.71))
                self.assertEqual(eq.results_held(p), 'stpm')
                app.refresh_from_db()
                self.assertEqual(app.results_change_notes, [])

    def test_the_misfiled_slip_is_moved_too(self):
        app = _app(STPM_HELD, DEGREE)
        doc = _doc(app, 'higher_results', {'candidate_name': 'PRIYA', 'results_kind_detected': 'spm'})
        r = self._post(app, document_id=doc.id)
        self.assertTrue(r.json()['refiled'])
        doc.refresh_from_db()
        self.assertEqual(doc.doc_type, 'results_slip')

    def test_nothing_to_clear_for_an_spm_holder(self):
        self.assertEqual(self._post(_app(SPM_HELD, DEGREE)).status_code, 400)

    def test_the_sync_guard_still_refuses_a_stale_demotion(self):
        """The explicit clear is the ONE door down; a stale browser's 'spm' sync still is not."""
        p = make_student(**STPM_HELD)
        s = ProfileUpdateSerializer(p, data={'results_exam_type': 'spm', 'exam_type': 'spm',
                                             'completed_qualifications': ['spm']}, partial=True)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(eq.results_held(s.save()), 'stpm')


# ── D11/D13: one higher qualification at a time ──────────────────────────────────────────────


@override_settings(THIRD_ROUTE_OPEN=True)
class TestOneHigherQualificationAtATime(TestCase):
    def _save(self, profile, data):
        s = ProfileUpdateSerializer(profile, data=data, partial=True)
        self.assertTrue(s.is_valid(), s.errors)
        return s.save()

    def test_stpm_to_diploma_clears_the_stpm_entries(self):
        p = make_student(**STPM_HELD)
        # the browser resends its stored STPM CGPA on every finish — the switch must still win
        saved = self._save(p, {'exam_type': 'diploma', 'results_exam_type': 'diploma', 'higher_cgpa': 3.1,
                               'higher_institution_type': 'public', 'stpm_cgpa': 3.71,
                               'completed_qualifications': ['spm', 'diploma']})
        self.assertEqual((saved.stpm_grades, saved.stpm_cgpa), ({}, None))
        self.assertEqual(saved.completed_qualifications, ['spm', 'diploma'])
        self.assertEqual(eq.results_held(saved), 'diploma')

    def test_diploma_to_stpm_clears_the_third_route(self):
        p = make_student(**DIPLOMA_HELD)
        saved = self._save(p, {'exam_type': 'stpm', 'results_exam_type': 'stpm', 'stpm_grades': STPM,
                               'stpm_cgpa': 3.71, 'completed_qualifications': ['spm', 'stpm']})
        self.assertEqual((saved.higher_cgpa, saved.higher_koko, saved.higher_institution_type),
                         (None, None, ''))
        self.assertEqual(saved.completed_qualifications, ['spm', 'stpm'])
        self.assertEqual(eq.results_held(saved), 'stpm')

    def test_a_marker_with_no_results_behind_it_clears_nothing(self):
        p = make_student(**STPM_HELD)
        saved = self._save(p, {'results_exam_type': 'diploma'})
        self.assertEqual(saved.stpm_grades, STPM)
        self.assertEqual(eq.results_held(saved), 'stpm')
