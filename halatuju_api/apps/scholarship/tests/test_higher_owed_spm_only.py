"""Every degree student must have STPM / Matriculation / Asasi / Diploma results on file (owner
2026-11-07, apps 158 / 168 / 247, widened the same day) — `apps/scholarship/higher_owed.py`.

The SHAPES (never their data), from a read-only audit of the live rows, all submitted before S3a
(frozen "SPM slip required", no `higher_results` key) on intakes that ask for higher results:

1. Declared SPM only, no higher upload — a catalogue degree (158 …) or no `course_id` and a degree by
   name with pathway 'degree' / 'university' (187 / 274 / 361). Was: nothing. Now: owed, kind
   unknown; Academic at best Unsure; the declare + upload ask.
2. Higher results DECLARED on a legacy row whose recorded completion still reads SPM (STPM grades
   and CGPA entered; 161 / 205 / 226 / 243 / 251 / 276). `results_held` honours the recorded 'spm',
   so #388's catch-up never fired. Now: owed as 'stpm' — #388's slot, cap and upload ask, and the
   upload carries 'stpm'. 251: a stale 'stpm' pathway code, no course_id, a degree offer letter.
3. A higher upload on file, nothing declared (168 / 277 / 278, and 171 frozen after S3a). Now: never
   Certain, the reason named, and the declare + upload ask.

Exempt: a UA diploma / PISMP (SPM entry), an intake asking no higher results (D16c), and — owner,
2026-11-07 — an application at Recommended or later ("too late") for these new arms.
"""
from django.test import TestCase, override_settings

from apps.scholarship import higher_owed, results_route
from apps.scholarship.check2_queries import sync_check2_queries
from apps.scholarship.models import ResolutionItem
from apps.scholarship.resolution import resolve_doc_items_for_upload
from apps.scholarship.results_requests import answers
from apps.scholarship.services import application_completeness
from apps.scholarship.tests.factories import make_cohort
from apps.scholarship.tests.test_third_route_higher_owed import GENUINE_SPM, STPM_SLIP, _ask, _submitted
from apps.scholarship.tests.test_third_route_s4 import (
    DEGREE, HIGHER_FROZEN, POLY, SPM, SPM_HELD, SPM_READ, STPM_CERT_READ, STPM_HELD, _academic, _app,
    _doc, _fresh,
)

UNDECLARED = higher_owed.UNDECLARED_NOTE_CODE
ON_FILE = higher_owed.UNDECLARED_ON_FILE_CODE
DECLARE = higher_owed.DECLARE_ASK_CODE
#: Declared STPM, SPM results so far: a Form Six student (her semester ask is her route).
FORM_SIX = dict(exam_type='stpm', results_exam_type='spm', grades=SPM, completed_qualifications=['spm'])
#: Group 2: a legacy row — recorded completion SPM, list blank — with STPM grades and CGPA entered.
LEGACY_STPM = dict(exam_type='spm', results_exam_type='spm', grades=SPM, stpm_cgpa=3.71,
                   stpm_grades={'PA': 'A', 'MATH_T': 'A-', 'PHYSICS': 'A-'})
NO_ID_DEGREE = {'chosen_pathway': 'degree', 'pathway_certainty': 'sure',
                'chosen_programme': {'course_name': 'Sarjana Muda Perakaunan (Kepujian)'}}
NO_ID_UNIVERSITY = {**NO_ID_DEGREE, 'chosen_pathway': 'university'}
#: 251's shape: a stale 'stpm' pathway code (her own Form Six letter's autofill), no course_id.
STALE_STPM = {'chosen_pathway': 'stpm', 'pathway_certainty': 'sure',
              'chosen_programme': {'course_name': 'SARJANA MUDA SAINS GUNAAN DENGAN KEPUJIAN'}}
STALE_PISMP = {**STALE_STPM, 'chosen_programme': {'course_name': 'IJAZAH SARJANA MUDA PERGURUAN DENGAN KEPUJIAN'}}
STALE_DIPLOMA = {**STALE_STPM, 'chosen_programme': {'course_name': 'DIPLOMA PERAKAUNAN'}}


def _spm_only(stage='profile_complete', **kw):
    return _submitted(profile=SPM_HELD, stage=stage, **kw)


def _codes(items):
    return [i['code'] for i in items]


def _items(app, code):
    return ResolutionItem.objects.filter(application=app, source='check2', code=code)


def _set_docs(app, **docs):
    app.requirements_snapshot = {**app.requirements_snapshot, 'documents': {
        **app.requirements_snapshot['documents'], **docs}}
    app.save(update_fields=['requirements_snapshot'])
    return _fresh(app)


def _declare_stpm(app):
    """She enters her STPM results on the results page (the declare half of the ask)."""
    p = app.profile
    p.stpm_grades, p.stpm_cgpa = dict(LEGACY_STPM['stpm_grades']), 3.71
    p.save(update_fields=['stpm_grades', 'stpm_cgpa'])
    return _fresh(app)


def _academic_or_none(app):
    from apps.scholarship.verdict_engine import build_verdict
    facts = [f for f in build_verdict(_fresh(app)) if f['fact'] == 'academic']   # none when results are off
    return facts[0] if facts else None


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class TestGroup1DeclaredSpmOnly(TestCase):
    def test_the_shape(self):
        app = _spm_only()
        self.assertEqual((results_route.held(app), results_route.held_kind(app)), ('spm', ''))
        self.assertEqual(results_route.destination(app), results_route.DEGREE)
        self.assertTrue(results_route.gift_asks_higher(app))
        self.assertNotIn('higher_results', app.requirements_snapshot['documents'])

    def test_owed_with_the_kind_unspecified(self):
        app = _spm_only()
        self.assertEqual(higher_owed.owed_kind(app), higher_owed.UNSPECIFIED)
        self.assertTrue(higher_owed.undeclared(app))
        from apps.scholarship.wrong_slip import HIGHER_KINDS
        self.assertNotIn(higher_owed.UNSPECIFIED, HIGHER_KINDS)     # never mistaken for a declared kind

    def test_academic_is_unsure_and_the_drawer_slot_is_generic(self):
        f = _academic(_spm_only())
        self.assertEqual(f['status'], 'recommend')                  # was Certain on the SPM slip alone
        note = next(i for i in f['unresolved'] if i['code'] == UNDECLARED)
        self.assertEqual(note['params'], {'kind': ''})              # '' → "STPM / Matriculation / Asasi / Diploma results"
        self.assertNotIn(higher_owed.NOTE_CODE, _codes(f['unresolved']))

    def test_one_declare_and_upload_ask_in_the_completed_stage(self):
        app = _spm_only()
        sync_check2_queries(app)
        sync_check2_queries(_fresh(app))
        item = _items(app, DECLARE).get()
        self.assertEqual((item.status, item.kind, item.doc_type, item.fact, item.params),
                         ('open', 'doc', 'higher_results', 'academic', {}))
        self.assertFalse(_ask(app).exists())                        # one card, not two

    def test_the_stage_rule_is_unchanged(self):
        app = _spm_only(stage='interviewing')                       # only profile_complete asks
        sync_check2_queries(app)
        self.assertFalse(_items(app, DECLARE).exists())
        app = _spm_only()                                           # the live 'interviewed' status
        type(app).objects.filter(pk=app.pk).update(status='interviewed')
        sync_check2_queries(_fresh(app))
        self.assertFalse(_items(app, DECLARE).exists())
        self.assertEqual(_academic(app)['status'], 'recommend')     # the cap still shows the gap

    def test_no_course_id_but_a_degree_by_name(self):
        """187 / 274 / 361: pathway 'degree' or 'university', a degree course name, no catalogue id."""
        for plan in (NO_ID_DEGREE, NO_ID_UNIVERSITY):
            app = _submitted(profile=SPM_HELD, plan=plan)
            self.assertEqual(higher_owed.owed_kind(app), higher_owed.UNSPECIFIED, plan['chosen_pathway'])

    def test_never_a_gate(self):
        owing, twin = _spm_only(), _spm_only(plan=POLY)
        self.assertEqual(application_completeness(owing), application_completeness(twin))
        sync_check2_queries(owing)
        app = _fresh(owing)
        self.assertNotIn('higher_results', app.requirements_snapshot['documents'])
        self.assertIsNotNone(app.profile_completed_at)


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class TestGroup2DeclaredOnALegacyRow(TestCase):
    """Why #388's catch-up missed them: `results_held` honours the recorded 'spm' on a legacy row."""

    def test_the_shape_reads_spm_held(self):
        app = _submitted(profile=LEGACY_STPM)
        self.assertEqual(results_route.held_kind(app), '')
        self.assertEqual(higher_owed.declared_kind(app), 'stpm')
        self.assertFalse(higher_owed.undeclared(app))

    def test_owed_as_stpm_with_388s_slot_cap_and_ask(self):
        app = _submitted(profile=LEGACY_STPM)
        self.assertEqual(higher_owed.owed_kind(app), 'stpm')
        f = _academic(app)
        self.assertEqual(f['status'], 'recommend')
        note = next(i for i in f['unresolved'] if i['code'] == higher_owed.NOTE_CODE)
        self.assertEqual(note['params'], {'held': 'STPM', 'kind': 'stpm'})
        sync_check2_queries(app)
        self.assertEqual(_ask(app).get().params, {'results_kind': 'stpm'})
        self.assertFalse(_items(app, DECLARE).exists())

    def test_the_upload_carries_stpm_and_a_clean_one_closes_the_ask(self):
        app = _submitted(profile=LEGACY_STPM)
        sync_check2_queries(app)
        self.assertEqual(results_route.upload_kind(app), 'stpm')
        doc = _doc(app, 'higher_results', STPM_SLIP, results_kind=results_route.upload_kind(app))
        resolve_doc_items_for_upload(_fresh(app), doc)
        sync_check2_queries(_fresh(app))
        self.assertEqual(_ask(app).get().status, 'resolved')
        f = _academic(app)
        self.assertNotIn(ON_FILE, _codes(f['unresolved']))          # declared: an honest match can tick
        self.assertIn('higher_results_kind_ok', _codes(f['evidence']))

    def test_251_a_stale_stpm_pathway_over_a_degree_course(self):
        app = _submitted(profile=LEGACY_STPM, plan=STALE_STPM)
        self.assertEqual(results_route.destination(app), results_route.POST_SPM)   # unchanged globally
        self.assertEqual(higher_owed.owed_kind(app), 'stpm')


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class TestGroup3OnFileButUndeclared(TestCase):
    """A tick only on a match: an upload she never declared has nothing to match."""

    def test_the_upload_lands_in_the_higher_card_with_no_kind(self):
        self.assertEqual(results_route.upload_kind(_spm_only()), '')

    def test_168s_shape_unread_split_upload(self):
        app = _spm_only()
        _doc(app, 'higher_results', None, results_kind='stpm')
        app = _fresh(app)
        sync_check2_queries(app)
        self.assertEqual(_items(app, DECLARE).get().status, 'open')
        f = _academic(app)
        self.assertEqual(f['status'], 'recommend')
        self.assertIn(ON_FILE, _codes(f['unresolved']))
        self.assertNotIn(UNDECLARED, _codes(f['unresolved']))      # the drawer's Missing slot goes

    def test_168s_shape_once_read_still_unsure(self):
        app = _spm_only()
        _doc(app, 'higher_results', STPM_SLIP, results_kind='stpm')
        f = _academic(app)
        self.assertEqual(f['status'], 'recommend')
        self.assertIn(ON_FILE, _codes(f['unresolved']))
        self.assertNotIn('higher_results_cgpa_ok', _codes(f['evidence']))

    def test_an_upload_alone_never_closes_the_declare_ask(self):
        app = _spm_only()
        sync_check2_queries(app)
        doc = _doc(app, 'higher_results', STPM_SLIP, results_kind='')
        self.assertFalse(answers(doc, _items(app, DECLARE).get()))
        resolve_doc_items_for_upload(_fresh(app), doc)
        sync_check2_queries(_fresh(app))
        self.assertEqual(_items(app, DECLARE).get().status, 'open')

    def test_declared_then_uploaded_closes_it_and_no_second_ask(self):
        app = _spm_only()
        sync_check2_queries(app)
        app = _declare_stpm(app)
        sync_check2_queries(app)                                     # declared, no upload yet
        self.assertEqual(_items(app, DECLARE).get().status, 'open')  # the same card stays
        self.assertFalse(_ask(app).exists())
        doc = _doc(app, 'higher_results', STPM_SLIP, results_kind=results_route.upload_kind(_fresh(app)))
        self.assertEqual(doc.results_kind, 'stpm')
        resolve_doc_items_for_upload(_fresh(app), doc)
        sync_check2_queries(_fresh(app))
        self.assertEqual(_items(app, DECLARE).get().status, 'resolved')
        self.assertFalse(_ask(app).exists())

    def test_an_spm_slip_in_the_higher_card_never_answers(self):
        """A blank kind compares nothing, so the read's own 'spm' detection must refuse it."""
        app = _declare_stpm(_spm_only())
        doc = _doc(app, 'higher_results', {**SPM_READ, 'results_kind_detected': 'spm'}, results_kind='')
        from apps.scholarship.higher_results import answers_higher_ask
        self.assertFalse(answers_higher_ask(doc))

    def test_171s_shape_frozen_after_s3a(self):
        """Snapshot already requires the upload (S3's card): no #388 slot, but never Certain on an
        undeclared upload, and the declare ask."""
        app = _app(SPM_HELD, DEGREE, stage='profile_complete')
        app.requirements_snapshot = {**HIGHER_FROZEN, 'documents': {**HIGHER_FROZEN['documents'],
                                                                    'results_slip': 'required'}}
        app.save(update_fields=['requirements_snapshot'])
        _doc(app, 'results_slip', SPM_READ, authenticity=GENUINE_SPM)
        _doc(app, 'higher_results', STPM_SLIP, results_kind='')
        app = _fresh(app)
        self.assertEqual(higher_owed.owed_kind(app), '')
        f = _academic(app)
        self.assertEqual(f['status'], 'recommend')
        self.assertIn(ON_FILE, _codes(f['unresolved']))
        sync_check2_queries(app)
        self.assertEqual(_items(app, DECLARE).get().status, 'open')

    def test_the_cap_never_lets_certain_through(self):
        app = _spm_only()
        _doc(app, 'higher_results', STPM_SLIP)
        for status in ('verified', 'review'):
            f = higher_owed.cap_undeclared(_fresh(app), {'fact': 'academic', 'status': status,
                                                         'evidence': [], 'unresolved': []})
            self.assertEqual((f['status'], _codes(f['unresolved'])), ('recommend', [ON_FILE]))
        f = higher_owed.cap_undeclared(_fresh(app), {'fact': 'academic', 'status': 'gap',
                                                     'evidence': [], 'unresolved': []})
        self.assertEqual(f['status'], 'gap')                        # a worse band stands

    def test_a_declared_students_upload_is_not_capped_by_it(self):
        app = _submitted(profile=STPM_HELD)
        _doc(app, 'higher_results', STPM_SLIP, results_kind='stpm')
        f = {'fact': 'academic', 'status': 'verified', 'evidence': [], 'unresolved': []}
        self.assertEqual(higher_owed.cap_undeclared(_fresh(app), f)['status'], 'verified')


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class TestNotOwed(TestCase):
    def _nothing(self, app):
        self.assertEqual(higher_owed.owed_kind(app), '')
        self.assertFalse(higher_owed.undeclared(app))
        self.assertEqual(higher_owed.ask_codes(app), set())
        f = _academic_or_none(app)
        self.assertNotIn(UNDECLARED, _codes(f['unresolved']) if f else [])

    def test_a_post_spm_destination(self):
        app = _spm_only(plan=POLY)
        self._nothing(app)
        self.assertEqual(_academic(app)['status'], 'verified')

    def test_pismp_is_not_a_degree(self):
        """'Ijazah Sarjana Muda Perguruan' is PISMP (SPM entry), not a degree for this rule."""
        self._nothing(_submitted(profile=SPM_HELD, plan=STALE_PISMP))

    def test_a_ua_diploma_is_not_a_degree(self):
        self._nothing(_submitted(profile=SPM_HELD, plan=STALE_DIPLOMA))

    def test_an_intake_that_asks_no_higher_results(self):
        app = _app(SPM_HELD, DEGREE, stage='profile_complete', cohort=make_cohort(min_stpm_pngk=None))
        _doc(app, 'results_slip', SPM_READ, authenticity=GENUINE_SPM)
        self.assertFalse(results_route.gift_asks_higher(_fresh(app)))
        self._nothing(_fresh(app))

    def test_a_snapshot_already_requiring_them_owes_no_388_slot(self):
        app = _set_docs(_spm_only(), higher_results='required')
        self.assertEqual(higher_owed.owed_kind(app), '')

    def test_a_programme_asking_no_results(self):
        self._nothing(_set_docs(_spm_only(), results_slip='off'))

    def test_unsubmitted(self):
        app = _app(SPM_HELD, DEGREE, stage='shortlisted')
        self.assertEqual(higher_owed.owed_kind(app), '')
        self.assertFalse(higher_owed.undeclared(app))

    def test_a_higher_result_already_in_the_spm_card(self):
        self._nothing(_spm_only(slip=STPM_CERT_READ))

    def test_a_form_six_student_keeps_her_semester_route(self):
        self._nothing(_submitted(profile=FORM_SIX))

    def test_a_tertiary_holder_is_unchanged(self):
        app = _submitted(profile=STPM_HELD)
        self.assertEqual(higher_owed.owed_kind(app), 'stpm')
        f = _academic(app)
        self.assertIn(higher_owed.NOTE_CODE, _codes(f['unresolved']))
        self.assertNotIn(UNDECLARED, _codes(f['unresolved']))


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class TestRecommendedOrLaterIsTooLate(TestCase):
    """Owner 2026-11-07: the new arms stop at Recommended (`family.DECIDED_STATUSES`); 187 / 276."""

    def _gone(self, app):
        self.assertEqual(higher_owed.owed_kind(app), '')
        self.assertFalse(higher_owed.undeclared(app))
        self.assertEqual(higher_owed.ask_codes(app), set())
        self.assertNotIn(UNDECLARED, _codes(_academic(app)['unresolved']))

    def test_the_spm_only_arm_stops_at_recommended(self):
        self._gone(_submitted(profile=SPM_HELD, stage='recommended'))

    def test_the_legacy_declared_arm_stops_at_recommended(self):
        self._gone(_submitted(profile=LEGACY_STPM, stage='recommended'))

    def test_and_later(self):
        app = _spm_only()
        type(app).objects.filter(pk=app.pk).update(status='awarded')
        self._gone(_fresh(app))

    def test_388s_own_shape_is_unchanged(self):
        self.assertEqual(higher_owed.owed_kind(_submitted(profile=STPM_HELD, stage='recommended')), 'stpm')
